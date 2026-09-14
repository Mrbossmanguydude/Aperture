# This file is meant for an NNUE network to be trained and used for the evaluation in engine.py
#
# Authorship note: roughly 50-75% of this file is original work. The
# performance-critical pieces (the one-time feature cache, the pyarrow-based
# batch loading, the sparse-embedding optimiser split) were adapted from
# external code specifically to speed up training - not to change what the
# pipeline does. The core architecture, feature formula, and training loop
# logic are original, as it pertains to my learning, all things I wanted to learn are original.

from engine import State
from lichess_loader import lichess_positions

import json
import os
import random
import zlib
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

import pyarrow as pa
import pyarrow.parquet as pq



# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

FEATURE_COUNT = 40_960
ACCUMULATOR_SIZE = 256
CACHE_VERSION = 1

PIECE_TYPE = {
    "p": 0,
    "n": 1,
    "b": 2,
    "r": 3,
    "q": 4,
}


# -----------------------------------------------------------------------------
# Model
# -----------------------------------------------------------------------------

class NNUE(nn.Module):
    def __init__(self):
        super().__init__()

        self.l1 = nn.EmbeddingBag(
            FEATURE_COUNT,
            ACCUMULATOR_SIZE,
            mode="sum",
            sparse=True,
        )
        self.l2 = nn.Linear(512, 32)
        self.l3 = nn.Linear(32, 32)
        self.l4 = nn.Linear(32, 1)

    def forward(
        self,
        white_indices,
        white_offsets,
        black_indices,
        black_offsets,
        turn,
    ):
        white_acc = self.l1(white_indices, white_offsets)
        black_acc = self.l1(black_indices, black_offsets)

        turn = turn.unsqueeze(1)
        first = torch.where(turn, white_acc, black_acc)
        second = torch.where(turn, black_acc, white_acc)
        combined = torch.cat((first, second), dim=1)

        x = torch.relu(self.l2(combined))
        x = torch.relu(self.l3(x))
        return self.l4(x)


# -----------------------------------------------------------------------------
# Existing State-based feature helpers kept for engine/inference compatibility.
# Training does NOT use these; it uses the faster direct-FEN encoder below.
# -----------------------------------------------------------------------------

def get_index(king_pos, piece_pos, piece_type, perspective):
    """
    piece_type = (colour, ptype)
    perspective = "wh" or "bl"
    """
    colour, ptype = piece_type

    if perspective == "bl":
        king_pos ^= 56
        piece_pos ^= 56
        colour = "wh" if colour == "bl" else "bl"

    colour_offset = 0 if colour == "wh" else 5
    piece_index = colour_offset + PIECE_TYPE[ptype]

    return 640 * king_pos + 64 * piece_index + piece_pos


def get_indices(s, perspective):
    king_pos = s.pieces[perspective]["k"].bit_length() - 1
    indices = []

    for colour in ("wh", "bl"):
        for ptype in s.pieces[colour]:
            if ptype == "k":
                continue

            bitboard = s.pieces[colour][ptype]

            while bitboard:
                lsb = bitboard & -bitboard
                piece_pos = lsb.bit_length() - 1
                indices.append(
                    get_index(
                        king_pos,
                        piece_pos,
                        (colour, ptype),
                        perspective,
                    )
                )
                bitboard &= bitboard - 1

    return indices


def get_offsets(examples):
    """Compatibility path for existing engine code."""
    woffsets = []
    windices = []
    boffsets = []
    bindices = []
    turns = []

    for example in examples:
        s = State(example)
        turns.append(s.init_info[0] == "wh")

        woffsets.append(len(windices))
        boffsets.append(len(bindices))

        windices.extend(get_indices(s, "wh"))
        bindices.extend(get_indices(s, "bl"))

    return (
        torch.tensor(woffsets, dtype=torch.int32),
        torch.tensor(windices, dtype=torch.int32),
        torch.tensor(boffsets, dtype=torch.int32),
        torch.tensor(bindices, dtype=torch.int32),
        torch.tensor(turns, dtype=torch.bool),
    )


@torch.inference_mode()
def run_inference(
    model,
    white_indices,
    white_offsets,
    black_indices,
    black_offsets,
    turn,
):
    return model(
        white_indices,
        white_offsets,
        black_indices,
        black_offsets,
        turn,
    )


