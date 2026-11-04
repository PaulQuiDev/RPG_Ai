"""Tests de npc.Npc : construction, statique, patrouille, collision,
interaction, affichage. Solutions génériques (masques/sheets synthétiques)."""
import unittest

from .base import BaseTestCase
from .factories import (
    build_fake_one_world,
    build_fake_two_worlds,
    fake_player_data,
    fake_npc_data,
)
from .pygame_setup import write_sheet, make_sheet
from settings import (
    NPC_CONTACT_RADIUS,
    NPC_DEFAULT_COLLISION_RADIUS,
    NPC_DEFAULT_SPEED,
    NPC_INTERACT_COOLDOWN,
)
from npc import Npc
from player import Player


class TestNpcConstruction(BaseTestCase):
    """__init__ : validation des champs + valeurs par défaut."""

    def _base(self, **kw):
        data = {
            "name": "T",
            "sprite": self.fake_sheet_path,
            "pos": [400.0, 360.0],
        }
        data.update(kw)
        return data

    def test_requires_name(self):
        with self.assertRaises(ValueError):
            Npc({"sprite": self.fake_sheet_path, "pos": [400, 360]}, 0)

    def test_requires_sprite(self):
        with self.assertRaises(ValueError):
            Npc({"name": "T", "pos": [400, 360]}, 0)

    def test_requires_pos_non_patrol(self):
        with self.assertRaises(ValueError):
            Npc({"name": "T", "sprite": self.fake_sheet_path}, 0)

    def test_patrol_requires_points(self):
        with self.assertRaises(ValueError):
            Npc(
                {
                    "name": "T",
                    "sprite": self.fake_sheet_path,
                    "behavior": "patrol",
                    "pos": [400, 360],
                },
                0,
            )

    def test_patrol_start_at_first_waypoint(self):
        npc = Npc(
            {
                "name": "T",
                "sprite": self.fake_sheet_path,
                "behavior": "patrol",
                "points": [[400.0, 360.0], [500.0, 400.0]],
            },
            0,
        )
        self.assertEqual((npc.x, npc.y), (400.0, 360.0))
        self.assertEqual(npc.path, [(400.0, 360.0), (500.0, 400.0)])
        self.assertEqual(npc.path_index, 0)

    def test_defaults(self):
        npc = Npc(self._base(), 0)
        self.assertEqual(npc.behavior, "static")
        self.assertEqual(npc.speed, NPC_DEFAULT_SPEED)
        self.assertEqual(npc.collision_radius, NPC_DEFAULT_COLLISION_RADIUS)
        self.assertTrue(npc.collide)
        self.assertEqual(npc.interact_cooldown, 0.0)
        self.assertTrue(npc.can_interact())
        self.assertFalse(npc.in_contact(None))
        self.assertEqual(len(npc.frames["face"]), 3)
        self.assertEqual(len(npc.frames["gauche"]), 3)


