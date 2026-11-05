"""Tests du flag debug (--debug) : overlay de collision + chemins de
déplacement des PNJ.

Quand un PNJ a des waypoints de patrouille (``path``), le flag debug
dessine :
    - le tracé fermé des segments (magenta) ;
    - les waypoints (petits points magenta) ;
    - le waypoint courant (point jaune, plus grand) ;
    - une flèche de la position actuelle vers le waypoint suivant.
Un PNJ sans path (statique/flee) ne produit aucun tracé magenta.
"""
import unittest
import pygame

from game import Game
from .factories import (
    _write,
    fake_npc_data,
    fake_player_data,
    make_fake_background,
    make_fake_mask,
)
from .base import BaseTestCase

# Couleur du tracé de patrouille (voir ``_draw_debug_overlay``).
PATROL_COLOR = (255, 0, 128)


class TestDebugOverlay(BaseTestCase):
    """Overlay de debug : le flag --debug dessine les déplacements des PNJ."""

    def _build_game(self, npcs, debug):
        """Crée un Game sur une carte fake avec ``npcs`` et le flag ``debug``."""
        font = pygame.font.SysFont("sans", 18)
        player_data = fake_player_data(
            self._tmp.name, self.fake_sheet_path,
            name="Tester", speed=220, scale=0.25, collision_radius=5)
        bg = _write(make_fake_background(), self._tmp.name, "bg.png")
        mask = _write(make_fake_mask(), self._tmp.name, "mask.png")
        maps = [{"name": "Map A", "background": bg, "mask": mask,
                 "npcs": npcs}]
        return Game(self.screen, font, [player_data], maps,
                    collisions_enabled=False, debug=debug)

    @staticmethod
    def _any_pixel_color(screen, x0, x1, y0, y1, color, tol=16):
        """True s'il y a au moins un pixel proche de ``color`` dans la zone."""
        rgb = color if len(color) == 3 else color[:3]
        r, g, b = rgb
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                pr, pg, pb, _ = screen.get_at((x, y))
                if abs(pr - r) <= tol and abs(pg - g) <= tol and abs(pb - b) <= tol:
                    return True
        return False

    def test_debug_overlay_draws_patrol_paths(self):
        """PNJ en patrouille -> le flag debug dessine son tracé (magenta)."""
        npc = fake_npc_data(
            self._tmp.name, self.fake_sheet_path,
            name="Patrouilleur", behavior="patrol", pos=[200, 200],
            points=[[200, 200], [400, 200], [400, 400]])
        g = self._build_game([npc], debug=True)
        g.render()
        # Le segment (200,200)-(400,200) doit contenir des pixels magenta.
        self.assertTrue(
            self._any_pixel_color(g.screen, 210, 390, 198, 202, PATROL_COLOR),
            "Aucun pixel magenta sur le tracé : le flag debug ne dessine pas "
            "les déplacements du PNJ en patrouille.")

    def test_no_path_no_magenta(self):
        """PNJ statique (pas de ``path``) -> aucun tracé magenta."""
        npc = fake_npc_data(
            self._tmp.name, self.fake_sheet_path,
            name="Statique", behavior="static", pos=[200, 200])
        g = self._build_game([npc], debug=True)
        g.render()
        self.assertFalse(
            self._any_pixel_color(g.screen, 190, 410, 190, 410, PATROL_COLOR),
            "Pixel magenta sur un PNJ statique (aucun déplacement).")

    def test_debug_off_no_patrol_magenta(self):
        """Sans le flag --debug -> pas de tracé magenta même avec patrouille."""
        npc = fake_npc_data(
            self._tmp.name, self.fake_sheet_path,
            name="Patrouilleur", behavior="patrol", pos=[200, 200],
            points=[[200, 200], [400, 200], [400, 400]])
        g = self._build_game([npc], debug=False)
        g.render()
        self.assertFalse(
            self._any_pixel_color(g.screen, 190, 410, 190, 410, PATROL_COLOR),
            "Tracé magenta visible sans le flag --debug.")


if __name__ == "__main__":
    unittest.main()
