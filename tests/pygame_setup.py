"""Helpers pygame pour la suite de tests.

- une fenêtre dummy unique (pas de fenêtre visible),
- sheets de personnages 4x3 synthétiques (contenus colorés),
- tableau de touches vide.
"""
import os

import pygame

from settings import COLS, ROWS


_screen = None


def init_display(width=960, height=720):
    """Initialise pygame + une fenêtre unique (dummy). Idempotent."""
    global _screen
    if _screen is None:
        if not pygame.display.get_init():
            pygame.init()
        _screen = pygame.display.set_mode((width, height))
    return _screen


def make_sheet(width=600, height=1200):
    """Sheet 4x3 synthétique (3 frames par direction).

    600x1200 => cellules 200x300 (CELL_W x CELL_H de settings),
    cohérent avec CROP_SIZE/CROP_OFFSETS (découpes dans la cellule).
    Chaque cellule reçoit une couleur distincte (tests de contenu).
    """
    surf = pygame.Surface((width, height))
    cell_w = width // COLS
    cell_h = height // ROWS
    for col in range(COLS):
        for row in range(ROWS):
            x0 = col * cell_w
            y0 = row * cell_h
            color = (255, (col * 64) % 256, (row * 128) % 256)
            pygame.draw.rect(surf, color, (x0, y0, cell_w, cell_h))
    return surf


def write_sheet(tmp_dir, surf, name="sheet.png"):
    """Écrit une surface PNG dans tmp_dir ; retourne le chemin."""
    path = os.path.join(tmp_dir, name)
    pygame.image.save(surf, path)
    return path


def empty_keys():
    """Touches toutes à False (aucun mouvement)."""
    return {
        pygame.K_LEFT: False,
        pygame.K_RIGHT: False,
        pygame.K_UP: False,
        pygame.K_DOWN: False,
    }
