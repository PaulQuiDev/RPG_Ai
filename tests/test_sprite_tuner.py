"""Tests de tuner : logique pure (lecture/écriture des overrides) et
GUI (instantiation, si DISPLAY dispo).

La logique pure est testable SANS GUI (pas de fenêtre tkinter requise pour
`load_overrides` / `save_overrides` / `save_tuned` / `list_characters` /
`read_character_config` / `cell_bounds` / `_clamp_rect`).
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.base import BaseTestCase
from tests.pygame_setup import init_display

import settings
from settings import CROP_SIZE, DIRECTIONS, MAPS, CHARACTERS

import tuner


class TestListCharacters(unittest.TestCase):
    """list_characters : joueur + NPC, dédupliqué par nom."""

    def test_contient_joueurs(self):
        names = {n for n, _, _ in tuner.list_characters()}
        for ch in CHARACTERS:
            self.assertIn(ch["name"], names)

    def test_contient_npcs(self):
        names = {n for n, _, _ in tuner.list_characters()}
        all_npc_names = {npc["name"] for m in MAPS for npc in m.get("npcs", [])}
        for name in all_npc_names:
            self.assertIn(name, names)

    def test_kinds_et_paths(self):
        for name, kind, sprite in tuner.list_characters():
            self.assertIn(kind, ("joueur", "npc"))
            self.assertTrue(isinstance(sprite, str), f"path non str : {name}")
            self.assertNotEqual(name, "")

    def test_pas_de_doublons_par_nom(self):
        # "Monster" est joueur et NPC : dédupliqué par nom.
        names = [n for n, _, _ in tuner.list_characters()]
        self.assertEqual(len(names), len(set(names)), "doublons détectés")


class TestReadCharacterConfig(unittest.TestCase):
    def test_joueur(self):
        name, data, kind = tuner.read_character_config("Femme")
        self.assertEqual(name, "Femme")
        self.assertEqual(data, CHARACTERS[0])
        self.assertEqual(kind, "joueur")

    def test_npc(self):
        name = MAPS[0]["npcs"][0]["name"]
        data = tuner.read_character_config(name)
        self.assertIsNotNone(data)
        self.assertEqual(data[2], "npc")
        self.assertEqual(data[1]["name"], name)

    def test_inconnu(self):
        self.assertIsNone(tuner.read_character_config("Inexistant_XXX"))


class TestCellBounds(unittest.TestCase):
    """cell_bounds : bornes d'une cellule (x0, y0, x1, y1)."""

    def test_grid_200x300(self):
        for row, direction in enumerate(list(DIRECTIONS)):
            for col in range(3):
                x0, y0, x1, y1 = tuner.cell_bounds(600, 1200, direction, col)
                self.assertEqual(x1 - x0, 200)
                self.assertEqual(y1 - y0, 300)
                self.assertEqual(x0, col * 200)
                self.assertEqual(y0, row * 300)

    def test_cellule_centre(self):
        # face[1] sur feuille 600x1200 => (200, 0, 400, 300).
        self.assertEqual(tuner.cell_bounds(600, 1200, "face", 1), (200, 0, 400, 300))


class TestClampRect(unittest.TestCase):
    """_clamp_rect : clamp un rect (x,y,w,h) dans un cell (x0,y0,x1,y1)."""

    def test_dans_le_bounds_invariant(self):
        # Rect entièrement à l'intérieur du cell => inchangé.
        self.assertEqual(
            tuner._clamp_rect((50, 10, 50, 50), (0, 0, 200, 300)), (50, 10, 50, 50)
        )

    def test_déborde_reduit_au_cell(self):
        # Rect plus grand que le cell => réduit à la taille du cell, ancré.
        r = tuner._clamp_rect((150, 250, 300, 300), (0, 0, 200, 300))
        self.assertEqual(r, (0, 0, 200, 300))
        self.assertTrue(0 <= r[0] + r[2] <= 200)
        self.assertTrue(0 <= r[1] + r[3] <= 300)

    def test_négatif_revenant_dans_le_cell(self):
        self.assertEqual(
            tuner._clamp_rect((-5, -5, 150, 100), (0, 0, 200, 300)), (0, 0, 150, 100)
        )


class TestToJSONDict(unittest.TestCase):
    def test_int_keys_to_str(self):
        obj = {"face": {0: (200, 300), 1: (210, 260)}}
        self.assertEqual(tuner._to_json_dict(obj),
                         {"face": {"0": [200, 300], "1": [210, 260]}})

    def test_non_dict_ignoré(self):
        self.assertEqual(tuner._to_json_dict({"face": "garbage"}), {})


