
import pygame

from settings import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    COLLISIONS_ENABLED_DEFAULT,
    COLLISION_RADIUS,
    CHARACTERS,
    MAPS,
)
from game_map import GameMap
from player import Player


def find_spawn(game_map):
    """Cherche une position de départ accessible sur la carte."""
    center_x = WINDOW_WIDTH // 2
    center_y = WINDOW_HEIGHT // 2

    if game_map.can_stand_at(center_x, center_y, COLLISION_RADIUS):
        return center_x, center_y

    # Recherche progressive d'une zone verte.
    for radius in range(20, max(WINDOW_WIDTH, WINDOW_HEIGHT), 20):
        for x in range(0, WINDOW_WIDTH, 10):
            for y in (
                center_y - radius,
                center_y + radius,
            ):
                if (
                    0 <= y < WINDOW_HEIGHT
                    and game_map.can_stand_at(
                        x, y, COLLISION_RADIUS
                    )
                ):
                    return x, y

        for y in range(0, WINDOW_HEIGHT, 10):
            for x in (
                center_x - radius,
                center_x + radius,
            ):
                if (
                    0 <= x < WINDOW_WIDTH
                    and game_map.can_stand_at(
                        x, y, COLLISION_RADIUS
                    )
                ):
                    return x, y

    raise RuntimeError(
        "Aucune position de départ accessible trouvée sur cette carte."
    )


def check_map_transition(player, current_map_data, map_index):
    """Change de carte lorsque le joueur atteint une sortie."""

    margin = 8
    x = player.x
    y = player.y

    side = None

    # Sortie par le bord droit
    if x >= WINDOW_WIDTH - margin:
        side = "right"

    # Sortie par le bord gauche
    elif x <= margin:
        side = "left"

    # Sortie par le bord supérieur
    elif y <= margin:
        side = "top"

    # Sortie par le bord inférieur
    elif y >= WINDOW_HEIGHT - margin:
        side = "bottom"

    if side is None:
        return map_index, None

    exits = current_map_data.get("exits", {})
    exit_data = exits.get(side)

    if exit_data is None:
        # Pas de connexion : le joueur reste sur la carte actuelle.
        player.x = max(10, min(WINDOW_WIDTH - 10, player.x))
        player.y = max(10, min(WINDOW_HEIGHT - 10, player.y))
        return map_index, None

    destination_name = exit_data["map"]

    # Cherche la carte de destination par son nom.
    destination_index = next(
        (
            i for i, data in enumerate(MAPS)
            if data["name"] == destination_name
        ),
        None,
    )

    if destination_index is None:
        print(f"Carte de destination introuvable : {destination_name}")
        return map_index, None

    destination_data = MAPS[destination_index]

    try:
        new_map = GameMap(
            destination_data["background"],
            destination_data["mask"],
            destination_data.get("perspective"),
        )
    except (RuntimeError, ValueError, KeyError) as error:
        print(f"Impossible de charger la carte : {error}")
        return map_index, None

    spawn_x, spawn_y = exit_data["spawn"]

    # Vérifie que le point d'arrivée est praticable.
    radius = getattr(player, "collision_radius", 5)
    if not new_map.can_stand_at(spawn_x, spawn_y, radius):
        print(
            f"Point d'arrivée bloqué sur {destination_name} : "
            f"{spawn_x}, {spawn_y}"
        )
        return map_index, None

    player.x = float(spawn_x)
    player.y = float(spawn_y)

    print(
        f"Transition : {current_map_data['name']} "
        f"-> {destination_name} ({side})"
    )

    return destination_index, new_map


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
    map_index = 0
    collisions_enabled = COLLISIONS_ENABLED_DEFAULT

    try:
        current_map_data = MAPS[map_index]
        game_map = GameMap(
            current_map_data["background"],
            current_map_data["mask"],
            current_map_data.get("perspective"),
        )

        spawn_x, spawn_y = find_spawn(game_map)

        character_data = CHARACTERS[character_index]
        player = Player(
            spawn_x,
            spawn_y,
            character_data,
        )

    except (RuntimeError, ValueError, KeyError) as error:
        pygame.quit()
        raise SystemExit(str(error))

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

                elif event.key == pygame.K_p:
                    # Personnage suivant
                    character_index = (
                        character_index + 1
                    ) % len(CHARACTERS)

                    character_data = CHARACTERS[character_index]

                    try:
                        player = Player(
                            player.x,
                            player.y,
                            character_data,
                        )
                    except (RuntimeError, ValueError) as error:
                        print(f"Changement de personnage impossible : {error}")

                elif event.key == pygame.K_m:
                    # Carte suivante
                    next_index = (map_index + 1) % len(MAPS)
                    map_data = MAPS[next_index]

                    try:
                        new_map = GameMap(
                            map_data["background"],
                            map_data["mask"],
                            map_data.get("perspective"),
                        )

                        new_x, new_y = find_spawn(new_map)

                        game_map = new_map
                        map_index = next_index
                        player.x = float(new_x)
                        player.y = float(new_y)
                        

                        print(f"Carte chargée : {map_data['name']}")

                    except (RuntimeError, ValueError, KeyError) as error:
                        print(f"Changement de carte impossible : {error}")

        keys = pygame.key.get_pressed()

        player.update(
            dt,
            keys,
            game_map,
            collisions_enabled,
        )
        current_map_data = MAPS[map_index]

        new_map_index, new_map = check_map_transition(
            player,
            current_map_data,
            map_index,
        )

        if new_map is not None:
            map_index = new_map_index
            game_map = new_map

        game_map.draw(screen)
        player.draw(screen, game_map)

        character_name = CHARACTERS[character_index]["name"]
        map_name = MAPS[map_index]["name"]

        info = [
            f"Personnage : {character_name} (P pour changer)",
            f"Carte : {map_name} (M pour changer)",
            "Flèches : déplacer | E : collisions",
            f"Collisions : {'ACTIVÉES' if collisions_enabled else 'DÉSACTIVÉES'}",
            "Échap : quitter",
        ]

        for i, line in enumerate(info):
            label = font.render(line, True, (255, 255, 255))

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
