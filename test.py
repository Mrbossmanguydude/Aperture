# class Box:
#     def __init__(self):
#         self.items = []

# def bad_result(box, item):
#     box.items.append(item)
#     return box

# original = Box()

# child_a = bad_result(original, "A")
# child_b = bad_result(original, "B")

# print("original:", original.items)
# print("child_a:", child_a.items)
# print("child_b:", child_b.items)
# print("same object?", original is child_a, original is child_b)

from magic import magic_hash
import pickle

with open("magic_tables.pkl", "rb") as file:
    data = pickle.load(file) 

square = 27
table, magic, shift, relevant_mask = data["rook"][square]

blockers = (1 << 43 | 1 << 29) & relevant_mask

index = magic_hash(blockers, magic, shift)
actual = table[index]

expected_rook = (
    (1 << 35) |
    (1 << 43) |
    (1 << 28) |
    (1 << 29) |
    (1 << 26) |
    (1 << 25) |
    (1 << 24) |
    (1 << 19) |
    (1 << 11) |
    (1 << 3)
)

print(actual == expected_rook)

# Context summary:
# We are building a chess engine and Pygame display in this NOVA project.
#
# Engine state:
# - engine.py has a State class using nested bitboard dicts:
#   state.pieces["wh"]["p/n/b/r/q/k"]
#   state.pieces["bl"]["p/n/b/r/q/k"]
# - Bit mapping:
#   bit 0 = a1, bit 1 = b1, ..., bit 7 = h1,
#   bit 8 = a2, ..., bit 63 = h8.
# - State.copy() copies both inner dicts.
# - result(s, a) expects a = (source_mask, destination_mask).
# - result copies state, finds moving piece by source mask, removes captures,
#   moves the piece with source/destination XOR mask, and returns the copy.
# - Assumption: actions only generates legal moves, so result does not validate.
#
# Display:
# - display.py loads images/Chess_Pieces.png and slices the spritesheet.
# - chess_pieces matches engine naming:
#   chess_pieces["wh"]["p"], chess_pieces["bl"]["k"], etc.
# - draw_board(screen, chess_pieces, state) draws squares, scans bitboards,
#   and draws pieces from bits 0..63.
# - Display has self.block_size = 100.
# - Future drag plan:
#   Display handles mouse input, square/mask conversion, dragging state, drawing.
#   Engine handles State, actions, result, legal move checks, and turn updates.
#
# Magic bitboards:
# - magic.py generates rook/bishop magic tables.
# - Important functions:
#   magic_hash(blockers, magic, shift)
#   get_blocker_mask(pos, vectors)
#   get_attack_mask(blocker, pos, vectors)
#   get_all_blockers(vectors)
#   find_magics(data, blockers, vectors)
#   build_magic_tables()
#   save_magic_tables(filename="magic_tables.pkl")
# - Data shape:
#   rook_data[square] = [table, magic, shift, relevant_mask]
#   bishop_data[square] = [table, magic, shift, relevant_mask]
#   table[index] = attack_mask
# - Pickle shape:
#   {"rook": rook_data, "bishop": bishop_data}
# - Magic lookup flow:
#   table, magic, shift, relevant_mask = data[piece][square]
#   blockers = occupancy & relevant_mask
#   index = magic_hash(blockers, magic, shift)
#   attack_mask = table[index]
#   legal_destinations = attack_mask & ~friendly_occupancy
#
# Current test:
# - test.py tests rook lookup for rook on d4, square 27.
# - Blockers are on d6 and f4.
# - The lookup returns True against the expected rook attack mask.
#
# Next engine steps:
# 1. Load magic_tables.pkl in engine.py.
# 2. Add occupancy helpers for white, black, and all pieces.
# 3. Add sliding attack lookup helper.
# 4. Convert destination attack bits into actions.
# 5. Generate rook, bishop, and queen actions using magic lookup.
# 6. Add knight moves separately.
# 7. Add pawns and kings later.
# 8. Add king-safety legality filtering later.


square = 27
table, magic, shift, relevant_mask = data["bishop"][square]

blockers = (1 << 45 | 1 << 41 | 1 << 13) & relevant_mask

index = magic_hash(blockers, magic, shift)
actual = table[index]

expected_bishop = (
    (1 << 36) |
    (1 << 45) |
    (1 << 34) |
    (1 << 41) |
    (1 << 20) |
    (1 << 13) |
    (1 << 18) |
    (1 << 9) |
    (1 << 0)
)

print(actual == expected_bishop)