class TestNpcUpdate(BaseTestCase):
    """update / _patrol : statique immobile, patrouille avance."""

    def setUp(self):
        self.world = build_fake_one_world(self._tmp.name)
        self.game_map = self.world.game_map
        self.player = Player(
            100.0, 100.0, fake_player_data(self._tmp.name, self.fake_sheet_path)
        )

    def test_static_does_not_move(self):
        npc = Npc(self.fake_npc_static(), 0)
        self.game_map.npcs.append(npc)
        before = (npc.x, npc.y)
        for _ in range(60):
            self.game_map.update_npcs(1.0 / 60.0, self.player)
        self.assertEqual((npc.x, npc.y), before)

    def test_patrol_moves_towards_waypoint(self):
        npc = Npc(self.fake_patrol([[400.0, 360.0], [600.0, 360.0]]), 0)
        self.game_map.npcs.append(npc)
        before_x = npc.x
        for _ in range(30):
            self.game_map.update_npcs(1.0 / 60.0, self.player)
        self.assertGreater(npc.x, before_x)

    def test_patrol_bounces_between_waypoints(self):
        npc = Npc(self.fake_patrol([[400.0, 360.0], [500.0, 360.0]], speed=500.0), 0)
        self.game_map.npcs.append(npc)
        for _ in range(90):
            self.game_map.update_npcs(1.0 / 60.0, self.player)
        # il oscille entre les deux waypoints (400 et 500)
        self.assertGreaterEqual(npc.x, 390.0)
        self.assertLessEqual(npc.x, 510.0)

    def test_static_updates_cooldown(self):
        npc = Npc(self.fake_npc_static(), 0)
        self.game_map.npcs.append(npc)
        npc.interact_cooldown = NPC_INTERACT_COOLDOWN
        self.game_map.update_npcs(NPC_INTERACT_COOLDOWN + 1.0, self.player)
        self.assertTrue(npc.can_interact())

    def test_patrol_ne_passe_pas_dans_un_mur(self):
        world = build_fake_one_world(
            self._tmp.name, blocked=[(400.0, 300.0, 120.0, 120.0)]
        )
        self.game_map = world.game_map
        self.player = Player(
            100.0, 100.0, fake_player_data(self._tmp.name, self.fake_sheet_path)
        )
        npc = Npc(
            self.fake_patrol([[100.0, 360.0], [800.0, 360.0]], speed=400.0), 0
        )
        self.game_map.npcs.append(npc)
        for _ in range(180):
            self.game_map.update_npcs(1.0 / 60.0, self.player)
        self.assertTrue(
            self.game_map.can_stand_at(
                npc.x, npc.y, npc.collision_radius, ignore=npc
            ),
            f"le NPC finit coincé dans le mur : ({npc.x:.0f},{npc.y:.0f})",
        )

    def fake_npc_static(self):
        return fake_npc_data(self._tmp.name, self.fake_sheet_path, name="T")

    def fake_patrol(self, points, speed=300.0):
        return fake_npc_data(
            self._tmp.name, self.fake_sheet_path, name="P",
            behavior="patrol", points=points, speed=speed,
            pos=points[0],
        )


