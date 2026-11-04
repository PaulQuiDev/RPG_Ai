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
- Transformation monster2 (P4) : les constantes MONSTER_SPRITE_FINAL /
  MONSTER_SPEED2 et le mécanisme `set_sprite()` ; la transformation
  déclenchée par le trône est du JOUEUR (pas du monstre).

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
from monster import (
    Monster, CELL_SIZE, PATHFINDING_RADIUS, MONSTER_SPRITE, MONSTER_SPRITE_FINAL,
    STUCK_THRESHOLD, BACKUP_DISTANCE, RECOVERY_COOLDOWN,
)

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
        self.assertIsNone(m._path_anchor)
        self.assertEqual(m._last_heading, (0.0, 0.0))
        self.assertEqual(m._stuck_since, 0.0)
        self.assertEqual(m._recovery_cooldown, 0.0)
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

    def test_create_monster_always_normal(self):
        """Via Game._create_monster (P4) : le drapeau monster2_active
        transforme le JOUEUR, PAS le monstre. Le monstre créé est TOUJOURS
        normal (monster.png, MONSTER_SPEED) — peu importe le drapeau."""
        from game import Game
        from settings import CHARACTERS

        game = Game(
            self.screen,
            pygame.font.SysFont("sans", 18),
            CHARACTERS, MAPS,
            collisions_enabled=False,
            debug=False,
        )
        # Drapeau BAISSÉ -> monstre normal (monster.png, MONSTER_SPEED).
        game.world.flag_set("monster2_active", False)
        m1 = game._create_monster(400.0, 400.0)
        self.assertEqual(m1.speed, 55.0)
        self.assertTrue(str(m1.sprite_path).endswith("monster.png"))
        # Drapeau LEVÉ -> le monstre reste normal (P4 : pas de
        # transformation du monstre — la transformation est du JOUEUR).
        game.world.flag_set("monster2_active", True)
        m2 = game._create_monster(400.0, 400.0)
        self.assertEqual(m2.speed, 55.0)
        self.assertTrue(str(m2.sprite_path).endswith("monster.png"))
        self.assertEqual(m2.speed, m1.speed)

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


