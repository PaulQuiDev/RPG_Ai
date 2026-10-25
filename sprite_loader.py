"""Découpe générique des sheets de personnages 4x3 (RGB).

Une seule source de vérité, partagée par Player (player.py) et Npc (npc.py)
pour le découpage des frames, les découpes personnalisées (offsets/tailles)
et le blit vers les surfaces de sortie transparentes.
"""

import pygame

from settings import (
    COLS,
    CROP_OFFSETS,
    CROP_SIZE,
    DIRECTIONS,
    ROWS,
)


def slice_sprite_sheet(sheet, sheet_w, sheet_h):
    """Découpe une sheet 4x3 en frames par direction.

    Renvoie {direction: [frame_0, frame_1, frame_2]} selon le format
    DIRECTIONS (face/gauche/droite/dos) et la grille ROWS x COLS.

    Identique au découpage historique de Player, mais fonction module
    réutilisable par tout personnage (joueur ou NPC).
    """
    sprites = {}

    for direction, row in DIRECTIONS.items():
        sprites[direction] = []

        for col in range(COLS):
            # Limites de la cellule d'origine.
            x0 = col * sheet_w // COLS
            x1 = (col + 1) * sheet_w // COLS
            y0 = row * sheet_h // ROWS
            y1 = (row + 1) * sheet_h // ROWS

            cell_w = x1 - x0
            cell_h = y1 - y0

            # Taille spécifique de la découpe.
            custom_size = CROP_SIZE[direction].get(col)

            if custom_size is None:
                crop_w, crop_h = cell_w, cell_h
            else:
                crop_w, crop_h = custom_size

            # Centre de la cellule comme référence.
            center_x = (x0 + x1) // 2
            center_y = (y0 + y1) // 2

            # Position initiale du rectangle centré.
            crop_x = center_x - crop_w // 2
            crop_y = center_y - crop_h // 2

            # Ajouter les offsets personnalisés.
            dx, dy = CROP_OFFSETS[direction].get(col, (0, 0))
            crop_x += dx
            crop_y += dy

            # Surface de sortie transparente.
            frame = pygame.Surface(
                (crop_w, crop_h),
                pygame.SRCALPHA,
            )

            # Intersection entre la découpe et l'image source.
            # Aucune limitation des offsets eux-mêmes.
            src_left = max(0, crop_x)
            src_top = max(0, crop_y)
            src_right = min(sheet_w, crop_x + crop_w)
            src_bottom = min(sheet_h, crop_y + crop_h)

            if src_right > src_left and src_bottom > src_top:
                source_rect = pygame.Rect(
                    src_left,
                    src_top,
                    src_right - src_left,
                    src_bottom - src_top,
                )
                target_rect = pygame.Rect(
                    src_left - crop_x,
                    src_top - crop_y,
                    source_rect.width,
                    source_rect.height,
                )
                frame.blit(sheet, target_rect, source_rect)

            sprites[direction].append(frame)

    return sprites
