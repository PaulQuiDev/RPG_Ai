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

import math
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

    def test_village_npc_flee_is_reversible(self):
        """Fuite NON DÉFINITIVE des PNJ du village.

        Quand le joueur est en forme boss (``monster2_active`` levé), les
        PNJ du village — *hors du « Monstre », qui est la forme du joueur
        (P4) et qui reste toujours* — « sortent » de la carte (``hidden``
        : invisibles, inactifs, non interactifs, pas de collision). Quand
        le joueur est redevenu normal (``monster2_active`` désactivé), ils
        reviennent et reprennent leur comportement « de base ». Effet
        réversible, dérivé de l'état (flag) : aucun effet permanent.

        Note : chaque ``change_map`` recharge la carte (nouveaux objets
        NPC) ; on re-capture donc les PNJ *après* chaque transition.
        """
        def npcs():
            return self.game.game_map.npcs
        def monster():
            return next(
                n for n in npcs() if n.name == "Monstre"
            )
        def others():
            return [n for n in npcs() if n.name != "Monstre"]

        # --- 0) Joueur normal : tous présents (hidden = False).
        self._enter(0)
        self.assertEqual(
            self.game.world.current_map_data["name"], "Village"
        )
        village = npcs()
        self.assertTrue(village, "Le village doit avoir des PNJ")
        self.assertTrue(
            others(),
            "Le village doit contenir au moins un PNJ « normal »",
        )
        self.assertFalse(self.game.world.flag_get("monster2_active"))
        for npc in village:
            self.assertFalse(
                npc.hidden, f"{npc.name} hidden à l'état initial"
            )

        # --- 1) Joueur transformé en boss (monster2_active = True) :
        #       PNJ normaux sortent, « Monstre » reste.
        self.game.world.flag_set("monster2_active", True)
        self._enter(0)
        self.assertTrue(self.game.world.flag_get("monster2_active"))
        for npc in others():
            self.assertTrue(
                npc.hidden, f"{npc.name} devrait fuir le village"
            )
        self.assertFalse(
            monster().hidden,
            "Le « Monstre » (forme du joueur) doit rester présent",
        )
        # Le comportement « flee » est posé (cohérent avec le test
        # historique : any(n.behavior == "flee")).
        self.assertTrue(any(n.behavior == "flee" for n in npcs()))

        # --- 2) Joueur redevenu normal (monster2_active = False) :
        #       PNJ reviennent et reprennent leur comportement de base.
        self.game.world.flag_set("monster2_active", False)
        self._enter(0)
        self.assertFalse(self.game.world.flag_get("monster2_active"))
        for npc in others():
            self.assertFalse(
                npc.hidden, f"{npc.name} devrait revenir au village"
            )
        self.assertFalse(monster().hidden, "Le « Monstre » doit rester")

        # --- 3) Joueur de nouveau boss : les PNJ sortent à nouveau.
        self.game.world.flag_set("monster2_active", True)
        self._enter(0)
        self.assertTrue(self.game.world.flag_get("monster2_active"))
        for npc in others():
            self.assertTrue(
                npc.hidden, f"{npc.name} devrait fuir (de nouveau)"
            )
        self.assertFalse(
            monster().hidden,
            "Le « Monstre » doit rester (toujours présent)",
        )

    def test_village_monster_follows_player_transformation(self):
        """Le « Monstre » du village suit la transformation du joueur (P4).

        Quand le joueur est en forme boss (``monster2_active`` levé), le
        « Monstre » du village — la forme du joueur — prend la forme
        ``monster2`` (``monster2.png``). Quand le joueur est redevenu
        normal, il revient à sa forme de base (celle déclarée dans le
        JSON, conservée dans ``_base_sprite``). Réversible et
        data-driven, synchronisé par ``sync_npc_presence`` (appelé à
        chaque frame dans ``update``).

        Note : chaque ``change_map`` recharge la carte (nouveaux objets
        NPC) ; on re-capture donc le « Monstre » *après* chaque transition.
        """
        def get_monster():
            return next(
                n for n in self.game.game_map.npcs if n.name == "Monstre"
            )

        # --- 0) Joueur normal : le « Monstre » a sa forme de base.
        self._enter(0)
        self.assertEqual(
            self.game.world.current_map_data["name"], "Village"
        )
        self.assertFalse(self.game.world.flag_get("monster2_active"))
        mon = get_monster()
        self.assertEqual(
            mon.sprite_path.name,
            mon._base_sprite.name,
            "Forme de base : sprite déclarée dans le JSON",
        )
        self.assertFalse(mon._is_monster2)
        self.assertNotEqual(
            mon.sprite_path.name,
            self.game.quest.monster2_sprite.name,
            "Forme de base distincte de la forme boss",
        )

        # --- 1) Joueur transformé en boss : le « Monstre » suit la forme
        #       monster2.
        self.game.world.flag_set("monster2_active", True)
        self._enter(0)
        self.assertTrue(self.game.world.flag_get("monster2_active"))
        mon = get_monster()
        self.assertEqual(
            mon.sprite_path.name,
            self.game.quest.monster2_sprite.name,
            "Forme boss : le « Monstre » suit monster2",
        )
        self.assertTrue(mon._is_monster2)

        # --- 2) Joueur redevenu normal : le « Monstre » revient à sa forme
        #       de base.
        self.game.world.flag_set("monster2_active", False)
        self._enter(0)
        self.assertFalse(self.game.world.flag_get("monster2_active"))
        mon = get_monster()
        self.assertEqual(
            mon.sprite_path.name,
            mon._base_sprite.name,
            "Forme de base : restaurée depuis le JSON",
        )
        self.assertFalse(mon._is_monster2)

        # --- 3) Joueur de nouveau boss : la transformation se re-synchronise.
        self.game.world.flag_set("monster2_active", True)
        self._enter(0)
        self.assertTrue(self.game.world.flag_get("monster2_active"))
        mon = get_monster()
        self.assertEqual(
            mon.sprite_path.name,
            self.game.quest.monster2_sprite.name,
            "De nouveau en forme boss",
        )
        self.assertTrue(mon._is_monster2)

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

    # -- P10 : marcher sur les objets interactifs « très bleus et très verts ».

    def test_can_walk_on_central_lantern(self):
        """P10 : marcher sur une lanterne « très bleue ET très verte »
        au centre de la MAP village.

        La segmentation du village colorie certains objets interactifs en
        « très bleu » (b > seuil) ET « très vert » (g > seuil) — ex. :
        l'objet central segmenté ~(0, 112, 255). La physique doit alors
        laisser le joueur *marcher* dessus (et interagir), ce qui n'était
        pas le cas avant (règle « vert-dominant » uniquement).

        On identifie l'objet bleu interactif le plus proche du centre de
        la carte (la « lanterne du centre ») puis on vérifie :
          1. son centre est praticable (`is_walkable`),
          2. le joueur peut réellement s'y placer (`can_stand_at`,
             le même test que la physique du mouvement) => marcher dessus,
          3. l'objet reste interactif (a un comportement).
        + régression : le centre exact (sol, vert-dominant) reste
          praticable ; un mur (rouge-dominant) n'est PAS praticable.
        """
        self._enter(0)
        self.assertEqual(
            self.game.world.current_map_data["name"], "Village"
        )
        map_ = self.game.game_map
        self.assertTrue(
            map_.interact_objects,
            "La MAP village devrait avoir des objets bleus (lanternes).",
        )
        cx, cy = map_.width / 2.0, map_.height / 2.0
        # Objet bleu interactif le plus proche du centre = la lanterne.
        nearest = min(
            map_.interact_objects,
            key=lambda o: math.hypot(
                o["box"].centerx - cx,
                o["box"].centery - cy,
            ),
        )
        lcx, lcy = nearest["box"].centerx, nearest["box"].centery

        # 1) Centre de la lanterne praticable (règle « très bleu + vert »).
        self.assertTrue(
            map_.is_walkable(lcx, lcy),
            f"Le centre de la lanterne ({int(lcx)}, {int(lcy)}) "
            f"(action={nearest.get('action')!r}) devrait être praticable.",
        )
        # 2) Le joueur peut réellement SE PLACER sur la lanterne (marcher
        #    dessus) : c'est le même test que la physique du mouvement
        #    (``can_stand_at``), avec le rayon de collision du joueur.
        self.assertTrue(
            map_.can_stand_at(
                lcx, lcy, self.game.player.collision_radius
            ),
            "Le joueur devrait pouvoir se placer (marcher) sur la lanterne "
            f"({int(lcx)}, {int(lcy)}) (action={nearest.get('action')!r}).",
        )
        # 3) L'objet reste interactif (on peut interagir).
        self.assertTrue(
            nearest.get("action"),
            f"La lanterne du centre devrait être interactive "
            f"(action={nearest.get('action')!r}).",
        )
        # 4) Régression : le centre exact (sol, vert-dominant) reste
        #    praticable (la règle n'a pas cassé la marche normale).
        self.assertTrue(
            map_.is_walkable(cx, cy),
            "Le centre (sol, vert-dominant) devrait rester praticable.",
        )
        # 5) Régression : un mur (rouge-dominant) n'est PAS praticable.
        wall = None
        W, H = map_.width, map_.height
        for y in (0, 15, 40, H - 40, H - 15, H):
            for x in (0, 15, 40, W - 40, W - 15, W):
                r, g, b = map_.collision_mask.get_at((x, y))[:3]
                if r > 150 and g < 60 and b < 60:
                    wall = (x, y)
                    break
            if wall:
                break
        if wall is not None:
            self.assertFalse(
                map_.is_walkable(*wall),
                f"Un mur ({wall}) devrait être NON praticable.",
            )


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
