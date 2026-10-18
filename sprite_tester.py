
import sys
import pygame

# ============================================================
# CONFIGURATION
# ============================================================

IMAGE_PATH = (
    sys.argv[1]
    if len(sys.argv) > 1
    else "Qwen_image_2.1_00003.png"
    #else "Qwen_image_2.1_00133.png"
    #else "Qwen_image_2.1_00122.png"
)

ROWS = 4
COLS = 3

IDLE_COL = 1
ANIMATION_FPS = 8
SCALE = 2
BACKGROUND = (45, 48, 58)

# Ordre des lignes dans l'image
DIRECTIONS = {
    "face": 0,
    "gauche": 1,
    "droite": 2,
    "dos": 3,
}

# Séquence des colonnes pendant la marche
ANIMATION = {
    "face":   [0, 1, 2, 1],
    "gauche": [0, 1, 2, 1],
    "droite": [0, 1, 2, 1],
    "dos":    [0, 1, 2, 1],
}

# ------------------------------------------------------------
# DÉCALAGE DE LA ZONE DE DÉCOUPE
# ------------------------------------------------------------
# (dx, dy), en pixels source.
# Positif : vers la droite / le bas.
# Négatif : vers la gauche / le haut.
#
# La zone peut dépasser des limites de la cellule et de l'image.
# Les parties extérieures à l'image deviennent transparentes.

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
# None = dimensions normales de la cellule.
# Sinon : (largeur, hauteur), en pixels source.
#
# Exemple : (330, 340) récupère une zone plus grande.
# Chaque colonne peut avoir sa propre taille.
celL = 200
celH = 300

CROP_SIZE = {
    "face": {
        0: (celL, celH),
        1: (celL, celH),
        2: (celL, celH),
    },
    "gauche": {
        0: (celL, celH-20),
        1: (celL, celH),
        2: (celL, celH),
    },
    "droite": {
        0: (celL, celH),
        1: (celL, celH),
        2: (celL, celH),
    },
    "dos": {
        0: (celL, celH),
        1: (celL, celH),
        2: (celL, celH),
    },
}

# ------------------------------------------------------------
# POSITION À L'ÉCRAN
# ------------------------------------------------------------
# (dx, dy), en pixels source après découpe.
# Cela déplace l'image affichée, pas la zone source.
# Utilise ceci pour régler le centrage visuel du personnage.

ANCHOR_OFFSETS = {
    "face": (0, 0),
    "gauche": (0, 0),
    "droite": (0, 0),
    "dos": (0, 0),
}

# ============================================================
# INITIALISATION
# ============================================================

pygame.init()
pygame.display.set_caption("Sprite Tester - RPG")

sheet = pygame.image.load(IMAGE_PATH)
sheet_w, sheet_h = sheet.get_size()

print(f"Sprite sheet : {sheet_w} x {sheet_h}")

if sheet_w != 832 or sheet_h != 1248:
    print("Attention : dimensions différentes de 832 x 1248.")

# ============================================================
# DÉCOUPAGE AVEC OFFSETS ET TAILLES PERSONNALISÉES
# ============================================================

sprites = {}

for direction, row in DIRECTIONS.items():
    sprites[direction] = []

    for col in range(COLS):
        # Limites de la cellule d'origine
        x0 = col * sheet_w // COLS
        x1 = (col + 1) * sheet_w // COLS
        y0 = row * sheet_h // ROWS
        y1 = (row + 1) * sheet_h // ROWS

        cell_w = x1 - x0
        cell_h = y1 - y0

        # Taille spécifique de la découpe
        custom_size = CROP_SIZE[direction].get(col)

        if custom_size is None:
            crop_w, crop_h = cell_w, cell_h
        else:
            crop_w, crop_h = custom_size

        # Centre de la cellule comme référence
        center_x = (x0 + x1) // 2
        center_y = (y0 + y1) // 2

        # Position initiale du rectangle centré
        crop_x = center_x - crop_w // 2
        crop_y = center_y - crop_h // 2

        # Ajouter les offsets personnalisés
        dx, dy = CROP_OFFSETS[direction].get(col, (0, 0))
        crop_x += dx
        crop_y += dy

        # Surface de sortie transparente
        frame = pygame.Surface(
            (crop_w, crop_h),
            pygame.SRCALPHA,
        )

        # Intersection entre la découpe et l'image source.
        # Aucune limitation des offsets eux-mêmes.
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

        sprites[direction].append(frame)

# ============================================================
# FENÊTRE
# ============================================================

frame_w = max(
    sprite.get_width()
    for frames in sprites.values()
    for sprite in frames
)

frame_h = max(
    sprite.get_height()
    for frames in sprites.values()
    for sprite in frames
)

screen = pygame.display.set_mode(
    (frame_w * SCALE + 240, frame_h * SCALE + 150)
)

