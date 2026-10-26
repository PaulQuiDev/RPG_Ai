"""Tests de la couche d'état global (quêtes) : drapeaux + conditions.

Vérifie que les transitions gated et les interactions gated sont appliquées
par l'engine (World.check_transition et Game._interact), de façon générique.

Reutilise l'infrastructure test existante (tests/factories.py) — pas de
dépendance supplémentaire (pas de numpy).
"""
import unittest

import pygame

from settings import WINDOW_HEIGHT, WINDOW_WIDTH

from player import Player
from game_map import GameMap
from behaviors import BEHAVIORS
from world import World
from game import Game

from tests.base import BaseTestCase
from tests.factories import (
    _write,
    fake_player_data,
    make_fake_background,
    make_fake_mask,
)


class TestQuestFlags(BaseTestCase):
    """API pure flag/condition de World (sans engine)."""

    def _world(self, name="X"):
        t = self._tmp.name
        bg = _write(make_fake_background(), t, "bg.png")
        mask = _write(make_fake_mask(), t, "mask.png")
        return World([{"name": name, "background": bg, "mask": mask}])

    def test_flag_set_get_reset(self):
        world = self._world()
        world.flag_set("a")
        self.assertTrue(world.flag_get("a"))
        world.flag_set("b", False)
        # la valeur posée l'emporte sur le default
        self.assertEqual(world.flag_get("b"), False)
        self.assertEqual(world.flag_get("b", True), False)
        # default appliqué si le drapeau n'est pas défini
        self.assertEqual(world.flag_get("c", True), True)
        self.assertFalse(world.flag_get("c"))
        world.flag_reset("a")
        self.assertFalse(world.flag_get("a"))
        world.flag_reset()
        self.assertEqual(world.flags, {})
        self.assertFalse(world.flag_get("c", False))

    def test_condition_holds_none_empty(self):
        world = self._world()
        self.assertTrue(world.condition_holds(None))
        self.assertTrue(world.condition_holds(None, None))
        self.assertTrue(world.condition_holds([]))
        self.assertTrue(world.condition_holds((), None))

    def test_flag_condition(self):
        world = self._world()
        world.register_condition("is_lit", world.flag_condition("lit"))
        self.assertFalse(world.condition_holds(["is_lit"]))
        self.assertFalse(world.condition_holds(["is_lit"], None))
        world.flag_set("lit")
        self.assertTrue(world.condition_holds(["is_lit"]))
        world.flag_reset("lit")
        self.assertFalse(world.condition_holds(["is_lit"]))
        # condition sur une valeur négative
        world.flag_set("dead", False)
        world.register_condition("alive", world.flag_condition("dead"))
        self.assertFalse(world.condition_holds(["alive"]))

    def test_multiple_conditions_all_must_hold(self):
        world = self._world()
        world.flag_set("x")
        world.flag_reset("y")
        world.register_condition("c_x", world.flag_condition("x"))
        world.register_condition("c_y", world.flag_condition("y"))
        self.assertTrue(world.condition_holds(["c_x"]))
        self.assertFalse(world.condition_holds(["c_x", "c_y"]))
        world.flag_set("y")
        self.assertTrue(world.condition_holds(["c_y", "c_x"]))

    def test_unknown_condition_blocks(self):
        world = self._world()
        # fail-closed : une condition inconnue bloque.
        self.assertFalse(world.condition_holds(["nope"]))
        self.assertFalse(world.condition_holds(["nope", "x"]))

    def test_condition_that_raises_blocks(self):
        world = self._world()
        world.register_condition("boom", lambda w, p: 1 / 0)
        self.assertFalse(world.condition_holds(["boom"]))


def _two_world(t, sheet_path, requires=None):
    """Monde de 2 cartes (A->B) ; la sortie droite de A est gated."""
    bg_a = _write(make_fake_background(), t, "bg_a.png")
    mask_a = _write(make_fake_mask(), t, "mask_a.png")
    bg_b = _write(make_fake_background((80, 140, 210)), t, "bg_b.png")
    mask_b = _write(make_fake_mask(), t, "mask_b.png")
    exit_a = {"map": "B", "spawn": [WINDOW_WIDTH - 5, 360]}
    if requires is not None:
        exit_a["requires"] = requires
    world = World(
        [
            {
                "name": "A",
                "background": bg_a,
                "mask": mask_a,
                "exits": {"right": exit_a},
            },
            {
                "name": "B",
                "background": bg_b,
                "mask": mask_b,
                "exits": {"left": {"map": "A", "spawn": [5, 360]}},
            },
        ]
    )
    spawn_x, spawn_y = world.find_spawn(world.game_map)
    player = Player(
        float(spawn_x),
        float(spawn_y),
        fake_player_data(t, sheet_path),
    )
    return world, player


