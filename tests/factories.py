"""Usines de données de test (fake).

Couleurs du masque :
    VERT (0,255,0) = praticable
    ROUGE (255,0,0) = bloqué
    BLEU (0,0,255)  = objet interactif (extrait par _extract_interactables)
                      ET non praticable

Les cartes fausses utilisent un masque synthétique : tests de LOGIQUE
rapides et isolés, sans dépendre des assets réels.
"""
import os

import pygame

from settings import WINDOW_WIDTH, WINDOW_HEIGHT
from game_map import GameMap
from world import World


def make_fake_background(color=(100, 150, 200)):
    surf = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
    surf.fill(color)
    return surf


def make_fake_mask(blocked=(), blue=()):
    surf = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
    surf.fill((0, 255, 0))  # vert = praticable
    for r in blocked:
        pygame.draw.rect(surf, (255, 0, 0), r)  # rouge = bloqué
    for r in blue:
        pygame.draw.rect(surf, (0, 0, 255), r)  # bleu = interactif
    return surf


def _write(surf, tmp_dir, name):
    path = os.path.join(tmp_dir, name)
    pygame.image.save(surf, path)
    return path


def build_fake_map(tmp_dir, blocked=(), blue=(), npcs=None,
                  interactions=None):
    """Une GameMap sur un masque synthétique (vite, isolée)."""
    bg = _write(make_fake_background(), tmp_dir, "bg.png")
    mask = _write(make_fake_mask(blocked, blue), tmp_dir, "mask.png")
    return GameMap(bg, mask, None, None, interactions or [], npcs or [])


def build_fake_world(tmp_dir, maps):
    """Un World à partir d'une liste de dicts pointant sur des PNG."""
    return World(maps)



def build_fake_two_worlds(tmp_dir, name_a="Map A", name_b="Map B",
                          blocked_a=(), blue_a=(), blocked_b=(), blue_b=()):
    """Deux cartes A <-> B reliées (exits right/left)."""
    a_bg = _write(make_fake_background(), tmp_dir, "bg_a.png")
    a_mask = _write(make_fake_mask(blocked_a, blue_a), tmp_dir, "mask_a.png")
    b_bg = _write(make_fake_background((80, 140, 210)), tmp_dir, "bg_b.png")
    b_mask = _write(make_fake_mask(blocked_b, blue_b), tmp_dir, "mask_b.png")
    return build_fake_world(tmp_dir, [
        {
            "name": name_a,
            "background": a_bg,
            "mask": a_mask,
            "exits": {"right": {"map": name_b, "spawn": [800, 360]}},
        },
        {
            "name": name_b,
            "background": b_bg,
            "mask": b_mask,
            "exits": {"left": {"map": name_a, "spawn": [100, 360]}},
        },
    ])


def write_fake_fg(tmp_dir, blobs=()):
    """Couche de premier plan (SRCALPHA) avec des blobs RGBA.

    blobs : liste de (x, y, w, h, rgba).
    """
    surf = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    for x, y, w, h, rgba in blobs:
        b = pygame.Surface((w, h), pygame.SRCALPHA)
        b.fill(rgba)
        surf.blit(b, (x, y))
    return _write(surf, tmp_dir, "fg.png")


def build_fake_one_world(tmp_dir, blocked=(), blue=(), name="Map A",
                         fg=False, fg_blobs=()):
    """Une carte (optionnel : couche de premier plan)."""
    bg = _write(make_fake_background(), tmp_dir, "bg_a.png")
    mask = _write(make_fake_mask(blocked, blue), tmp_dir, "mask_a.png")
    m = {"name": name, "background": bg, "mask": mask}
    if fg:
        m["foreground"] = write_fake_fg(tmp_dir, fg_blobs)
    return build_fake_world(tmp_dir, [m])


def fake_npc_data(tmp_dir, sheet_path, name="NPC", behavior="static",
                  pos=(400, 360), **kwargs):
    """Dict de NPC prêt à être passé à Npc()/GameMap(npcs=[...])."""
    data = {
        "name": name,
        "sprite": sheet_path,
        "behavior": behavior,
        "pos": [pos[0], pos[1]],
    }
    data.update(kwargs)
    return data


def fake_player_data(tmp_dir, sheet_path, name="Joueur",
                     speed=220, scale=0.25, collision_radius=5):
    """Dict de personnage (format settings.CHARACTERS)."""
    return {
        "name": name,
        "sprite": sheet_path,
        "speed": speed,
        "scale": scale,
        "collision_radius": collision_radius,
    }
