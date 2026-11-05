
import pygame

from pathlib import Path

from settings import (
    IDLE_COL,
    ANIMATION_FPS,
    SPRITE_SCALE,
    ANIMATION,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
)
from sprite_loader import resolve_crop_config, slice_sprite_sheet

# --- Croissance du joueur (boss) — cumul par PNJ dévoré ---
# Chaque PNJ « mangé » au contact augmente, de façon cumulative :
SCALE_INCREMENT = 0.08    # +8 % de taille (base_scale) par PNJ
RADIUS_INCREMENT = 4.0    # +4 px de hitbox (collision_radius) par PNJ
SPEED_INCREMENT = 8.0     # +8 px/s de vitesse par PNJ


class Player:
    def __init__(self, x, y, character_data):
        # Paramètres propres au personnage
        self.name = character_data["name"]
        self.sprite_path = character_data["sprite"]

        self.base_scale = (
            SPRITE_SCALE * character_data.get("scale", 0.25)
        )
        self.speed = character_data.get("speed", 220)
        self.collision_radius = character_data.get(
            "collision_radius", 5
        )

        # Valeurs de référence (avant transformation / croissance).
        self._base_scale = float(self.base_scale)
        self._base_speed = float(self.speed)
        self._base_collision_radius = float(self.collision_radius)

        # Croissance (boss) : cumul par PNJ dévoré.
        self.eaten_count = 0

        # Config de découpe résolue : override par personnage (data-driven)
        # + défauts globaux. Le blit et l'anchor en utilisent.
        self.crop_size, self.crop_offsets, self.anchor_offsets = (
            resolve_crop_config(character_data)
        )

        try:
            sheet = pygame.image.load(
                str(self.sprite_path)
            ).convert_alpha()
        except (pygame.error, FileNotFoundError) as error:
            raise RuntimeError(
                f"Impossible de charger le personnage : "
                f"{self.sprite_path}\n{error}"
            ) from error

        sheet_w, sheet_h = sheet.get_size()
        print(f"Sprite sheet ({self.name}) : {sheet_w} x {sheet_h}")

        # Les images sont découpées à leur taille de référence.
        # Leur échelle finale sera appliquée au moment du dessin.
        self.sprites = slice_sprite_sheet(
            sheet,
            sheet_w,
            sheet_h,
            self.crop_size,
            self.crop_offsets,
        )

        self.x = float(x)
        self.y = float(y)

        self.direction = "face"
        self.anim_index = 0
        self.anim_timer = 0.0
        self.moving = False

        # --- État « boss » (monster2) — P4 : le trône transforme le
        # JOUEUR (monster2.png + vitesse 180), pas le monstre. ---
        self._monster2 = False
        self._monster2_speed = self._base_speed
        self._original_sprite = self.sprite_path

        # Synchronise les stats (base_scale / speed / collision_radius).
        self._sync_stats()


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

        # Évite que le déplacement diagonal soit plus rapide.
        length = (move_x**2 + move_y**2) ** 0.5
        move_x /= length
        move_y /= length

        step_x = move_x * self.speed * dt
        step_y = move_y * self.speed * dt

        def can_move_to(x, y):
            if not collisions_enabled:
                return True

            return game_map.can_stand_at(
                x, y, self.collision_radius
            )

        # Séparer les axes permet de glisser le long des murs.
        if can_move_to(self.x + step_x, self.y):
            self.x += step_x

        if can_move_to(self.x, self.y + step_y):
            self.y += step_y

        if abs(move_x) > abs(move_y):
            self.direction = (
                "droite" if move_x > 0 else "gauche"
            )
        else:
            self.direction = "face" if move_y > 0 else "dos"

        sequence = ANIMATION[self.direction]
        self.anim_timer += dt

        while self.anim_timer >= 1.0 / ANIMATION_FPS:
            self.anim_timer -= 1.0 / ANIMATION_FPS
            self.anim_index = (
                self.anim_index + 1
            ) % len(sequence)

        self.x = max(0, min(WINDOW_WIDTH - 1, self.x))
        self.y = max(0, min(WINDOW_HEIGHT - 1, self.y))

    def draw(self, screen, game_map):
        if self.moving:
            col = ANIMATION[self.direction][self.anim_index]
        else:
            col = IDLE_COL

        # Facteur de perspective fourni par la carte.
        perspective_scale = game_map.get_perspective_scale(self.y)
        final_scale = self.base_scale * perspective_scale

        source_sprite = self.sprites[self.direction][col]

        width = max(1, round(source_sprite.get_width() * final_scale))
        height = max(1, round(source_sprite.get_height() * final_scale))

        sprite = pygame.transform.scale(
            source_sprite,
            (width, height),
        )

        #print("Position du joueur x , y :", self.x, self.y) # ------------------------------------
        # Le point (x, y) reste ancré au niveau des pieds.
        sprite_x = round(self.x - sprite.get_width() / 2)
        sprite_y = round(self.y - sprite.get_height())

        anchor_x, anchor_y = self.anchor_offsets[self.direction]
        sprite_x += round(anchor_x * final_scale)
        sprite_y += round(anchor_y * final_scale)

        screen.blit(sprite, (sprite_x, sprite_y))

    def _reload_sprite(self):
        """Recharge la feuille du sprite à ``self.sprite_path`` et la
        redécoupe avec les mêmes paramètres (découpes + anchor) qu'à
        l'initialisation."""
        try:
            sheet = pygame.image.load(str(self.sprite_path)).convert_alpha()
        except (pygame.error, FileNotFoundError) as error:
            raise RuntimeError(
                f"Impossible de charger le sprite : {self.sprite_path}\n{error}"
            ) from error
        sheet_w, sheet_h = sheet.get_size()
        print(f"Sprite sheet ({self.name}) : {sheet_w} x {sheet_h}")
        self.sprites = slice_sprite_sheet(
            sheet,
            sheet_w,
            sheet_h,
            self.crop_size,
            self.crop_offsets,
        )

    def transform_monster2(self, sprite_path, speed):
        """Met le joueur dans l'état « boss » : sprite ``sprite_path``
        (``monster2.png``) + ``speed`` augmenté (180). Idempotent ;
        ``reset_monster2()`` remet l'apparence et la vitesse d'origine.

        Seul l'apparence (sprite) et la vitesse de base changent — le
        comportement (mouvement, collisions) reste celui du joueur.
        La croissance (taille / hitbox / bonus vitesse) acquise par la
        dévoration de PNJ est conservée (voir ``feed`` / ``_sync_stats``)."""
        if self._monster2:
            return
        self._monster2 = True
        self._monster2_speed = float(speed)
        self.sprite_path = Path(sprite_path)
        self._reload_sprite()
        self._sync_stats()

    def reset_monster2(self):
        """Remet le joueur à son apparence et sa vitesse d'origine
        (annule l'état « boss »). La croissance acquise par la dévoration
        de PNJ (taille / hitbox / bonus vitesse) est CONSERVÉE.
        Idempotent."""
        if not self._monster2:
            return
        self._monster2 = False
        self.sprite_path = Path(self._original_sprite)
        self._reload_sprite()
        self._sync_stats()

    def feed(self, count):
        """Dévoration : le joueur vient de manger des PNJ (cumul).

        ``count`` = nombre TOTAL de PNJ dévorés (>= l'actuel). La taille
        (``base_scale``), le hitbox (``collision_radius``) et la vitesse
        augmentent de façon proportionnelle à chaque PNJ. Idempotent /
        fail-safe : aucune régression possible.
        """
        count = int(count)
        if count <= self.eaten_count:
            return
        self.eaten_count = count
        self._sync_stats()

    def _sync_stats(self):
        """Recalcule ``base_scale``, ``speed`` et ``collision_radius`` à
        partir des valeurs de référence, de l'état de transformation
        (``_monster2``) et de la croissance (``eaten_count``).

        Appelé par ``transform_monster2`` / ``reset_monster2`` / ``feed``
        (et à l'init) pour garder les stats cohérentes.
        """
        growth = 1.0 + SCALE_INCREMENT * self.eaten_count
        self.base_scale = self._base_scale * growth
        self.collision_radius = (
            self._base_collision_radius
            + RADIUS_INCREMENT * self.eaten_count
        )
        base_speed = (
            self._monster2_speed
            if self._monster2
            else self._base_speed
        )
        self.speed = base_speed + SPEED_INCREMENT * self.eaten_count
