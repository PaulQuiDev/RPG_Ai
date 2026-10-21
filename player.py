
import pygame

from settings import (
    SPRITE_PATH,
    ROWS,
    COLS,
    IDLE_COL,
    ANIMATION_FPS,
    DISPLAY_SCALE,
    MOVE_SPEED,
    DIRECTIONS,
    ANIMATION,
    CROP_OFFSETS,
    CROP_SIZE,
    ANCHOR_OFFSETS,
    COLLISION_RADIUS,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
)


class Player:
    def __init__(self, x, y):
        try:
            sheet = pygame.image.load(
                str(SPRITE_PATH)
            ).convert_alpha()
        except (pygame.error, FileNotFoundError) as error:
            raise RuntimeError(
                f"Impossible de charger la spritesheet : {error}"
            ) from error

        sheet_w, sheet_h = sheet.get_size()
        print(f"Sprite sheet : {sheet_w} x {sheet_h}")

        self.sprites = self._load_sprites(sheet, sheet_w, sheet_h)

        self.x = float(x)
        self.y = float(y)

        # Position (x, y) = centre des pieds.
        self.direction = "face"
        self.anim_index = 0
        self.anim_timer = 0.0
        self.moving = False

    def _load_sprites(self, sheet, sheet_w, sheet_h):
        sprites = {}

        for direction, row in DIRECTIONS.items():
            sprites[direction] = []

            for col in range(COLS):
                x0 = col * sheet_w // COLS
                x1 = (col + 1) * sheet_w // COLS
                y0 = row * sheet_h // ROWS
                y1 = (row + 1) * sheet_h // ROWS

                cell_w = x1 - x0
                cell_h = y1 - y0

                crop_w, crop_h = CROP_SIZE[direction].get(
                    col, (cell_w, cell_h)
                )

                center_x = (x0 + x1) // 2
                center_y = (y0 + y1) // 2

                dx, dy = CROP_OFFSETS[direction].get(
                    col, (0, 0)
                )

                crop_x = center_x - crop_w // 2 + dx
                crop_y = center_y - crop_h // 2 + dy

                frame = pygame.Surface(
                    (crop_w, crop_h), pygame.SRCALPHA
                )

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

                scaled = pygame.transform.scale(
                    frame,
                    (
                        max(1, round(crop_w * DISPLAY_SCALE)),
                        max(1, round(crop_h * DISPLAY_SCALE)),
                    ),
                )

                sprites[direction].append(scaled)

        return sprites

    def update(self, dt, keys, game_map, collisions_enabled):
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

        self.moving = move_x != 0 or move_y != 0

        if not self.moving:
            self.anim_index = 0
            self.anim_timer = 0.0
            return

        # Vitesse identique en diagonale et en ligne droite.
        length = (move_x**2 + move_y**2) ** 0.5
        move_x /= length
        move_y /= length

        step_x = move_x * MOVE_SPEED * dt
        step_y = move_y * MOVE_SPEED * dt

        def can_move_to(x, y):
            if not collisions_enabled:
                return True

            return game_map.can_stand_at(
                x, y, COLLISION_RADIUS
            )

        # Séparer les axes permet de glisser le long des murs.
        if can_move_to(self.x + step_x, self.y):
            self.x += step_x

        if can_move_to(self.x, self.y + step_y):
            self.y += step_y

        if abs(move_x) > abs(move_y):
            self.direction = "droite" if move_x > 0 else "gauche"
        else:
            self.direction = "face" if move_y > 0 else "dos"

        sequence = ANIMATION[self.direction]
        self.anim_timer += dt

        while self.anim_timer >= 1.0 / ANIMATION_FPS:
            self.anim_timer -= 1.0 / ANIMATION_FPS
            self.anim_index = (
                self.anim_index + 1
            ) % len(sequence)

        # Garder les pieds dans la fenêtre.
        self.x = max(0, min(WINDOW_WIDTH - 1, self.x))
        self.y = max(0, min(WINDOW_HEIGHT - 1, self.y))

    def draw(self, screen):
        if self.moving:
            col = ANIMATION[self.direction][self.anim_index]
        else:
            col = IDLE_COL

        sprite = self.sprites[self.direction][col]

        sprite_x = int(self.x - sprite.get_width() / 2)
        sprite_y = int(self.y - sprite.get_height())

        anchor_x, anchor_y = ANCHOR_OFFSETS[self.direction]
        sprite_x += round(anchor_x * DISPLAY_SCALE)
        sprite_y += round(anchor_y * DISPLAY_SCALE)

        screen.blit(sprite, (sprite_x, sprite_y))
