import pickle
from magic import magic_hash

class State:
    def __init__(self, fen=None):
        '''
        Represents one chess position: piece placement plus (optionally)
        metadata parsed from a FEN string.

        Input:
            fen - a FEN string, or None for the standard starting position.

        Sets:
            self.pieces    - nested bitboard dict: pieces["wh"/"bl"]["p/n/b/r/q/k"]
            self.init_info - [castling_availability, en_passant_target_square,
                              halfmove_clock, fullmove_number] parsed from the
                              FEN, or None if using the default starting position.
        '''

        if fen == None:
            self.pieces = {
                "wh": {
                    "p": 0x000000000000FF00,
                    "n": 0x0000000000000042,
                    "b": 0x0000000000000024,
                    "r": 0x0000000000000081,
                    "q": 0x0000000000000008,
                    "k": 0x0000000000000010,
                },
                "bl": {
                    "p": 0x00FF000000000000,
                    "n": 0x4200000000000000,
                    "b": 0x2400000000000000,
                    "r": 0x8100000000000000,
                    "q": 0x0800000000000000,
                    "k": 0x1000000000000000,
                },
            }

            self.init_info = None

        else:
            self.pieces, self.init_info = self.fen_to_pos(fen)

    def fen_to_pos(self, fen):
        '''
        Parses a FEN string into piece bitboards and game metadata.

        Input:
            fen - a full FEN string (all 6 space-separated fields).

        Output:
            (pieces, info) where:
              pieces - nested bitboard dict, same shape as State.pieces.
              info   - [castling_availability, en_passant_target_square,
                        halfmove_clock, fullmove_number].

        Process:
            Reverses each rank then reverses the whole string, so the
            characters can be walked left-to-right while still filling
            squares in bit-index order (bit 0 = a1 ... bit 63 = h8).
            Digits skip that many empty squares; letters set a bit in the
            matching colour/piece bitboard.
        '''

        self.pieces = {
            "wh": {
                "p": 0,
                "n": 0,
                "b": 0,
                "r": 0,
                "q": 0,
                "k": 0,
            },
            "bl": {
                "p": 0,
                "n": 0,
                "b": 0,
                "r": 0,
                "q": 0,
                "k": 0,
            },
        }
        
        fen_parts = fen.split(' ')
        rows = "/".join([i[::-1] for i in fen_parts[0].split("/")])[::-1]
        square = 0

        for ptype in rows:
            if ptype.isdigit():
                square += int(ptype)

            elif ptype != "/":
                
                col = "bl" if ptype.lower() == ptype else "wh"
                self.pieces[col][ptype.lower()] |= 1 << square

                square += 1

        turn = fen_parts[1] + "h" if fen_parts[1] == "w" else fen_parts[1] + "l"
        castling_availability = fen_parts[2]
        en_passant_target_square = fen_parts[3]
        halfmove_clock = int(fen_parts[4])
        fullmove_number = int(fen_parts[5])

        info = [turn, castling_availability, en_passant_target_square, halfmove_clock, fullmove_number]

        return self.pieces, info

    def copy(self):
        '''
        Returns a new State with an independent copy of the piece bitboards
        (safe to mutate without affecting the original).

        Input: none.
        Output: a new State object.
        '''
        s1 = State()
        s1.pieces = {
            "wh": self.pieces["wh"].copy(),
            "bl": self.pieces["bl"].copy(),
        }
        return s1

