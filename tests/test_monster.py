"""Tests de monster.Monster : pathfinding A*, mouvement, transformation.

Ces tests gardent la régression principale du combat :
« le monstre se bloque / ne parvient pas à atteindre les bougies » (la
pathfinding A* ne trouvait pas de chemin vers le haut de la carte et le
monstre restait bloqué en haut-a-droite).

Couverts :
- Construction du monstre (position, vitesse, sprite).
- A* sur un masque synthétique (chemin autour d'obstacles, fin près de la
  cible, toutes les cases du chemin praticables).
- A* sur la VRAIE carte de combat : chemin vers CHAQUE des 5 bougies (y
  compris celles du haut), et toutes les cases du chemin praticables.
- Mouvement (move_towards) : le monstre progresse vers le joueur (distance
  décroissante) et finit par le toucher sur la vraie carte.
- Transformation monster2 (plus rapide + sprite monster2.png).

Notes :
- Le monstre ne nécessite AUCUN `character_data` : son sprite est chargé
  directement depuis `sprite_path` (voir monster.py). Les tests passent
  donc `sprite_path` directement.
- La pathfinding A* opère à la grille des cellules : pour que le monstre
  puisse se déplacer, sa case d'origine (centre) doit être praticable
  (rayon PATHFINDING_RADIUS). Les tests placent le monstre à une telle
  position (comme le fait le vrai jeu via `find_nearest_walkable`).
"""
import math
import unittest

import pygame

from settings import MAPS
from world import World
from player import Player
from monster import Monster, CELL_SIZE, PATHFINDING_RADIUS, MONSTER_SPRITE, MONSTER_SPRITE_FINAL

from .base import BaseTestCase, new_world
from .factories import build_fake_one_world, fake_player_data

# Index de la carte "Boss Combat" dans MAPS (le combat principal).
_BOSS_INDEX = [i for i, m in enumerate(MAPS) if m["name"] == "Boss Combat"][0]


def _player_data(tmp_dir, sheet_path):
    """Dict de personnage (format settings.CHARACTERS)."""
    return fake_player_data(tmp_dir, sheet_path)


class TestMonsterConstruction(BaseTestCase):
    """Attributs de base du monstre."""

    def _make(self, x, y, speed=55.0, **kw):
        return Monster(
            float(x), float(y), speed=float(speed),
            sprite_path=self.fake_sheet_path,
            **kw,
        )

    def test_defaults(self):
        m = self._make(400.0, 300.0)
        self.assertEqual(m.x, 400.0)
        self.assertEqual(m.y, 300.0)
        self.assertEqual(m.speed, 55.0)
        self.assertEqual(m.collision_radius, 12.0)
        self.assertEqual(m.hit_radius, 45.0)
        self.assertIsNone(m._path)
        self.assertEqual(m._path_time, 0.0)
        # Le sprite s'est bien chargé (4x3 frames).
        self.assertEqual(len(self._make(10, 10).sprites["face"]), 3)

    def test_custom_speed(self):
        m = self._make(10.0, 10.0, speed=180.0)
        self.assertEqual(m.speed, 180.0)


class TestMonsterAstarFakeMap(BaseTestCase):
    """A* sur un masque synthétique : chemin valide autour d'obstacles."""

    def setUp(self):
        # Mur vertical au milieu : le monstre doit passer dessus/en dessous.
        blocked = [(400, 100, 40, 500)]
        self.world = build_fake_one_world(self._tmp.name, blocked=blocked)
        self.gmap = self.world.game_map  # GameMap (can_stand_at), PAS la World
        self.m = self._make(100.0, 360.0)

    def _make(self, x, y, speed=55.0, **kw):
        return Monster(
            float(x), float(y), speed=float(speed),
            sprite_path=self.fake_sheet_path,
            **kw,
        )

    def test_path_finds_way_around_obstacle(self):
        """Chemin existe, passe autour du mur, fin près de la cible."""
        path = self.m._compute_path(800.0, 360.0, self.gmap)
        assert path is not None, "A* n'a rien trouvé — chemin impossible"
        self.assertGreater(len(path), 2, "chemin trop court")
        lx, ly = path[-1]
        self.assertLess(
            math.hypot(lx - 800.0, ly - 360.0),
            CELL_SIZE + 20,
            "le dernier waypoint est loin de la cible",
        )

    def test_all_path_cells_walkable(self):
        """Aucun waypoint ne tombe dans un obstacle."""
        path = self.m._compute_path(800.0, 360.0, self.gmap)
        assert path is not None
        for (px, py) in path:
            self.assertTrue(
                self.gmap.can_stand_at(px, py, PATHFINDING_RADIUS),
                f"case du chemin non praticable : ({round(px)},{round(py)})",
            )


