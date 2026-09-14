import glob
import random
import pyarrow.parquet as pq
import os

def lichess_positions(
    folder,
    max_positions=50_000_000
):
    """
    Streams unique Lichess positions from the downloaded
    parquet files.

    For each FEN:
        - chooses the highest-depth evaluation
        - chooses the first PV at that depth
        - converts evaluation to side-to-move perspective
        - converts mate scores to ~8500
    """

    files = sorted(
        glob.glob(os.path.join(folder, "train-*.parquet"))
    )

    positions_yielded = 0

    current_fen = None
    best_depth = -1
    best_cp = None
    best_mate = None

    def finalise(fen, cp, mate):
        if fen is None:
            return None

        if cp is not None:
            target = float(cp)

        elif mate is not None and mate != 0:
            target = (
                (1 if mate > 0 else -1)
                * (8500 - abs(mate))
            )

        else:
            return None

        side_to_move = fen.split()[1]

        if side_to_move == "b":
            target = -target

        fen = fen + " 0 1"

        return fen, target

    for filename in files:

        parquet = pq.ParquetFile(filename)

        for batch in parquet.iter_batches(
            batch_size=100_000,
            columns=["fen", "depth", "cp", "mate"]
        ):

            data = batch.to_pydict()

            for fen, depth, cp, mate in zip(
                data["fen"],
                data["depth"],
                data["cp"],
                data["mate"]
            ):
                if current_fen is not None and fen != current_fen:

                    result = finalise(
                        current_fen,
                        best_cp,
                        best_mate
                    )

                    if result is not None:
                        yield result

                        positions_yielded += 1

                        if positions_yielded >= max_positions:
                            return

                    current_fen = fen
                    best_depth = -1
                    best_cp = None
                    best_mate = None

                elif current_fen is None:
                    current_fen = fen

                if depth > best_depth:
                    best_depth = depth
                    best_cp = cp
                    best_mate = mate

    # Last FEN
    result = finalise(
        current_fen,
        best_cp,
        best_mate
    )

    if result is not None:
        yield result

positions = lichess_positions(
    "lichess_data",
    max_positions=50_000_000
)