
import pygame

from settings import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_BACKGROUND,
    WINDOW_TITLE,
    COLLISIONS_ENABLED_DEFAULT,
)
from game_map import GameMap
from player import Player


def main():
    pygame.init()

    screen = pygame.display.set_mode(
        (WINDOW_WIDTH, WINDOW_HEIGHT)
    )
    pygame.display.set_caption(WINDOW_TITLE)

    clock = pygame.time.Clock()
    font = pygame.font.SysFont("sans", 18)

    try:
        game_map = GameMap()
        player = Player(
            WINDOW_WIDTH / 2,
            WINDOW_HEIGHT / 2,
        )
    except (RuntimeError, ValueError) as error:
        pygame.quit()
        raise SystemExit(str(error))

    collisions_enabled = COLLISIONS_ENABLED_DEFAULT
    running = True

    while running:
        dt = min(clock.tick(60) / 1000.0, 0.05)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                elif event.key == pygame.K_e:
                    collisions_enabled = not collisions_enabled

        keys = pygame.key.get_pressed()

        player.update(
            dt,
            keys,
            game_map,
            collisions_enabled,
        )

        # Dessin de la carte puis du personnage.
        game_map.draw(screen)
        player.draw(screen)

        # Informations affichées à l'écran.
        status = "Marche" if player.moving else "À l'arrêt"
        collision_status = (
            "ACTIVÉES" if collisions_enabled else "DÉSACTIVÉES"
        )

        info = [
            f"Direction : {player.direction} | État : {status}",
            "Flèches : déplacer le personnage",
            "E : activer/désactiver les collisions",
            f"Collisions : {collision_status}",
            "Échap : quitter",
        ]

        for i, line in enumerate(info):
            label = font.render(
                line, True, (255, 255, 255)
            )

            label_bg = pygame.Surface(
                (label.get_width() + 12, label.get_height() + 8),
                pygame.SRCALPHA,
            )
            label_bg.fill((0, 0, 0, 150))

            screen.blit(label_bg, (8, 8 + i * 30))
            screen.blit(label, (14, 12 + i * 30))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