clock = pygame.time.Clock()
font = pygame.font.SysFont("sans", 18)

KEY_DIRECTIONS = {
    pygame.K_UP: "face",
    pygame.K_LEFT: "gauche",
    pygame.K_RIGHT: "droite",
    pygame.K_DOWN: "dos",
}

# ============================================================
# TOUCHES DE SÉLECTION DES FRAMES
# ============================================================

FRAME_KEYS = {
    pygame.K_1: 0,
    pygame.K_2: 1,
    pygame.K_3: 2,
    pygame.K_KP1: 0,
    pygame.K_KP2: 1,
    pygame.K_KP3: 2,
}

# Constantes alternatives si disponibles
for key_name, col in [
    ("K_KP_END", 0),
    ("K_KP_DOWN", 1),
    ("K_KP_PAGEDOWN", 2),
]:
    key_code = getattr(pygame, key_name, None)
    if key_code is not None:
        FRAME_KEYS[key_code] = col

# ============================================================
# ÉTAT DU TESTEUR
# ============================================================

direction = "face"
anim_index = 0
anim_timer = 0.0

debug_mode = False
debug_index = 0
selected_col = IDLE_COL

running = True

# ============================================================
# BOUCLE PRINCIPALE
# ============================================================

while running:
    dt = clock.tick(60) / 1000
    keys = pygame.key.get_pressed()

    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.KEYDOWN:

            if event.key == pygame.K_ESCAPE:
                running = False

            ctrl = bool(event.mod & pygame.KMOD_CTRL)

            # Ctrl + flèche :
            # appuis successifs sur la même direction = frame suivante.
            if ctrl and event.key in KEY_DIRECTIONS:
                new_direction = KEY_DIRECTIONS[event.key]

                if debug_mode and new_direction == direction:
                    sequence = ANIMATION[direction]
                    debug_index = (debug_index + 1) % len(sequence)
                    selected_col = sequence[debug_index]
                else:
                    direction = new_direction
                    debug_mode = True
                    debug_index = 0
                    selected_col = ANIMATION[direction][debug_index]

                anim_index = debug_index
                anim_timer = 0.0

            # Choisir directement une colonne en mode debug
            elif debug_mode and event.key in FRAME_KEYS:
                selected_col = FRAME_KEYS[event.key]

                # Synchroniser l'index avec la séquence si possible
                sequence = ANIMATION[direction]

                if selected_col in sequence:
                    debug_index = sequence.index(selected_col)
                else:
                    # Colonne libre, hors de la séquence
                    debug_index = -1

                anim_timer = 0.0

    # --------------------------------------------------------
    # ANIMATION NORMALE
    # --------------------------------------------------------

    moving = False

    if not debug_mode:
        for key, dir_name in KEY_DIRECTIONS.items():
            if keys[key]:
                direction = dir_name
                moving = True
                break

    if debug_mode:
        # La colonne choisie reste affichée
        col = selected_col

    elif moving:
        sequence = ANIMATION[direction]
        anim_timer += dt

        while anim_timer >= 1 / ANIMATION_FPS:
            anim_timer -= 1 / ANIMATION_FPS
            anim_index = (anim_index + 1) % len(sequence)

        col = sequence[anim_index]

    else:
        col = IDLE_COL
        anim_index = 0
        anim_timer = 0.0

    # --------------------------------------------------------
    # AFFICHAGE
    # --------------------------------------------------------

    screen.fill(BACKGROUND)

    sprite = sprites[direction][col]

    sprite = pygame.transform.scale(
        sprite,
        (
            sprite.get_width() * SCALE,
            sprite.get_height() * SCALE,
        ),
    )

    # Centrage à l'écran
    x = (screen.get_width() - sprite.get_width()) // 2
    y = (screen.get_height() - sprite.get_height()) // 2 - 35

    # Offset d'affichage indépendant de la découpe
    anchor_x, anchor_y = ANCHOR_OFFSETS[direction]
    x += anchor_x * SCALE
    y += anchor_y * SCALE

    screen.blit(sprite, (x, y))

    # --------------------------------------------------------
    # INFORMATIONS DE DEBUG
    # --------------------------------------------------------

    status = "DEBUG FIGE" if debug_mode else (
        "MARCHE" if moving else "STATIQUE"
    )

    lines = [
        f"Direction : {direction} | Colonne : {col + 1}",
        f"Mode : {status}",
        "Ctrl + fleche : frame suivante, puis figer",
        "1/2/3 ou pave numerique : choisir colonne",
        "Fleche sans Ctrl : reprendre la marche",
        "ESC : quitter",
    ]

    for i, line in enumerate(lines):
        label = font.render(line, True, (240, 240, 240))
        screen.blit(
            label,
            (10, screen.get_height() - 137 + i * 22),
        )

    pygame.display.flip()

pygame.quit()
