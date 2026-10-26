"""Tests de player.Player : mouvement, collision, direction, clamp."""
import unittest

import pygame

from .base import BaseTestCase
from .factories import build_fake_one_world, fake_player_data
from settings import SPRITE_SCALE, WINDOW_HEIGHT, WINDOW_WIDTH
from player import Player


class TestPlayerConstruction(BaseTestCase):
    def setUp(self):
        self.player = Player(
            480.0, 360.0,
            fake_player_data(self._tmp.name, self.fake_sheet_path),
        )

    def test_defaults(self):
        self.assertEqual(self.player.name, "Joueur")
        self.assertEqual(self.player.x, 480.0)
        self.assertEqual(self.player.speed, 220.0)
        # base_scale = scale (0.25) * SPRITE_SCALE (2.0)
        self.assertEqual(self.player.base_scale, SPRITE_SCALE * 0.25)

    def test_custom_speed_and_radius(self):
        p = Player(
            10.0, 10.0,
            fake_player_data(self._tmp.name, self.fake_sheet_path,
                             speed=300, collision_radius=8),
        )
        self.assertEqual(p.speed, 300.0)
        self.assertEqual(p.collision_radius, 8.0)

    def test_requires_character_data(self):
        with self.assertRaises(KeyError):
            Player(0, 0, {})


class TestPlayerUpdate(BaseTestCase):
    def setUp(self):
        self.world = build_fake_one_world(self._tmp.name)
        self.player = Player(
            480.0, 360.0,
            fake_player_data(self._tmp.name, self.fake_sheet_path),
        )

    def _keys(self, *on_keys):
        d = {}
        for k in dir(pygame.constants):
            if k.startswith("K_"):
                d[getattr(pygame.constants, k)] = (k in on_keys)
        return d

    def test_no_keys_not_moving(self):
        self.player.update(
            0.016, self._keys(), self.world.game_map, True
        )
        self.assertFalse(self.player.moving)

    def test_move_right(self):
        self.player.update(
            0.1, self._keys("K_RIGHT"), self.world.game_map, True
        )
        self.assertTrue(self.player.moving)
        self.assertGreater(self.player.x, 480.0)

    def test_move_left(self):
        self.player.update(
            0.1, self._keys("K_LEFT"), self.world.game_map, True
        )
        self.assertLess(self.player.x, 480.0)

    def test_move_up(self):
        self.player.update(
            0.1, self._keys("K_UP"), self.world.game_map, True
        )
        self.assertLess(self.player.y, 360.0)

    def test_move_down(self):
        self.player.update(
            0.1, self._keys("K_DOWN"), self.world.game_map, True
        )
        self.assertGreater(self.player.y, 360.0)

    def test_direction_changes(self):
        self.player.update(
            0.1, self._keys("K_LEFT"), self.world.game_map, True
        )
        self.assertEqual(self.player.direction, "gauche")
        self.player.update(
            0.1, self._keys("K_UP"), self.world.game_map, True
        )
        self.assertEqual(self.player.direction, "dos")
        self.player.update(
            0.1, self._keys("K_DOWN"), self.world.game_map, True
        )
        self.assertEqual(self.player.direction, "face")

    def test_no_collision_passes_wall(self):
        world = build_fake_one_world(self._tmp.name,
                                     blocked=[(300, 300, 100, 100)])
        p = Player(
            250.0, 350.0,
            fake_player_data(self._tmp.name, self.fake_sheet_path)
        )
        p.update(0.016, self._keys("K_RIGHT"), world.game_map, False)
        # sans collision, le mur ne bloque pas
        self.assertGreater(p.x, 250.0)

    def test_collision_blocks_wall(self):
        world = build_fake_one_world(self._tmp.name,
                                     blocked=[(300, 300, 100, 100)])
        p = Player(
            250.0, 350.0,
            fake_player_data(self._tmp.name, self.fake_sheet_path)
        )
        for _ in range(60):
            p.update(0.016, self._keys("K_RIGHT"), world.game_map, True)
        self.assertLess(p.x, 300.0)

    def test_diagonal_moves_both_axes(self):
        start_x, start_y = self.player.x, self.player.y
        self.player.update(
            0.016, self._keys("K_RIGHT", "K_DOWN"),
            self.world.game_map, True,
        )
        self.assertGreater(self.player.x, start_x)
        self.assertGreater(self.player.y, start_y)

    def test_clamp_to_window(self):
        p = Player(
            WINDOW_WIDTH - 5.0, 360.0,
            fake_player_data(self._tmp.name, self.fake_sheet_path)
        )
        p.update(0.1, self._keys("K_RIGHT"), self.world.game_map, True)
        self.assertLessEqual(
            p.x, WINDOW_WIDTH - p.collision_radius + 1
        )

    def test_draw_no_raise(self):
        screen = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.player.draw(screen, self.world.game_map)