# -----------------------------------------------------------------------------
# Fast training feature extraction
# -----------------------------------------------------------------------------

def encode_fen_features(fen):
    """
    Parse only the information NNUE needs directly from a standard FEN.

    Returns:
        white_indices: list[int]
        black_indices: list[int]
        white_to_move: bool

    Square numbering is a1=0 ... h8=63.
    """
    fields = fen.split()
    if len(fields) < 2:
        raise ValueError(f"Invalid FEN: {fen!r}")

    board = fields[0]
    white_to_move = fields[1] == "w"

    white_king = -1
    black_king = -1
    pieces = []

    rank = 7
    for fen_rank in board.split("/"):
        file_index = 0

        for symbol in fen_rank:
            if symbol.isdigit():
                file_index += ord(symbol) - 48
                continue

            square = rank * 8 + file_index

            if symbol == "K":
                white_king = square
            elif symbol == "k":
                black_king = square
            else:
                pieces.append((square, symbol.lower(), symbol.isupper()))

            file_index += 1

        rank -= 1

    if white_king < 0 or black_king < 0:
        raise ValueError(f"FEN is missing a king: {fen!r}")

    white_indices = []
    black_indices = []
    flipped_black_king = black_king ^ 56

    for square, ptype, is_white in pieces:
        base_type = PIECE_TYPE[ptype]

        # White perspective: white=friendly (0..4), black=enemy (5..9).
        white_piece_type = base_type if is_white else base_type + 5
        white_indices.append(
            640 * white_king + 64 * white_piece_type + square
        )

        # Black perspective: flip ranks and swap friendly/enemy colour slots.
        black_piece_type = base_type + 5 if is_white else base_type
        black_indices.append(
            640 * flipped_black_king
            + 64 * black_piece_type
            + (square ^ 56)
        )

    return white_indices, black_indices, white_to_move


# -----------------------------------------------------------------------------
# One-time feature cache
# -----------------------------------------------------------------------------

def _cache_manifest_path(cache_folder):
    return Path(cache_folder) / "manifest.json"


def _write_cache_part(cache_folder, split, part_number, rows, row_group_size):
    if not rows:
        return part_number

    cache_folder = Path(cache_folder)
    filename = cache_folder / f"{split}-{part_number:05d}.parquet"

    table = pa.table(
        {
            "windices": pa.array(
                [row[0] for row in rows],
                type=pa.list_(pa.int32()),
            ),
            "bindices": pa.array(
                [row[1] for row in rows],
                type=pa.list_(pa.int32()),
            ),
            "turn": pa.array(
                [row[2] for row in rows],
                type=pa.bool_(),
            ),
            "target": pa.array(
                [row[3] for row in rows],
                type=pa.float32(),
            ),
        }
    )

    pq.write_table(
        table,
        filename,
        compression="zstd",
        row_group_size=row_group_size,
    )

    return part_number + 1


