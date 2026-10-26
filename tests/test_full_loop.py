"""Test d'intégration sur les assets réels (Village ↔ Forêt) : spawn,
NPC, objets bleus interactifs et changement de carte. Assertions robustes
(position praticable / focus), sans coordonnées exactes. Le joueur est
transmis explicitement à `World` (pas d'attribut `World.player`).

Facts (settings.MAPS) :
- Village (0) : 5 NPC (3 statiques, 2 patrols) + 1 objet `go_forest`.
- Forêt (1)   : 0 NPC ; objets bleus `cycle_map_seg` / `cycle_map_bg`
  (aucun `go_village`). Retour Forêt → Village = exit left (borde) ou
  `World.change_map` programmatique.
"""
import math
import unittest

from .base import BaseTestCase
from .factories import fake_player_data
from behaviors import BEHAVIORS
from settings import MAPS
from player import Player
from world import World


class TestFullLoop(BaseTestCase):
    """Intégration sur les assets réels (Village + Forêt)."""

    def setUp(self):
        self.world = World(MAPS)
        self.game_map = self.world.game_map
        self.player = self._make_player()

    def _make_player(self):
        x, y = self.world.find_spawn(self.world.game_map)
        return Player(
            float(x), float(y),
            fake_player_data(self._tmp.name, self.fake_sheet_path)
        )

    def _object_with_action(self, action):
        for obj in self.game_map.interact_objects:
            if obj.get("action") == action:
                return obj
        return None

    def test_spawn_on_village(self):
        """La carte par défaut (Village) a un spawn praticable et des
        NPC."""
        self.assertTrue(self.game_map.npcs)
        x, y = self.world.find_spawn(self.game_map)
        self.assertTrue(
            self.game_map.can_stand_at(
                float(x), float(y), self.player.collision_radius
            )
        )

    def test_village_npcs_have_frames(self):
        """Chaque NPC du village a un nom et un sheet chargé (frames)."""
        for npc in self.game_map.npcs:
            self.assertTrue(npc.name)
            self.assertIsInstance(npc.frames, dict)
            self.assertTrue(npc.frames.get("face"))

    def test_go_forest_via_object(self):
        """L'objet `go_forest` du Village emmène vers la Forêt ; le joueur
        finit sur un point praticable."""
        obj = self._object_with_action("go_forest")
        self.assertIsNotNone(obj, "pas d'objet go_forest sur le Village")
        behavior = BEHAVIORS.get(obj.get("action"))
        self.assertIsNotNone(behavior)
        self.assertTrue(behavior(self.player, self.world, self.game_map))
        self.assertEqual(self.world.map_index, 1)
        self.assertEqual(self.world.current_map_data["name"], "Forêt")
        self.assertTrue(
            self.world.game_map.can_stand_at(
                self.player.x, self.player.y, self.player.collision_radius
            )
        )

    def test_forest_npcs_and_objects(self):
        """La Forêt (réelle) : 0 NPC ; objets bleus `cycle_map_seg` et
        `cycle_map_bg`."""
        w = World(MAPS)
        w.change_map(1, self.player)
        self.assertEqual(w.current_map_data["name"], "Forêt")
        gm = w.game_map
        self.assertEqual(len(gm.npcs), 0)
        actions = {o.get("action") for o in gm.interact_objects}
        self.assertIn("cycle_map_seg", actions)
        self.assertIn("cycle_map_bg", actions)

    def test_change_back_to_village(self):
        """Forêt → Village via `World.change_map` (mechanisme du retour)."""
        self.assertTrue(self.world.change_map(1, self.player))
        self.assertEqual(self.world.current_map_data["name"], "Forêt")
        self.assertTrue(self.world.change_map(0, self.player))
        self.assertEqual(self.world.current_map_data["name"], "Village")

    def test_roundtrip_change_map(self):
        """Aller/retour complet Village → Forêt → Village."""
        self.assertTrue(self.world.change_map(1, self.player))
        self.assertEqual(self.world.current_map_data["name"], "Forêt")
        self.assertTrue(self.world.change_map(0, self.player))
        self.assertEqual(self.world.current_map_data["name"], "Village")
        self.assertEqual(self.world.map_index, 0)

    def test_headless_npc_update(self):
        """Mise à jour des NPC du village en mode headless ne plante pas ;
        les positions restent finies."""
        n = len(self.game_map.npcs)
        dt = 0.016
        for _ in range(3):
            for npc in self.game_map.npcs:
                npc.update(dt, self.game_map, self.player)
        self.assertEqual(len(self.game_map.npcs), n)
        for npc in self.game_map.npcs:
            self.assertTrue(math.isfinite(npc.x))
            self.assertTrue(math.isfinite(npc.y))

    def test_focus_go_forest_object(self):
        """Sur le Village, l'objet proche `go_forest` est au focus."""
        obj = self._object_with_action("go_forest")
        box = obj["box"]
        self.player.x = float(box.x + box.width // 2)
        self.player.y = float(box.y + box.height // 2)
        focused = self.world.game_map.get_focused_object(self.player)
        self.assertIsNotNone(focused)
        self.assertEqual(focused.get("action"), "go_forest")
