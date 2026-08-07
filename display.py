import pygame
from os.path import join
from engine import State

class Display:
    def __init__(self, width, height, fps):
        self.width = width
        self.height = height
        self.fps = fps
        self.caption = "Aperture"
        self.block_size = 100
        
        self.running = True

    def draw(self):
        pygame.init()

        win = pygame.display.set_mode((self.width, self.height))
        clock = pygame.time.Clock()
        pygame.display.set_caption(self.caption)

        white_pieces = spritesheet("Chess_Pieces.png", 161, 155, 0)
        black_pieces = spritesheet("Chess_Pieces.png", 161, 155, 155)
        state = State()
    
        chess_pieces = {
            "wh": {
                "k": [None, (8, 0)],
                "q": [None, (2, 0)],
                "b": [None, (0, 0)],
                "n": [None, (-5, 0)],
                "r": [None, (-13, 0)],
                "p": [None, (-20, 0)],
            },
            "bl": {
                "k": [None, (8, 0)],
                "q": [None, (2, 0)],
                "b": [None, (0, 0)],
                "n": [None, (-5, 0)],
                "r": [None, (-13, 0)],
                "p": [None, (-20, 0)],
            },
        }
    
        pieces_order = ["k", "q", "b", "n", "r", "p"]
        for i, piece in enumerate(pieces_order):
            chess_pieces["wh"][piece][0] = white_pieces["Chess_Pieces"][i]
            chess_pieces["bl"][piece][0] = black_pieces["Chess_Pieces"][i]
    

        while self.running:
            clock.tick(self.fps)

            self.draw_board(win, chess_pieces, state)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

            pygame.display.flip()
        pygame.quit()

    def draw_board(self, screen, chess_pieces, s):
        for x in range(0, self.width, self.block_size):
            for y in range(0, self.height, self.block_size):
                if (x//self.block_size-y//self.block_size) % 2 == 0:
                    pygame.draw.rect(screen, (125, 135, 150), pygame.Rect(x, y, self.block_size, self.block_size))
                else:
                    pygame.draw.rect(screen, (233, 236, 239), pygame.Rect(x, y, self.block_size, self.block_size))

        for colour in s.pieces:
            for ptype in s.pieces[colour]:
                bitboard = s.pieces[colour][ptype]
                x = 0
                y = 7

                for i in range(64):
                    mask = 1 << i
                    if bitboard & mask:
                        sprite, offset = chess_pieces[colour][ptype]
                        screen.blit(pygame.transform.scale(sprite.convert_alpha(), (self.block_size, self.block_size)), (x*self.block_size + offset[0], y*self.block_size + offset[1]))

                    x += 1
                    if x == 8:
                        x = 0
                        y -= 1

def flip(sprites):
    return [pygame.transform.flip(sprite, True, False) for sprite in sprites]

def spritesheet(filename, width, height, y, direction=False):
    path = join("images", "Chess_Pieces.png")

    all_sprites = {}

    sprite_sheet = pygame.image.load(path).convert_alpha()
    sprites = []
    for i in range(sprite_sheet.get_width() // width):
        surface = pygame.Surface((width, height), pygame.SRCALPHA, 32)
        rect = pygame.Rect(i * width, y, width, height)
        surface.blit(sprite_sheet, (0,0), rect)
        sprites.append(pygame.transform.scale2x(surface))
    if direction:
        all_sprites[filename.replace(".png", "") + "_right"] = sprites 
        all_sprites[filename.replace(".png", "") + "_left"] = flip(sprites)
    else:
        all_sprites[filename.replace(".png", "")] = sprites
    return all_sprites


if __name__ == "__main__":

    display = Display(800, 800, 60)
    display.draw()

# Drag/move plan:
# Display handles mouse input, square/mask conversion, dragging state, and drawing.
# Engine handles State, actions, result, legal move checks, and turn updates.
# Mouse down finds the clicked piece and starts dragging.
# Mouse up builds a source/destination mask action and asks the engine to apply it.
# Draw all pieces except the dragged source piece, then draw the dragged sprite at the mouse.
