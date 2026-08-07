class State:
    def __init__(self):
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

    def copy(self):
        s1 = State()
        s1.pieces = {
            "wh": self.pieces["wh"].copy(),
            "bl": self.pieces["bl"].copy(),
        }
        return s1

class Engine:
    def __init__(self):
        self.s = State()
        self.pturn = True
        self.pcol = "wh"

    def actions(self, s):
        
        '''
        Pieces Left:
        Knight:
        - Regular moving:
            - Cannot move if in check.
            - Cannot move outside board (Use vectorised movement conversion)
            - Can move in vectors: [(1, 2), (-1, 2), (1, -2), (-1, -2)]

        Rook:
        - Castling
        Pawn:
        - En Passant.
        - Promotion.
        - First move can be 2.
        - Takes on diagonals, moves up square by square.

        Queen:
        King:
        - Checks, Checkmate:
            - Add a broad check for all moves, by first making the move on a temp board, checking if the same colour is 
            still in check; if so, then revert move otherwise keep as a legal attacking mask. temp board is 
            derivative of current state passed into actions.
        - Castling:
            - Since this is a special move, 
        Bishop:

        
        '''

    def not_playercol(self):
        return "wh" if self.pcol == "bl" else "bl"

    def result(self, s, a):
        s1 = s.copy()
        src_mask, dest_mask = a
        move_mask = src_mask | dest_mask

        dest_colour = None
        dest_piece = None

        pos = False

        enpassant_pos = None

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
                break

        s1.pieces[pos_colour][pos_piece] ^= move_mask

        return s1, enpassant_pos

    def terminal(self, s):
        pass

    def check_for_checks(self, s):
        pass

    def evaluation(self, s):
        pass

    def switch(self, t):
        return True if t == False else False

    def minimax(self, s, depth, max_turn, a, b):
        if depth == 0 or self.terminal(s) != False:
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
        pass


if __name__ == "__main__":
    pass

# Reminder:
# Add an engine helper that loads the stored magic table data, takes a square
# and blocker bitboard, and returns the matching rook/bishop attack mask.