class TestMonsterRecovery(BaseTestCase):
    """P2 : le monstre ne doit pas rester coincé dans un obstacle.

    Le débloquage (recul / pousser) se déclenche quand le monstre ne
    progresse plus pendant `STUCK_THRESHOLD`. On teste les pièces
    (`_is_stuck` / `_back_up` / `_unstick`) et le chemin complet
    (`move_towards`).
    """

    def setUp(self):
        # Mur vertical : x ∈ [400, 440], y ∈ [100, 600].
        self.world = build_fake_one_world(
            self._tmp.name, blocked=[(400, 100, 40, 500)]
        )
        self.gmap = self.world.game_map  # GameMap (can_stand_at), PAS la World
        self.m = Monster(100.0, 300.0, 55.0, sprite_path=self.fake_sheet_path)

    @staticmethod
    def _fake_player(x, y):
        class _FakePlayer:
            def __init__(self):
                self.x = float(x)
                self.y = float(y)

        return _FakePlayer()

    def test_is_stuck(self):
        """_is_stuck : bloqué seulement si pas au contact ET refroidissement
        écoulé."""
        self.m.x, self.m.y = 100.0, 300.0
        # Loin du joueur (320 px > hit_radius).
        self.m._stuck_since = 0.0
        self.m._recovery_cooldown = 0.0
        self.assertFalse(self.m._is_stuck(500.0, 300.0, self.gmap))  # pas encore
        self.m._stuck_since = STUCK_THRESHOLD
        self.assertTrue(self.m._is_stuck(500.0, 300.0, self.gmap))   # bloqué
        # Le refroidissement bloque la réactivation.
        self.m._recovery_cooldown = RECOVERY_COOLDOWN
        self.assertFalse(self.m._is_stuck(500.0, 300.0, self.gmap))
        # Au contact du joueur : on n'est pas bloqué (objectif atteint),
        # et le timer est remis à 0.
        self.m._recovery_cooldown = 0.0
        self.m._stuck_since = STUCK_THRESHOLD
        self.assertFalse(self.m._is_stuck(140.0, 300.0, self.gmap))  # 40 px
        self.assertEqual(self.m._stuck_since, 0.0)

    def test_back_up(self):
        """_back_up : recul (inverse du heading) vers une case praticable."""
        self.m.x, self.m.y = 360.0, 300.0  # à côté du mur, pratique
        self.assertTrue(
            self.gmap.can_stand_at(self.m.x, self.m.y, self.m.collision_radius)
        )
        self.m._last_heading = (1.0, 0.0)  # avançait vers l'Est (vers le mur)
        old = (self.m.x, self.m.y)
        self.assertTrue(self.m._back_up(self.gmap))  # le recul doit réussir
        self.assertNotEqual((self.m.x, self.m.y), old)
        self.assertTrue(
            self.gmap.can_stand_at(self.m.x, self.m.y, self.m.collision_radius)
        )
        # Le recul suit le sens inverse (Est -> Ouest) : x diminue.
        self.assertLess(self.m.x, old[0])

    def test_unstick_snap_out_of_wall(self):
        """Monstre DANS un mur -> _unstick le snap vers une case pratique
        et re-calcule le chemin."""
        self.m.x, self.m.y = 420.0, 300.0  # dans le mur
        self.assertFalse(
            self.gmap.can_stand_at(420.0, 300.0, self.m.collision_radius)
        )
        old = (self.m.x, self.m.y)
        self.m._unstick(100.0, 300.0, self.gmap)
        self.assertTrue(
            self.gmap.can_stand_at(self.m.x, self.m.y, self.m.collision_radius),
            "après _unstick, le monstre doit être sur une case pratique",
        )
        self.assertNotEqual((self.m.x, self.m.y), old)

    def test_move_towards_unsticks(self):
        """move_towards : le monstre coincé (pas de mouvement) est débloqué
        au premier appel et progresse vers le joueur."""
        self.m.x, self.m.y = 420.0, 300.0  # dans le mur
        player = self._fake_player(100.0, 300.0)  # loin
        # Simule "pas de mouvement pendant > STUCK_THRESHOLD".
        self.m._stuck_since = STUCK_THRESHOLD + 1.0
        self.m._recovery_cooldown = 0.0
        self.m._last_heading = (1.0, 0.0)
        self.m._path = []
        before = (self.m.x, self.m.y)
        self.assertFalse(self.gmap.can_stand_at(*before, self.m.collision_radius))
        self.m.move_towards(100.0, 300.0, 1.0 / 60.0, self.gmap, player)
        after = (self.m.x, self.m.y)
        # Le monstre est sorti du mur (case pratique).
        self.assertTrue(self.gmap.can_stand_at(*after, self.m.collision_radius))
        self.assertNotEqual(after, before)
        # Et il a commencé à s'approcher du joueur (le débloquage a
        # déverrouillé le chemin).
        old_d = math.hypot(before[0] - 100.0, before[1] - 300.0)
        new_d = math.hypot(after[0] - 100.0, after[1] - 300.0)
        self.assertLessEqual(new_d, old_d + 10.0)

    def test_stuck_timer_resets_on_movement(self):
        """_stuck_since ne s'initialise que quand le monstre bouge."""
        self.m.x, self.m.y = 100.0, 300.0  # terrain libre (à gauche du mur)
        self.m._stuck_since = 1.0
        self.assertTrue(
            self.gmap.can_stand_at(self.m.x, self.m.y, self.m.collision_radius)
        )
        self.m._path = []
        self.m.move_towards(200.0, 300.0, 1.0 / 30.0, self.gmap,
                            self._fake_player(200.0, 300.0))
        # Le monstre a avancé -> le timer a été remis à 0.
        self.assertEqual(self.m._stuck_since, 0.0)
        self.assertNotEqual(
            (self.m.x, self.m.y), (100.0, 300.0),
            "le monstre doit avancer vers le joueur",
        )


if __name__ == "__main__":
    unittest.main()