class TestNpcEdgeClamp(BaseTestCase):
    """Marge du bord (solution globale) : le PNJ est clampé pour que
    son **sprite** (pas ses pieds) soit toujours entièrement visible.
    Ancien bug : clamp fixe à 5.0 px, le sprite (~100x150 px) était
    clipé au bord haut/latéral -> le PNJ « disparaissait ».
    """

    def setUp(self):
        self.world = build_fake_one_world(self._tmp.name)
        self.game_map = self.world.game_map
        self.player = Player(
            100.0, 100.0, fake_player_data(self._tmp.name, self.fake_sheet_path)
        )

    def _static_at(self, x, y):
        npc = Npc(
            fake_npc_data(self._tmp.name, self.fake_sheet_path, name="E",
                          pos=[float(x), float(y)]),
            0,
        )
        self.game_map.npcs.append(npc)
        return npc

    def _sprite_in_view(self, npc, wmap):
        """True si le sprite (avec offset d'anchor) est entièrement à
        l'intérieur de la fenêtre (aucun clipping par le bord)."""
        y = npc.y
        persp = wmap.get_perspective_scale(y)
        fscale = npc.base_scale * persp
        ref = npc.frames["face"][0]
        sw, sh = ref.get_width() * fscale, ref.get_height() * fscale
        ax, ay = npc.anchor_offsets.get(npc.direction, (0, 0))
        tl_x = npc.x - sw / 2.0 + ax * fscale
        tl_y = npc.y - sh + ay * fscale
        return (
            tl_x >= -1.0
            and tl_x + sw <= wmap.width + 1.0
            and tl_y >= -1.0
            and tl_y + sh <= wmap.height + 1.0
        )

    def test_static_clamped_at_top(self):
        npc = self._static_at(self.game_map.width / 2.0, 1.0)
        self.game_map.update_npcs(0.1, self.player)
        self.assertTrue(self._sprite_in_view(npc, self.game_map))
        # La marge top est strictement > 5 (le haut du sprite n'est pas clipé).
        self.assertGreater(npc.y, 5.0)

    def test_static_clamped_at_bottom(self):
        npc = self._static_at(self.game_map.width / 2.0, self.game_map.height - 0.5)
        self.game_map.update_npcs(0.1, self.player)
        self.assertTrue(self._sprite_in_view(npc, self.game_map))

    def test_static_clamped_at_left(self):
        npc = self._static_at(1.0, self.game_map.height / 2.0)
        self.game_map.update_npcs(0.1, self.player)
        self.assertTrue(self._sprite_in_view(npc, self.game_map))
        self.assertGreater(npc.x, 5.0)

    def test_static_clamped_at_right(self):
        npc = self._static_at(self.game_map.width - 0.5, self.game_map.height / 2.0)
        self.game_map.update_npcs(0.1, self.player)
        self.assertTrue(self._sprite_in_view(npc, self.game_map))
        self.assertLess(npc.x, self.game_map.width - 5.0)

    def test_corners_all_visible(self):
        """Les 4 coins : le sprite est entièrement visible
        (plus de « PNJ qui disparaît » au coin)."""
        w, h = self.game_map.width, self.game_map.height
        corners = [(1, 1), (w - 1, 1), (1, h - 1), (w - 1, h - 1)]
        for (x, y) in corners:
            npc = self._static_at(x, y)
            self.game_map.update_npcs(0.1, self.player)
            self.assertTrue(
                self._sprite_in_view(npc, self.game_map),
                f"sprite du PNJ clipé au coin ({round(x)},{round(y)}) : "
                f"pos=({round(npc.x)},{round(npc.y)})",
            )
        # on nettoie pour ne pas polluer les autres tests
        self.game_map.npcs.clear()

    def test_patrol_keeps_sprite_visible(self):
        """Un NPC en **patrouille** qui passe près d'un bord reste visible
        (pas de clipping)."""
        w, h = self.game_map.width, self.game_map.height
        npc = Npc(
            fake_npc_data(
                self._tmp.name, self.fake_sheet_path, name="P",
                behavior="patrol",
                points=[(1.0, h / 2.0), (w - 1.0, h / 2.0)],
                speed=300.0,
                pos=[1.0, h / 2.0],
            ),
            0,
        )
        self.game_map.npcs.append(npc)
        for _ in range(120):
            self.game_map.update_npcs(1.0 / 60.0, self.player)
        self.assertTrue(
            self._sprite_in_view(npc, self.game_map),
            f"sprite du NPC en patrouille clipé : pos=({round(npc.x)},{round(npc.y)})",
        )
        self.game_map.npcs.clear()


class TestNpcCollision(BaseTestCase):
    """can_stand_at tient compte des NPC (rayon + collision_radius)."""

    def setUp(self):
        self.world = build_fake_one_world(self._tmp.name)
        self.game_map = self.world.game_map
        self.player = Player(
            480.0, 360.0, fake_player_data(self._tmp.name, self.fake_sheet_path)
        )
        self.npc = Npc(
            {
                "name": "T",
                "sprite": self.fake_sheet_path,
                "pos": [480.0, 360.0],
            },
            0,
        )
        self.game_map.npcs.append(self.npc)

    def test_can_stand_at_blocked_by_npc(self):
        self.assertFalse(self.game_map.can_stand_at(480.0, 360.0, 5.0))
        self.assertTrue(self.game_map.can_stand_at(100.0, 100.0, 5.0))

    def test_can_stand_at_ignore_npc(self):
        self.assertTrue(
            self.game_map.can_stand_at(480.0, 360.0, 5.0, ignore=self.npc)
        )

    def test_player_cannot_stand_on_npc(self):
        # le joueur (rayon 5) ne peut pas se placer sur un NPC collé
        self.npc.collision_radius = 40.0
        self.assertFalse(self.game_map.can_stand_at(485.0, 360.0, 5.0))