class TestLoadSaveOverrides(BaseTestCase):
    """Round-trip fichier : save_tuned / load_overrides / save_overrides."""

    def setUp(self):
        self._orig_path = settings.SPRITE_CONFIGS_PATH
        self.tmp_config = Path(tempfile.mkstemp(suffix=".json",
                                                prefix="tuner_cfg")[1])
        settings.SPRITE_CONFIGS_PATH = self.tmp_config
        if self.tmp_config.exists():
            self.tmp_config.unlink()

    def tearDown(self):
        if self.tmp_config.exists():
            self.tmp_config.unlink()
        settings.SPRITE_CONFIGS_PATH = self._orig_path

    def test_round_trip(self):
        size = {d: {c: CROP_SIZE[d][c] for c in range(3)} for d in DIRECTIONS}
        size["face"][1] = (220, 260)
        offsets = {d: {c: (0, 0) for c in range(3)} for d in DIRECTIONS}
        offsets["face"][1] = (10, 50)
        anchors = {d: (0, 0) for d in DIRECTIONS}
        anchors["face"] = (10, -8)

        out = tuner.save_tuned("Femme", size, offsets, anchors)
        self.assertTrue(out.exists())

        loaded = tuner.load_overrides(out)
        self.assertIn("Femme", loaded)
        self.assertEqual(loaded["Femme"]["crop_size"]["face"][1], (220, 260))
        self.assertEqual(loaded["Femme"]["crop_offsets"]["face"][1], (10, 50))
        self.assertEqual(loaded["Femme"]["anchor_offsets"]["face"], (10, -8))
        # Les clés de colonne sont int à la lecture (pas str du JSON).
        self.assertEqual(loaded["Femme"]["crop_size"]["face"][1], (220, 260))

    def test_load_absent(self):
        self.assertEqual(tuner.load_overrides(self.tmp_config), {})

    def test_load_malformé(self):
        self.tmp_config.write_text("not json {{{", encoding="utf-8")
        self.assertEqual(tuner.load_overrides(self.tmp_config), {})

    def test_save_overrides_créat_dossiers(self):
        # save_overrides doit créer les dossiers parents qui n'existent pas.
        tmp_dir = Path(tempfile.mkdtemp(prefix="tuner_dir_"))
        target = tmp_dir / "deep" / "dir" / "out.json"
        p = tuner.save_overrides(target, {"A": {"crop_size": {}}})
        self.assertEqual(p, target)
        self.assertTrue(p.exists())
        with open(p, "r", encoding="utf-8") as fh:
            self.assertIn("A", json.load(fh))

    def test_save_tuned_fusionne_autres(self):
        tuner.save_tuned("Femme",
                         {d: {c: (200, 300) for c in range(3)}
                          for d in DIRECTIONS},
                         {d: {c: (0, 0) for c in range(3)}
                          for d in DIRECTIONS},
                         {d: (0, 0) for d in DIRECTIONS})
        tuner.save_tuned("Monster",
                         {d: {c: (220, 200) for c in range(3)}
                          for d in DIRECTIONS},
                         {d: {c: (1, 1) for c in range(3)}
                          for d in DIRECTIONS},
                         {d: (5, 5) for d in DIRECTIONS})
        loaded = tuner.load_overrides(self.tmp_config)
        self.assertIn("Femme", loaded)
        self.assertIn("Monster", loaded)
        self.assertEqual(loaded["Monster"]["crop_size"]["face"][1], (220, 200))
        self.assertEqual(loaded["Monster"]["anchor_offsets"]["face"], (5, 5))


def _has_display():
    import sys
    if sys.platform == "win32":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


class TestGuiImport(unittest.TestCase):
    """Le module tuner importe proprement ; la classe GUI existe."""

    def test_import(self):
        self.assertTrue(hasattr(tuner, "SpriteTunerWindow"))
        self.assertTrue(callable(tuner.list_characters))
        self.assertTrue(callable(tuner.read_character_config))
        self.assertTrue(callable(tuner.save_tuned))

    def test_gui_instantiation(self):
        if not _has_display():
            self.skipTest("pas de DISPLAY, GUI non testable headless")
        import tkinter as tk
        init_display()
        root = tk.Tk()
        try:
            win = tuner.SpriteTunerWindow(root, initial_name="Femme")
            self.assertIsNotNone(win.sheet)
            self.assertEqual(win.character_name, "Femme")
            self.assertEqual(len(win.crops), 12, "12 cadres attendus")
            self.assertEqual(len(win.anchors), 4)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
