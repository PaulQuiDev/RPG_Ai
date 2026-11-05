"""Contrat data-driven de la quête et des assets.

Ce fichier vérifie le contrat du projet :

    « importer l'aventure (JSON) + ses assets => une aventure jouable »

Concrètement : TOUT asset utilisé par le jeu (monstre, monstre transformé
``monster2.png``, bougies/trône, personnages, cartes, NPCs) doit être
déclaré dans le JSON d'aventure, et chaque asset déclaré doit exister sur
disque.

C'est le test du bug P4 : avant, le sprite du monstre transformé
(``monster2.png``) et la carte de combat étaient codés en dur dans
``game.py`` / ``monster.py`` (un « hotfix » local), et ``monster2.png``
n'apparaissait nulle part dans le JSON. Après la correction, la quête est
entièrement déclarée dans le JSON et pilotée par ``quest_config``.

Chaque test ci-dessous **échouerait avant la correction** (aucun bloc
``quest`` dans le JSON, ``monster2.png`` absent, sprite en dur).
"""
import ast
import json
import re
import unittest
from pathlib import Path

from settings import ADVENTURES_DIR, BASE_DIR, QUEST_CONFIG, load_adventure

DEFAULT_ADV = ADVENTURES_DIR / "demo-test.json"

# Pattern : chemin d'asset d'aventure (relatif au projet), ex.
#   "asset/carater/monster2.png"
ASSET_RE = re.compile(r"asset/(carater|world)/[^\"']+\.png")


