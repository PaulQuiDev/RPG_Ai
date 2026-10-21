import sys
from pathlib import Path
import pygame

# ============================================================
# CONFIGURATION
# ============================================================

# Utilisation :
#   python gameTest_corrige.py
#   python gameTest_corrige.py spritesheet.png fond.png
#
# Les chemins peuvent aussi être définis directement ci-dessous.

SCRIPT_DIR = Path(__file__).resolve().parent

# Par défaut, les images sont cherchées à côté de ce script.
# Si un chemin est fourni en argument, il est utilisé tel quel
# s'il est absolu ; sinon il est résolu depuis le dossier courant.
SPRITE_PATH = (
    Path(sys.argv[1]).expanduser()
    if len(sys.argv) > 1
    else SCRIPT_DIR / "Qwen_image_2.1_00006.png"
)
BACKGROUND_PATH = (
    Path(sys.argv[2]).expanduser()
    if len(sys.argv) > 2
    else SCRIPT_DIR / "Krea2_BG2.png"
)

MASK_PATH = SCRIPT_DIR / "Segmentation.png"

if not SPRITE_PATH.is_absolute() and len(sys.argv) > 1:
    SPRITE_PATH = (Path.cwd() / SPRITE_PATH).resolve()
if not BACKGROUND_PATH.is_absolute() and len(sys.argv) > 2:
    BACKGROUND_PATH = (Path.cwd() / BACKGROUND_PATH).resolve()

ROWS = 4
COLS = 3

IDLE_COL = 1
ANIMATION_FPS = 8
SPRITE_SCALE = 2  # Échelle de base
CHARACTER_SCALE = 0.25  # Réduction supplémentaire : 0.50 = moitié de la taille précédente
DISPLAY_SCALE = SPRITE_SCALE * CHARACTER_SCALE
COLLISIONS_ENABLED = True

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 720
WINDOW_BACKGROUND = (45, 48, 58)

# Vitesse du personnage en pixels par seconde.
MOVE_SPEED = 220

# Ordre des lignes dans la sprite sheet
DIRECTIONS = {
    "face": 0,
    "gauche": 1,
    "droite": 2,
    "dos": 3,
}

# Colonnes utilisées pendant la marche
ANIMATION = {
    "face":   [0, 1, 2, 1],
    "gauche": [0, 1, 2, 1],
    "droite": [0, 1, 2, 1],
    "dos":    [0, 1, 2, 1],
}

# ------------------------------------------------------------
# DÉCALAGE DE LA ZONE DE DÉCOUPE
# ------------------------------------------------------------
# (dx, dy), en pixels de l'image source.
# Positif : droite / bas ; négatif : gauche / haut.

