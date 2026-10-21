
from pathlib import Path

# Dossier contenant les fichiers du jeu
BASE_DIR = Path(__file__).resolve().parent

# Images
SPRITE_PATH = BASE_DIR / "asset/carater/woman.png"
BACKGROUND_PATH = BASE_DIR / "asset/world/vil1.png"
MASK_PATH = BASE_DIR / "asset/world/vil1SEG.png"

# Fenêtre
WINDOW_WIDTH = 960
WINDOW_HEIGHT = 720
WINDOW_BACKGROUND = (45, 48, 58)
WINDOW_TITLE = "RPG - Prototype"

# Personnage
ROWS = 4
COLS = 3
IDLE_COL = 1
ANIMATION_FPS = 8
SPRITE_SCALE = 2
CHARACTER_SCALE = 0.25
DISPLAY_SCALE = SPRITE_SCALE * CHARACTER_SCALE
MOVE_SPEED = 220

# Collisions
COLLISIONS_ENABLED_DEFAULT = True
COLLISION_RADIUS = 5

# Lignes de la spritesheet
DIRECTIONS = {
    "face": 0,
    "gauche": 1,
    "droite": 2,
    "dos": 3,
}

# Séquence des frames de marche
ANIMATION = {
    "face": [0, 1, 2, 1],
    "gauche": [0, 1, 2, 1],
    "droite": [0, 1, 2, 1],
    "dos": [0, 1, 2, 1],
}

# Décalage de la zone découpée dans l'image source
CROP_OFFSETS = {
    "face": {
        0: (0, 15),
        1: (0, 15),
        2: (0, 15),
    },
    "gauche": {
        0: (0, 0),
        1: (0, 0),
        2: (0, 10),
    },
    "droite": {
        0: (0, -10),
        1: (0, -10),
        2: (0, -10),
    },
    "dos": {
        0: (-12, -25),
        1: (0, -25),
        2: (2, -25),
    },
}

# Taille de chaque découpe, en pixels de l'image source
CELL_W = 200
CELL_H = 300

CROP_SIZE = {
    "face": {
        0: (CELL_W, CELL_H),
        1: (CELL_W, CELL_H),
        2: (CELL_W, CELL_H),
    },
    "gauche": {
        0: (CELL_W, CELL_H - 20),
        1: (CELL_W, CELL_H),
        2: (CELL_W, CELL_H),
    },
    "droite": {
        0: (CELL_W, CELL_H),
        1: (CELL_W, CELL_H),
        2: (CELL_W, CELL_H),
    },
    "dos": {
        0: (CELL_W, CELL_H),
        1: (CELL_W, CELL_H),
        2: (CELL_W, CELL_H),
    },
}

# Ajustement visuel du point d'ancrage
ANCHOR_OFFSETS = {
    "face": (0, 0),
    "gauche": (0, 0),
    "droite": (0, 0),
    "dos": (0, 0),
}
