
import pygame

from settings import WINDOW_WIDTH, WINDOW_HEIGHT


class GameMap:
    def __init__(self, background_path, mask_path):
        try:
            original = pygame.image.load(
                str(background_path)
            ).convert()

            mask_original = pygame.image.load(
                str(mask_path)
            ).convert()

        except (pygame.error, FileNotFoundError) as error:
            raise RuntimeError(
                f"Impossible de charger la carte : {error}"
            ) from error

        if original.get_size() != mask_original.get_size():
            raise ValueError(
                "Le masque doit avoir la même taille que le fond."
            )

        self.background = pygame.transform.smoothscale(
            original, (WINDOW_WIDTH, WINDOW_HEIGHT)
        )

        self.collision_mask = pygame.transform.scale(
            mask_original, (WINDOW_WIDTH, WINDOW_HEIGHT)
        )

        self.width = WINDOW_WIDTH
        self.height = WINDOW_HEIGHT

    def draw(self, screen):
        screen.blit(self.background, (0, 0))

    def is_walkable(self, x, y):
        x = int(x)
        y = int(y)

        if not (0 <= x < self.width and 0 <= y < self.height):
            return False

        color = self.collision_mask.get_at((x, y))

        # Vert = zone praticable
        return color.g > color.r and color.g > color.b

        
    def can_stand_at(self, x, y, radius=5):
        """Vérifie que le personnage reste dans une zone praticable."""
        points = [
            (x - radius, y - radius),
            (x + radius, y - radius),
            (x - radius, y + radius),
            (x + radius, y + radius),
        ]

        return all(
            self.is_walkable(px, py)
            for px, py in points
        )