class TestMonsterAstarRealMap(BaseTestCase):
    """A* sur la VRAIE carte de combat : atteindre les 5 bougies (régression)."""

    def setUp(self):
        self.world = new_world()
        self.player = Player(
            0.0, 0.0,
            _player_data(self._tmp.name, self.fake_sheet_path),
        )
        # Entremap de combat : le joueur est repositionné au spawn.
        ok = self.world.change_map(_BOSS_INDEX, self.player)
        self.assertTrue(ok, "échec à changer vers Boss Combat")
        self.gmap = self.world.game_map
        self.spawn = (self.player.x, self.player.y)

    def _candles(self):
        """Positions (x,y) des 5 bougies (action light_candle)."""
        return [
            (round(o["box"].centerx), round(o["box"].centery))
            for o in self.gmap.interact_objects
            if o.get("action") == "light_candle"
        ]

    def test_five_candles_exist(self):
        self.assertEqual(len(self._candles()), 5)

    def test_path_reaches_each_candle(self):
        """Le monstre (A*) peut atteindre CHAQUE bougie, y compris les hautes.
        C'est LA régression « bloqué en haut-a-droite »."""
        m = Monster(
            self.spawn[0], self.spawn[1], 55.0,
            sprite_path=self.fake_sheet_path,
        )
        for cx, cy in self._candles():
            path = m._compute_path(cx, cy, self.gmap)
            assert path is not None, (
                f"A* a échoué pour la bougie ({cx},{cy}) — régression « bloqué »"
            )
            self.assertGreater(len(path), 0, f"chemin vide pour ({cx},{cy})")
            lx, ly = path[-1]
            self.assertLess(
                math.hypot(lx - cx, ly - cy),
                CELL_SIZE + 20,
                f"le dernier point du chemin ({lx},{ly}) est trop loin de "
                f"la bougie ({cx},{cy})",
            )

    def test_path_cells_walkable_on_real_map(self):
        """Toutes les cases du chemin sont praticables (pas de passage au
        travers d'une bougie/mur)."""
        candles = self._candles()
        m = Monster(
            self.spawn[0], self.spawn[1], 55.0,
            sprite_path=self.fake_sheet_path,
        )
        path = m._compute_path(candles[0][0], candles[0][1], self.gmap)
        assert path is not None
        for (px, py) in path:
            self.assertTrue(
                self.gmap.can_stand_at(px, py, PATHFINDING_RADIUS),
                f"case non praticable ({round(px)},{round(py)})",
            )

    def test_top_candles_reachable(self):
        """Les bougies les plus hautes (y < 300) sont atteignables — le
        cas « bloqué en haut » qui posait problème."""
        top = [(cx, cy) for cx, cy in self._candles() if cy < 300]
        self.assertGreater(len(top), 0, "aucune bougie haute — inattendu")
        m = Monster(
            self.spawn[0], self.spawn[1], 55.0,
            sprite_path=self.fake_sheet_path,
        )
        for cx, cy in top:
            path = m._compute_path(cx, cy, self.gmap)
            self.assertIsNotNone(
                path,
                f"bougie haute ({cx},{cy}) inatteignable",
            )


