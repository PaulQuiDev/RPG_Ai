"""Découpe générique des sheets de personnages (RGB).

Une seule source de vérité, partagée par Player (player.py) et Npc (npc.py)
pour le découpage des frames, les découpes personnalisées (offsets/tailles)
et le blit vers les surfaces de sortie transparentes.

Config de découpe par personnage (data-driven)
----------------------------------------------

Chaque personnage (un dict de `CHARACTERS` dans settings.py, ou un dict
« npc » dans la liste `npcs` d'une carte) peut fournir des clés optionnelles
de la même forme que les defaults globaux :

    "crop_size"      : {direction: {col: (w, h)}}
    "crop_offsets"   : {direction: {col: (dx, dy)}}
    "anchor_offsets" : {direction: (dx, dy)}

Chaque champ absent garde le défaut global (`CROP_SIZE` / `CROP_OFFSETS` /
`ANCHOR_OFFSETS`). L'ajout d'un personnage ne demande donc qu'une ligne
(nom + sprite, + éventuellement ces overrides) — aucune retouche du code
de découpe.
"""

import pygame

from settings import (
    COLS,
    ROWS,
    DIRECTIONS,
    CROP_SIZE,
    CROP_OFFSETS,
    ANCHOR_OFFSETS,
)


def resolve_crop_config(character_data):
    """Renvoie la config de découpe résolue pour un personnage.

    Priorité : override par personnage > défaut global (settings).

    Renvoie un 3-tuple :
        crop_size     : {direction: {col: (w, h) | None}}
        crop_offsets  : {direction: {col: (dx, dy) | None}}
        anchor_offsets: {direction: (dx, dy)}

    Une valeur `None` dans `crop_size`/`crop_offsets` signale « pas de
    valeur » : le découpeur retombe alors sur la taille réelle de la
    cellule (le sheet est plus petit, ou le champ est volontairement
    absent).
    """
    per_char_size = character_data.get("crop_size", {})
    per_char_offsets = character_data.get("crop_offsets", {})
    per_char_anchor = character_data.get("anchor_offsets", {})

    crop_size = {}
    for direction in DIRECTIONS:
        per_direction = per_char_size.get(direction, {})
        crop_size[direction] = {
            col: per_direction.get(col, CROP_SIZE[direction].get(col))
            for col in range(COLS)
        }
    crop_offsets = {}
    for direction in DIRECTIONS:
        per_direction = per_char_offsets.get(direction, {})
        crop_offsets[direction] = {
            col: per_direction.get(col, CROP_OFFSETS[direction].get(col))
            for col in range(COLS)
        }
    anchor_offsets = {
        direction: per_char_anchor.get(direction, ANCHOR_OFFSETS[direction])
        for direction in DIRECTIONS
    }
    return crop_size, crop_offsets, anchor_offsets


def slice_sprite_sheet(sheet, sheet_w, sheet_h, crop_size=None,
                       crop_offsets=None):
    """Découpe une sheet (grille ROWS x COLS) en frames par direction.

    Renvoie `{direction: [frame_0, frame_1, frame_2]}` selon le format
    `DIRECTIONS` et la grille `ROWS x COLS`.

    Identique au découpage historique de Player, mais fonction module
    réutilisable par tout personnage (joueur ou NPC).

    crop_size / crop_offsets :
        Config résolues pour un personnage (voir `resolve_crop_config`),
        ou `None` pour utiliser les defaults globaux (`CROP_SIZE` /
        `CROP_OFFSETS`). Rétrocompatible : les appels sans args ne
        changent rien.
    """
    if crop_size is None:
        crop_size = CROP_SIZE
    if crop_offsets is None:
        crop_offsets = CROP_OFFSETS

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
            custom_size = crop_size[direction].get(col)

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
            dx, dy = crop_offsets[direction].get(col, (0, 0))
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
