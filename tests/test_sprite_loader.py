"""Tests de sprite_loader.slice_sprite_sheet (découpe 4x3)."""
import unittest

from .base import BaseTestCase
from .pygame_setup import make_sheet
from settings import COLS, ROWS, CROP_SIZE, DIRECTIONS
from sprite_loader import slice_sprite_sheet


class TestSliceSpriteSheet(BaseTestCase):

    def _result(self, sheet):
        return slice_sprite_sheet(sheet, sheet.get_width(), sheet.get_height())

    def test_quatre_directions(self):
        result = self._result(make_sheet())
        self.assertEqual(sorted(result.keys()), sorted(DIRECTIONS.keys()))

    def test_trois_frames_par_direction(self):
        result = self._result(make_sheet())
        for d in DIRECTIONS:
            self.assertEqual(len(result[d]), COLS)
            self.assertEqual(len(result[d]), 3)

    def test_tailles_cohérentes(self):
        sheet = make_sheet()
        result = self._result(sheet)
        cell_w = sheet.get_width() // COLS
        cell_h = sheet.get_height() // ROWS
        for d in DIRECTIONS:
            for col in range(COLS):
                expected = CROP_SIZE[d].get(col, (cell_w, cell_h))
                frame = result[d][col]
                msg = f"{d} {col}"
                self.assertEqual(frame.get_width(), expected[0], msg)
                self.assertEqual(frame.get_height(), expected[1], msg)

    def test_frames_contenu_non_vide(self):
        result = self._result(make_sheet())
        for d in DIRECTIONS:
            for frame in result[d]:
                # une frame doit contenir au moins un pixel opaque
                # (certains offsets déplacent le contenu, on ne teste pas
                #  une position fixe mais l'ensemble de la frame)
                opaque = 0
                for y in range(0, frame.get_height(), 5):
                    for x in range(0, frame.get_width(), 5):
                        if frame.get_at((x, y))[3] > 0:
                            opaque += 1
                self.assertGreater(opaque, 0, f"frame vide: {d}")

    def test_sheet_trop_petite_ne_crase_pas(self):
        # cellules 40x30, découpes (200x300) plus grandes que la cellule :
        # l'intersection doit couper sans exception.
        sheet = make_sheet(120, 120)
        result = slice_sprite_sheet(sheet, 120, 120)
        self.assertEqual(sorted(result.keys()), sorted(DIRECTIONS.keys()))

    def test_sheet_trop_petite_frames_vides_acceptables(self):
        sheet = make_sheet(60, 60)
        result = slice_sprite_sheet(sheet, 60, 60)
        for d in DIRECTIONS:
            self.assertEqual(len(result[d]), 3)
            for frame in result[d]:
                # une frame peut être entièrement vide sans crasher
                self.assertTrue(frame.get_width() > 0)
