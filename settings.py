from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Personnages disponibles
CHARACTERS = [
    {
        "name": "Femme",
        "sprite": BASE_DIR / "asset/carater/woman.png",
    },
    {
        "name": "Homme",
        "sprite": BASE_DIR / "asset/carater/man.png",
    },
]

# Cartes disponibles
MAPS = [
    {
        "name": "Village",
        "background": BASE_DIR / "asset/world/vil1.png",
        "mask": BASE_DIR / "asset/world/vil1SEG.png",
    },
    {
        "name": "Forêt",
        "background": BASE_DIR / "asset/world/forest.png",
        "mask": BASE_DIR / "asset/world/forestSEG.png",
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