from pathlib import Path

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
            {"name": "Champignon 1", "sprite": BASE_DIR / "asset/carater/mush1.png", "pos": [400, 430], "message": "Salut !"},
            {"name": "Champignon 2", "sprite": BASE_DIR / "asset/carater/mush2.png", "pos": [720, 400], "message": "Bonjour."},
            {"name": "Champignon 3", "sprite": BASE_DIR / "asset/carater/mush3.png", "pos": [680, 450], "message": "Bonsoir."},
            {"name": "Monstre", "sprite": BASE_DIR / "asset/carater/monster2.png", "behavior": "patrol", "speed": 55, "scale": 0.35,
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