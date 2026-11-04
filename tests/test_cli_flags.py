"""Tests des flags CLI de `main.py`.

- parsing de chaque option (`--debug`, `--window`, `--fullscreen`, `--save`,
  `--load`, `--adv`) via `main._build_parser()` (sans `pygame.init`).
- validation du format `WxH` (`main._parse_window_size`).
- mutual exclusion `--window` / `--fullscreen`.
- **smoke headless du rendu en `--debug`** : filet anti-regression du bug P1
  (crash du flag `--debug` lors du rendu).
"""
import unittest

import pygame

from main import _build_parser, _parse_window_size
from .base import BaseTestCase
from settings import CHARACTERS, MAPS
from game import Game, GameState


class TestArgParse(unittest.TestCase):
    """Parsing de chaque flag via `main._build_parser()` (argparse pur,
    sans pygame). C'est le filet qui garantit qu'aucune combinaison de
    flags ne fait crasher le parsing au lancement."""

    def test_debug_default_false(self):
        self.assertFalse(_build_parser().parse_args([]).debug)

    def test_debug_set(self):
        self.assertTrue(_build_parser().parse_args(["--debug"]).debug)

    def test_window_set(self):
        args = _build_parser().parse_args(["--window", "800x600"])
        self.assertEqual(args.window, "800x600")

    def test_fullscreen_set(self):
        self.assertTrue(_build_parser().parse_args(["--fullscreen"]).fullscreen)

    def test_save_load_adv_set(self):
        args = _build_parser().parse_args(
            ["--save", "s.json", "--load", "l.json", "--adv", "a.json"])
        self.assertEqual(args.save, "s.json")
        self.assertEqual(args.load, "l.json")
        self.assertEqual(args.adv, "a.json")

    def test_defaults_none_or_false(self):
        args = _build_parser().parse_args([])
        self.assertFalse(args.debug)
        self.assertFalse(args.fullscreen)
        self.assertIsNone(args.window)
        self.assertIsNone(args.save)
        self.assertIsNone(args.load)
        self.assertIsNone(args.adv)

    def test_window_fullscreen_mutual_exclusion(self):
        """`--window` + `--fullscreen` ensemble => SystemExit code 2."""
        with self.assertRaises(SystemExit) as cm:
            _build_parser().parse_args(["--window", "800x600", "--fullscreen"])
        self.assertEqual(cm.exception.code, 2)

    def test_combined_valid_flags(self):
        args = _build_parser().parse_args(
            ["--debug", "--window", "1024x768", "--save", "s.json"])
        self.assertTrue(args.debug)
        self.assertEqual(args.window, "1024x768")
        self.assertFalse(args.fullscreen)
        self.assertEqual(args.save, "s.json")


class TestParseWindowSize(unittest.TestCase):
    """Validation du format `WxH` (`main._parse_window_size`)."""

    VALID = {
        "800x600": (800, 600),
        "800X600": (800, 600),
        "800×600": (800, 600),
        "800 x 600": (800, 600),
    }

    INVALID = ("abc", "x600", "800", "600x", "800x600x900", "0x0", "-1x600", "800x-600")

    def test_valid_formats(self):
        for value, expected in self.VALID.items():
            self.assertEqual(_parse_window_size(value), expected, value)

    def test_invalid_raises(self):
        for value in self.INVALID:
            with self.assertRaises(ValueError):
                _parse_window_size(value)


class TestDebugHeadless(BaseTestCase):
    """Rendu headless avec `debug=True` — filet anti-regression du bug P1
    (crash du flag `--debug` dans `_draw_debug_overlay`).

    Les autres tests de `Game` (ex. `test_headless_frames`) ne rendent
    qu'avec `debug=False` : le chemin du overlay debug n'était jamais
    exercé. D'où le bug.
    """

    def _make_game(self, debug):
        return Game(
            self.screen,
            pygame.font.SysFont("sans", 18),
            CHARACTERS,
            MAPS,
            debug=debug,
        )

    def test_headless_frames_debug(self):
        """Quelques frames en `--debug` (update + render) ne plantent pas."""
        game = self._make_game(debug=True)
        dt = 0.016
        for _ in range(15):
            game.update(dt)
            game.render()
        self.assertEqual(game.state, GameState.RUNNING)

    def test_debug_mask_built_on_render(self):
        """Le rendu en `--debug` construit bien le masque (chemin exécuté)."""
        game = self._make_game(debug=True)
        for _ in range(3):
            game.update(0.016)
            game.render()
        self.assertIsNotNone(game._debug_mask)

    def test_no_mask_without_debug(self):
        """Sans `--debug`, le masque de collision n'est pas construit."""
        game = self._make_game(debug=False)
        for _ in range(3):
            game.update(0.016)
            game.render()
        self.assertIsNone(game._debug_mask)


if __name__ == "__main__":
    unittest.main()
