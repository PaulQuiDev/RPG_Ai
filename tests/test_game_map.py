"""Tests de game_map.GameMap : collision, walkable, extraction (bleu/FG),
NPC, perspective, spawn."""
import unittest

import pygame

from .base import BaseTestCase
from .factories import (
    build_fake_one_world,
    build_fake_two_worlds,
    fake_npc_data,
    fake_player_data,
)
from settings import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
)
from npc import Npc
from player import Player


class TestGameMapWalkable(BaseTestCase):
    """is_walkable et can_stand_at selon le masque (vert/rouge/bleu)."""

    def setUp(self):
        self.world = build_fake_one_world(self._tmp.name)
        self.game_map = self.world.game_map

    def test_walkable_green(self):
        # point vert (pas de mur ni bleu)
        self.assertTrue(self.game_map.is_walkable(100, 100))

    def test_not_walkable_red(self):
        world = build_fake_one_world(
            self._tmp.name, blocked=[(300, 300, 100, 100)]
        )
        self.assertFalse(world.game_map.is_walkable(350, 350))

    def test_not_walkable_blue(self):
        world = build_fake_one_world(self._tmp.name, blue=[(400, 400, 80, 80)])
        self.assertFalse(world.game_map.is_walkable(440, 440))

    def test_can_stand_at_green(self):
        self.assertTrue(self.game_map.can_stand_at(200, 200, 5.0))

    def test_can_stand_at_red(self):
        world = build_fake_one_world(
            self._tmp.name, blocked=[(300, 300, 100, 100)]
        )
        self.assertFalse(world.game_map.can_stand_at(350, 350, 5.0))

    def test_can_stand_at_blue_not_walkable(self):
        world = build_fake_one_world(self._tmp.name, blue=[(400, 400, 80, 80)])
        self.assertFalse(world.game_map.can_stand_at(440, 440, 5.0))


class TestGameMapNpcCollision(BaseTestCase):
    """can_stand_at tient compte des NPC (rayon + collision_radius)."""

    def setUp(self):
        self.world = build_fake_one_world(self._tmp.name)
        self.game_map = self.world.game_map
        self.npc = Npc(
            fake_npc_data(self._tmp.name, self.fake_sheet_path,
                          name="T", pos=[480.0, 360.0]),
            0,
        )
        self.game_map.npcs.append(self.npc)
        self.player = Player(
            100.0, 100.0,
            fake_player_data(self._tmp.name, self.fake_sheet_path)
        )

    def test_blocked_by_npc(self):
        self.assertFalse(self.game_map.can_stand_at(480.0, 360.0, 5.0))

    def test_far_ok(self):
        self.assertTrue(self.game_map.can_stand_at(100.0, 100.0, 5.0))

    def test_ignore_npc(self):
        self.assertTrue(
            self.game_map.can_stand_at(480.0, 360.0, 5.0, ignore=self.npc)
        )

    def test_npcs_in_contact(self):
        # self.game_map.npcs contient déja le NPC de setUp à (480, 360)
        player = Player(
            480.0, 360.0,
            fake_player_data(self._tmp.name, self.fake_sheet_path)
        )
        self.assertEqual(
            len(self.game_map.npcs_in_contact(player)), 1
        )
        player.x, player.y = 100.0, 100.0
        self.assertEqual(len(self.game_map.npcs_in_contact(player)), 0)


class TestGameMapExtract(BaseTestCase):
    """Extraction des objets bleus (interactables) et des FG (alpha)."""

    def test_extract_interactables_blue_objects(self):
        # deux rectangles bleus => deux objets
        world = build_fake_one_world(
            self._tmp.name, blue=[(100, 100, 20, 20), (700, 500, 20, 20)]
        )
        self.assertEqual(len(world.game_map.interact_objects), 2)
        self.assertIsNotNone(world.game_map.interact_layer)

    def test_no_blue_no_objects(self):
        world = build_fake_one_world(self._tmp.name)
        self.assertEqual(len(world.game_map.interact_objects), 0)

    def test_extract_fg_elements(self):
        blobs = [
            (550, 150, 90, 70, (200, 160, 100, 255)),
            (250, 250, 70, 60, (200, 160, 100, 255)),
        ]
        world = build_fake_one_world(self._tmp.name, fg=True, fg_blobs=blobs)
        els = world.game_map.fg_elements
        self.assertIsInstance(els, list)
        # au moins un élément extrait (les blobs sont opaques)
        self.assertGreaterEqual(len(els), 1)
        el = els[0]
        self.assertIsInstance(el["surf"], pygame.Surface)
        self.assertIsInstance(el["box"], pygame.Rect)

    def test_no_fg_no_elements(self):
        world = build_fake_one_world(self._tmp.name)  # fg=False
        self.assertEqual(len(world.game_map.fg_elements), 0)


