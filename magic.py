import pickle
import random

MASK_64 = 0xFFFFFFFFFFFFFFFF

#Rook
# def count_bit_directions(pos: int, ptype):
#     count = 0
#     length = pos.bit_length() - 1
#     x = length % 8
#     y = length // 8

#     if ptype == "r":
#         vectors = [(0, 1), (1, 0), (0, -1), (-1, 0)]
#         count += count_move_until_end(x, y, vectors)

#     elif ptype == "b":
#         vectors = [(1, 1), (-1, 1), (-1, -1), (1, -1)]
#         count += count_move_until_end(x, y, vectors)

#     return count

def count_move_until_end(x, y, vectors: list) -> int:
    count = 0

    for vector in vectors:
        end = False
        tempx, tempy = x, y

        while not end:
            tempx += vector[0]
            tempy += vector[1]

            if (0 < tempx < 7) and (0 < tempy < 7):
                count += 1
            else:
                end = True

    return count

def magic_hash(blockers, magic, shift):
    return ((blockers * magic) & MASK_64) >> shift

def get_blocker_mask(pos: int, vectors):

    length = pos.bit_length() - 1
    x = length % 8
    y = length // 8
    blocker = 0
    positions = []

    for vector in vectors:
        end = False
        tempx, tempy = x, y

        while not end:
            tempx += vector[0]
            tempy += vector[1]

            if (0 <= tempx <= 7) and (0 <= tempy <= 7):
                curr_pos = 1 << (tempx + (tempy * 8))
                positions.append(curr_pos)
                blocker |= curr_pos
            else:
                end = True

    return blocker, positions

def get_attack_mask(blocker, pos, vectors):

    length = pos.bit_length() - 1
    x = length % 8
    y = length // 8
    attack_mask = 0

    for vector in vectors:
        end = False
        tempx, tempy = x, y

        while not end:
            tempx += vector[0]
            tempy += vector[1]

            if (0 <= tempx < 8) and (0 <= tempy < 8):
                curr_pos = 1 << (tempx + (tempy * 8))
                attack_mask |= curr_pos

                if blocker & curr_pos:
                    end = True
            else:
                end = True

    return attack_mask

def get_all_blockers(vectors):
    blockers = {i : [] for i in range(64)}
    data = {i : [{}, 0, 0, 0] for i in range(64)}

    for square in range(0, 64):
    
        pos = 1 << square
        blocker, positions = get_blocker_mask(pos, vectors)
        relevant = blocker.bit_count()

        data[square][2] = 64 - relevant
        data[square][3] = blocker

        lim = 2**relevant
        for count in range(0, lim):
            combo = 0

            for i in range(0, relevant):
                if count & (1 << i):
                    combo |= positions[i]

            blockers[square].append(combo)

    return data, blockers

def find_magics(data, blockers, vectors):
    for square in range(0, 64):
        found = False
        shift = data[square][2]
        attacks = {
            blocker: get_attack_mask(blocker, 1 << square, vectors)
            for blocker in blockers[square]
        }

        while not found:
            magic = random.getrandbits(64) & random.getrandbits(64) & random.getrandbits(64)
            table = {}
            invalid = False

            for blocker, attack_mask in attacks.items():
                index = magic_hash(blocker, magic, shift)

                if index not in table:
                    table[index] = attack_mask
                elif table[index] != attack_mask:
                    invalid = True
                    break

            if not invalid:
                found = True
                data[square][0] = table
                data[square][1] = magic

        print(f"Magic found for square {square}/63")

def build_magic_tables():

    rook_vectors = [(0, 1), (1, 0), (0, -1), (-1, 0)]
    bishop_vectors = [(1, 1), (-1, 1), (-1, -1), (1, -1)]

    rook_data, rook_blockers = get_all_blockers(rook_vectors)
    bishop_data, bishop_blockers = get_all_blockers(bishop_vectors)

    find_magics(rook_data, rook_blockers, rook_vectors)
    find_magics(bishop_data, bishop_blockers, bishop_vectors)

    return rook_data, bishop_data

def save_magic_tables(filename="magic_tables.pkl"):
    rook_data, bishop_data = build_magic_tables()
    with open(filename, "wb") as file:
        pickle.dump({"rook": rook_data, "bishop": bishop_data}, file)

if __name__ == "__main__":
    save_magic_tables(filename="magic_tables2.pkl")

# Magic Table Generation
#
# For each sliding piece type:
#   rook
#   bishop
#
# For each square on the board:
#   1. Build the relevant blocker mask for that square.
#      Rooks use horizontal/vertical directions.
#      Bishops use diagonal directions.
#      Edge squares are usually excluded from this mask.
#
#   2. Count the number of 1 bits in the relevant blocker mask.
#      If there are n relevant bits, there are 2 ** n blocker patterns.
#
#   3. Generate every blocker pattern.
#      Count from 0 to 2 ** n - 1.
#      Use the binary form of that count to decide which relevant squares
#      are occupied in that blocker pattern.
#
#   4. For each blocker pattern, calculate the true attack mask.
#      This is done by normal ray scanning:
#          move one square at a time in each direction
#          add each square to the attack mask
#          stop when a blocker is reached
#
#   5. Try one candidate magic number for this square.
#
#   6. For every blocker pattern:
#          index = magic_hash(blocker_pattern, candidate_magic)
#          attack = true attack mask for that blocker pattern
#
#      If table[index] is empty:
#          store attack there
#
#      If table[index] already stores the same attack:
#          this is a harmless collision
#
#      If table[index] already stores a different attack:
#          candidate magic fails
#
#   7. If the candidate magic fails:
#          clear the table for this square
#          try another candidate magic
#
#   8. If the candidate magic works for every blocker pattern:
#          record the magic number
#          record the relevant blocker mask
#          record the shift/relevant bit count
#          record the completed attack table
#
# Repeat this for all 64 rook squares and all 64 bishop squares.
#
#
# Magic Table Lookup
#
# During the game, for a sliding piece on a square:
#
#   1. Get the current all-piece occupancy bitboard.
#
#   2. Keep only blockers relevant to this square:
#          blockers = occupancy AND relevant_mask[square]
#
#   3. Convert those blockers into a table index:
#          index = magic_hash(blockers, magic[square])
#
#   4. Look up the precomputed attack mask:
#          attack_mask = attack_table[square][index]
#
#   5. Remove friendly-occupied squares:
#          legal_destinations = attack_mask AND NOT friendly_occupancy
#
#   6. Convert each remaining destination bit into an action:
#          source_mask, destination_mask
#
# The magic number gives the table index.
# The table gives the attack mask.
