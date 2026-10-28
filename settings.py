from pathlib import Path

import json

BASE_DIR = Path(__file__).resolve().parent

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


def _load_sprite_overrides(path):
    """Charger (une seule fois, au module) les overrides de coupe produits
    par le tuner dans ``asset/sprite_configs.json``.

    Format (par nom de personnage, joueur ou NPC) ::

        {
          "Femme": {
            "crop_size":     {"face": {"0": [200, 300], ...}, ...},
            "crop_offsets":  {"face": {"0": [0, 15], ...}, ...},
            "anchor_offsets":{"face": [0, 0], ...}
          }
        }

    Les clés de colonne sont des chaînes dans le JSON ; elles sont
    converties en ``int`` à la lecture. Un champ manquant est ignoré.
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
    out = {}
    for name, cfg in data.items():
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


# Personnages disponibles
CHARACTERS = [
    {
        "name": "Femme",
        "sprite": BASE_DIR / "asset/carater/woman.png",
        "scale": 0.25,
        "speed": 220,
        "collision_radius": 5,
    },
    {
        "name": "Monster",
        "sprite": BASE_DIR / "asset/carater/monster.png",
        "scale": 0.35,
        "speed": 180,
        "collision_radius": 4.5,
    },
]

# Cartes disponibles
MAPS = [
    {
        "name": "Village",
        "background": BASE_DIR / "asset/world/vil1.png",
        "mask": BASE_DIR / "asset/world/vil1SEG.png",
        # Couche de premier plan optionnelle (éléments devant le joueur).
        "foreground": BASE_DIR / "asset/world/vil1FG.png",

        # Comportements des objets bleus :
        #   "pos"     = centre de l'objet (px, coordonnées fenêtre).
        #   "action"  = clé dans behaviors.BEHAVIORS (comportement custom),
        #               OU "dest" = nom de carte pour un téléport direct.
        "interactions": [
            # Grand bâtiment (left) -> change de carte vers la Forêt.
            {"pos": [356, 305], "action": "go_forest"},
        ],

        "perspective": {
            "enabled": True,
            "top_scale": 0.70,
            "bottom_scale": 1.00,
        },

        "exits": {
            "right": {
                "map": "Forêt",
                "spawn": (10, 400),
            },
        },

        # Personnages de la carte (NPC) — voir npc.py.
        #   "static" : reste sur place ; "patrol" : suit la boucle "points".
        #   "action" : clé de behaviors.BEHAVIORS déclenchée au contact.
        "npcs": [
            {"name": "Champignon 1", "sprite": BASE_DIR / "asset/carater/mush1.png", "pos": [400, 430], "message": "Un monstre est enfermé dans la maison en forêt, à droite. Fais attention, il te fonce dessus."},
            {"name": "Champignon 2", "sprite": BASE_DIR / "asset/carater/mush2.png", "pos": [720, 400], "message": "Pour ouvrir la maison : le pilier en haut à gauche de la forêt (SEG 2). Ça ouvre le chemin vers le bord droit."},
            {"name": "Champignon 3", "sprite": BASE_DIR / "asset/carater/mush3.png", "pos": [680, 450], "message": "Bonsoir."},
            {"name": "Monstre", "sprite": BASE_DIR / "asset/carater/monster.png", "behavior": "patrol", "speed": 55, "scale": 0.35,
             "message": "Grrhh !",
             "points": [[478, 94], [500, 710]]},
            {"name": "Champignon errant", "sprite": BASE_DIR / "asset/carater/mush5.png", "behavior": "patrol", "speed": 40, "scale": 0.2,
             "message": "Hop...",
             "points": [[53, 380], [900, 360], [900, 500], [30, 505]]},
        ],
    },
    {
        "name": "Forêt",
        "background": FOREST_BG_DEFAULT,
        "mask": FOREST_SEG_DEFAULT,

        # Variantes d'actifs basculables à l'exécution (voir
        # cycle_map_seg / cycle_map_bg / cycle_map_fg dans behaviors.py).
        # Chaque liste contient au moins deux chemins ; l'actif courant
        # est celui de la clé correspondante (mask/background), et le
        # cycle passe au suivant en boucle.
        "variants": {
            "mask": [FOREST_SEG_DEFAULT, FOREST_SEG_ALT],
            "background": [FOREST_BG_DEFAULT, FOREST_BG_ALT],
        },

        # Comportements des objets bleus (carte courante) :
        #   cycle_map_seg : le masque SEG bascule vers la variante suivante
        #   cycle_map_bg  : l'image de fond bascule vers la variante suivante
        # Les positions doivent correspondre au centre d'un objet bleu de
        # la carte (dans INTERACT_MATCH_TOLERANCE).
        "interactions": [
            {"pos": [184, 154], "action": "cycle_map_seg"},
            {"pos": [112, 227], "action": "cycle_map_bg"},
        ],

        "perspective": {
            "enabled": False,
            "top_scale": 1.00,
            "bottom_scale": 1.00,
        },

        "exits": {
            "left": {
                "map": "Village",
                "spawn": (950, 437),
            },
            "right": {
                "map": "Boss Combat",
                "spawn": (500, 370),
            },
        },
    },
    {
        "name": "Boss Combat",
        "background": BASE_DIR / "asset/world/bossecombat.png",
        "mask": BASE_DIR / "asset/world/bossecombatSEG.png",

        # Les 5 bougies (centre de la pièce). Activer chaque bougie
        # (action "light_candle", traitée dans game.py) fait progresser
        # le combat ; les 5 allumées -> le monstre meurt et on bascule
        # sur la carte "Post Combat".
        "interactions": [
            {"pos": [506, 224], "action": "light_candle"},
            {"pos": [649, 325], "action": "light_candle"},
            {"pos": [348, 330], "action": "light_candle"},
            {"pos": [597, 495], "action": "light_candle"},
            {"pos": [402, 498], "action": "light_candle"},
        ],

        "perspective": {
            "enabled": False,
            "top_scale": 1.00,
            "bottom_scale": 1.00,
        },

        # Sortie vers la forêt (échappatoire si le combat n'est pas fini).
        "exits": {
            "left": {
                "map": "Forêt",
                "spawn": (800, 360),
            },
        },
    },
    {
        "name": "Post Combat",
        "background": BASE_DIR / "asset/world/bossepasscombat.png",
        "mask": BASE_DIR / "asset/world/bossepasscombatSEG.png",

        # Le trône (droite) : interagir transforme le monstre en monster2
        # (behavior "transform_monster") et pose le drapeau "monster2_active"
        # (quand on revient au village, tous les PNJ fuient).
        # Interactable seulement après la victoire (condition monster_defeated).
        "interactions": [
            {
                "pos": [860, 545],
                "action": "transform_monster",
                "name": "Trône",
                "requires": ["monster_defeated"],
                "flag": "monster2_active",
                "flag_value": True,
            },
        ],

        "perspective": {
            "enabled": False,
            "top_scale": 1.00,
            "bottom_scale": 1.00,
        },

        # On quitte la carte par la gauche (vers le village).
        "exits": {
            "left": {
                "map": "Village",
                "spawn": (950, 437),
            },
        },
    },
]

# Appliquer les overrides du tuner à tous les personnages (joueur et NPC)
# pour qu'ils soient pris en compte dès la construction des Player / Npc.
for _character in CHARACTERS:
    apply_sprite_overrides(_character)
for _map in MAPS:
    for _npc in _map.get("npcs", []):
        apply_sprite_overrides(_npc)

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