class TestGatedTransition(BaseTestCase):
    """World.check_transition : gated par `requires` sur une sortie."""

    def _two_world(self, requires=None):
        return _two_world(
            self._tmp.name, self.fake_sheet_path, requires=requires
        )

    def test_transition_gated_blocks_then_allows(self):
        world, player = self._two_world(requires=["has_stone"])
        world.register_condition(
            "has_stone", world.flag_condition("has_stone")
        )
        # Joueur au bord droit
        player.x = float(WINDOW_WIDTH - 5)
        player.y = float(WINDOW_HEIGHT // 2)
        # Condition fausse : bloqué, reste sur A.
        self.assertFalse(world.check_transition(player))
        self.assertEqual(world.map_index, 0)
        self.assertEqual(world.current_map_data["name"], "A")
        # Joueur non déplacé (resté au bord).
        self.assertGreater(player.x, WINDOW_WIDTH - 12)
        # Condition vraie : transition vers B.
        world.flag_set("has_stone")
        self.assertTrue(world.check_transition(player))
        self.assertEqual(world.map_index, 1)
        self.assertEqual(world.current_map_data["name"], "B")

    def test_transition_without_requires_still_works(self):
        world, player = self._two_world(requires=None)
        player.x = float(WINDOW_WIDTH - 5)
        player.y = float(WINDOW_HEIGHT // 2)
        # Pas de requires => transition immédiate (compat).
        self.assertTrue(world.check_transition(player))
        self.assertEqual(world.map_index, 1)
        self.assertEqual(world.current_map_data["name"], "B")

    def test_unknown_condition_in_requires_blocks(self):
        world, player = self._two_world(requires=["missing_cond"])
        # Pas de condition enregistrée => fail-closed (bloqué).
        player.x = float(WINDOW_WIDTH - 5)
        player.y = float(WINDOW_HEIGHT // 2)
        self.assertFalse(world.check_transition(player))
        self.assertEqual(world.map_index, 0)


class TestGatedInteraction(BaseTestCase):
    """Game._interact : gated par `requires` + pose du `flag` après succès."""

    def setUp(self):
        super().setUp()
        # Comportements de test (retournent True/False, avec effet).
        self.calls = []
        BEHAVIORS["test_record"] = (lambda p, w, gm: (
            self.calls.append("recorded"), True
        )[1])
        BEHAVIORS["test_fail"] = (lambda p, w, gm: (
            self.calls.append("fail"), False
        )[1])

    def tearDown(self):
        BEHAVIORS.pop("test_record", None)
        BEHAVIORS.pop("test_fail", None)
        super().tearDown()

    def _blue_world_and_game(self, interaction):
        """Monde avec un unique objet bleu ; `interaction` est associée.

        Le `World` est construit (flags/conditions sur l'instance) puis
        injecté dans `Game` (injection de dépendance) : pas de chargement des
        maps réelles.
        """
        t = self._tmp.name
        bg = _write(make_fake_background(), t, "bg.png")
        mask = _write(make_fake_mask(blue=[(100, 100, 40, 40)]), t, "mask.png")
        # centre réel de l'objet bleu (après la flip top-down du masque).
        tmp_gm = GameMap(bg, mask, None, None, [], [])
        objs = tmp_gm.interact_objects
        self.assertGreaterEqual(len(objs), 1)
        cx, cy = objs[0]["box"].centerx, objs[0]["box"].centery

        map_data = {
            "name": "X",
            "background": bg,
            "mask": mask,
            "interactions": [
                {"pos": (round(cx), round(cy)), **interaction}
            ],
        }
        world = World([map_data])
        game = Game(
            self.screen,
            pygame.font.SysFont("sans", 18),
            [fake_player_data(t, self.fake_sheet_path)],
            [],
            world=world,
        )
        # joueur à côté de l'objet bleu (portée < INTERACT_DISTANCE).
        game.player.x = float(cx - 20)
        game.player.y = float(cy)
        return world, game

    def test_interaction_blocked_by_requires(self):
        world, game = self._blue_world_and_game(
            {"action": "test_record", "requires": ["has_stone"], "flag": "lit"}
        )
        world.register_condition(
            "has_stone", world.flag_condition("has_stone")
        )
        self.assertIsNotNone(game.game_map.get_focused_object(game.player))
        # Condition fausse : action non exécutée, flag non posé.
        game._interact()
        self.assertEqual(self.calls, [])
        self.assertFalse(world.flag_get("lit"))

    def test_interaction_allowed_and_sets_flag(self):
        world, game = self._blue_world_and_game(
            {
                "action": "test_record",
                "requires": ["has_stone"],
                "flag": "lit",
                "flag_value": True,
            }
        )
        world.register_condition(
            "has_stone", world.flag_condition("has_stone")
        )
        world.flag_set("has_stone")
        self.assertIsNotNone(game.game_map.get_focused_object(game.player))
        game._interact()
        self.assertEqual(self.calls, ["recorded"])
        self.assertTrue(world.flag_get("lit"))

    def test_interaction_flag_value_false(self):
        world, game = self._blue_world_and_game(
            {"action": "test_record", "flag": "lit", "flag_value": False}
        )
        game._interact()
        self.assertEqual(self.calls, ["recorded"])
        self.assertFalse(world.flag_get("lit"))

    def test_no_requires_backward_compat(self):
        world, game = self._blue_world_and_game({"action": "test_record"})
        self.assertIsNotNone(game.game_map.get_focused_object(game.player))
        game._interact()
        self.assertEqual(self.calls, ["recorded"])

    def test_flag_set_only_on_success(self):
        world, game = self._blue_world_and_game(
            {"action": "test_fail", "flag": "lit"}
        )
        game._interact()
        self.assertEqual(self.calls, ["fail"])
        # le flag n'est posé que si le comportement retourne True
        self.assertFalse(world.flag_get("lit"))

    def test_requires_empty_list_allows(self):
        world, game = self._blue_world_and_game(
            {"action": "test_record", "requires": []}
        )
        game._interact()
        self.assertEqual(self.calls, ["recorded"])


if __name__ == "__main__":
    unittest.main()