class TestNpcInteraction(BaseTestCase):
    """in_contact, can_interact, cooldown, action (go_forest/go_village)."""

    def setUp(self):
        # deux cartes Village(0)/Forêt(1) pour tester le changement de carte
        self.world = build_fake_two_worlds(
            self._tmp.name, name_a="Village", name_b="Forêt"
        )
        self.game_map = self.world.game_map
        self.player = Player(
            480.0, 360.0, fake_player_data(self._tmp.name, self.fake_sheet_path)
        )

    def _npc_at_contact(self, **kw):
        # joueur et NPC au même point => au contact
        npc = Npc(
            fake_npc_data(
                self._tmp.name, self.fake_sheet_path, name="T",
                pos=[480.0, 360.0], **kw,
            ),
            0,
        )
        self.game_map.npcs.append(npc)
        return npc

    def test_not_in_contact_returns_false(self):
        npc = Npc(
            fake_npc_data(
                self._tmp.name, self.fake_sheet_path, name="T",
                pos=[900.0, 900.0],
            ),
            0,
        )
        self.assertFalse(npc.in_contact(self.player))

    def test_in_contact_within_radius(self):
        npc = self._npc_at_contact()
        self.assertTrue(npc.in_contact(self.player))

    def test_default_message_no_map_change(self):
        npc = self._npc_at_contact()
        changed = npc.interact(self.player, self.world, self.game_map)
        self.assertFalse(changed)
        self.assertEqual(self.world.map_index, 0)
        self.assertEqual(self.world.current_map_data["name"], "Village")
        self.assertGreater(npc.interact_cooldown, 0.0)
        self.assertFalse(npc.can_interact())

    def test_cooldown_blocks_second_immediate_interact(self):
        npc = self._npc_at_contact()
        npc.interact(self.player, self.world, self.game_map)
        # 2e NPC au même point : son cooldown est encore 0, mais le
        # premier a été utilisé ; on vérifie le cooldown du 2e après un reset
        npc2 = self._npc_at_contact()
        self.assertTrue(npc2.can_interact())
        npc2.interact(self.player, self.world, self.game_map)
        self.assertFalse(npc2.can_interact())
        # après expiration : re-disponible
        npc2.interact_cooldown = 0.0
        self.assertTrue(npc2.can_interact())

    def test_goforest_changes_to_foret(self):
        npc = self._npc_at_contact(action="go_forest", message="Bois !")
        changed = npc.interact(self.player, self.world, self.game_map)
        self.assertTrue(changed)
        self.assertEqual(self.world.map_index, 1)
        self.assertEqual(self.world.current_map_data["name"], "Forêt")

    def test_govillage_stays_in_village(self):
        npc = self._npc_at_contact(action="go_village")
        changed = npc.interact(self.player, self.world, self.game_map)
        self.assertTrue(changed)
        self.assertEqual(self.world.map_index, 0)
        self.assertEqual(self.world.current_map_data["name"], "Village")

    def test_unknown_action_no_change(self):
        npc = self._npc_at_contact(action="action_inconnue_inexistante")
        changed = npc.interact(self.player, self.world, self.game_map)
        self.assertFalse(changed)
        self.assertEqual(self.world.map_index, 0)


class TestNpcDraw(BaseTestCase):
    """draw : ne lève pas d'exception, halo au contact."""

    def setUp(self):
        self.world = build_fake_one_world(self._tmp.name)
        self.game_map = self.world.game_map
        self.npc = Npc(
            fake_npc_data(
                self._tmp.name, self.fake_sheet_path, name="T",
                pos=[480.0, 360.0],
            ),
            0,
        )

    def test_draw_static_no_raise(self):
        self.npc.draw(self.screen, self.game_map)

    def test_draw_with_player_no_raise(self):
        player = Player(
            480.0, 360.0, fake_player_data(self._tmp.name, self.fake_sheet_path)
        )
        self.npc.draw(self.screen, self.game_map, player)

    def test_draw_forced_directions_no_raise(self):
        for d in ("face", "gauche", "droite", "dos"):
            self.npc.direction = d
            self.npc.moving = True
            self.npc.anim_index = 0
            self.npc.draw(self.screen, self.game_map)
