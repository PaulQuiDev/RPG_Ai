"""Tests de la dévoration des PNJ (boss) — feature P8.

Après transformation (drapeau ``monster2_active`` levé), si le joueur
entre au contact d'un PNJ, le PNJ est « mangé » :

    - il disparaît (retiré de la carte courante **et** de la donnée
      persistante, donc il ne reparaît plus si on quitte/rechange la
      carte) ;
    - le joueur grossit de façon cumulative :
        * taille (``base_scale``) + ``SCALE_INCREMENT`` par PNJ ;
        * hitbox (``collision_radius``) + ``RADIUS_INCREMENT`` par PNJ ;
        * vitesse (``speed``) + ``SPEED_INCREMENT`` par PNJ.

La croissance est conservée (pas de « régression ») :
    - après un reset de la transformation (``reset_monster2``) ;
    - après un changement de personnage ;
    - à chaque pas de dévoration supplémentaire.
"""
import unittest
import pygame

from game import Game
from player import RADIUS_INCREMENT, SCALE_INCREMENT, SPEED_INCREMENT
from .factories import (
    _write,
    fake_npc_data,
    fake_player_data,
    make_fake_background,
    make_fake_mask,
)
from .base import BaseTestCase


class TestEatNpc(BaseTestCase):
    """Dévoration des PNJ (boss) : contact -> disparition + croissance."""

    def setUp(self):
        font = pygame.font.SysFont("sans", 18)

        # Deux PNJ statiques à des positions connues, bien distancés
        # de l'autre et du centre (spawn).
        self.NPC1_POS = (150, 150)
        self.NPC2_POS = (800, 600)

        npc1 = fake_npc_data(
            self._tmp.name, self.fake_sheet_path,
            name="Vil1", behavior="static", pos=self.NPC1_POS,
            collision_radius=12)
        npc2 = fake_npc_data(
            self._tmp.name, self.fake_sheet_path,
            name="Vil2", behavior="static", pos=self.NPC2_POS,
            collision_radius=12)

        # Un seul personnage (joueur) ; base stats connues :
        # speed 220, scale 0.25, collision_radius 5.
        player_data = fake_player_data(
            self._tmp.name, self.fake_sheet_path,
            name="Tester", speed=220, scale=0.25, collision_radius=5)

        bg = _write(make_fake_background(), self._tmp.name, "bg.png")
        mask = _write(make_fake_mask(), self._tmp.name, "mask.png")

        maps = [
            {
                "name": "Map A",
                "background": bg,
                "mask": mask,
                "npcs": [npc1, npc2],
            }
        ]
        self.game = Game(
            self.screen, font, [player_data], maps,
            collisions_enabled=False, debug=False)

    def tearDown(self):
        self.game = None

    # ----------------------------------------------------------------------
    # Aides
    # ----------------------------------------------------------------------
    def _transform(self):
        """Lève le drapeau ``monster2_active`` et laisse une frame pour la
        synchronisation (sprite + vitesse + stats) du joueur-boss."""
        self.game.world.flag_set("monster2_active", True)
        self.game.update(0.016)

    def _move_to(self, pos, frames=1):
        """Positionne le joueur à ``pos`` puis lance ``frames`` frames."""
        self.game.player.x, self.game.player.y = float(pos[0]), float(pos[1])
        for _ in range(frames):
            self.game.update(0.016)

    # ----------------------------------------------------------------------
    # Tests
    # ----------------------------------------------------------------------
    def test_transformed_eat_removes_and_grows(self):
        """Transformé + contact -> PNJ disparu et joueur grossit (1 pas)."""
        base_scale = self.game.player.base_scale
        base_radius = self.game.player.collision_radius

        self._transform()
        self.assertTrue(self.game.world.flag_get("monster2_active"))
        self.assertTrue(self.game.player._monster2)
        self.assertEqual(self.game.player.eaten_count, 0)
        self.assertEqual(len(self.game.game_map.npcs), 2)

        # Base stats du boss (avant dévoration) : vitesse 180, pas encore
        # de croissance.
        self.assertEqual(self.game.player.speed, 180.0)
        self.assertAlmostEqual(self.game.player.base_scale, base_scale, places=6)
        self.assertAlmostEqual(self.game.player.collision_radius, base_radius,
                              places=6)

        # Contact avec le premier PNJ.
        self._move_to(self.NPC1_POS)

        self.assertEqual(self.game.player.eaten_count, 1)
        self.assertEqual(len(self.game.game_map.npcs), 1)
        remaining = self.game.game_map.npcs[0]
        self.assertEqual(remaining.name, "Vil2")

        # Croissance : +1 pas par PNJ.
        self.assertAlmostEqual(self.game.player.collision_radius,
                               base_radius + RADIUS_INCREMENT, places=6)
        self.assertAlmostEqual(self.game.player.speed,
                               180.0 + SPEED_INCREMENT, places=6)
        self.assertAlmostEqual(
            self.game.player.base_scale,
            base_scale * (1.0 + SCALE_INCREMENT), places=6)

        # Le PNJ mangé n'existe plus dans la donnée persistante.
        self.assertNotIn(
            "Vil1",
            [d.get("name") for d in self.game.world.maps[0].get("npcs", [])])

    def test_eating_is_cumulative(self):
        """Manger deux PNJ = deux pas de croissance (additionnés)."""
        base_scale = self.game.player.base_scale
        base_radius = self.game.player.collision_radius

        self._transform()
        self.assertEqual(self.game.player.eaten_count, 0)

        self._move_to(self.NPC1_POS)
        self._move_to(self.NPC2_POS)

        self.assertEqual(self.game.player.eaten_count, 2)
        self.assertEqual(len(self.game.game_map.npcs), 0)

        self.assertAlmostEqual(self.game.player.collision_radius,
                               base_radius + 2 * RADIUS_INCREMENT, places=6)
        self.assertAlmostEqual(self.game.player.speed,
                               180.0 + 2 * SPEED_INCREMENT, places=6)
        self.assertAlmostEqual(
            self.game.player.base_scale,
            base_scale * (1.0 + 2 * SCALE_INCREMENT), places=6)

    def test_not_transformed_does_not_eat(self):
        """Non transformé : le contact avec un PNJ ne le mange PAS
        (pas de disparition, pas de croissance)."""
        base_scale = self.game.player.base_scale
        base_radius = self.game.player.collision_radius
        base_speed = self.game.player.speed

        # Contact avec le PNJ sans transformer.
        self._move_to(self.NPC1_POS, frames=3)

        self.assertEqual(len(self.game.game_map.npcs), 2)
        self.assertEqual(self.game.player.eaten_count, 0)
        self.assertAlmostEqual(self.game.player.base_scale, base_scale,
                              places=6)
        self.assertAlmostEqual(self.game.player.collision_radius, base_radius,
                              places=6)
        self.assertEqual(self.game.player.speed, base_speed)

    def test_eaten_npc_does_not_reappear(self):
        """Un PNJ mangé ne reparaît pas si on quitte la carte (le
        changement de carte recharge la donnée persistante, qui ne
        contient plus le PNJ mangé)."""
        base_scale = self.game.player.base_scale

        self._transform()
        self._move_to(self.NPC1_POS)
        self.assertEqual(self.game.player.eaten_count, 1)
        self.assertEqual(len(self.game.game_map.npcs), 1)

        # Quitte la carte : on recharge la donnée persistante.
        # (Il n'y a qu'une carte dans ce monde ; on force un
        # rechargement via change_map sur le même index.)
        self.game.world.change_map(0, self.game.player)
        self.game.game_map = self.game.world.game_map
        self.game.update(0.016)

        # Vil1 ne reparaît PAS (il a été mangé).
        self.assertEqual(len(self.game.game_map.npcs), 1)
        self.assertEqual(self.game.game_map.npcs[0].name, "Vil2")

    def test_character_change_keeps_growth(self):
        """Changement de personnage : le boss conserve sa croissance
        (nombre de PNJ dévorés) — le nouveau personnage grossit."""
        base_scale = self.game.player.base_scale
        base_radius = self.game.player.collision_radius

        self._transform()
        self._move_to(self.NPC1_POS)
        self.assertEqual(self.game.player.eaten_count, 1)
        self.assertTrue(self.game.player._monster2)

        # Change de personnage : on recrée le Player avec le personnage
        # suivant et on re-propage la croissance (old_eaten). Ici il
        # n'y a qu'un seul personnage (index 0) -> changement circulaire.
        self.game._change_character()

        # La croissance est conservée (pas de régression).
        self.assertEqual(self.game.player.eaten_count, 1)
        self.assertAlmostEqual(
            self.game.player.base_scale,
            base_scale * (1.0 + SCALE_INCREMENT), places=6)
        self.assertAlmostEqual(
            self.game.player.collision_radius,
            base_radius + RADIUS_INCREMENT, places=6)

    def test_reset_monster2_keeps_growth(self):
        """``reset_monster2`` (transformation désactivée) : la croissance
        acquis est CONSERVÉE (pas de régression)."""
        base_scale = self.game.player.base_scale
        base_radius = self.game.player.collision_radius

        self._transform()
        self._move_to(self.NPC1_POS)
        self.assertEqual(self.game.player.eaten_count, 1)
        self.assertAlmostEqual(
            self.game.player.base_scale,
            base_scale * (1.0 + SCALE_INCREMENT), places=6)
        self.assertTrue(self.game.player._monster2)

        # Désactive la transformation (reset).
        self.game.world.flag_set("monster2_active", False)
        self._move_to(self.NPC2_POS, frames=2)

        # La croissance est conservée (pas de régression).
        self.assertEqual(self.game.player.eaten_count, 1)
        self.assertFalse(self.game.player._monster2)
        self.assertAlmostEqual(
            self.game.player.base_scale,
            base_scale * (1.0 + SCALE_INCREMENT), places=6)
        self.assertAlmostEqual(
            self.game.player.collision_radius,
            base_radius + RADIUS_INCREMENT, places=6)


if __name__ == "__main__":
    unittest.main()
