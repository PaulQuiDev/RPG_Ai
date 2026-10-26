"""Tests de sprite_loader : slice_sprite_sheet (découpe 4x3) et
resolve_crop_config (découpe data-driven par personnage)."""

import unittest

from pygame import Color

from settings import (
    COLS,
    ROWS,
    DIRECTIONS,
    CROP_SIZE,
    CROP_OFFSETS,
    ANCHOR_OFFSETS,
)
from sprite_loader import resolve_crop_config, slice_sprite_sheet


def _pixels_equal(a, b):
    """Vrai si deux surfaces ont la même taille et exactement les mêmes pixels."""
    if a.get_size() != b.get_size():
        return False
    return all(
        a.get_at((x, y)) == b.get_at((x, y))
        for x in range(a.get_width())
        for y in range(a.get_height())
    )


def _make_fake_sheet(w=120, h=120, color=(0, 200, 0)):
    """Sheet 4x3, chaque cellule remplie d'une plaque colorée."""
    import pygame

    sheet = pygame.Surface((w, h))
    cell_w, cell_h = w // COLS, h // ROWS

    for row in range(ROWS):
        for col in range(COLS):
            pygame.draw.rect(
                sheet,
                Color(*color),
                (
                    col * cell_w,
                    row * cell_h,
                    cell_w,
                    cell_h,
                ),
            )

    # Bordures de cellule (1 px) pour vérifier les offsets.
    border = Color(255, 0, 0)
    for row in range(ROWS):
        for col in range(COLS):
            x0, y0 = col * cell_w, row * cell_h
            for bx in range(x0, x0 + cell_w):
                for by in (y0, y0 + cell_h - 1):
                    if 0 <= bx < w and 0 <= by < h:
                        sheet.set_at((bx, by), border)
            for by in range(y0, y0 + cell_h):
                for bx in (x0, x0 + cell_w - 1):
                    if 0 <= bx < w and 0 <= by < h:
                        sheet.set_at((bx, by), border)

    return sheet


def _pixel_sum(surface):
    """Somme des canaux R des pixels de `surface` (mesure de matière)."""
    w, h = surface.get_size()
    total = 0
    for y in range(h):
        for x in range(w):
            total += surface.get_at((x, y)).r
    return total


class TestResolveCropConfig(unittest.TestCase):
    """La config de découpe est data-driven (override par personnage)."""

    def test_sans_override_gardes_defauts(self):
        size, offsets, anchors = resolve_crop_config({})
        self.assertEqual(size, CROP_SIZE)
        self.assertEqual(offsets, CROP_OFFSETS)
        self.assertEqual(anchors, ANCHOR_OFFSETS)

    def test_override_crop_offsets_priority(self):
        size, offsets, anchors = resolve_crop_config(
            {"crop_offsets": {"face": {0: (999, 999)}}}
        )
        self.assertEqual(offsets["face"][0], (999, 999))
        self.assertEqual(offsets["face"][1], CROP_OFFSETS["face"][1])
        self.assertEqual(offsets["dos"][0], CROP_OFFSETS["dos"][0])
        self.assertEqual(size, CROP_SIZE)

    def test_override_crop_size_partiel(self):
        size, _, _ = resolve_crop_config(
            {"crop_size": {"gauche": {2: (33, 44)}}}
        )
        self.assertEqual(size["gauche"][2], (33, 44))
        self.assertEqual(size["gauche"][0], CROP_SIZE["gauche"][0])
        self.assertEqual(size["face"][0], CROP_SIZE["face"][0])

    def test_override_anchor(self):
        size, _, anchors = resolve_crop_config(
            {"anchor_offsets": {"droite": (10, 20)}}
        )
        self.assertEqual(anchors["droite"], (10, 20))
        self.assertEqual(anchors["face"], ANCHOR_OFFSETS["face"])
        self.assertEqual(size, CROP_SIZE)

    def test_dict_minimal_ne_cassent_pas(self):
        """Un dict de personnage minimal (comme fake_player_data) fonctionne."""
        data = {"name": "Test", "sprite": "x.png"}
        size, offsets, anchors = resolve_crop_config(data)
        self.assertEqual(size, CROP_SIZE)
        self.assertEqual(offsets, CROP_OFFSETS)
        self.assertEqual(anchors, ANCHOR_OFFSETS)