def build_feature_cache(
    dataset_folder,
    cache_folder,
    total_positions,
    validation_positions,
    cache_chunk_size=131_072,
    row_group_size=16_384,
):
    if not 0 < validation_positions < total_positions:
        raise ValueError("validation_positions must be between 0 and total_positions")

    cache_folder = Path(cache_folder)
    cache_folder.mkdir(parents=True, exist_ok=True)

    manifest_path = _cache_manifest_path(cache_folder)
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as file:
            manifest = json.load(file)

        expected = {
            "cache_version": CACHE_VERSION,
            "total_positions_requested": total_positions,
            "validation_positions_requested": validation_positions,
        }

        if all(manifest.get(key) == value for key, value in expected.items()):
            print(
                f"Using existing feature cache: {cache_folder} "
                f"({manifest['training_positions']:,} train / "
                f"{manifest['validation_positions']:,} validation)"
            )
            return manifest

        raise RuntimeError(
            f"Cache {cache_folder} was built with different settings. "
            "Delete it or choose a different cache_folder."
        )

    validation_fraction = validation_positions / total_positions
    validation_cutoff = int(validation_fraction * (2**32))

    train_rows = []
    validation_rows = []
    train_part = 0
    validation_part = 0
    train_count = 0
    validation_count = 0
    seen = 0

    positions = lichess_positions(
        dataset_folder,
        max_positions=total_positions,
    )

    print("Building one-time NNUE feature cache...")

    for fen, target in positions:
        windices, bindices, turn = encode_fen_features(fen)
        row = (windices, bindices, turn, float(target))

        # Deterministic hash split: fixed validation set, independent of source order.
        hash_value = zlib.crc32(fen.encode("utf-8")) & 0xFFFFFFFF

        if hash_value < validation_cutoff:
            validation_rows.append(row)
            validation_count += 1

            if len(validation_rows) >= cache_chunk_size:
                validation_part = _write_cache_part(
                    cache_folder,
                    "validation",
                    validation_part,
                    validation_rows,
                    row_group_size,
                )
                validation_rows.clear()
        else:
            train_rows.append(row)
            train_count += 1

            if len(train_rows) >= cache_chunk_size:
                train_part = _write_cache_part(
                    cache_folder,
                    "train",
                    train_part,
                    train_rows,
                    row_group_size,
                )
                train_rows.clear()

        seen += 1
        if seen % 500_000 == 0:
            print(
                f"Cached {seen:,}/{total_positions:,} positions "
                f"({train_count:,} train / {validation_count:,} validation)"
            )

    train_part = _write_cache_part(
        cache_folder,
        "train",
        train_part,
        train_rows,
        row_group_size,
    )
    validation_part = _write_cache_part(
        cache_folder,
        "validation",
        validation_part,
        validation_rows,
        row_group_size,
    )

    if seen < total_positions:
        raise RuntimeError(
            f"Only {seen:,} usable positions were found, but "
            f"{total_positions:,} were requested. Download more Lichess shards "
            "and rebuild the cache."
        )

    manifest = {
        "cache_version": CACHE_VERSION,
        "total_positions_requested": total_positions,
        "validation_positions_requested": validation_positions,
        "positions_seen": seen,
        "training_positions": train_count,
        "validation_positions": validation_count,
        "train_parts": train_part,
        "validation_parts": validation_part,
        "cache_chunk_size": cache_chunk_size,
        "row_group_size": row_group_size,
    }

    with open(manifest_path, "w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2)

    print(
        f"Feature cache complete: {train_count:,} train / "
        f"{validation_count:,} validation"
    )

    return manifest


def _list_array_to_numpy(list_array):
    """Flatten one Arrow list column and return (indices, offsets)."""
    offsets = list_array.offsets.to_numpy(zero_copy_only=False).astype(
        np.int32,
        copy=False,
    )

    start = int(offsets[0])
    end = int(offsets[-1])

    values = list_array.values.slice(start, end - start).to_numpy(
        zero_copy_only=False
    )
    values = values.astype(np.int32, copy=False)
    offsets = (offsets[:-1] - start).astype(np.int32, copy=False)

    return values, offsets


def _arrow_batch_to_tensors(table, pin_memory):
    windices_array = table.column("windices").combine_chunks()
    bindices_array = table.column("bindices").combine_chunks()

    windices_np, woffsets_np = _list_array_to_numpy(windices_array)
    bindices_np, boffsets_np = _list_array_to_numpy(bindices_array)

    turns_np = table.column("turn").combine_chunks().to_numpy(
        zero_copy_only=False
    )
    targets_np = table.column("target").combine_chunks().to_numpy(
        zero_copy_only=False
    )

    windices = torch.from_numpy(windices_np)
    woffsets = torch.from_numpy(woffsets_np)
    bindices = torch.from_numpy(bindices_np)
    boffsets = torch.from_numpy(boffsets_np)
    turns = torch.from_numpy(turns_np.astype(np.bool_, copy=False))
    targets = torch.from_numpy(targets_np.astype(np.float32, copy=False)).unsqueeze(1)

    if pin_memory:
        windices = windices.pin_memory()
        woffsets = woffsets.pin_memory()
        bindices = bindices.pin_memory()
        boffsets = boffsets.pin_memory()
        turns = turns.pin_memory()
        targets = targets.pin_memory()

    return windices, woffsets, bindices, boffsets, turns, targets


def cached_batches(
    cache_folder,
    split,
    batch_size,
    shuffle,
    seed,
    pin_memory,
):
    """
    Shuffling is performed at three levels:
      1. cache-file order
      2. parquet row-group order
      3. rows inside each row group

    This gives much better mixing than a fixed 100k streaming shuffle while
    avoiding a 50M-row in-memory permutation.
    """
    cache_folder = Path(cache_folder)
    files = sorted(cache_folder.glob(f"{split}-*.parquet"))

    if not files:
        raise RuntimeError(f"No cached {split} parquet files found in {cache_folder}")

    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)

    if shuffle:
        rng.shuffle(files)

    pending = None

    for filename in files:
        parquet_file = pq.ParquetFile(filename)
        row_groups = list(range(parquet_file.num_row_groups))

        if shuffle:
            rng.shuffle(row_groups)

        for row_group in row_groups:
            table = parquet_file.read_row_group(
                row_group,
                columns=["windices", "bindices", "turn", "target"],
            )

            if shuffle and table.num_rows > 1:
                permutation = np_rng.permutation(table.num_rows)
                table = table.take(pa.array(permutation))

            if pending is not None:
                table = pa.concat_tables([pending, table])
                pending = None

            full_rows = (table.num_rows // batch_size) * batch_size

            for start in range(0, full_rows, batch_size):
                yield _arrow_batch_to_tensors(
                    table.slice(start, batch_size),
                    pin_memory,
                )

            if full_rows < table.num_rows:
                pending = table.slice(full_rows)

# -----------------------------------------------------------------------------
# Training
# -----------------------------------------------------------------------------

def _move_batch_to_device(batch, device):
    non_blocking = device.type == "cuda"
    return tuple(
        tensor.to(device, non_blocking=non_blocking)
        for tensor in batch
    )


def train(
    epochs,
    learning_rate,
    batch_size,
    dataset_folder="lichess_data",
    cache_folder="nnue_feature_cache",
    total_positions=50_000_000,
    validation_positions=1_000_000,
    modelparams=None,
    latest_model_path="NNUE.pt",
    best_model_path="NNUE_best.pt",
    training_checkpoint_path="NNUE_training_checkpoint.pt",
):
    manifest = build_feature_cache(
        dataset_folder=dataset_folder,
        cache_folder=cache_folder,
        total_positions=total_positions,
        validation_positions=validation_positions,
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    if device.type == "cuda":
        torch.set_float32_matmul_precision("high")

    model = NNUE().to(device)

    if modelparams is not None:
        model.load_state_dict(modelparams)

    lossfn = nn.HuberLoss(delta=100)

    # SparseAdam only touches active embedding rows.
    embedding_optimiser = torch.optim.SparseAdam(
        model.l1.parameters(),
        lr=learning_rate,
    )

    dense_parameters = (
        list(model.l2.parameters())
        + list(model.l3.parameters())
        + list(model.l4.parameters())
    )

    dense_optimiser = torch.optim.AdamW(
        dense_parameters,
        lr=learning_rate,
        weight_decay=1e-5,
    )

    best_validation_loss = float("inf")
    start_epoch = 0

    if os.path.exists(training_checkpoint_path):
        checkpoint = torch.load(
            training_checkpoint_path,
            map_location=device,
            weights_only=False,
        )

        checkpoint_manifest = checkpoint.get("manifest")
        if checkpoint_manifest is not None:
            for key in (
                "cache_version",
                "total_positions_requested",
                "validation_positions_requested",
            ):
                if checkpoint_manifest.get(key) != manifest.get(key):
                    raise RuntimeError(
                        "Training checkpoint was created for a different dataset/cache "
                        "configuration. Move/delete NNUE_training_checkpoint.pt or use "
                        "the matching cache settings."
                    )

        model.load_state_dict(checkpoint["model_state_dict"])
        embedding_optimiser.load_state_dict(
            checkpoint["embedding_optimiser_state_dict"]
        )
        dense_optimiser.load_state_dict(
            checkpoint["dense_optimiser_state_dict"]
        )
        best_validation_loss = checkpoint["best_validation_loss"]
        start_epoch = checkpoint["epoch"] + 1

        print(
            f"Resuming from epoch {start_epoch}; "
            f"best validation loss = {best_validation_loss:.4f}"
        )

    pin_memory = device.type == "cuda"

    for local_epoch in range(epochs):
        epoch = start_epoch + local_epoch

        # ------------------------------------------------------------------
        # Training
        # ------------------------------------------------------------------
        model.train()

        training_loss_sum = torch.zeros((), device=device)
        training_batches = 0

        train_iterator = cached_batches(
            cache_folder=cache_folder,
            split="train",
            batch_size=batch_size,
            shuffle=True,
            seed=epoch,
            pin_memory=pin_memory,
        )

        for batch in train_iterator:
            (
                windices,
                woffsets,
                bindices,
                boffsets,
                turns,
                targets,
            ) = _move_batch_to_device(batch, device)

            embedding_optimiser.zero_grad(set_to_none=True)
            dense_optimiser.zero_grad(set_to_none=True)

            predictions = model(
                windices,
                woffsets,
                bindices,
                boffsets,
                turns,
            )

            loss = lossfn(predictions, targets)
            loss.backward()

            torch.nn.utils.clip_grad_norm_(
                dense_parameters,
                max_norm=1.0,
                foreach=True,
            )

            embedding_optimiser.step()
            dense_optimiser.step()

            training_loss_sum += loss.detach()
            training_batches += 1

            if training_batches % 1000 == 0:
                print(
                    f"Epoch {epoch} | "
                    f"batch {training_batches:,} | "
                    f"current Huber loss {loss.detach().item():.3f}"
                )

        if training_batches == 0:
            raise RuntimeError("No training batches were produced.")

        # ------------------------------------------------------------------
        # Validation
        # ------------------------------------------------------------------
        model.eval()

        validation_loss_sum = torch.zeros((), device=device)
        validation_batches = 0

        validation_iterator = cached_batches(
            cache_folder=cache_folder,
            split="validation",
            batch_size=batch_size,
            shuffle=False,
            seed=0,
            pin_memory=pin_memory,
        )

        with torch.inference_mode():
            for batch in validation_iterator:
                (
                    windices,
                    woffsets,
                    bindices,
                    boffsets,
                    turns,
                    targets,
                ) = _move_batch_to_device(batch, device)

                predictions = model(
                    windices,
                    woffsets,
                    bindices,
                    boffsets,
                    turns,
                )

                validation_loss_sum += lossfn(predictions, targets)
                validation_batches += 1

        if validation_batches == 0:
            raise RuntimeError("No validation batches were produced.")

        avg_training_loss = (
            training_loss_sum / training_batches
        ).item()
        avg_validation_loss = (
            validation_loss_sum / validation_batches
        ).item()

        print(
            f"Epoch: {epoch}, "
            f"Training Loss: {avg_training_loss:.6f}, "
            f"Validation Loss: {avg_validation_loss:.6f}"
        )

        torch.save(model.state_dict(), latest_model_path)

        if avg_validation_loss < best_validation_loss:
            best_validation_loss = avg_validation_loss
            torch.save(model.state_dict(), best_model_path)
            print(
                f"New best validation loss: {best_validation_loss:.6f} "
                f"-> saved {best_model_path}"
            )

        # Full checkpoint for efficient continuation of Adam/SparseAdam state.
        torch.save(
            {
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "embedding_optimiser_state_dict": embedding_optimiser.state_dict(),
                "dense_optimiser_state_dict": dense_optimiser.state_dict(),
                "best_validation_loss": best_validation_loss,
                "manifest": manifest,
            },
            training_checkpoint_path,
        )

    return model.state_dict()


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    initial_params = None

    if (
        os.path.exists("NNUE.pt")
        and not os.path.exists("NNUE_training_checkpoint.pt")
    ):
        initial_params = torch.load(
            "NNUE.pt",
            weights_only=True,
        )

    params = train(
        epochs=100,
        learning_rate=1e-3,
        batch_size=1024,
        dataset_folder="lichess_data",
        cache_folder="nnue_feature_cache",
        total_positions=50_000_000,
        validation_positions=1_000_000,
        modelparams=initial_params,
    )

    torch.save(params, "NNUE.pt")