class TestMonsterMovement(BaseTestCase):
    """Mouvement (move_towards) : progression vers le joueur, depuis le
    spawn réel du monstre (MONSTER_START ajusté), comme dans le jeu."""

    def _real_spawn_pos(self, gmap):
        """Position du monstre au spawn réel (rayon de collision = 12)."""
        from game import MONSTER_START
        sx, sy = MONSTER_START
        r = 12.0
        if not gmap.can_stand_at(sx, sy, r):
            sx, sy = gmap.find_nearest_walkable(sx, sy, r)
        return sx, sy

    def setUp(self):
        self.world = new_world()
        self.player = Player(
            0.0, 0.0,
            _player_data(self._tmp.name, self.fake_sheet_path),
        )
        self.world.change_map(_BOSS_INDEX, self.player)
        self.gmap = self.world.game_map
        sx, sy = self._real_spawn_pos(self.gmap)
        self.spawn = (sx, sy)
        self.monster = Monster(sx, sy, 55.0, sprite_path=self.fake_sheet_path)

    def test_astar_from_real_spawn(self):
        """A* trouve bien un chemin du spawn réel du monstre vers le joueur
        (le monstre n'est pas isolé)."""
        path = self.monster._compute_path(self.player.x, self.player.y, self.gmap)
        assert path is not None, "A* n'a pas de chemin depuis le spawn réel du monstre"
        self.assertGreater(len(path), 0, "chemin vide depuis le spawn réel")
        lx, ly = path[-1]
        self.assertLess(
            math.hypot(lx - self.player.x, ly - self.player.y),
            CELL_SIZE + 20,
            "le chemin ne termine pas près du joueur",
        )

    def test_monster_moves_and_closes_distance(self):
        """Le monstre progresse vers le joueur : sa position change et sa
        distance au joueur diminue (pas d'immobilité = régression)."""
        start = (self.monster.x, self.monster.y)
        start_d = math.hypot(self.monster.x - self.player.x,
                             self.monster.y - self.player.y)
        for _ in range(60 * 4):  # 4 s
            self.monster.move_towards(
                self.player.x, self.player.y, 1.0 / 60.0,
                self.gmap, self.player,
            )
        end = (self.monster.x, self.monster.y)
        end_d = math.hypot(self.monster.x - self.player.x,
                           self.monster.y - self.player.y)
        moved = (end[0] != start[0]) or (end[1] != start[1])
        self.assertTrue(moved, "monstre immobile — A*/mouvement cassés")
        self.assertLess(end_d, start_d, "monstre ne s'approche PAS du joueur")

    def test_monster_touches_player_on_real_map(self):
        """Sur la vraie carte, le monstre finit par toucher le joueur (pas
        d'immobilité : régression du blocage)."""
        dt = 1.0 / 60.0
        steps = 0
        touched = False
        while steps < 900 and not touched:  # 15 s max
            touched = self.monster.move_towards(
                self.player.x, self.player.y, dt, self.gmap, self.player,
            )
            steps += 1
        self.assertTrue(
            touched,
            "monstre n'a JAMAIS touché le joueur en 15 s — bloqué",
        )


class TestMonsterTransformation(BaseTestCase):
    """Transformation monster2 : plus rapide + sprite monster2.png."""

    def test_monster2_is_faster_and_different_sprite(self):
        """Le monstre final doit être plus rapide et porter le sprite
        monster2.png."""
        m_slow = Monster(
            400.0, 400.0,
            speed=55.0,
            sprite_path=str(MONSTER_SPRITE),
        )
        m_fast = Monster(
            400.0, 400.0,
            speed=180.0,
            sprite_path=str(MONSTER_SPRITE_FINAL),
        )
        self.assertGreater(m_fast.speed, m_slow.speed)
        self.assertNotEqual(str(m_slow.sprite_path), str(m_fast.sprite_path))
        self.assertTrue(str(MONSTER_SPRITE).endswith("monster.png"))
        self.assertTrue(str(MONSTER_SPRITE_FINAL).endswith("monster2.png"))

    def test_create_monster_respects_flag(self):
        """Via Game._create_monster : le drapeau monster2_active décide
        sprite/vitesse (la transformation après le trône)."""
        from game import Game
        from settings import CHARACTERS

        game = Game(
            self.screen,
            pygame.font.SysFont("sans", 18),
            CHARACTERS, MAPS,
            collisions_enabled=False,
            debug=False,
        )
        # Drapeau BAISSÉ -> monstre lent + monster.png
        game.world.flag_set("monster2_active", False)
        m1 = game._create_monster(400.0, 400.0)
        self.assertEqual(m1.speed, 55.0)
        self.assertTrue(str(m1.sprite_path).endswith("monster.png"))
        # Drapeau LEVÉ -> monstre rapide + monster2.png
        game.world.flag_set("monster2_active", True)
        m2 = game._create_monster(400.0, 400.0)
        self.assertEqual(m2.speed, 180.0)
        self.assertTrue(str(m2.sprite_path).endswith("monster2.png"))
        self.assertGreater(m2.speed, m1.speed)

    def test_set_sprite_switches_monster_to_monster2(self):
        """set_sprite() bascule le sprite (le mécanisme de transformation
        utilisé à la place du re-instantiation)."""
        m = Monster(
            400.0, 400.0,
            speed=55.0,
            sprite_path=str(MONSTER_SPRITE),
        )
        m.set_sprite(str(MONSTER_SPRITE_FINAL))
        self.assertTrue(str(m.sprite_path).endswith("monster2.png"))
        # Le sprite est bien rechargé (4x3 frames intactes).
        self.assertEqual(len(m.sprites["face"]), 3)


if __name__ == "__main__":
    unittest.main()
