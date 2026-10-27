"""Monstre : entité hostile qui fonce lentement sur le joueur.

Même format de sheet que les personnages (4 directions x 3 frames, format
data-driven via `sprite_loader`). Chargée depuis `asset/carater/monster.png`
(forme initiale) ; `set_sprite()` permet de passer à `monster2.png` (forme
définitive après l'interaction avec le trône).

La détection de touche est séparée de la collision de mouvement : le
monstre se déplace avec une petite `collision_radius` (navigation), mais
il "touche" le joueur dès qu'il est à `hit_radius` (distance entre centres).
"""

import math
from pathlib import Path

import pygame

from settings import ANIMATION, ANIMATION_FPS, IDLE_COL, SPRITE_SCALE
from sprite_loader import resolve_crop_config, slice_sprite_sheet

BASE_DIR = Path(__file__).resolve().parent
MONSTER_SPRITE = BASE_DIR / "asset/carater/monster.png"
MONSTER_SPRITE_FINAL = BASE_DIR / "asset/carater/monster2.png"


class Monster:
    """Monstre qui fonce lentement sur le joueur."""

    def __init__(self, x, y, speed=55.0, scale=0.35, sprite_path=MONSTER_SPRITE):
        self.x = float(x)
        self.y = float(y)
        self.speed = float(speed)
        self.scale = scale
        self.base_scale = SPRITE_SCALE * scale
        # Collision de mouvement (navigation) — distincte de la détection
        # de contact avec le joueur (`hit_radius`).
        self.collision_radius = 12.0
        self.hit_radius = 45.0
        self.sprite_path = sprite_path
        self._load_sheet(sprite_path)
        self.direction = "face"
        self.anim_index = 0
        self.anim_timer = 0.0
        self.moving = False

    def _load_sheet(self, sprite_path):
        """Charge la feuille et découpe toutes les frames."""
        self.crop_size, self.crop_offsets, self.anchor_offsets = (
            resolve_crop_config({})
        )
        try:
            sheet = pygame.image.load(str(sprite_path)).convert_alpha()
        except (pygame.error, FileNotFoundError) as error:
            raise RuntimeError(
                f"Impossible de charger le monstre : {sprite_path}\n{error}"
            ) from error
        sheet_w, sheet_h = sheet.get_size()
        self.sprites = slice_sprite_sheet(
            sheet, sheet_w, sheet_h, self.crop_size, self.crop_offsets
        )
        self.anim_index = 0

    def set_sprite(self, sprite_path):
        """Change la feuille de sprites (transforme l'apparence, ex.
        monster -> monster2)."""
        self.sprite_path = sprite_path
        self._load_sheet(sprite_path)

    def touches(self, player):
        """True si le monstre est à `hit_radius` du centre du joueur."""
        return math.hypot(self.x - player.x, self.y - player.y) < self.hit_radius

    def move_towards(self, target_x, target_y, dt, game_map, player):
        """Avance vers la cible en respectant les collisions de la carte.

        Retourne True si, après le déplacement, le monstre touche le
        joueur (à gérer par l'appelant : remise en jeu).
        """
        dx = target_x - self.x
        dy = target_y - self.y
        dist = math.hypot(dx, dy)
        if dist < 2.0:
            self._stop()
            return self.touches(player)

        ux, uy = dx / dist, dy / dist
        step = self.speed * dt
        step_x, step_y = ux * step, uy * step

        # Orientation = direction du déplacement (comme le joueur).
        if abs(dx) > abs(dy):
            self.direction = "droite" if dx > 0 else "gauche"
        else:
            self.direction = "face" if dy > 0 else "dos"

        # Déplacement axe par axe (glisse le long des murs).
        if game_map.can_stand_at(self.x + step_x, self.y, self.collision_radius):
            self.x += step_x
        if game_map.can_stand_at(self.x, self.y + step_y, self.collision_radius):
            self.y += step_y

        self._advance_animation(dt)
        return self.touches(player)

    def _advance_animation(self, dt):
        self.moving = True
        self.anim_timer += dt
        while self.anim_timer >= 1.0 / ANIMATION_FPS:
            self.anim_timer -= 1.0 / ANIMATION_FPS
            self.anim_index = (self.anim_index + 1) % len(ANIMATION[self.direction])

    def _stop(self):
        self.moving = False
        self.anim_index = 0
        self.anim_timer = 0.0

    def draw(self, screen, game_map):
        """Draw le monstre (même logique que Player)."""
        if self.moving:
            col = ANIMATION[self.direction][self.anim_index]
        else:
            col = IDLE_COL

        perspective_scale = game_map.get_perspective_scale(self.y)
        final_scale = self.base_scale * perspective_scale
        source = self.sprites[self.direction][col]
        width = max(1, round(source.get_width() * final_scale))
        height = max(1, round(source.get_height() * final_scale))
        sprite = pygame.transform.scale(source, (width, height))

        sprite_x = round(self.x - sprite.get_width() / 2)
        sprite_y = round(self.y - sprite.get_height())
        anchor_x, anchor_y = self.anchor_offsets[self.direction]
        sprite_x += round(anchor_x * final_scale)
        sprite_y += round(anchor_y * final_scale)
        screen.blit(sprite, (sprite_x, sprite_y))
