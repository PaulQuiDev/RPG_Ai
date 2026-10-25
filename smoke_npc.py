"""Smoke test headless du système de NPC (personnages de carte).

Vérifie, sans boucle de jeu, sans fenêtre :
    1. Création des NPC dans le village (5 : 3 statiques, 2 en patrouille).
    2. Positions praticables + blocage de la collision (can_stand_at).
    3. Statiques immobiles, patrouille qui bouge.
    4. Le joueur ne traverse pas un NPC.
    5. Interaction au contact + cooldown + message par défaut.
    6. Action custom (action : go_forest) change la carte.
    7. Rendu (draw + draw_top) sans erreur (avec/ sans collisions).

    Lancer :  cd RPG_Ai && .venv/bin/python smoke_npc.py
"""

import os

if "DISPLAY" not in os.environ:
    os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame

import sys

sys.path.insert(0, "/home/paul/Bureau/RPG_Ai")

from settings import CHARACTERS, MAPS, NPC_CONTACT_RADIUS
from world import World
from player import Player
from npc import Npc


def empty_keys():
    return {
        pygame.K_UP: False,
        pygame.K_DOWN: False,
        pygame.K_LEFT: False,
        pygame.K_RIGHT: False,
    }


def wait_cooldown(gm, npc, dt, player, max_frames=1800):
    """Attend que l'interaction du NPC soit à nouveau possible."""
    frames = 0
    while not npc.can_interact() and frames < max_frames:
        gm.update_npcs(dt, player)
        frames += 1
    return npc.can_interact()


def main():
    pygame.init()
    screen = pygame.display.set_mode((960, 720))
    dt = 1.0 / 60.0

    # --- 1. Création des NPC du village ---
    world = World(MAPS)
    gm = world.game_map
    assert len(gm.npcs) == 5, [n.name for n in gm.npcs]
    static = [n for n in gm.npcs if n.behavior == "static"]
    patrol = [n for n in gm.npcs if n.behavior == "patrol"]
    assert len(static) == 3, [n.name for n in static]
    assert len(patrol) == 2, [n.name for n in patrol]
    print("1/ OK : 5 NPC (3 statiques, 2 patrouille)")

    # --- 2. Positions praticables + blocage collision ---
    for npc in gm.npcs:
        assert gm.can_stand_at(
            npc.x, npc.y, npc.collision_radius, ignore=npc
        ), f"{npc.name} : point non praticable"
        # Sans ignore : un autre "joueur" ne peut pas s'y positionner.
        assert not gm.can_stand_at(
            npc.x, npc.y, npc.collision_radius
        ), f"{npc.name} : collision inactif"
    print("2/ OK : positions praticables, collision bloquante")

    # --- 3. Statiques immobiles, patrouille qui bouge ---
    start = {(n.name, (round(n.x), round(n.y))) for n in static}
    p0 = patrol[0]
    pos0 = (round(p0.x), round(p0.y))
    for _ in range(3000):
        gm.update_npcs(dt, None)
    for n in static:
        assert (n.name, (round(n.x), round(n.y))) in start, n.name
    assert (round(p0.x), round(p0.y)) != pos0, p0.name
    print("3/ OK : statiques immobiles, patrouille en mouvement")

    # --- 4. Le joueur ne traverse pas un NPC ---
    npc = static[0]
    start_y = 380.0
    player = Player(npc.x, start_y, CHARACTERS[0])
    keys = {
        pygame.K_UP: False,
        pygame.K_DOWN: True,
        pygame.K_LEFT: False,
        pygame.K_RIGHT: False,
    }
    for _ in range(800):
        player.update(dt, keys, gm, True)
    # Le joueur a bien essayé de descendre (il est plus bas qu'au départ).
    assert player.y > start_y + 5.0, (
        f"Le joueur n'a pas bougé (départ {start_y} -> "
        f"{player.y}) : point de départ non praticable ?"
    )
    # Mais il est resté loin du centre du NPC (collision).
    dist_y = abs(player.y - npc.y)
    min_dist = npc.collision_radius + player.collision_radius - 0.5
    assert dist_y >= min_dist, (
        f"Joueur trop proche de {npc.name} : {dist_y:.1f} < {min_dist:.1f}"
    )
    print("4/ OK : joueur bloqué par NPC, dy = %.1f" % dist_y)

    # --- 5. Interaction au contact + cooldown + message par défaut ---
    player = Player(npc.x, npc.y - NPC_CONTACT_RADIUS * 0.5, CHARACTERS[0])
    assert npc.in_contact(player)
    assert npc.can_interact()
    changed = npc.interact(player, world, gm)
    assert not changed, "action custom inattendue"
    assert npc.interact_cooldown > 0
    assert not npc.can_interact()
    print("5a/ OK : interaction + cooldown déclenchée")
    assert wait_cooldown(gm, npc, dt, player), "timeout cooldown"
    print("5b/ OK : cooldown écoulé via update_npcs")

    # --- 6. Action custom change la carte ---
    test_npc = Npc(
        {
            "name": "Test",
            "sprite": gm.npcs[0].sprite_path,
            "pos": [400, 430],
            "action": "go_forest",
            "message": "Test",
        },
        99,
    )
    assert world.current_map_data["name"] == "Village"
    changed = test_npc.interact(player, world, gm)
    assert changed, "go_forest n'a pas changé la carte"
    assert world.current_map_data["name"] == "Forêt", world.current_map_data["name"]
    print("6/ OK : action go_forest ->", world.current_map_data["name"])

    # --- 7. Rendu sans erreur (avec + sans collision) ---
    world2 = World(MAPS)
    g2 = world2.game_map
    p2x, p2y = world2.find_spawn(g2)
    p2 = Player(p2x, p2y, CHARACTERS[0])
    for collisions in (True, False):
        for i in range(120):
            g2.update_npcs(dt, p2)
            p2.update(dt, empty_keys(), g2, collisions)
            g2.draw(screen, p2, collisions)
            p2.draw(screen, g2)
            g2.draw_top(screen, p2, i * 16, collisions)
    print("7/ OK : rendu sans erreur")

    print("SMOKE NPC : OK")


if __name__ == "__main__":
    main()
