# # class Box:
# #     def __init__(self):
# #         self.items = []

# # def bad_result(box, item):
# #     box.items.append(item)
# #     return box

# # original = Box()

# # child_a = bad_result(original, "A")
# # child_b = bad_result(original, "B")

# # print("original:", original.items)
# # print("child_a:", child_a.items)
# # print("child_b:", child_b.items)
# # print("same object?", original is child_a, original is child_b)

# # from magic import magic_hash
# # import pickle

# # with open("magic_tables.pkl", "rb") as file:
# #     data = pickle.load(file) 

# # square = 27
# # table, magic, shift, relevant_mask = data["rook"][square]

# # blockers = (1 << 43 | 1 << 29) & relevant_mask

# # index = magic_hash(blockers, magic, shift)
# # actual = table[index]

# # expected_rook = (
# #     (1 << 35) |
# #     (1 << 43) |
# #     (1 << 28) |
# #     (1 << 29) |
# #     (1 << 26) |
# #     (1 << 25) |
# #     (1 << 24) |
# #     (1 << 19) |
# #     (1 << 11) |
# #     (1 << 3)
# # )

# # print(actual == expected_rook)

# # Context summary:
# # We are building a chess engine and Pygame display in this NOVA project.
# #
# # Engine state:
# # - engine.py has a State class using nested bitboard dicts:
# #   state.pieces["wh"]["p/n/b/r/q/k"]
# #   state.pieces["bl"]["p/n/b/r/q/k"]
# # - Bit mapping:
# #   bit 0 = a1, bit 1 = b1, ..., bit 7 = h1,
# #   bit 8 = a2, ..., bit 63 = h8.
# # - State.copy() copies both inner dicts.
# # - result(s, a) expects a = (source_mask, destination_mask).
# # - result copies state, finds moving piece by source mask, removes captures,
# #   moves the piece with source/destination XOR mask, and returns the copy.
# # - Assumption: actions only generates legal moves, so result does not validate.
# #
# # Display:
# # - display.py loads images/Chess_Pieces.png and slices the spritesheet.
# # - chess_pieces matches engine naming:
# #   chess_pieces["wh"]["p"], chess_pieces["bl"]["k"], etc.
# # - draw_board(screen, chess_pieces, state) draws squares, scans bitboards,
# #   and draws pieces from bits 0..63.
# # - Display has self.block_size = 100.
# # - Future drag plan:
# #   Display handles mouse input, square/mask conversion, dragging state, drawing.
# #   Engine handles State, actions, result, legal move checks, and turn updates.
# #
# # Magic bitboards:
# # - magic.py generates rook/bishop magic tables.
# # - Important functions:
# #   magic_hash(blockers, magic, shift)
# #   get_blocker_mask(pos, vectors)
# #   get_attack_mask(blocker, pos, vectors)
# #   get_all_blockers(vectors)
# #   find_magics(data, blockers, vectors)
# #   build_magic_tables()
# #   save_magic_tables(filename="magic_tables.pkl")
# # - Data shape:
# #   rook_data[square] = [table, magic, shift, relevant_mask]
# #   bishop_data[square] = [table, magic, shift, relevant_mask]
# #   table[index] = attack_mask
# # - Pickle shape:
# #   {"rook": rook_data, "bishop": bishop_data}
# # - Magic lookup flow:
# #   table, magic, shift, relevant_mask = data[piece][square]
# #   blockers = occupancy & relevant_mask
# #   index = magic_hash(blockers, magic, shift)
# #   attack_mask = table[index]
# #   legal_destinations = attack_mask & ~friendly_occupancy
# #
# # Current test:
# # - test.py tests rook lookup for rook on d4, square 27.
# # - Blockers are on d6 and f4.
# # - The lookup returns True against the expected rook attack mask.
# #
# # Next engine steps:
# # 1. Load magic_tables.pkl in engine.py.
# # 2. Add occupancy helpers for white, black, and all pieces.
# # 3. Add sliding attack lookup helper.
# # 4. Convert destination attack bits into actions.
# # 5. Generate rook, bishop, and queen actions using magic lookup.
# # 6. Add knight moves separately.
# # 7. Add pawns and kings later.
# # 8. Add king-safety legality filtering later.


# # square = 27
# # table, magic, shift, relevant_mask = data["bishop"][square]

# # blockers = (1 << 45 | 1 << 41 | 1 << 13) & relevant_mask

# # index = magic_hash(blockers, magic, shift)
# # actual = table[index]

# # expected_bishop = (
# #     (1 << 36) |
# #     (1 << 45) |
# #     (1 << 34) |
# #     (1 << 41) |
# #     (1 << 20) |
# #     (1 << 13) |
# #     (1 << 18) |
# #     (1 << 9) |
# #     (1 << 0)
# # )

