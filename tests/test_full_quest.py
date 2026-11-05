"""Tests de la boucle complète de la quête (cartes RÉELLES, asset/world/*.png).

Couvre la bonne exécution des objets à travers tout le cycle :
Village -> Forêt -> Boss Combat (5 bougies) -> Post Combat (trône)
-> Village (transformation + fuite des PNJ) -> re-entrée aire du boss
(Post Combat, redirection post-victoire : pas de respawn, plus de bougies).

C'est aussi le test du compteur HUD « Bougies : x/5 » (pas /10)
et du cycle sauvegarde / chargement de l'état du jeu (JSON).
"""
import json
import unittest
from pathlib import Path

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

        # 5) Trône : pose le drapeau monster2_active (P4 : transforme le
        #    JOUEUR en boss, pas le monstre).
        throne = self._objects_by_action("transform_monster")
        self.assertEqual(len(throne), 1)
        self._interact_at(throne[0]["box"].centerx, throne[0]["box"].centery)
        self.assertTrue(self.game.world.flag_get("monster2_active"))

        # 6) Retour au village : le joueur est en forme boss + les PNJ
        #    du village fuient (P4 + fuite des PNJ).
        self._enter(0)
        self.assertEqual(self.game.world.current_map_data["name"], "Village")
        # Le joueur a bien été transformé en boss (monster2.png, vitesse 180).
        self.assertTrue(self.game.player._monster2)
        self.assertTrue(self.game.player.sprite_path.name == "monster2.png")
        self.assertEqual(self.game.player.speed, 180.0)
        self.assertTrue(
            any(n.behavior == "flee" for n in self.game.game_map.npcs)
        )

        # 7) Re-entrée dans le Boss Combat : le monstre est DÉJÀ vaincu,
        #    donc AUCUN respawn (pas de monstre, pas de bougies).
        #    (Persistance de l'état vaincu : pas de « réaffrontement ».)
        self._enter(2)
        self.assertEqual(
            self.game.world.current_map_data["name"], BOSS_COMBAT_MAP
        )
        self.assertIsNone(self.game._monster)
        self.assertTrue(self.game.world.flag_get("monster_defeated"))
        self.assertEqual(self.game._candle_lit_count, 0)
        self.assertEqual(len(self.game._candle_lit), 0)

    # -- P5 : navigation RÉELLE (exits), pas sélection directe.

    def _edge_left(self):
        """Mets le joueur sur la bordure gauche puis lance 2 updates :
        la 1re déclenche `check_transition` (changement de carte), la
        seconde ` _on_map_change` (reset / respawn)."""
        self.game.player.x = 0.0
        self.game.update(0.016)
        self.game.update(0.016)

    def _edge_right(self):
        """Mets le joueur sur la bordure droite puis lance 2 updates."""
        self.game.player.x = self.game.game_map.width - 1.0
        self.game.update(0.016)
        self.game.update(0.016)

    def test_real_navigation_redirects_to_post_combat_after_victory(self):
        """P5/fix : après la mort du monstre, la ré-entrée dans l'aire du
        boss via le flux de navigation réel (exits : Post Combat → Village
        → Forêt → aire du boss) bascule vers la carte du **post-combat**
        (Post Combat) et NON vers la salle de combat (monstre déjà vaincu).
        De là, le joueur peut interagir avec le trône (siège) pour se
        transformer en boss, même « après coup ».
        """
        # Boss Combat : tuer le monstre -> Post Combat.
        self._enter(2)
        self.assertEqual(
            self.game.world.current_map_data["name"], BOSS_COMBAT_MAP
        )
        candles = self._objects_by_action("light_candle")
        for o in candles:
            self._interact_at(o["box"].centerx, o["box"].centery)
        # La carte reste bien celle du post-combat (P5).
        self.assertEqual(
            self.game.world.current_map_data["name"], "Post Combat"
        )

        # Post Combat (bordure gauche) -> Village.
        self._edge_left()
        self.assertEqual(
            self.game.world.current_map_data["name"], "Village"
        )
        # Village (bordure droite) -> Forêt.
        self._edge_right()
        self.assertEqual(
            self.game.world.current_map_data["name"], "Forêt"
        )
        # Forêt (bordure droite) : REDIRECTION vers Post Combat (pas Boss
        # Combat, car le monstre est vaincu).
        self._edge_right()
        self.assertEqual(
            self.game.world.current_map_data["name"], "Post Combat"
        )
        # Pas de respawn dans l'aire du boss (monstre vaincu) : pas de
        # monstre, pas de bougies à allumer.
        self.assertIsNone(self.game._monster)
        self.assertTrue(self.game.world.flag_get("monster_defeated"))
        self.assertEqual(self.game._candle_lit_count, 0)
        self.assertEqual(len(self.game._candle_lit), 0)

        # Le joueur peut maintenant interagir avec le trône (siège) pour
        # se transformer (P4), même après coup.
        throne = self._objects_by_action("transform_monster")
        self.assertEqual(len(throne), 1)
        self._interact_at(throne[0]["box"].centerx, throne[0]["box"].centery)
        # La transformation (P4) est synchronisée à chaque frame dans
        # update() (pas seulement au moment de l'interaction) : on lance un
        # frame pour laisser le sprite/la vitesse passer au boss.
        self.game.update(0.016)
        self.assertTrue(self.game.world.flag_get("monster2_active"))
        self.assertTrue(self.game.player._monster2)
        self.assertTrue(self.game.player.sprite_path.name == "monster2.png")
        self.assertEqual(self.game.player.speed, 180.0)


