
import pygame

from settings import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    COLLISIONS_ENABLED_DEFAULT,
    CHARACTERS,
    MAPS,
)
from player import Player
from world import World




def main():
    if not CHARACTERS:
        raise SystemExit("Aucun personnage défini dans settings.py.")

    if not MAPS:
        raise SystemExit("Aucune carte définie dans settings.py.")

    pygame.init()

    screen = pygame.display.set_mode(
        (WINDOW_WIDTH, WINDOW_HEIGHT)
    )
    pygame.display.set_caption(WINDOW_TITLE)

    clock = pygame.time.Clock()
    font = pygame.font.SysFont("sans", 18)

    character_index = 0
    collisions_enabled = COLLISIONS_ENABLED_DEFAULT

    try:
        # Le monde gère les cartes et leurs connexions.
        world = World(MAPS)
        game_map = world.game_map

        spawn_x, spawn_y = world.find_spawn(game_map)

        player = Player(
            spawn_x,
            spawn_y,
            CHARACTERS[character_index],
        )

    except (RuntimeError, ValueError, KeyError) as error:
        pygame.quit()
        raise SystemExit(str(error))

    running = True

    while running:
        dt = min(clock.tick(60) / 1000.0, 0.05)

        # 1. Gestion des événements
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                elif event.key == pygame.K_e:
                    collisions_enabled = not collisions_enabled

                elif event.key == pygame.K_p:
                    # Changer de personnage en conservant sa position.
                    next_index = (
                        (character_index + 1) % len(CHARACTERS)
                    )
                    character_data = CHARACTERS[next_index]

                    try:
                        new_player = Player(
                            player.x,
                            player.y,
                            character_data,
                        )
                        player = new_player
                        character_index = next_index

                    except (RuntimeError, ValueError) as error:
                        print(
                            "Changement de personnage impossible : "
                            f"{error}"
                        )

                elif event.key == pygame.K_m:
                    # Le monde gère lui-même le changement de carte.
                    world.next_map(player)

        # 2. Mise à jour du jeu
        keys = pygame.key.get_pressed()

        game_map = world.game_map

        player.update(
            dt,
            keys,
            game_map,
            collisions_enabled,
        )

        world.check_transition(player)

        # Récupérer la carte après une éventuelle transition.
        game_map = world.game_map

        # 3. Affichage du monde et du personnage
        game_map.draw(screen, player, pygame.time.get_ticks())
        player.draw(screen, game_map)

        # 4. Affichage des informations
        character_name = CHARACTERS[character_index]["name"]
        map_name = world.current_map_data["name"]

        info = [
            f"Personnage : {character_name} (P pour changer)",
            f"Carte : {map_name} (M pour changer)",
            "Flèches : déplacer | E : collisions",
            (
                "Collisions : "
                f"{'ACTIVÉES' if collisions_enabled else 'DÉSACTIVÉES'}"
            ),
"Objets bleus : interactifs (s'approche : mise en avant)",
            "Échap : quitter",
        ]

        for i, line in enumerate(info):
            label = font.render(
                line,
                True,
                (255, 255, 255),
            )

            label_bg = pygame.Surface(
                (
                    label.get_width() + 12,
                    label.get_height() + 8,
                ),
                pygame.SRCALPHA,
            )
            label_bg.fill((0, 0, 0, 150))

            screen.blit(label_bg, (8, 8 + i * 30))
            screen.blit(label, (14, 12 + i * 30))

        pygame.display.flip()

    pygame.quit()



if __name__ == "__main__":
    main()
