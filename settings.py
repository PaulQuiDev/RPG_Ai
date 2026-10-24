from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

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
    },
    {
        "name": "Forêt",
        "background": BASE_DIR / "asset/world/fro1.png",
        "mask": BASE_DIR / "asset/world/fro1SEG.png",

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
        },
    },
]

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
INTERACT_PROXIMITY = 70.0
INTERACT_CONTACT = 45.0
INTERACT_BLUE_THRESHOLD = 96
INTERACT_MIN_AREA = 100