from pathlib import Path

import json

BASE_DIR = Path(__file__).resolve().parent
ADVENTURES_DIR = BASE_DIR / "adventures"


# Masques SEG de la Forêt (défaut + alternée) et images de fond
# (défaut + alternée).
# L'image de fond alternée (fro2.png) est un miroir horizontal de fro1.png,
# générée à des fins de test du changement d'image — à remplacer par une
# vraie image quand celle-ci existera.
FOREST_SEG_DEFAULT = BASE_DIR / "asset/world/fro1SEG.png"
FOREST_SEG_ALT = BASE_DIR / "asset/world/fro2SEG.png"
FOREST_BG_DEFAULT = BASE_DIR / "asset/world/fro1.png"
FOREST_BG_ALT = BASE_DIR / "asset/world/fro2.png"


# ---------------------------------------------------------------------------
# Overrides de coupe produits par le tuner (tuner.py)
# ---------------------------------------------------------------------------
# Les PNG d'un personnage sont générés : la position et la hauteur du sprite
# varient un peu d'une génération à l'autre. ``tuner.py`` permet d'ajuster
# ces valeurs par personnage (joueur et NPC) et d'en écrire une copie dans
# ``asset/sprite_configs.json``. Ce module recharge ce fichier au démarrage
# et le merge vers les personnages, de façon data-driven (champs manquants
# -> défaut global).

def _deep_merge(a: dict, b: dict) -> dict:
    """Merge ``b`` vers ``a`` (``b`` gagne les clés communes). Helper pour
    ``apply_sprite_overrides``."""
    out = dict(a)
    for key, value in b.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _parse_sprite_overrides(raw):
    """Parser un dict ``sprite_overrides`` (format JSON d'aventure) vers le
    format ``SPRITE_OVERRIDES`` (clés de colonne en ``int``, valeurs en
    tuple). Renvoie ``{}`` si ``raw`` n'est pas un dict.

    Format entrant (par nom de personnage, joueur ou NPC) ::

        {
          "Femme": {
            "crop_size":     {"face": {"0": [200, 300], ...}, ...},
            "crop_offsets":  {"face": {"0": [0, 15], ...}, ...},
            "anchor_offsets":{"face": [0, 0], ...}
          }
        }

    Les clés de colonne sont des chaînes dans le JSON ; elles sont
    converties en ``int``. Un champ manquant ou illisible est ignoré.
    """
    if not isinstance(raw, dict):
        return {}
    out = {}
    for name, cfg in raw.items():
        if not isinstance(cfg, dict):
            continue
        entry = {}
        for field in ("crop_size", "crop_offsets"):
            parsed = {}
            for direction, cols in cfg.get(field, {}).items():
                if not isinstance(cols, dict):
                    continue
                parsed[direction] = {
                    int(col): tuple(v) for col, v in cols.items()
                }
            entry[field] = parsed
        anchor_offsets = {}
        for direction, value in cfg.get("anchor_offsets", {}).items():
            try:
                anchor_offsets[direction] = tuple(value)
            except TypeError:
                pass
        entry["anchor_offsets"] = anchor_offsets
        out[name] = entry
    return out


def _load_sprite_overrides(path):
    """Charger (une seule fois, au module) les overrides de coupe produits
    par le tuner dans ``asset/sprite_configs.json``.

    Un fichier absent, mal formé ou illisible renvoie ``{}`` (graceful :
    le jeu démarre avec les défauts plutôt que de planter).
    """
    path = Path(path)
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        print(f"AVERTISSEMENT : {path} illisible, overrides ignorés")
        return {}
    if not isinstance(data, dict):
        return {}
    return _parse_sprite_overrides(data)


SPRITE_CONFIGS_PATH = BASE_DIR / "asset" / "sprite_configs.json"
SPRITE_OVERRIDES = _load_sprite_overrides(SPRITE_CONFIGS_PATH)


def apply_sprite_overrides(data: dict) -> dict:
    """Merge les overrides du tuner dans un dict de personnage (joueur ou
    NPC), en conservant les valeurs du dict pour les champs non fournis par
    l'override. ``data`` est modifié en place et renvoyé (convenience).
    """
    name = data.get("name")
    if name is None or name not in SPRITE_OVERRIDES:
        return data
    overrides = SPRITE_OVERRIDES[name]
    for field in ("crop_size", "crop_offsets", "anchor_offsets"):
        value = overrides.get(field)
        if value:
            data[field] = _deep_merge(data.get(field, {}), value)
    return data


# ---------------------------------------------------------------------------
# Chargement des aventures (JSON)
# ---------------------------------------------------------------------------
# Les données d'aventure (personnages + cartes) ne sont plus durcies dans ce
# module : elles sont chargées depuis des fichiers JSON du répertoire
# ``adventures/``. Chaque fichier est une aventure. Les chemins d'assets y
# sont relatifs à la racine du projet (BASE_DIR) et résolus à la charge.
def _resolve_asset(path_str):
    """Résoudre un chemin d'asset (relatif ou absolu) vers un Path absolu.

    Les chemins relatifs sont interprétés relativement à ``BASE_DIR``.
    """
    p = Path(path_str)
    if p.is_absolute():
        return p
    return BASE_DIR / p


