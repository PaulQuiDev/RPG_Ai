"""Point d'entrée du jeu : initialisation pygame, création de `Game`,
boucle (clock → événements → update → render). Toute la logique de jeu
vit dans `game.Game`."""

import pygame

from settings import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    COLLISIONS_ENABLED_DEFAULT,
    CHARACTERS,
    MAPS,
)
from game import Game


def main():
    if not CHARACTERS:
        raise SystemExit("Aucun personnage défini dans settings.py.")
    if not MAPS:
        raise SystemExit("Aucune carte définie dans settings.py.")

    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption(WINDOW_TITLE)
    font = pygame.font.SysFont("sans", 18)

    try:
        game = Game(
            screen,
            font,
            CHARACTERS,
            MAPS,
            collisions_enabled=COLLISIONS_ENABLED_DEFAULT,
        )
    except (RuntimeError, ValueError, KeyError) as error:
        pygame.quit()
        raise SystemExit(str(error)) from error

    clock = pygame.time.Clock()
    while not game.should_quit:
        dt = min(clock.tick(60) / 1000.0, 0.05)
        game.handle_events()
        game.update(dt)
        game.render()

    pygame.quit()


if __name__ == "__main__":
    main()
