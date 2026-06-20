import pygame

class Display:
    def __init__(self, width, height, fps):
        self.width = width
        self.height = height
        
        self.running = True

    def draw(self):
        pygame.init()

        win = pygame.display.set_mode(self.width, self.height)
        clock = pygame.time.Clock()

        while self.running:
            clock.tick(self.fps)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

            pygame.display.flip()
        pygame.quit()

if __name__ == "__main__":
    display = Display(500, 500, 60)
    Display.draw()