
import pygame

from settings import (
    BACKGROUND_PATH,
    MASK_PATH,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
)


class GameMap:
    def __init__(self):
        try:
            original = pygame.image.load(
                str(BACKGROUND_PATH)
            ).convert()

            mask_original = pygame.image.load(
                str(MASK_PATH)
            ).convert()

        except (pygame.error, FileNotFoundError) as error:
            raise RuntimeError(
                f"Impossible de charger le fond ou le masque : {error}"
            ) from error

        if original.get_size() != mask_original.get_size():
            raise ValueError(
                "Le masque de collision doit avoir "
                "la même taille que l'image de fond."
            )

        self.background = pygame.transform.smoothscale(
            original, (WINDOW_WIDTH, WINDOW_HEIGHT)
        )

        # scale, plutôt que smoothscale, évite de mélanger
        # les couleurs rouge et verte du masque.
        self.collision_mask = pygame.transform.scale(
            mask_original, (WINDOW_WIDTH, WINDOW_HEIGHT)
        )

    def draw(self, screen):
        screen.blit(self.background, (0, 0))

    def is_walkable(self, x, y):
        x, y = int(x), int(y)

        if not (0 <= x < WINDOW_WIDTH and 0 <= y < WINDOW_HEIGHT):
            return False

        red, green, blue, *_ = self.collision_mask.get_at((x, y))

        # Vert dominant = accessible.
        return green > red and green > blue

    def can_stand_at(self, x, y, radius):
        # Vérifie plusieurs points autour des pieds.
        points = [
            (x, y),
            (x - radius, y),
            (x + radius, y),
            (x, y - radius),
            (x - radius, y - radius),
            (x + radius, y - radius),
        ]

        return all(
            self.is_walkable(px, py)
            for px, py in points
        )