class TestGameMapPerspective(BaseTestCase):
    """get_perspective_scale : désactivé => 1.0 ; activé => interpolation."""

    def test_disabled_returns_one(self):
        world = build_fake_one_world(self._tmp.name)
        self.assertEqual(world.game_map.get_perspective_scale(360.0), 1.0)

    def test_enabled_interpolates(self):
        world = build_fake_one_world(self._tmp.name)
        gm = world.game_map
        gm.perspective = {
            "enabled": True,
            "top_scale": 0.6,
            "bottom_scale": 1.2,
        }
        self.assertAlmostEqual(gm.get_perspective_scale(0.0), 0.6, places=5)
        self.assertAlmostEqual(
            gm.get_perspective_scale(WINDOW_HEIGHT), 1.2, places=5
        )
        self.assertAlmostEqual(
            gm.get_perspective_scale(WINDOW_HEIGHT // 2), 0.9, places=5
        )

    def test_focused_object_in_range(self):
        world = build_fake_one_world(
            self._tmp.name,
            blue=[(400, 400, 80, 80)],
            interactions=[{"pos": [440, 440], "action": "t"}],
        )
        player = Player(
            420.0, 440.0,
            fake_player_data(self._tmp.name, self.fake_sheet_path)
        )
        obj = world.game_map.get_focused_object(player)
        self.assertIsNotNone(obj)
        if obj is None:
            self.fail("objet focalisé attendu")
        self.assertEqual(obj.get("action"), "t")

    def test_focused_object_skips_non_interactive(self):
        # Un objet bleu SANS comportement n'est PAS focalisable.
        world = build_fake_one_world(
            self._tmp.name, blue=[(400, 400, 80, 80)]
        )
        player = Player(
            420.0, 440.0,
            fake_player_data(self._tmp.name, self.fake_sheet_path)
        )
        self.assertIsNone(world.game_map.get_focused_object(player))

    def test_focused_object_prefers_interactive(self):
        # Deux objets bleus dans la portée : le non-interactif est ignoré,
        # on retourne l'interactif.
        world = build_fake_one_world(
            self._tmp.name,
            blue=[(400, 400, 40, 40), (460, 400, 40, 40)],
            interactions=[{"pos": [480, 420], "action": "t"}],
        )
        player = Player(
            420.0, 440.0,
            fake_player_data(self._tmp.name, self.fake_sheet_path)
        )
        obj = world.game_map.get_focused_object(player)
        self.assertIsNotNone(obj)
        if obj is None:
            self.fail("objet focalisé attendu")
        self.assertEqual(obj.get("action"), "t")

    def test_focused_object_none_far(self):
        world = build_fake_one_world(
            self._tmp.name, blue=[(400, 400, 80, 80)]
        )
        player = Player(
            900.0, 900.0,
            fake_player_data(self._tmp.name, self.fake_sheet_path)
        )
        self.assertIsNone(world.game_map.get_focused_object(player))

    def test_focused_object_none_no_player(self):
        world = build_fake_one_world(
            self._tmp.name, blue=[(400, 400, 80, 80)]
        )
        self.assertIsNone(world.game_map.get_focused_object(None))

    def test_validate_interactions_flags_unassociated_object(self):
        # Objet bleu SANS comportement associé => avertissement.
        world = build_fake_one_world(
            self._tmp.name, blue=[(400, 400, 80, 80)]
        )
        warnings = world.game_map.interaction_warnings
        self.assertTrue(any(
            "sans comportement associé" in w for w in warnings
        ))

    def test_validate_interactions_flags_orphan_interaction(self):
        # Interaction sans objet bleu à proximité => avertissement.
        world = build_fake_one_world(
            self._tmp.name,
            interactions=[{"pos": [1000, 1000], "action": "t"}],
        )
        warnings = world.game_map.interaction_warnings
        self.assertTrue(any(
            "sans objet bleu associé" in w for w in warnings
        ))

    def test_interaction_label(self):
        world = build_fake_one_world(self._tmp.name)
        gm = world.game_map
        self.assertEqual(
            gm._interaction_label({"name": "Trône"}), "Trône"
        )
        self.assertEqual(
            gm._interaction_label({"action": "go_forest"}), "go_forest"
        )
        self.assertEqual(
            gm._interaction_label({"name": "", "action": "t"}), "t"
        )
        self.assertEqual(gm._interaction_label({}), "")

    def test_count_action(self):
        world = build_fake_one_world(
            self._tmp.name,
            blue=[(100, 100, 40, 40), (200, 100, 40, 40), (300, 100, 40, 40)],
            interactions=[
                {"pos": [120, 120], "action": "light_candle"},
                {"pos": [220, 120], "action": "light_candle"},
                {"pos": [320, 120], "action": "other"},
            ],
        )
        gm = world.game_map
        self.assertEqual(gm.count_action("light_candle"), 2)
        self.assertEqual(gm.count_action("other"), 1)
        self.assertEqual(gm.count_action("none"), 0)


class TestGameMapSpawn(BaseTestCase):
    """find_nearest_walkable / find_spawn : snap vers le praticable le plus proche."""

    def test_find_nearest_walkable_same_point(self):
        world = build_fake_one_world(self._tmp.name)
        x, y = world.game_map.find_nearest_walkable(300, 300, 5.0)
        self.assertTrue(world.game_map.can_stand_at(300.0, 300.0, 5.0))
        # point proche : (300,300) est praticable => retourne (300,300)
        self.assertEqual((x, y), (300, 300))

    def test_world_find_spawn_center_walkable(self):
        world = build_fake_one_world(self._tmp.name)
        x, y = world.find_spawn(world.game_map)
        self.assertEqual((x, y), (480, 360))  # centre => praticable

    def test_world_find_spawn_center_blocked(self):
        # boucher le centre => on sort du centre
        world = build_fake_one_world(
            self._tmp.name, blocked=[(440, 320, 80, 80)]
        )
        x, y = world.find_spawn(world.game_map)
        self.assertNotEqual((x, y), (480, 360))
        self.assertTrue(world.game_map.can_stand_at(float(x), float(y), 5.0))

    def test_world_find_nearest_walkable_near_wall(self):
        # point dans le mur => snap au bord
        world = build_fake_one_world(self._tmp.name, blocked=[(300, 300, 100, 100)])
        x, y = world.game_map.find_nearest_walkable(350, 350, 5.0)
        self.assertTrue(world.game_map.can_stand_at(x, y, 5.0))
