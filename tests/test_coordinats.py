"""Tests du testeur de précision des coordonnées (`map_editor.py`).

Vérifie `verify_coordinates()` :
  * structure et cohérence des compteurs du rapport ;
  * limites de fenêtre (une pos hors bornes => erreur) ;
  * pixel « objet bleu » (critère b>100, g>50, r<60) ;
  * précision de la peinture à un clic (le pixel image cible est atteint) ;
  * cohérence du round-trip écran↔fenêtre (éditeur ↔ jeu) ;
  * la CLI `--headless --verify` sort 0 et affiche le rapport.
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

import pygame

from map_editor import MapEditor
from settings import ADVENTURES_DIR, DEFAULT_ADVENTURE


class TestVerifyCoordinates(unittest.TestCase):
    """Le testeur est lancé tête-à-queue et inspecté."""

    @classmethod
    def setUpClass(cls):
        # Driver dummy par défaut (avant toute initialisation pygame) pour
        # rester indépendant du display du reste de la suite.
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

    def setUp(self):
        if not pygame.display.get_init():
            pygame.init()
        self.adv = str(ADVENTURES_DIR / (DEFAULT_ADVENTURE + ".json"))
        self.editor = MapEditor(self.adv, headless=True)

    def tearDown(self):
        self.editor.running = False

    def verify(self):
        return self.editor.verify_coordinates()

    def test_counts_are_consistent(self):
        res = self.verify()
        c = res["counts"]
        self.assertEqual(c["maps"], 4)
        self.assertEqual(c["objects"], len(res["items"]))
        self.assertEqual(c["paint"], len(res["paint"]))
        self.assertEqual(c["errors"], len(res["errors"]))
        self.assertEqual(c["warnings"], len(res["warnings"]))
        self.assertEqual(c["objects"], 9)    # Village 1 + Forêt 2 + Boss 5 + PostCombat 1
        self.assertEqual(c["paint"], 12)     # 3 points x 4 cartes

    def test_round_trip_coherent(self):
        """Aucune erreur de round-trip écran↔fenêtre (cohérence éditeur/jeu)."""
        res = self.verify()
        rt = sum(1 for e in res["errors"] if "round-trip" in e)
        self.assertEqual(rt, 0)

    def test_paint_tests_land_on_target_pixel(self):
        """Chaque test peinture atterrit au pixel image prévu (ok=True)."""
        res = self.verify()
        for p in res["paint"]:
            self.assertTrue(p["ok"], p)
            self.assertEqual(len(p["orig"]), 2)
            self.assertEqual(len(p["screen"]), 2)

    def test_items_keys_and_types(self):
        res = self.verify()
        keys = ("index", "map", "name", "action", "pos", "in_bounds",
                "in_orig", "is_blue", "orig", "screen", "error", "warning")
        for it in res["items"]:
            for k in keys:
                self.assertIn(k, it, f"manque {k!r} dans l'objet")
            self.assertEqual(len(it["orig"]), 2)
            self.assertEqual(len(it["screen"]), 2)
            self.assertIsInstance(it["pos"], list)
            self.assertIsInstance(it["is_blue"], bool)

    def test_objects_within_window(self):
        """Tous les objets de la default aventure sont dans la fenêtre."""
        res = self.verify()
        for it in res["items"]:
            self.assertTrue(it["in_bounds"], it)
            self.assertTrue(it["in_orig"], it)

    def test_known_blue_objects_detected(self):
        """Les objets « bleu traversable » sont détectés is_blue=True."""
        res = self.verify()
        blues = [it for it in res["items"] if it["is_blue"]]
        self.assertGreater(len(blues), 0, "Aucun objet bleu détecté")

    def test_non_blue_flag_object_is_warned(self):
        """Le Trône (flag, pas pixel bleu) génère une avert., pas une erreur."""
        res = self.verify()
        throne = next((it for it in res["items"] if it["name"] == "Trône"), None)
        self.assertIsNotNone(throne, "objet Trône absent")
        self.assertFalse(throne["is_blue"])
        self.assertTrue(throne["warning"], throne)
        self.assertFalse(throne["error"])

    def test_out_of_bounds_is_an_error(self):
        """Une pos hors limites fenêtre => erreur détectée."""
        first = self.editor.data["maps"][0]
        orig_inter = list(first.get("interactions") or [])
        first["interactions"].append({"pos": [1500, 1500],
                                      "name": "Hors limites",
                                      "action": "x"})
        try:
            res = self.verify()
        finally:
            first["interactions"] = orig_inter
        self.assertTrue(
            any("hors limites fenêtre" in e for e in res["errors"]))

    def test_is_interactive_px_synthetic(self):
        """Critère bleu (b>100, g>50, r<60) sur un masque synthétique."""
        surf = pygame.Surface((20, 20))
        surf.fill((0, 0, 0))
        pygame.draw.circle(surf, (0, 112, 255), (10, 10), 6)  # bleu objet
        pygame.draw.circle(surf, (0, 255, 0), (18, 18), 3)    # vert pur (b=0)
        pygame.draw.circle(surf, (255, 255, 0), (2, 2), 3)    # jaune (r>60)
        self.assertTrue(self.editor._is_interactive_px(10, 10, surf))
        self.assertFalse(self.editor._is_interactive_px(0, 0, surf))   # noir
        self.assertFalse(self.editor._is_interactive_px(18, 18, surf)) # vert pur
        self.assertFalse(self.editor._is_interactive_px(2, 2, surf))   # jaune
        self.assertFalse(self.editor._is_interactive_px(100, 0, surf)) # hors bornes

    def test_report_text(self):
        res = self.verify()
        self.assertIn("TESTEUR COORDONNÉES", res["report"])
        self.assertIn("COHERENT", res["report"].upper())

    def test_cli_headless_exit(self):
        """CLI --headless --verify sort 0 et affiche le rapport."""
        repo = str(Path(__file__).parent.parent)
        out = subprocess.run(
            [sys.executable, "map_editor.py", "--headless", "--verify"],
            cwd=repo, capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("TESTEUR COORDONNÉES", out.stdout)


if __name__ == "__main__":
    unittest.main()
