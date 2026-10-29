"""Tests de la boucle complète de la quête (cartes RÉELLES, asset/world/*.png).

Couvre la bonne exécution des objets à travers tout le cycle :
Village -> Forêt -> Boss Combat (5 bougies) -> Post Combat (trône)
-> Village (transformation + fuite des PNJ) -> re-entrée Boss Combat
(nouveau monstre, bougies à zéro).

C'est aussi le test du compteur HUD « Bougies : x/5 » (pas /10).
"""
import unittest

import pygame

from settings import CHARACTERS, MAPS
from game import BOSS_COMBAT_MAP, Game
from .base import BaseTestCase


class TestFullQuest(BaseTestCase):
    """Quête complète avec les cartes réelles (World(MAPS))."""

    def setUp(self):
        self.game = Game(
            self.screen,
            pygame.font.SysFont("sans", 18),
            CHARACTERS,
            MAPS,
            collisions_enabled=False,
            debug=False,
        )

    def tearDown(self):
        self.game = None

    def _enter(self, index):
        """Change de carte + reset d'état, comme dans la boucle réelle
        (change_map puis update => _on_map_change)."""
        self.game.world.change_map(index, self.game.player)
        self.game.game_map = self.game.world.game_map
        self.game.update(0.016)

    def _interact_at(self, cx, cy):
        """Positionne le joueur en (cx, cy) puis interagit (touche I)."""
        self.game.player.x, self.game.player.y = float(cx), float(cy)
        self.game._interact()

    def _objects_by_action(self, action):
        return [
            o
            for o in self.game.game_map.interact_objects
            if o.get("action") == action
        ]

    def test_combat_candle_total_is_five(self):
        # Le TOTAL du HUD est le nombre de bougies (light_candle), PAS
        # le nombre d'objets bleus totaux (fix du bug « Bougies : x/10 »).
        self._enter(2)
        self.assertEqual(
            self.game.world.current_map_data["name"], BOSS_COMBAT_MAP
        )
        self.assertEqual(self.game.combat_candle_total(), 5)
        # La carte de combat a bien 10 objets bleus, dont 5 bougies.
        self.assertEqual(len(self.game.game_map.interact_objects), 10)
        # Hors carte de combat, le total est zéro.
        self._enter(0)
        self.assertEqual(self.game.combat_candle_total(), 0)

    def test_full_quest_flow(self):
        # 1) Départ : Village.
        self.assertEqual(self.game.world.current_map_data["name"], "Village")

        # 2) Forêt.
        self._enter(1)
        self.assertEqual(self.game.world.current_map_data["name"], "Forêt")

        # 3) Boss Combat : un monstre est présent, bougies à zéro.
        self._enter(2)
        self.assertEqual(
            self.game.world.current_map_data["name"], BOSS_COMBAT_MAP
        )
        self.assertIsNotNone(self.game._monster)
        self.assertEqual(self.game._candle_lit_count, 0)
        self.assertEqual(self.game.combat_candle_total(), 5)

        # 4) Allume les 5 bougies -> le monstre meurt -> Post Combat.
        candles = self._objects_by_action("light_candle")
        self.assertEqual(len(candles), 5)
        for o in candles:
            self._interact_at(o["box"].centerx, o["box"].centery)
        self.assertEqual(
            self.game.world.current_map_data["name"], "Post Combat"
        )
        self.assertIsNone(self.game._monster)
        self.assertTrue(self.game.world.flag_get("monster_defeated"))

        # 5) Trône : transforme le monstre (flag monster2_active).
        throne = self._objects_by_action("transform_monster")
        self.assertEqual(len(throne), 1)
        self._interact_at(throne[0]["box"].centerx, throne[0]["box"].centery)
        self.assertTrue(self.game.world.flag_get("monster2_active"))

        # 6) Retour au village : transformation + fuite des PNJ.
        self._enter(0)
        self.assertEqual(self.game.world.current_map_data["name"], "Village")
        self.assertTrue(self.game._monster2_transformed)
        self.assertTrue(
            any(n.behavior == "flee" for n in self.game.game_map.npcs)
        )

        # 7) Re-entrée dans le Boss Combat : nouveau monstre, bougies à zéro
        #    (persistance du reset — le bug « en bosse après le retour »).
        self._enter(2)
        self.assertEqual(
            self.game.world.current_map_data["name"], BOSS_COMBAT_MAP
        )
        self.assertIsNotNone(self.game._monster)
        self.assertEqual(self.game._candle_lit_count, 0)
        self.assertEqual(len(self.game._candle_lit), 0)


if __name__ == "__main__":
    unittest.main()