def _load_raw(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _non_docstring_literals(src: str) -> set:
    """Les littéraux str du code, **sans** les docstrings.

    Permet de ne tester que le code réel (assignments, arguments, ...)
    et pas le texte des commentaires/docstrings.
    """
    tree = ast.parse(src)
    docs = set()

    def _collect_docstring(expr: ast.Expr) -> None:
        """Si le premier énoncé est une constante str (docstring), on l'ajoute
        à l'ensemble des docstrings à exclure."""
        val = expr.value
        if isinstance(val, ast.Constant) and isinstance(val.value, str):
            docs.add(val.value)

    body = tree.body
    if body and isinstance(body[0], ast.Expr):
        _collect_docstring(body[0])
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.body and isinstance(node.body[0], ast.Expr):
                _collect_docstring(node.body[0])
    all_str = {
        n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }
    return all_str - docs


class QuestTestMixin:
    """Base commune : JSON brut + QuestConfig chargée."""

    def setUp(self):
        self.raw = _load_raw(DEFAULT_ADV)
        self.base = BASE_DIR
        chars, maps, meta = load_adventure(DEFAULT_ADV)
        self.characters = chars
        self.maps = maps
        self.quest = meta["quest"]

    def _rel(self, p) -> str:
        p = Path(str(p))
        try:
            return str(p.relative_to(self.base))
        except ValueError:
            return str(p)

    def _json_declared(self) -> set:
        """Chemins (relatifs) d'assets déclarés dans le JSON :
        personnages, cartes (fond / masque / FG / variants), NPCs, quête."""
        declared = set()
        for c in self.raw.get("characters", []):
            if c.get("sprite"):
                declared.add(str(c["sprite"]))
        for m in self.raw.get("maps", []):
            for key in ("background", "mask", "foreground"):
                v = m.get(key)
                if v:
                    declared.add(str(v))
            for values in (m.get("variants") or {}).values():
                for v in values:
                    declared.add(str(v))
            for n in m.get("npcs", []):
                if n.get("sprite"):
                    declared.add(str(n["sprite"]))
        quest = self.raw.get("quest") or {}
        for k in ("monster_sprite", "monster2_sprite"):
            if quest.get(k):
                declared.add(str(quest[k]))
        return declared

    def _game_used(self) -> set:
        """Chemins (relatifs) d'assets réellement utilisés par le jeu,
        issus de la configuration data-driven : joueur, NPCs, cartes et
        quête (monstre + monstre transformé)."""
        used = set()
        for c in self.characters:
            if c.get("sprite"):
                used.add(self._rel(c["sprite"]))
        for m in self.maps:
            for n in m.get("npcs", []):
                if n.get("sprite"):
                    used.add(self._rel(n["sprite"]))
            for key in ("background", "mask", "foreground"):
                if m.get(key):
                    used.add(self._rel(m[key]))
            for values in (m.get("variants") or {}).values():
                for v in values:
                    used.add(self._rel(v))
        used.add(self._rel(self.quest.monster_sprite))
        used.add(self._rel(self.quest.monster2_sprite))
        return used

    def _source(self, name: str) -> str:
        return (Path(__file__).resolve().parent.parent / name).read_text(
            encoding="utf-8"
        )


# ---------------------------------------------------------------------------
# 1. Le JSON déclare la quête (le bug P4)
# ---------------------------------------------------------------------------

class TestQuestDeclaredInJson(QuestTestMixin, unittest.TestCase):
    """Le JSON d'aventure déclare la quête complète. (Échoue avant la
    correction : pas de bloc ``quest`` / pas de ``monster2.png``.)"""

    def test_quest_block_present(self):
        self.assertIn("quest", self.raw)
        self.assertIsInstance(self.raw["quest"], dict)

    def test_monster_and_monster2_assets_declared(self):
        """Les sprites du monstre et du monstre transformé sont déclarés
        dans le JSON (plus codés en dur dans game.py / monster.py)."""
        q = self.raw["quest"]
        self.assertIn("monster_sprite", q)
        self.assertIn("monster2_sprite", q)
        self.assertTrue(str(q["monster_sprite"]).endswith("monster.png"))
        self.assertTrue(str(q["monster2_sprite"]).endswith("monster2.png"))

    def test_monster2_asset_specifically_declared(self):
        """Régression P4 : ``monster2.png`` (sprite du monstre transformé)
        doit figurer dans le JSON. C'était absent avant la correction."""
        declared = self._json_declared()
        self.assertIn("asset/carater/monster2.png", declared)


# ---------------------------------------------------------------------------
# 2. La QuestConfig (celle que le jeu utilise) vient du JSON
# ---------------------------------------------------------------------------

class TestQuestConfigFromJson(QuestTestMixin, unittest.TestCase):
    """La ``QuestConfig`` chargée porte les valeurs du JSON (et résout les
    chemins en absolu). C'est elle que le ``Game`` consomme."""

    def test_quest_config_matches_json(self):
        c = QUEST_CONFIG
        self.assertTrue(c.has_quest)
        self.assertEqual(c.boss_combat_map, "Boss Combat")
        self.assertEqual(c.post_combat_map, "Post Combat")
        self.assertEqual(c.monster_speed, 55.0)
        self.assertEqual(c.monster2_speed, 180.0)
        self.assertEqual(c.candle_total, 5)
        self.assertEqual(self._rel(c.monster_sprite), "asset/carater/monster.png")
        self.assertEqual(self._rel(c.monster2_sprite), "asset/carater/monster2.png")
        self.assertTrue(c.monster_sprite.is_absolute())
        self.assertTrue(c.monster2_sprite.is_absolute())

    def test_quest_config_monster_assets_match_json(self):
        """Le sprite que le jeu utilisera pour le monstre / la transformation
        correspond bien à ce que le JSON déclare."""
        declared = self._json_declared()
        self.assertIn(self._rel(self.quest.monster_sprite), declared)
        self.assertIn(self._rel(self.quest.monster2_sprite), declared)


# ---------------------------------------------------------------------------
# 3. Contrat : tout asset utilisé est déclaré ; tout déclaré existe
# ---------------------------------------------------------------------------

class TestAssetContract(QuestTestMixin, unittest.TestCase):
    """Tous les assets utilisés par le jeu sont déclarés dans le JSON,
    et chaque asset déclaré existe sur disque."""

    def test_all_game_assets_are_declared(self):
        """Aucun asset « orphelin » : tout asset que le jeu utilise
        (joueur, NPCs, cartes, quête) est déclaré dans le JSON."""
        used = self._game_used()
        declared = self._json_declared()
        missing = used - declared
        self.assertEqual(
            missing,
            set(),
            f"Assets utilisés par le jeu mais NON déclarés dans le JSON : "
            f"{sorted(missing)}",
        )

    def test_all_declared_assets_exist_on_disk(self):
        """Chaque asset déclaré dans le JSON existe réellement — c'est
        ce qui rend « importer l'aventure JSON + assets » jouable."""
        for asset in self._json_declared():
            p = self.base / asset
            self.assertTrue(p.exists(), f"Asset déclaré absent : {asset}")


# ---------------------------------------------------------------------------
# 4. Garde-fou : pas d'asset d'aventure durcisé dans le cœur du jeu
# ---------------------------------------------------------------------------

class TestNoHardcodedAdvantageAssets(QuestTestMixin, unittest.TestCase):
    """Le cœur du jeu (modules de logique) ne référence **aucun** asset
    d'aventure (``asset/carater/*.png``, ``asset/world/*.png``) en dur :
    tout passe par le JSON.

    C'est le vrai garde-fou du bug P4 : avant, ``monster.py``/``game.py``
    contenaient ``MONSTER_SPRITE_FINAL = BASE_DIR / "asset/carater/monster2.png"``
    et ``MONSTER_SPRITE = BASE_DIR / "asset/carater/monster.png"`` (en dur,
    hors JSON). Ce test s'assure qu'aucun tel chemin ne revient dans le code
    (les fallbacks `DEFAULT_*` vivent dans ``quest_config.py``, le config
    moteur dans ``settings.py``)."""

    CORE_MODULES = ("game.py", "monster.py", "npc.py", "player.py",
                    "world.py", "behaviors.py")

    def test_core_modules_have_no_orphan_hardcoded_assets(self):
        declared = self._json_declared()
        for name in self.CORE_MODULES:
            literals = _non_docstring_literals(self._source(name))
            used = {lit for lit in literals if ASSET_RE.search(lit)}
            missing = {u for u in used if u not in declared}
            self.assertEqual(
                missing,
                set(),
                f"{name} référence un asset d'aventure non déclaré dans "
                f"le JSON (réintroduction d'un hotfix en dur ?) : "
                f"{sorted(missing)}",
            )


if __name__ == "__main__":
    unittest.main()
