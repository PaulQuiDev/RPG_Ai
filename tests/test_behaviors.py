"""Tests des comportements (behaviors) et de leur déclenche dans Npc :
go_forest / go_village / go_to_map, World.change_map / next_map, et les
actions `action` des NPC.

Assertions basées sur `current_map_data["name"]` et l'index de carte,
pas sur de coordonnées fragiles.
"""
import unittest

from .base import BaseTestCase
from .factories import (
    build_fake_one_world,
    build_fake_two_worlds,
    fake_npc_data,
    fake_player_data,
)
from settings import WINDOW_HEIGHT, WINDOW_WIDTH
from behaviors import go_forest, go_to_map, go_village
from npc import Npc
from player import Player


class TestBehaviorsWorld(BaseTestCase):
    """go_forest / go_village / go_to_map sur un monde à 2 cartes."""

    def setUp(self):
        self.world = build_fake_two_worlds(
            self._tmp.name, name_a="Village", name_b="Forêt"
        )
        self.player = Player(
            480.0, 360.0,
            fake_player_data(self._tmp.name, self.fake_sheet_path)
        )

    def test_go_forest_moves_to_foret(self):
        self.assertEqual(self.world.current_map_data["name"], "Village")
        self.assertTrue(go_forest(self.player, self.world, self.world.game_map))
        self.assertEqual(self.world.map_index, 1)
        self.assertEqual(self.world.current_map_data["name"], "Forêt")

    def test_go_village_from_foret(self):
        self.world.change_map(1, self.player)
        self.assertTrue(go_village(self.player, self.world, self.world.game_map))
        self.assertEqual(self.world.map_index, 0)
        self.assertEqual(self.world.current_map_data["name"], "Village")

    def test_go_to_map_by_name(self):
        self.assertTrue(go_to_map(self.player, self.world, "Forêt"))
        self.assertEqual(self.world.current_map_data["name"], "Forêt")

    def test_go_to_map_unknown_false(self):
        world = build_fake_one_world(self._tmp.name, name="Village")
        self.assertFalse(go_to_map(self.player, world, "Nullepart"))

    def test_change_map_invalid_index(self):
        world = build_fake_two_worlds(
            self._tmp.name, name_a="Village", name_b="Forêt"
        )
        self.assertFalse(world.change_map(99, self.player))
        self.assertEqual(world.map_index, 0)

    def test_next_map(self):
        world = build_fake_two_worlds(
            self._tmp.name, name_a="Village", name_b="Forêt"
        )
        self.assertTrue(world.next_map(self.player))
        self.assertEqual(world.current_map_data["name"], "Forêt")


class TestNpcBehaviorInteract(BaseTestCase):
    """L'interaction avec un NPC action=... déplace le Joueur vers la bonne
    carte. Le joueur doit être au contact du NPC (même position)."""

    def setUp(self):
        self.world = build_fake_two_worlds(
            self._tmp.name, name_a="Village", name_b="Forêt"
        )

    def _player_at(self, x, y):
        return Player(
            float(x), float(y),
            fake_player_data(self._tmp.name, self.fake_sheet_path)
        )

    def test_npc_go_forest_interact_moves_player(self):
        self.world.game_map.npcs.append(
            Npc(
                fake_npc_data(
                    self._tmp.name, self.fake_sheet_path,
                    action="go_forest", pos=(480.0, 360.0),
                ),
                0,
            )
        )
        player = self._player_at(480.0, 360.0)
        result = self.world.game_map.npcs[0].interact(
            player, self.world, self.world.game_map
        )
        self.assertEqual(self.world.map_index, 1)
        self.assertEqual(self.world.current_map_data["name"], "Forêt")
        self.assertTrue(result)

    def test_npc_go_village_interact_moves_player(self):
        self.world.change_map(1, self._player_at(480.0, 360.0))
        self.world.game_map.npcs.append(
            Npc(
                fake_npc_data(
                    self._tmp.name, self.fake_sheet_path,
                    action="go_village", pos=(480.0, 360.0),
                ),
                0,
            )
        )
        player = self._player_at(480.0, 360.0)
        result = self.world.game_map.npcs[0].interact(
            player, self.world, self.world.game_map
        )
        self.assertEqual(self.world.map_index, 0)
        self.assertEqual(self.world.current_map_data["name"], "Village")
        self.assertTrue(result)

    def test_npc_static_interact_no_map_change(self):
        world = build_fake_two_worlds(
            self._tmp.name, name_a="Village", name_b="Forêt"
        )
        world.game_map.npcs.append(
            Npc(
                fake_npc_data(
                    self._tmp.name, self.fake_sheet_path,
                    pos=(480.0, 360.0),
                ),
                0,
            )
        )
        player = self._player_at(480.0, 360.0)
        result = world.game_map.npcs[0].interact(
            player, world, world.game_map
        )
        self.assertEqual(world.map_index, 0)
        self.assertFalse(result)  # pas de changement de carte

    def test_npc_unknown_action_no_change(self):
        world = build_fake_two_worlds(
            self._tmp.name, name_a="Village", name_b="Forêt"
        )
        world.game_map.npcs.append(
            Npc(
                fake_npc_data(
                    self._tmp.name, self.fake_sheet_path,
                    action="inconnu", pos=(480.0, 360.0),
                ),
                0,
            )
        )
        player = self._player_at(480.0, 360.0)
        result = world.game_map.npcs[0].interact(
            player, world, world.game_map
        )
        self.assertEqual(world.map_index, 0)
        self.assertFalse(result)