CROP_OFFSETS = {
    "face": {
        0: (0, 15),
        1: (0, 15),
        2: (0, 15),
    },
    "gauche": {
        0: (0, 0),
        1: (0, 0),
        2: (0, +10),
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

# ------------------------------------------------------------
# TAILLE PERSONNALISÉE DE LA ZONE DE DÉCOUPE
# ------------------------------------------------------------
# None = taille de la cellule d'origine.
# Sinon : (largeur, hauteur), en pixels source.

cell_w_custom = 200
cell_h_custom = 300

CROP_SIZE = {
    "face": {
        0: (cell_w_custom, cell_h_custom),
        1: (cell_w_custom, cell_h_custom),
        2: (cell_w_custom, cell_h_custom),
    },
    "gauche": {
        0: (cell_w_custom, cell_h_custom - 20),
        1: (cell_w_custom, cell_h_custom),
        2: (cell_w_custom, cell_h_custom),
    },
    "droite": {
        0: (cell_w_custom, cell_h_custom),
        1: (cell_w_custom, cell_h_custom),
        2: (cell_w_custom, cell_h_custom),
    },
    "dos": {
        0: (cell_w_custom, cell_h_custom),
        1: (cell_w_custom, cell_h_custom),
        2: (cell_w_custom, cell_h_custom),
    },
}

# ------------------------------------------------------------
# DÉCALAGE VISUEL DU PERSONNAGE
# ------------------------------------------------------------
# (dx, dy), en pixels source après découpe.
# Permet de corriger le centrage de chaque orientation.

ANCHOR_OFFSETS = {
    "face": (0, 0),
    "gauche": (0, 0),
    "droite": (0, 0),
    "dos": (0, 0),
}

# ============================================================
# INITIALISATION DE PYGAME ET CHARGEMENT DES IMAGES
# ============================================================

pygame.init()
pygame.display.set_caption("RPG - Déplacement du personnage")

# IMPORTANT : créer le mode vidéo AVANT d'appeler convert_alpha().
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
clock = pygame.time.Clock()
font = pygame.font.SysFont("sans", 18)

try:
    sheet = pygame.image.load(str(SPRITE_PATH)).convert_alpha()
except (pygame.error, FileNotFoundError) as error:
    pygame.quit()
    raise SystemExit(
        f"Impossible de charger la sprite sheet :\\n{SPRITE_PATH}\\n{error}"
    )

try:
    background_original = pygame.image.load(str(BACKGROUND_PATH)).convert()
except (pygame.error, FileNotFoundError) as error:
    pygame.quit()
    raise SystemExit(
        f"Impossible de charger l'image de fond :\\n{BACKGROUND_PATH}\\n{error}"
    )

sheet_w, sheet_h = sheet.get_size()
print(f"Sprite sheet : {sheet_w} x {sheet_h}")
print(f"Fond : {BACKGROUND_PATH}")

if sheet_w != 832 or sheet_h != 1248:
    print("Attention : dimensions différentes de 832 x 1248.")

# Le fond est redimensionné une fois à la taille de la fenêtre.
background = pygame.transform.smoothscale(
    background_original, (WINDOW_WIDTH, WINDOW_HEIGHT)
)

try:
    mask_original = pygame.image.load(str(MASK_PATH)).convert()
except (pygame.error, FileNotFoundError) as error:
    pygame.quit()
    raise SystemExit(f"Impossible de charger le masque :\n{MASK_PATH}\n{error}")

if mask_original.get_size() != background_original.get_size():
    pygame.quit()
    raise SystemExit("Le masque doit avoir la même taille que le fond.")

collision_mask = pygame.transform.scale(
    mask_original, (WINDOW_WIDTH, WINDOW_HEIGHT)
)

# ============================================================
# DÉCOUPAGE DES SPRITES
# ============================================================

sprites = {}

for direction, row in DIRECTIONS.items():
    sprites[direction] = []

    for col in range(COLS):
        # Limites de la cellule dans la sprite sheet
        x0 = col * sheet_w // COLS
        x1 = (col + 1) * sheet_w // COLS
        y0 = row * sheet_h // ROWS
        y1 = (row + 1) * sheet_h // ROWS

        cell_w = x1 - x0
        cell_h = y1 - y0

        # Taille de découpe personnalisée
        custom_size = CROP_SIZE[direction].get(col)
        if custom_size is None:
            crop_w, crop_h = cell_w, cell_h
        else:
            crop_w, crop_h = custom_size

        # Rectangle centré sur la cellule, puis décalé
        center_x = (x0 + x1) // 2
        center_y = (y0 + y1) // 2
        crop_x = center_x - crop_w // 2
        crop_y = center_y - crop_h // 2

        dx, dy = CROP_OFFSETS[direction].get(col, (0, 0))
        crop_x += dx
        crop_y += dy

        # Surface transparente de destination
        frame = pygame.Surface((crop_w, crop_h), pygame.SRCALPHA)

        # Copier uniquement la partie qui existe dans l'image source
        src_left = max(0, crop_x)
        src_top = max(0, crop_y)
        src_right = min(sheet_w, crop_x + crop_w)
        src_bottom = min(sheet_h, crop_y + crop_h)

        if src_right > src_left and src_bottom > src_top:
            source_rect = pygame.Rect(
                src_left,
                src_top,
                src_right - src_left,
                src_bottom - src_top,
            )
            target_rect = pygame.Rect(
                src_left - crop_x,
                src_top - crop_y,
                source_rect.width,
                source_rect.height,
            )
            frame.blit(sheet, target_rect, source_rect)

        # Redimensionner chaque frame une seule fois
        scaled_frame = pygame.transform.scale(
            frame,
            (max(1, round(crop_w * DISPLAY_SCALE)), max(1, round(crop_h * DISPLAY_SCALE))),
        )
        sprites[direction].append(scaled_frame)

# ============================================================
# CONTRÔLES ET ÉTAT DU PERSONNAGE
# ============================================================

COLLISION_RADIUS = 5

def is_walkable(x, y):
    x, y = int(x), int(y)

    if not (0 <= x < WINDOW_WIDTH and 0 <= y < WINDOW_HEIGHT):
        return False

    red, green, blue, *_ = collision_mask.get_at((x, y))

    # Vert = accessible ; rouge = interdit.
    return green > red and green > blue


def can_stand_at(x, y):
    # Vérification autour des pieds du personnage.
    points = [
        (x, y),
        (x - COLLISION_RADIUS, y),
        (x + COLLISION_RADIUS, y),
        (x, y - COLLISION_RADIUS),
        (x - COLLISION_RADIUS, y - COLLISION_RADIUS),
        (x + COLLISION_RADIUS, y - COLLISION_RADIUS),
    ]

    return all(is_walkable(px, py) for px, py in points)

KEY_DIRECTIONS = {
    pygame.K_UP: "dos",
    pygame.K_DOWN: "face",
    pygame.K_LEFT: "gauche",
    pygame.K_RIGHT: "droite",
}

direction = "face"
anim_index = 0
anim_timer = 0.0

# Position horizontale du centre du personnage et position de ses pieds.
player_x = WINDOW_WIDTH / 2
player_y = WINDOW_HEIGHT / 2

running = True

# ============================================================
# BOUCLE PRINCIPALE
# ============================================================

while running:
    dt = min(clock.tick(60) / 1000.0, 0.05)
    moving = False

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False

            elif event.key == pygame.K_e:
                COLLISIONS_ENABLED = not COLLISIONS_ENABLED

    keys = pygame.key.get_pressed()

    move_x = 0
    move_y = 0

    if keys[pygame.K_LEFT]:
        move_x -= 1
    if keys[pygame.K_RIGHT]:
        move_x += 1
    if keys[pygame.K_UP]:
        move_y -= 1
    if keys[pygame.K_DOWN]:
        move_y += 1


    if move_x != 0 or move_y != 0:
        moving = True

        # Éviter que le déplacement en diagonale soit plus rapide.
        length = (move_x * move_x + move_y * move_y) ** 0.5
        move_x /= length
        move_y /= length

        step_x = move_x * MOVE_SPEED * dt
        step_y = move_y * MOVE_SPEED * dt

        # Vérifier l'axe horizontal séparément.
        if not COLLISIONS_ENABLED or can_stand_at(player_x + step_x, player_y):
            player_x += step_x

        # Vérifier l'axe vertical séparément.
        if not COLLISIONS_ENABLED or can_stand_at(player_x, player_y + step_y):
            player_y += step_y

        # Choisir l'orientation correspondant à l'axe dominant.
        if abs(move_x) > abs(move_y):
            direction = "droite" if move_x > 0 else "gauche"
        else:
            direction = "face" if move_y > 0 else "dos"

        # Faire défiler l'animation à une vitesse indépendante du mouvement.
        sequence = ANIMATION[direction]
        anim_timer += dt
        while anim_timer >= 1.0 / ANIMATION_FPS:
            anim_timer -= 1.0 / ANIMATION_FPS
            anim_index = (anim_index + 1) % len(sequence)
    else:
        # À l'arrêt, afficher la colonne centrale.
        anim_index = 0
        anim_timer = 0.0

    # Limiter la position à la fenêtre.
    player_x = max(0, min(WINDOW_WIDTH, player_x))
    player_y = max(0, min(WINDOW_HEIGHT, player_y))

    # Choisir la frame actuelle.
    if moving:
        col = ANIMATION[direction][anim_index]
    else:
        col = IDLE_COL

    sprite = sprites[direction][col]

    # Dessiner le fond, puis le personnage.
    screen.blit(background, (0, 0))

    # player_x/player_y correspondent au centre des pieds du sprite.
    sprite_x = int(player_x - sprite.get_width() / 2)
    sprite_y = int(player_y - sprite.get_height())

    anchor_x, anchor_y = ANCHOR_OFFSETS[direction]
    sprite_x += round(anchor_x * DISPLAY_SCALE)
    sprite_y += round(anchor_y * DISPLAY_SCALE)

    screen.blit(sprite, (sprite_x, sprite_y))

    # Indications simples à l'écran
    status = "Marche" if moving else "À l'arrêt"
    info = [
        f"Direction : {direction} | État : {status}",
        "Flèches : déplacer le personnage",
        "Échap : quitter",
        f"Collisions E: {'activées' if COLLISIONS_ENABLED else 'désactivées'} ",
    ]

    for i, line in enumerate(info):
        label = font.render(line, True, (255, 255, 255))
        # Petit fond sombre pour rendre le texte lisible sur le décor.
        label_bg = pygame.Surface(
            (label.get_width() + 12, label.get_height() + 8),
            pygame.SRCALPHA,
        )
        label_bg.fill((0, 0, 0, 150))
        screen.blit(label_bg, (8, 8 + i * 30))
        screen.blit(label, (14, 12 + i * 30))

    pygame.display.flip()

pygame.quit()