def load_adventure(config_path=None):
    """Charger une aventure depuis un fichier JSON.

    Args:
        config_path : chemin vers le fichier JSON (str ou Path). Si ``None``,
            charge l'aventure par défaut (``ADVENTURES_DIR / "demo-test.json"``).

    Returns:
        Tuple ``(characters, maps, meta)`` ::

            - ``characters`` : liste de dicts de personnages (champ ``sprite``
              résolu en Path absolu).
            - ``maps``       : liste de dicts de cartes (champs ``background``,
              ``mask``, ``foreground`` et sprites des NPC résolus).
            - ``meta``       : dict d'info (``name``, ``title``, ``window_title``,
              ``start_map``).

    Raises:
        FileNotFoundError   : si le fichier JSON n'existe pas.
        json.JSONDecodeError: si le fichier JSON est mal formé.
    """
    if config_path is None:
        config_path = str(ADVENTURES_DIR / "demo-test.json")
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Aventure introuvable : {config_path}")

    with config_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    if not isinstance(data, dict):
        raise ValueError(f"Format d'aventure invalide (non-dict) : {config_path}")

    # Charger les overrides de sprite de l'aventure et les appliquer aux
    # personnages / NPCs (remplace la config globale du fichier
    # ``asset/sprite_configs.json`` pour l'aventure active).
    global SPRITE_OVERRIDES
    sprite_overrides = _parse_sprite_overrides(data.get("sprite_overrides"))
    SPRITE_OVERRIDES = sprite_overrides

    def _load_character(entry):
        out = dict(entry)
        if isinstance(out.get("sprite"), str):
            out["sprite"] = _resolve_asset(out["sprite"])
        apply_sprite_overrides(out)
        return out

    def _load_npc(entry):
        out = dict(entry)
        if isinstance(out.get("sprite"), str):
            out["sprite"] = _resolve_asset(out["sprite"])
        apply_sprite_overrides(out)
        return out

    def _load_map(entry):
        out = dict(entry)
        for key in ("background", "mask", "foreground"):
            if isinstance(out.get(key), str):
                out[key] = _resolve_asset(out[key])
        variants = out.get("variants")
        if isinstance(variants, dict):
            out["variants"] = {
                key: [_resolve_asset(p) for p in values]
                for key, values in variants.items()
            }
        if out.get("npcs"):
            out["npcs"] = [_load_npc(n) for n in out["npcs"]]
        return out

    characters = [_load_character(c) for c in data.get("characters", [])]
    maps = [_load_map(m) for m in data.get("maps", [])]

    meta = {
        "name": data.get("name", config_path.stem),
        "title": data.get("title", config_path.stem),
        "window_title": data.get("window_title", WINDOW_TITLE),
        "start_map": data.get("start_map"),
        "sprite_overrides": data.get("sprite_overrides") or {},
    }

    return characters, maps, meta

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 720
WINDOW_BACKGROUND = (45, 48, 58)
WINDOW_TITLE = "RPG - Prototype"

ROWS = 4
COLS = 3
IDLE_COL = 1
ANIMATION_FPS = 8
SPRITE_SCALE = 2
CHARACTER_SCALE = 0.25
DISPLAY_SCALE = SPRITE_SCALE * CHARACTER_SCALE
MOVE_SPEED = 220

COLLISIONS_ENABLED_DEFAULT = True
COLLISION_RADIUS = 5

DIRECTIONS = {
    "face": 0,
    "gauche": 1,
    "droite": 2,
    "dos": 3,
}

ANIMATION = {
    direction: [0, 1, 2, 1]
    for direction in DIRECTIONS
}

CROP_OFFSETS = {
    "face": {0: (0, 15), 1: (0, 15), 2: (0, 15)},
    "gauche": {0: (0, 0), 1: (0, 0), 2: (0, 10)},
    "droite": {0: (0, -10), 1: (0, -10), 2: (0, -10)},
    "dos": {0: (-12, -25), 1: (0, -25), 2: (2, -25)},
}

CELL_W = 200
CELL_H = 300

CROP_SIZE = {
    "face": {i: (CELL_W, CELL_H) for i in range(3)},
    "gauche": {
        0: (CELL_W, CELL_H - 20),
        1: (CELL_W, CELL_H),
        2: (CELL_W, CELL_H),
    },
    "droite": {i: (CELL_W, CELL_H) for i in range(3)},
    "dos": {i: (CELL_W, CELL_H) for i in range(3)},
}

ANCHOR_OFFSETS = {
    "face": (0, 0),
    "gauche": (0, 0),
    "droite": (0, 0),
    "dos": (0, 0),
}

# --- Objets interactifs : pixels bleus du masque de collision ---
# Bleu au masque = objet avec lequel on peut interagir : teint bleu
# constant (BASE_ALPHA) + halo agrandi quand le joueur s'approche/touche.
INTERACT_COLOR = (90, 170, 255)
INTERACT_GLOW_COLOR = (130, 200, 255)
INTERACT_BASE_ALPHA = 30
INTERACT_GLOW_ALPHA = 100
INTERACT_GLOW_PAD = 14
INTERACT_MAX_SCALE = 0.20
INTERACT_PROXIMITY = 80.0
INTERACT_CONTACT = 45.0
INTERACT_BLUE_THRESHOLD = 100
INTERACT_MIN_AREA = 100
# Distance max (px) pour associer un comportement à un objet bleu :
# le centre de l'objet le plus proche du "pos" de l'interaction.
INTERACT_MATCH_TOLERANCE = 90.0

# --- Personnages de carte (NPC) ---
# Voir npc.py pour le format des dicts de déclaration.
NPC_DEFAULT_SPEED = 60.0
NPC_DEFAULT_COLLISION_RADIUS = 5.0
NPC_CONTACT_RADIUS = 45.0
NPC_INTERACT_COOLDOWN = 3.0

# --- Couche de premier plan (FG) ---
# Surface min de composante FG conservée (filtre le bruit).
FG_MIN_AREA = 50
# Chargement de l'aventure par défaut (à la charge du module).
CHARACTERS, MAPS, ADVANTURE_META = load_adventure()
