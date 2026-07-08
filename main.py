import pygame

class Display:
    def __init__(self, width, height, fps):
        self.width = width
        self.height = height
        self.fps = fps
        
        self.running = True

    def draw(self):
        pygame.init()

        win = pygame.display.set_mode((self.width, self.height))
        clock = pygame.time.Clock()
        self.increasing = True

        while self.running:

            change = self.get_change()
            print(change)
            self.change_size(change[0], change[1])
            win = pygame.display.set_mode((self.width, self.height))

            clock.tick(self.fps)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

            pygame.display.flip()
        pygame.quit()

    def change_size(self, dx, dy):
        self.width += dx
        self.height += dy

    def get_change(self):
        dx, dy = 0, 0

        if self.increasing:
            if self.width >= 500 or self.height >= 500:
                self.increasing = False

            else:
                dx, dy = 5, 5

        else:
            if self.width <= 50 or self.height <= 50:
                self.increasing = True
            
            else:
                dx, dy = -5, -5

        return dx, dy

if __name__ == "__main__":
    display = Display(400, 400, 60)
    display.draw()