# # print(actual == expected_bishop)



# # --- Generic PyTorch example, built up step by step ---
# # Step 1: a single layer on its own, no class yet.

# import torch
# import torch.nn as nn

# # class TinyRegressor(nn.Module):
# #     def __init__(self):
# #         super().__init__()
# #         self.layer1 = nn.Linear(4, 8)
# #         self.layer2 = nn.Linear(8, 1)

# #     def forward(self, x):
# #         hidden = self.layer1(x)
# #         out = self.layer2(hidden)
# #         return out

# # model = TinyRegressor()
# # loss_fn = nn.MSELoss()
# # optimiser = torch.optim.SGD(model.parameters(), lr=0.015)

# # x = torch.rand(1, 4)
# # target = torch.rand(1, 1)

# # optimiser.zero_grad()
# # prediction = model(x)
# # loss = loss_fn(prediction, target)
# # loss.backward()


# # --- nn.EmbeddingBag: the sparse accumulator pattern NNUE needs ---

# # embedding_bag = nn.EmbeddingBag(10, 4, mode="sum")  # 10 possible feature ids, 4-dim vector each

# # # sample 1 has active features [1, 3]
# # # sample 2 has active features [0, 5, 7]
# # # flatten every sample's active indices into ONE 1D tensor:
# # indices = torch.tensor([1, 3, 0, 5, 7])
# # # offsets says where each sample's chunk starts inside 'indices'
# # offsets = torch.tensor([0, 2])


# # # --- Full HalfKP-shaped architecture skeleton ---
# # # ONE shared feature_transformer, called twice (white persp., black persp.),
# # # concatenated to 512, then plain nn.Linear layers from there on.
# # # Indices below are fake placeholders, not real HalfKP indices yet.

# # class NNUEShapeDemo(nn.Module):
# #     def __init__(self):
# #         super().__init__()
# #         self.feature_transformer = nn.EmbeddingBag(40960, 256, mode="sum")  # the ONE shared table
# #         self.layer1 = nn.Linear(512, 32)
# #         self.layer2 = nn.Linear(32, 32)
# #         self.output_layer = nn.Linear(32, 1)

# #     def forward(self, white_indices, white_offsets, black_indices, black_offsets, white_to_move):
# #         white_acc = self.feature_transformer(white_indices, white_offsets)  # (batch, 256)
# #         black_acc = self.feature_transformer(black_indices, black_offsets)  # (batch, 256), SAME table again

# #         # THE ACTUAL SWAP - this was missing before
# #         if white_to_move:
# #             combined = torch.cat([white_acc, black_acc], dim=1)  # mover's acc first
# #         else:
# #             combined = torch.cat([black_acc, white_acc], dim=1)  # mover's acc first

# #         x = torch.relu(self.layer1(combined))
# #         x = torch.relu(self.layer2(x))
# #         return self.output_layer(x)

# # nnue_demo = NNUEShapeDemo()

# # # SAME position, SAME indices both times - only white_to_move changes
# # white_indices = torch.tensor([123, 4567, 8900])
# # white_offsets = torch.tensor([0])
# # black_indices = torch.tensor([222, 5555, 9999, 12000])
# # black_offsets = torch.tensor([0])

# # out_white_to_move = nnue_demo(white_indices, white_offsets, black_indices, black_offsets, white_to_move=True)
# # out_black_to_move = nnue_demo(white_indices, white_offsets, black_indices, black_offsets, white_to_move=False)


# # # --- Decorators ---

# # def loud(func):
# #     def wrapper(*args, **kwargs):
# #         print(f"calling {func.__name__}")
# #         result = func(*args, **kwargs)
# #         print(f"{func.__name__} returned {result}")
# #         return result
# #     return wrapper

# # @loud
# # def add(a, b):
# #     return a + b

# # add(2, 3)

# # # torch.no_grad() used as a decorator: nothing inside builds a computation
# # # graph, since no backward() will ever be called on it.

# # def run_inference(model, x):
# #     torch.no_grad()
# #     return model(x)

# # no_grad_out = run_inference(model, torch.rand(1, 4))

# # with open("fen_analysis.csv", "r") as file:
# #     raw = file.readlines(1)

# #     for line in raw:
# #        prediciton = line.split(",")[-1]
# #        example = "".join(line.split(",")[:-1])


import random
# Shuffling the data:
lines = []
with open("fen_analysis.csv", "r") as file:
    for line in file:
       lines.append(line)

    lines = random.sample(lines, len(lines))

file.close()

with open("fen_randomised.csv", "w") as file:
    for line in lines:
        file.write(line)