class TestSliceSpriteSheet(unittest.TestCase):
    """Découpe 4x3 avec ou sans overrides par personnage."""

    def setUp(self):
        self.sheet = _make_fake_sheet()
        self.w, self.h = 120, 120

    def test_shape(self):
        """Renvoie les 4 directions, 3 frames chacune, dimensions attendues."""
        result = slice_sprite_sheet(self.sheet, self.w, self.h)
        self.assertEqual(len(result), len(DIRECTIONS))
        for direction in DIRECTIONS:
            self.assertEqual(len(result[direction]), COLS)
            for i in range(COLS):
                expected = CROP_SIZE[direction].get(
                    i, (self.w // COLS, self.h // ROWS)
                )
                self.assertEqual(
                    result[direction][i].get_size(), expected
                )

    def test_matiere_presente(self):
        """Les frames contiennent de la matière (non transparente)."""
        result = slice_sprite_sheet(self.sheet, self.w, self.h)
        for direction in DIRECTIONS:
            for col in range(COLS):
                total = _pixel_sum(result[direction][col])
                self.assertGreater(
                    total, 0,
                    f"Frame vide : {direction}/{col}",
                )

    def test_custom_crop_size_change_size(self):
        """Un override de crop_size change la taille des frames."""
        crop_size = {
            d: {c: CROP_SIZE[d][c] for c in range(COLS)}
            for d in DIRECTIONS
        }
        crop_size["face"][0] = (30, 30)
        result = slice_sprite_sheet(self.sheet, self.w, self.h, crop_size)
        self.assertEqual(result["face"][0].get_size(), (30, 30))
        self.assertEqual(
            result["face"][1].get_size(), CROP_SIZE["face"][1]
        )
        self.assertEqual(
            result["dos"][2].get_size(), CROP_SIZE["dos"][2]
        )

    def test_custom_crop_offsets_shifts_pixels(self):
        """Un offset personnalisé décale la matière découpée."""
        result_default = slice_sprite_sheet(self.sheet, self.w, self.h)
        # Seul face[0] est décalé ; le reste conserve les défauts.
        crop_offsets = {
            d: {c: CROP_OFFSETS[d][c] for c in range(COLS)}
            for d in DIRECTIONS
        }
        crop_offsets["face"][0] = (50, 50)
        result_shifted = slice_sprite_sheet(
            self.sheet, self.w, self.h, crop_offsets=crop_offsets
        )
        self.assertFalse(
            _pixels_equal(
                result_default["face"][0], result_shifted["face"][0]
            )
        )
        for d in DIRECTIONS:
            for col in range(COLS):
                if d == "face" and col == 0:
                    continue
                self.assertTrue(
                    _pixels_equal(
                        result_default[d][col],
                        result_shifted[d][col],
                    ),
                    f"Frame inattendue modifiée : {d}/{col}",
                )

    def test_no_args_retrocompatible(self):
        """Sans args == avec les défauts explicités : résultat identique."""
        a = slice_sprite_sheet(self.sheet, self.w, self.h)
        b = slice_sprite_sheet(
            self.sheet,
            self.w,
            self.h,
            crop_size=CROP_SIZE,
            crop_offsets=CROP_OFFSETS,
        )
        for d in DIRECTIONS:
            for col in range(COLS):
                self.assertTrue(
                    _pixels_equal(a[d][col], b[d][col]),
                    f"Divergence : {d}/{col}",
                )

    def test_small_sheet_no_crash(self):
        """Un sheet plus petit que la grille ne crash pas."""
        sheet = _make_fake_sheet(60, 60)
        result = slice_sprite_sheet(sheet, 60, 60)
        self.assertEqual(len(result), len(DIRECTIONS))
        self.assertEqual(
            result["dos"][2].get_size(),
            CROP_SIZE["dos"][2],
        )


if __name__ == "__main__":
    unittest.main()