class Engine:
    def __init__(self):
        '''
        Sets up a fresh engine: starting position, whose turn it live-plays
        as, and the pre-built magic bitboard tables used for sliding-piece
        move generation.

        Sets:
            self.s     - the current live State (starting position).
            self.pturn - bool, whether it's currently the live player's turn.
            self.pcol  - the live player's colour, "wh" or "bl".
            self.data  - {"rook": rook_data, "bishop": bishop_data} loaded
                         from magic_tables2.pkl.
        '''
        self.s = State()
        self.pturn = True
        self.pcol = "wh"
        with open("magic_tables2.pkl", "rb") as file:
            self.data = pickle.load(file) # magic_tables.pkl is the initial file that was erroneous for some corner squares for rooks.

    def actions(self, s, enpassant_square, turn, castling_data):

        '''
        Generates every LEGAL move for `turn` in state `s`.

        Inputs:
            s               - the State to generate moves from.
            enpassant_square - current en passant target square (bitmask) or None.
            turn            - "wh" or "bl", whose moves to generate.
            castling_data   - castling-rights tracking dict (shape below).

        Output:
            (legal_acs, enpassant_square) - legal_acs is a list of
            (src_mask, dest_mask, promo_piece) action tuples; enpassant_square
            is passed straight through unchanged.

        Process:
            Generates pseudo-legal moves piece type by piece type (knights,
            sliding pieces via magic bitboards, pawns incl. en passant/
            promotion, king, castling), then filters that whole list down to
            only moves that don't leave the mover's own king in check.

        castling_data = {

        "wh": {
            "left_r" : [init_pos, moved],
            "right_r" : [init_pos, moved],
            "k" : [init_pos, moved]
        } ,

        "bl" : {
            "left_r" : [init_pos, moved],
            "right_r" : [init_pos, moved],
            "k" : [init_pos, moved]
        }

        }

        Has the above assumed shape (Initially passed into actions when white first plays.)

        castling_positions = {
            "wh" : {
                "right" : [king_pos, rook_pos],
                "left" : [king_pos, rook_pos]
            },

            "bl" : {
                "right" : [king_pos, rook_pos],
                "left" : [king_pos, rook_pos]
            }
        }

        Which stores the final positions of the piece once castled (this one is always constant and is defined when used).
        '''
        acs = []
        col_occ = {}

        for col in s.pieces:
            occ = 0
            for piece in s.pieces[col]:
                occ |= s.pieces[col][piece]
            col_occ[col] = occ

        tot_occ = col_occ["wh"] | col_occ["bl"]

        '''
        Pieces Left:
        - Castling
        '''

        # Knight Movement:
        knight_positions = s.pieces[turn]["n"]
        knight_vectors = [(1, 2), (-1, 2), (1, -2), (-1, -2)
                   ,(2, 1), (2, -1), (-2, 1), (-2, -1)]

        for square in range(0, 64):
            pos = 1 << square 

            if pos & knight_positions != 0:
                length = pos.bit_length() - 1
                x = length % 8
                y = length // 8

                for vector in knight_vectors:
                    tempx, tempy = x + vector[0], y + vector[1]
                    if 0 <= tempx <= 7 and 0 <= tempy <= 7:
                        dest_pos = 1 << (tempx + (tempy * 8))
                        if dest_pos & col_occ[turn] == 0:
                            acs.append((pos, dest_pos, None))
        #---------------------
        #   Sliding Pieces    
        #---------------------

        # Compiling Data:

        rook_data = self.data["rook"]
        bishop_data = self.data["bishop"]

        # Bishop Movement:
        bishop_positions = s.pieces[turn]["b"]
        acs += self.sliding_piece_acs(bishop_positions, bishop_data, tot_occ, col_occ, turn)

        # Rook Movement:
        rook_positions = s.pieces[turn]["r"]
        acs += self.sliding_piece_acs(rook_positions, rook_data, tot_occ, col_occ, turn)

        # Queen Movement:
        queen_positions = s.pieces[turn]["q"]
        acs += self.sliding_piece_acs(queen_positions, rook_data, tot_occ, col_occ, turn)
        acs += self.sliding_piece_acs(queen_positions, bishop_data, tot_occ, col_occ, turn)

        # Pawn Movement:
        pawn_positions = s.pieces[turn]["p"]
        back_rank = {
            "wh" : 1,
            "bl" : 6
        }

        promo_rank = {
                    "wh" : 7,
                    "bl" : 0
                }

        take_vectors = {
            "wh" : [(1, 1), (-1, 1)],
            "bl" : [(1, -1), (-1, -1)]
        }

        promo_pieces = ["q", "r", "n", "b"]

        for square in range(0, 64):
            pos = 1 << square 
            if pos & pawn_positions != 0:
                length = pos.bit_length() - 1
                x = length % 8
                y = length // 8

                jump1_pos = 1 << (x + ((y + 1) * 8)) if turn == "wh" else 1 << (x + ((y - 1) * 8))

                if jump1_pos & tot_occ == 0:
                    if ((jump1_pos.bit_length() - 1) // 8) == promo_rank[turn]:
                        for piece in promo_pieces:
                            acs.append((pos, jump1_pos, piece))
                    else:
                        acs.append((pos, jump1_pos, None))

                if y == back_rank[turn]:
                    jump2_pos = 1 << (x + ((y + 2) * 8)) if turn == "wh" else 1 << (x + ((y - 2) * 8))
                    if jump1_pos & tot_occ == 0 and jump2_pos & tot_occ == 0:
                        acs.append((pos, jump2_pos, None))

                for vector in take_vectors[turn]:
                    tempx, tempy = x + vector[0], y + vector[1]
                    if 0 <= tempx <= 7 and 0 <= tempy <= 7:
                        take_pos = 1 << (tempx + (tempy * 8))
                        if col_occ[self.not_col(turn)] & take_pos != 0:
                            acs.append((pos, take_pos, None)) 

        if enpassant_square != None:
            eligibility_vectors = {
                "wh" : [(-1, -1), (1, -1)],
                "bl" : [(1, 1), (-1, 1)]
            }

            length = enpassant_square.bit_length() - 1
            x = length % 8
            y = length // 8

            for vector in eligibility_vectors[turn]:
                tempx, tempy = x + vector[0], y + vector[1]
                if 0 <= tempx <= 7 and 0 <= tempy <= 7:
                    pos = 1 << (tempx + (tempy * 8))
                    if s.pieces[turn]["p"] & pos != 0:
                        acs.append((pos, enpassant_square, None))

        # King Movement and Checks:

        king_vectors = [(1, 0), (-1, 0), (1, 1), (-1, 1), (0, 1), (0, -1), (-1, -1), (1, -1)]
        king_pos = s.pieces[turn]["k"]

        king_square = king_pos.bit_length() - 1
        x = king_square % 8
        y = king_square // 8

        for vector in king_vectors:
            tempx, tempy = x + vector[0], y + vector[1]
            if 0 <= tempx <= 7 and 0 <= tempy <= 7:
                dest_pos = 1 << (tempx + (tempy * 8))
                if (dest_pos & col_occ[turn] == 0 and 
                    not self.check_for_checks(rook_data, bishop_data, dest_pos, knight_vectors, tot_occ, s, turn)):
                    acs.append((king_pos, dest_pos, None))

        # Castling:
        if not self.check_for_checks(rook_data, bishop_data, king_pos, knight_vectors, tot_occ, s, turn):
            if not castling_data[turn]["k"][1]:
                eligible = True
                if not castling_data[turn]["left_r"][1]:
                    test_positions = [1 << ((x - i) + (y * 8)) for i in range(1, 4)]

                    for position in range(len(test_positions) - 1):
                        if (self.check_for_checks(rook_data, bishop_data, test_positions[position], knight_vectors, tot_occ, s, turn)
                            or test_positions[position] & tot_occ != 0):
                            eligible = False

                    if test_positions[2] & tot_occ != 0:
                        eligible = False

                    if eligible:
                        acs.append((king_pos, 1 << ((x - 2) + (y * 8)), None))

                eligible = True

                if not castling_data[turn]["right_r"][1]:
                    test_positions = [1 << ((x + i) + (y * 8)) for i in range(1, 3)]
                    for position in test_positions:
                        if (self.check_for_checks(rook_data, bishop_data, position, knight_vectors, tot_occ, s, turn)
                            or position & tot_occ != 0):
                            eligible = False

                    if eligible:
                        acs.append((king_pos, 1 << ((x + 2) + (y * 8)), None))

        # Legality Filter:
        legal_acs = []
        for action in acs:
            temp_s = self.result(s.copy(), action, [], castling_data, 0)[0]
            dest = king_pos
            if action[0] & s.pieces[turn]["k"]:
                dest = action[1]

            col_occ = {}
            
            for col in temp_s.pieces:
                occ = 0
                for piece in temp_s.pieces[col]:
                    occ |= temp_s.pieces[col][piece]
                col_occ[col] = occ
    
            temp_tot_occ = col_occ["wh"] | col_occ["bl"]

            if not self.check_for_checks(rook_data, bishop_data, dest, knight_vectors, temp_tot_occ, temp_s, turn):
                legal_acs.append(action)
        
        return legal_acs, enpassant_square

    def not_playercol(self):
        '''Returns the colour the live player is NOT playing ("wh"/"bl").'''
        return "wh" if self.pcol == "bl" else "bl"

    def not_col(self, col):
        '''Returns the opposite colour string to `col` ("wh" <-> "bl").'''
        return "wh" if col == "bl" else "bl"

    def sliding_piece_acs(self, piece_positions, piece_data, tot_occ, col_occ, turn):
        '''
        Generates pseudo-legal moves for one sliding piece type (rook or
        bishop table; queen is generated by calling this twice, once per
        table) using magic bitboard lookups.

        Inputs:
            piece_positions - bitboard of this piece type for `turn`.
            piece_data      - rook_data or bishop_data (from self.data).
            tot_occ         - bitboard of every occupied square.
            col_occ         - {"wh": occ, "bl": occ} per-colour occupancy.
            turn            - "wh" or "bl".

        Output:
            List of (src_mask, dest_mask, None) action tuples. Excludes
            squares occupied by `turn`'s own pieces; does not yet filter
            for check legality (actions() does that afterwards).
        '''
        acs = []

        for square in range(0, 64):
            pos = 1 << square
            if pos & piece_positions != 0:
                table, magic, shift, relevant_mask = piece_data[square]

                blockers = tot_occ & relevant_mask

                index = magic_hash(blockers, magic, shift)
                attack_mask = table[index]

                for sq in range(0, 64):
                    dest_pos = 1 << sq
                    if dest_pos & attack_mask:
                        if dest_pos & col_occ[turn] == 0:
                            acs.append((pos, dest_pos, None))

        return acs

    def result(self, s, a, enpassant_pos, castling_data, half_move):
        '''
        Applies action `a` to state `s` and returns the resulting position
        plus updated game metadata.

        Inputs:
            s             - the State BEFORE the move.
            a             - (src_mask, dest_mask, promo_piece).
            enpassant_pos - current en passant target square (or None); used
                            to detect whether this move IS an en passant
                            capture.
            castling_data - castling-rights dict; may be updated in place
                            (e.g. marking a king/rook as moved).
            half_move     - current halfmove clock (for the 50-move rule).

        Output:
            (s1, enpassant_pos, promo_flag, castling_data, half_move) where:
              s1            - the resulting State.
              enpassant_pos - the NEW en passant target this move creates
                              (or None) - feed this into the next call.
              promo_flag    - True if this move requires a promotion choice.
              castling_data - updated castling-rights dict.
              half_move     - updated halfmove clock.

        Process:
            Identifies the moving piece by src_mask, handles special cases
            (en passant capture, castling rook movement, promotion,
            castling-rights updates), removes any captured piece, then moves
            the piece via XOR on src/dest masks.
        '''
        s1 = s.copy()
        src_mask, dest_mask, promo_piece = a
        move_mask = src_mask | dest_mask

        dest_colour = None
        dest_piece = None

        pos = False
        promo_flag = False

        jump2 = False
        half_reset = False

        for ptype in s.pieces["wh"]:
            # Source/position masks:
            if (s1.pieces["wh"][ptype] & src_mask) != 0:
                pos_colour = "wh"
                pos_piece = ptype
                pos = True

            elif (s1.pieces["bl"][ptype] & src_mask) != 0:
                pos_colour = "bl"
                pos_piece = ptype
                pos = True

            if pos:
                break

        # En Passant and Promotion
        if pos_piece == "p":
            square = src_mask.bit_length() - 1
            x = square % 8
            y = square // 8

            jump_vectors = {
                        "wh" : (2, 1),
                        "bl" : (-2, -1)
                    }

            # Checking 2 jumps:
            if 0 <= y + jump_vectors[pos_colour][0] <= 7:
                test_dest = 1 << (x + ((y + jump_vectors[pos_colour][0]) * 8))
                if test_dest == dest_mask:
                    enpassant_pos = 1 << (x + ((y + jump_vectors[pos_colour][1]) * 8))
                    jump2 = True

        elif pos_piece == "r" or pos_piece == "k":
            if pos_piece == "k":
                square = src_mask.bit_length() - 1
                x = square % 8
                y = square // 8

                if dest_mask == 1 << ((x + 2) + (y * 8)) or dest_mask == 1 << ((x - 2) + (y * 8)):
                    # Castling
                    if not castling_data[pos_colour]["k"][1]:
                        castling_data[pos_colour]["k"][1] = True

                        castling_positions = {
                                    "wh" : {
                                        "right" : [(6, 0), (5, 0)],
                                        "left" : [(2, 0), (3, 0)]
                                    },
                        
                                    "bl" : {
                                        "right" : [(6, 7), (5, 7)],
                                        "left" : [(2, 7), (3, 7)]
                                    }
                                        }

                        side = {
                            2 : "right",
                            -2: "left"
                        }

                        dx = ((dest_mask.bit_length() - 1) % 8) - ((src_mask.bit_length() - 1) % 8)
                        castling_side = side[dx]

                        rook_mask = self.coord_to_mask(castling_positions[pos_colour][castling_side][1])
                        s1.pieces[pos_colour]["r"] ^= rook_mask # Adds the rook to the right position

                        # Removing the rook:

                        rook_mask = self.coord_to_mask(castling_data[pos_colour][castling_side + "_r"][0])
                        s1.pieces[pos_colour]["r"] ^= rook_mask
                        
            else:
                for ptype in castling_data[pos_colour]:
                    if ptype != "k":
                        if (not castling_data[pos_colour][ptype][1] and
                             self.coord_to_mask(castling_data[pos_colour][ptype][0]) & src_mask != 0):
                            
                            castling_data[pos_colour][ptype][1] = True

        else:
            # If a piece takes a rook that hasnt moved
            for ptype in castling_data[pos_colour]:
                if ptype != "k":
                    if (not castling_data[self.not_col(pos_colour)][ptype][1] and
                        self.coord_to_mask(castling_data[self.not_col(pos_colour)][ptype][0]) & dest_mask != 0):

                        castling_data[self.not_col(pos_colour)][ptype][1] = True

        for ptype in s.pieces["wh"]:
            # Destination masks:
            if (s1.pieces["wh"][ptype] & dest_mask) != 0:
                dest_colour = "wh"
                dest_piece = ptype

            elif (s1.pieces["bl"][ptype] & dest_mask) != 0:
                dest_colour = "bl"
                dest_piece = ptype

            if dest_colour != None:
                s1.pieces[dest_colour][dest_piece] ^= dest_mask
                half_move = 0
                half_reset = True
                break

        if pos_piece == "p":
            half_move = 0
            half_reset = True

            square = dest_mask.bit_length() - 1
            x = square % 8
            y = square // 8

            if dest_mask == enpassant_pos:
                take_vectors = {
                            "wh" : -1,
                            "bl" : 1
                        }

                square = dest_mask.bit_length() - 1
                x = square % 8
                y = square // 8

                true_dest = 1 << (x + ((y + take_vectors[pos_colour]) * 8))

                s1.pieces[self.not_col(pos_colour)]["p"] ^= true_dest

            if (pos_colour == "wh" and y == 7) or(pos_colour == "bl" and y == 0):
                promo_flag = True

        if promo_piece != None:
            s1.pieces[pos_colour][pos_piece] ^= src_mask
            s1.pieces[pos_colour][promo_piece] ^= dest_mask

        else:
            s1.pieces[pos_colour][pos_piece] ^= move_mask

        if not jump2:
            enpassant_pos = None

        if not half_reset:
            half_move += 1

        return s1, enpassant_pos, promo_flag, castling_data, half_move

    def coord_to_mask(self, coord):
        '''Converts an (x, y) coordinate tuple into its bitboard mask.'''
        x, y = coord

        mask = 1 << (x + (y * 8))

        return mask

    def terminal(self, s, turn, castling_data, halfmove):
        '''
        Checks whether the game has ended at state `s`, with `turn` to move.

        Inputs:
            s             - the State to check.
            turn          - "wh" or "bl", whose move it is.
            castling_data - castling-rights dict (needed to call actions()).
            halfmove      - current halfmove clock.

        Output:
            0    - draw (50-move rule, or stalemate).
            -1   - white has lost (checkmated).
            1    - black has lost (checkmated).
            None - game continues (legal moves remain).
        '''
        if halfmove == 100:
            return 0

        acs = self.actions(s, None, turn, castling_data)[0]

        if len(acs) == 0:
            rook_data = self.data["rook"]
            bishop_data = self.data["bishop"]

            knight_vectors = [(1, 2), (-1, 2), (1, -2), (-1, -2)
                               ,(2, 1), (2, -1), (-2, 1), (-2, -1)]
    
            king_pos = s.pieces[turn]["k"]

            col_occ = {}
            
            for col in s.pieces:
                occ = 0
                for piece in s.pieces[col]:
                    occ |= s.pieces[col][piece]
                col_occ[col] = occ
    
            tot_occ = col_occ["wh"] | col_occ["bl"]

            if self.check_for_checks(rook_data, bishop_data, king_pos, knight_vectors, tot_occ, s, turn):
                if turn == "wh":
                    return -1

                else:
                    return 1

            return 0

        return None
    
    def check_for_checks(self, rook_data, bishop_data, king_pos, knight_vectors, tot_occ, s, turn):
        '''
        Checks whether the king at `king_pos` (belonging to `turn`) is
        currently attacked by any opposing piece.

        Inputs: magic tables (rook_data/bishop_data), king_pos (bitmask),
                knight_vectors, tot_occ (full board occupancy), s, turn.

        Output: True if in check, False otherwise.

        Process: checks sliding-piece attacks via magic bitboard lookups
        (rooks/bishops/queens), then pawn/knight/king attacks by vector.
        '''
        square = king_pos.bit_length() - 1

        # Rooks:
        if self.check_for_sliding_checks(rook_data, tot_occ, s, turn, square, "r"):
            return True

        # Bishops:
        if self.check_for_sliding_checks(bishop_data, tot_occ, s, turn, square, "b"):
            return True

        # Queens:
        if (self.check_for_sliding_checks(bishop_data, tot_occ, s, turn, square, "q") or
            self.check_for_sliding_checks(rook_data, tot_occ, s, turn, square, "q")):
            return True

        # Pawns:
        take_vectors = {
                    "wh" : [(1, 1), (-1, 1)],
                    "bl" : [(1, -1), (-1, -1)]
                }

        length = king_pos.bit_length() - 1
        x = length % 8
        y = length // 8

        for vector in take_vectors[turn]:
            tempx, tempy = x + vector[0], y + vector[1]
            if 0 <= tempx <= 7 and 0 <= tempy <= 7:
                take_pos = 1 << (tempx + (tempy * 8))
                if take_pos & s.pieces[self.not_col(turn)]["p"] != 0:
                    return True
                
        # Knights:
        for vector in knight_vectors:
            tempx, tempy = x + vector[0], y + vector[1]
            if 0 <= tempx <= 7 and 0 <= tempy <= 7:
                dest_pos = 1 << (tempx + (tempy * 8))
                if dest_pos & s.pieces[self.not_col(turn)]["n"] != 0:
                    return True

        # Other King:
        king_vectors = [(1, 0), (-1, 0), (1, 1), (-1, 1), (0, 1), (0, -1), (-1, -1), (1, -1)]

        for vector in king_vectors:
            tempx, tempy = x + vector[0], y + vector[1]
            if 0 <= tempx <= 7 and 0 <= tempy <= 7:
                dest_pos = 1 << (tempx + (tempy * 8))
                if dest_pos & s.pieces[self.not_col(turn)]["k"] != 0:
                    return True

        return False

    def check_for_sliding_checks(self, piece_data, tot_occ, s, turn, square, ptype):
        '''
        Checks whether an opposing sliding piece of type `ptype` attacks
        `square`, via magic bitboard lookup.

        Inputs: piece_data (rook_data or bishop_data), tot_occ, s, turn,
                square (int, not a bitmask), ptype ("r"/"b"/"q").

        Output: True if an opposing `ptype` piece attacks `square`.
        '''
        table, magic, shift, relevant_mask = piece_data[square]

        blockers = tot_occ & relevant_mask
        index = magic_hash(blockers, magic, shift)

        attack_mask = table[index]

        for sq in range(0, 64):
            pos = 1 << sq
            if pos & attack_mask != 0:
                if pos & s.pieces[self.not_col(turn)][ptype]:
                    return True

        return False

    def evaluation(self, s):
        '''
        Stub - will return the static evaluation of state `s` (eventually
        via the trained NNUE network). Not yet implemented.
        '''
        pass

    def switch(self, t):
        '''
        Flips a boolean turn-indicator. Used only by minimax's `max_turn`
        (True/False) - NOT the same thing as not_col's "wh"/"bl" strings.
        '''
        return True if t == False else False

    def quiescence_search(self, s, a, t, b, castling_data, half_move, enpassant_pos):

        col_occ = {col: sum(pieces.values()) for col, pieces in s.pieces.items()}
        tot_occ = col_occ["wh"] | col_occ["bl"]

        if not self.check_for_checks(self.data["rook"], self.data["bishop"], s.pieces[t]["k"], [(1, 2), (-1, 2), (1, -2), (-1, -2),(2, 1), (2, -1), (-2, 1), (-2, -1)], tot_occ, s, t):

            eval = self.evaluation(s)
            best_value = eval

            if best_value >= b:
                return best_value
            if best_value > a:
                a = best_value

            capturing_moves = self.get_capturing_moves(s, enpassant_pos, t, castling_data)

            if len(capturing_moves) > 0:
                for action in capturing_moves:

                    s1, e_pos, c_data, hlf_move = self.result(s, action, enpassant_pos, castling_data, half_move)
                    score = -self.quiescence_search(s1, -b, self.not_col(t), -a, c_data, hlf_move, e_pos)

                    if score >= b:
                        return score
                    if score > best_value:
                        best_value = score
                    if score > a:
                        a = score

                return best_value

            else:
                return best_value

        else:

            best_value = -float("inf")
            moves, _ = self.actions(s, enpassant_pos, t, castling_data)

            if len(moves) > 0:
                for action in moves:
                    s1, e_pos, c_data, hlf_move = self.result(s, action, enpassant_pos, castling_data, half_move)
                    score = -self.quiescence_search(s1, -b, self.not_col(t), -a, c_data, hlf_move, e_pos)

                    if score >= b:
                        return score
                    if score > best_value:
                        best_value = score
                    if score > a:
                        a = score

                return best_value

            else:
                return best_value

    def get_capturing_moves(self, s, enpassant_pos, turn, castling_data):
        '''
        Filters actions() down to just the moves that capture a piece,
        including en passant captures.

        Inputs:
            s             - current State.
            enpassant_pos - current en passant target square (or None).
            turn          - "wh" or "bl", whose moves to generate.
            castling_data - castling-rights dict (needed to call actions()).

        Output: list of (src_mask, dest_mask, promo_piece) action tuples
        that are captures.

        Process:
            A move onto a square the opponent occupies is always a capture.
            En passant is the one exception - its destination square is
            empty - so it's detected separately by checking the moving
            piece is a pawn landing exactly on enpassant_pos.
        '''
        col_occ = {col: sum(pieces.values()) for col, pieces in s.pieces.items()}
        opponent_occ = col_occ[self.not_col(turn)]

        all_actions, _ = self.actions(s, enpassant_pos, turn, castling_data)

        capturing_moves = []
        for action in all_actions:
            src_mask, dest_mask, promo_piece = action

            is_normal_capture = dest_mask & opponent_occ != 0
            is_enpassant_capture = (
                enpassant_pos is not None
                and dest_mask == enpassant_pos
                and s.pieces[turn]["p"] & src_mask != 0
            )

            if is_normal_capture or is_enpassant_capture:
                capturing_moves.append(action)

        return capturing_moves

    def minimax(self, s, depth, max_turn, a, b):
        '''
        Recursive minimax search with alpha-beta pruning.

        Inputs:
            s        - current State.
            depth    - plies remaining to search.
            max_turn - bool, True if this node is currently maximizing.
            a, b     - alpha/beta bounds.

        Output: [best_action, best_value] for this node.

        Note: actions()/result()/terminal() are currently called here with
        fewer arguments than their real signatures require (missing
        enpassant_square/turn/castling_data/half_move) - stale calls, not
        yet updated to match their current parameter lists.
        '''
        if depth == 0 or self.terminal(s) != None:
            return [None, self.evaluation(s)]

        acs = self.actions(s)
        best_action = None

        '''
        eval: [action to get to child position, utility of child position]
        action: [pos of piece, pos of destination]
        '''

        if max_turn:
            max_eval = -float("inf")
            for action in acs:
                cpos = self.result(s, action)

                caction, cval = self.minimax(cpos, depth-1, self.switch(max_turn), a, b)
                if cval >= max_eval:
                    best_action = action
                    max_eval = cval

                a = max(a, cval)
                if a >= b:
                    break

            return [best_action, max_eval]

        else:
            min_eval = float("inf")
            for action in acs:
                cpos = self.result(s, action)

                caction, cval = self.minimax(cpos, depth-1, self.switch(max_turn), a, b)
                if cval <= min_eval:
                    best_action = action
                    min_eval = cval

                b = min(b, cval)
                if a >= b:
                    break
            return [best_action, min_eval]

    def game(self):
        '''Stub for the main game loop (not yet implemented).'''
        # TODO: need a square -> pos converter (e.g. "e5" -> bitmask) for the
        # en passant target square coming out of fen_to_pos's init_info.
        pass


if __name__ == "__main__":
    pass