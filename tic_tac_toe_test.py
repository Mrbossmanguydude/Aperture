# X is max and O is min.

class Node:
    def __init__(self, state, turn):
        self.utility = 0
        self.state = state
        self.turn = turn

        self.children = []

def create_initial_state(s) -> list:

    for i in range(len(s)):
        for _ in range(3):
            s[i].append("-")

    return s

def actions(s):
    actions = []
    for i in range(len(s)):
        for j in range(3):
            if s[i][j] == "-":
                actions.append((i, j))

    return actions 

def result(s, a, turn):
    s1 = [row.copy() for row in s]
    s1[a[0]][a[1]] = turn

    return s1

def terminal(s):

    # Checking rows
    for row in s:
        if row[0] != "-" and row[0] == row[1] == row[2]:
            return row[0]

    # Checking columns
    for col in range(3):
        if s[0][col] != "-" and s[0][col] == s[1][col] == s[2][col]:
            return s[0][col]
        
    # Checking diagonals
    if s[0][0] != "-" and s[0][0] == s[1][1] == s[2][2]:
        return s[0][0]
    
    if s[0][2] != "-" and s[0][2] == s[1][1] == s[2][0]:
        return s[0][2]

    if actions(s) == []:
        return True
        
    # If no winner yet and available moves
    return False

def utility(winner):
    # Of all terminal states

    if winner == "X":
        u = 1

    elif winner == "O":
        u = -1

    else:
        u = 0

    return u

def minimax(s, t):
    # Returns value of state given by backtracking game tree
    winner = terminal(s)

    if winner != False:
        return utility(winner)
    
    acs = actions(s)
    values = []

    for action in acs:
        s1 = result(s, action, t)
        t1 = "X" if t == "O" else "O"
        values.append(minimax(s1, t1))

    if t == "X":
        return max(values)
    elif t == "O":
        return min(values)

def best_move(s):
    acs = []

    for action in actions(s):
        s1 = result(s, action, "X")
        value = minimax(s1, "O")
        acs.append((action, value))

    return max(acs, key=lambda move: move[1])[0]

def check_win(s):
    winner = terminal(s)
    if winner != False:
        if winner == True:
            print("Draw.")
        else:
            print(f"{winner} wins.")
        return True
    return False

def game():
    s0 = create_initial_state([[],
      [],
      []
      ])

    while True:
        cmove = best_move(s0)
        s0[cmove[0]][cmove[1]] = "X"
        for row in s0:
            print(row)

        if check_win(s0):
            break

        while True:
            try:
                y = int(input("x value: "))
                x = int(input("y value: "))

                if s0[x][y] != "-":
                    print("Invalid move, choose an empty slot.")
                    continue

                s0[x][y] = "O"
                break
            except:
                print("Please choose x and y values between 0-2 (incl).")
                continue

        if check_win(s0):
            break
        for _ in range(2):
            print()

if __name__ == "__main__":
    game()
    print("Game Over.")