class TestSaveLoad(BaseTestCase):
    """Sauvegarde / chargement de l'état du jeu (cycle JSON)."""

    def setUp(self):
        self.game = Game(
            self.screen,
            pygame.font.SysFont("sans", 18),
            CHARACTERS,
            MAPS,
            collisions_enabled=False,
            debug=False,
        )
        self.save_path = Path(self._tmp.name) / "save_test.json"

    def tearDown(self):
        self.game = None
        if self.save_path.exists():
            self.save_path.unlink()
        default_save = (
            Path(__file__).parent.parent / "saves" / "game.json"
        )
        if default_save.exists():
            default_save.unlink()

    @staticmethod
    def _make_game(screen, font):
        """Crée un Game neuf (pour tester le chargement)."""
        return Game(
            screen,
            font,
            CHARACTERS,
            MAPS,
            collisions_enabled=False,
            debug=False,
        )

    def _enter(self, index):
        game = self.game
        assert game is not None
        game.world.change_map(index, game.player)
        game.game_map = game.world.game_map
        game.update(0.016)

    def _objects_by_action(self, action):
        game = self.game
        assert game is not None
        return [
            o
            for o in game.game_map.interact_objects
            if o.get("action") == action
        ]

    def _interact_at(self, cx, cy):
        game = self.game
        assert game is not None
        game.player.x, game.player.y = float(cx), float(cy)
        game._interact()

    def test_save_load_round_trip(self):
        # 1) Boss Combat, on allume 2 bougies sur 5.
        self._enter(2)
        self.assertEqual(
            self.game.world.current_map_data["name"], BOSS_COMBAT_MAP
        )
        candles = self._objects_by_action("light_candle")
        self.assertEqual(len(candles), 5)
        for o in candles[:2]:
            self._interact_at(o["box"].centerx, o["box"].centery)
        self.assertEqual(self.game._candle_lit_count, 2)
        self.assertIsNotNone(self.game._monster)

        # 2) Sauvegarde (fichier temp).
        self.assertTrue(self.game.save(self.save_path))
        self.assertTrue(self.save_path.exists())

        # 3) Nouveau Game (état neuf) + chargement.
        font = pygame.font.SysFont("sans", 18)
        fresh = self._make_game(self.screen, font)
        self.assertTrue(fresh.load(self.save_path))

        # 4) État restauré fidèlement.
        self.assertEqual(
            fresh.world.current_map_data["name"], BOSS_COMBAT_MAP
        )
        self.assertEqual(fresh._candle_lit_count, 2)
        self.assertEqual(len(fresh._candle_lit), 2)
        self.assertIsNotNone(fresh._monster)
        self.assertFalse(fresh.world.flag_get("monster_defeated"))
        self.assertFalse(fresh.world.flag_get("monster2_active"))
        self.assertTrue(fresh._action_history)

        # Le contenu JSON est correct.
        with self.save_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data["version"], 1)
        self.assertEqual(data["map_name"], BOSS_COMBAT_MAP)
        self.assertEqual(data["map_index"], 2)
        self.assertEqual(len(data["candle_lit"]), 2)
        self.assertIsInstance(data["flags"], dict)
        self.assertIsInstance(data["player"], dict)
        self.assertIsInstance(data["monster_pos"], list)
        self.assertIsInstance(data["action_history"], list)

        # Une partie fraîche (sans chargement) a bien un état neuf.
        blank = self._make_game(self.screen, font)
        self.assertEqual(blank._candle_lit_count, 0)
        self.assertIsNone(blank._monster)
        self.assertFalse(blank.world.flag_get("monster_defeated"))

        # Sauvegarde puis chargement d'un état neuf (0 bougie, pas de
        # monstre) : l'état reste neuf après le cycle.
        self.assertTrue(blank.save(self.save_path))
        clean = self._make_game(self.screen, font)
        self.assertTrue(clean.load(self.save_path))
        self.assertIsNone(clean._monster)
        self.assertEqual(clean._candle_lit_count, 0)
        self.assertEqual(clean._candle_lit, set())

    def test_flags_saved_and_restored(self):
        # Un drapeau posé est bien sérialisé puis restauré.
        self.game.world.flag_set("monster_defeated", True)
        self.assertTrue(self.game.save(self.save_path))
        with self.save_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertIn("monster_defeated", data["flags"])
        self.assertTrue(data["flags"]["monster_defeated"])

        # Chargement dans un Game neuf : le drapeau est restauré.
        font = pygame.font.SysFont("sans", 18)
        fresh = self._make_game(self.screen, font)
        self.assertTrue(fresh.load(self.save_path))
        self.assertTrue(fresh.world.flag_get("monster_defeated"))

    def test_load_missing_file(self):
        missing = Path(self._tmp.name) / "missing.json"
        self.assertFalse(self.game.load(missing))
        # L'état reste intact.
        self.assertEqual(len(self.game._candle_lit), 0)

    def test_load_corrupt_file(self):
        # Fichier corrompu : load() renvoie False (robuste, pas de crash),
        # l'état courant est conservé.
        corrupt = Path(self._tmp.name) / "corrupt.json"
        corrupt.write_text("{ pas valide json", encoding="utf-8")
        self.assertFalse(self.game.load(corrupt))
        self.assertEqual(len(self.game._candle_lit), 0)


if __name__ == "__main__":
    unittest.main()
