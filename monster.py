"""Monstre : entité hostile qui fonce lentement sur le joueur.

Même format de sheet que les personnages (4 directions x 3 frames, format
data-driven via `sprite_loader`). Chargée depuis `asset/carater/monster.png`
(forme initiale) ; `set_sprite()` permet de passer à `monster2.png` (forme
définitive après l'interaction avec le trône).

Le monstre suit un chemin A* à travers les cellules praticables pour
contourner les obstacles (bougies, rochers) et ne pas rester bloqué dans
les couloirs étroits du combat.
"""

import heapq
import math
from pathlib import Path

import pygame

from settings import ANIMATION, ANIMATION_FPS, IDLE_COL, SPRITE_SCALE
from sprite_loader import resolve_crop_config, slice_sprite_sheet

BASE_DIR = Path(__file__).resolve().parent
MONSTER_SPRITE = BASE_DIR / "asset/carater/monster.png"
MONSTER_SPRITE_FINAL = BASE_DIR / "asset/carater/monster2.png"

CELL_SIZE = 16.0


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
        # Chemin A* : liste de waypoints (x, y) ; None avant calcul.
        self._path = None
        self._path_anchor = None  # position du joueur au moment du calcul
        self._path_time = 0.0

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

    # -- Chemin A* ---------------------------------------------------------

    def _cell_walkable(self, cx, cy, game_map):
        """La cellule (cx, cy) est-elle praticable pour le monstre ?"""
        wx = cx * CELL_SIZE + CELL_SIZE / 2.0
        wy = cy * CELL_SIZE + CELL_SIZE / 2.0
        return game_map.can_stand_at(wx, wy, self.collision_radius)

    def _compute_path(self, tx, ty, game_map):
        """A* : liste de waypoints pixel (position actuelle vers (tx, ty))
        ou None s'il n'y a aucun chemin."""
        def heuristic(a, b):
            return math.hypot(a[0] - b[0], a[1] - b[1])

        start = (int(self.x // CELL_SIZE), int(self.y // CELL_SIZE))
        # Si la cellule du centre n'est pas praticable (corps dans un
        # obstacle), chercher une cellule praticable proche.
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                candidate = (start[0] + dx, start[1] + dy)
                if self._cell_walkable(candidate[0], candidate[1], game_map):
                    start = candidate
                    break
            else:
                continue
            break
        target = (int(tx // CELL_SIZE), int(ty // CELL_SIZE))

        open_set = [(heuristic(start, target), 0, start)]
        g_score = {start: 0.0}
        f_score = {start: heuristic(start, target)}
        came_from = {}
        in_open = {start}

        while open_set:
            _, _, current = heapq.heappop(open_set)
            if current == target:
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                path.reverse()
                return [
                    (
                        cx * CELL_SIZE + CELL_SIZE / 2.0,
                        cy * CELL_SIZE + CELL_SIZE / 2.0,
                    )
                    for cx, cy in path
                ]
            for dcx, dcy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                neighbor = (current[0] + dcx, current[1] + dcy)
                if not self._cell_walkable(neighbor[0], neighbor[1], game_map):
                    continue
                if neighbor in in_open:
                    continue
                tentative_g = g_score[current] + 1.0
                if tentative_g < g_score.get(neighbor, float("inf")):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + heuristic(neighbor, target)
                    open_set.append((f_score[neighbor], 0, neighbor))
                    in_open.add(neighbor)
        return None

    def _step_towards(self, tx, ty, dt, game_map):
        """Un pas vers (tx, ty) (axe par axe, glisse le long des murs).
        Renvoie True s'il y a eu un mouvement."""
        dx = tx - self.x
        dy = ty - self.y
        dist = math.hypot(dx, dy)
        if dist < 0.01:
            return False
        step = self.speed * dt
        step_x = (dx / dist) * step
        step_y = (dy / dist) * step
        moved = False
        if game_map.can_stand_at(self.x + step_x, self.y, self.collision_radius):
            self.x += step_x
            moved = True
        if game_map.can_stand_at(self.x, self.y + step_y, self.collision_radius):
            self.y += step_y
            moved = True
        return moved

    def _refresh_path(self, player_x, player_y, dt, game_map):
        """Recalcule le chemin A* si nécessaire.
        Recomputation : pas de chemin, joueur éloigné de l'anchor, ou
        monstre bloqué (pas de progrès sur 2s). Pas de recompute par
        timer (pour éviter l'oscillation)."""
        self._path_time += dt
        dist = math.hypot(player_x - self.x, player_y - self.y)
        if dist < 50.0:
            self._path = []
            return
        # Path empty (reached end) -> recompute
        if self._path is None or (isinstance(self._path, list) and not self._path):
            # But if we just reached the end and player is close, don't recompute
            if self._path_time < 0.3:
                return
            recompute = True
        else:
            recompute = False
            # Player moved far from anchor
            if self._path_anchor is not None:
                if (
                    abs(player_x - self._path_anchor[0]) > CELL_SIZE * 6
                    or abs(player_y - self._path_anchor[1]) > CELL_SIZE * 6
                ):
                    recompute = True
            # Monster stuck (no progress for 2s)
            if self._path_time >= 2.0:
                recompute = True
        if recompute:
            self._path = self._compute_path(player_x, player_y, game_map)
            if self._path is None:
                self._path = []
            self._path_anchor = (player_x, player_y)
            self._path_time = 0.0

    # -- Mouvement -----------------------------------------------------------

    def move_towards(self, target_x, target_y, dt, game_map, player):
        """Avance vers le joueur (ou vers le waypoint suivant du chemin
        A*). Retourne True si, après le déplacement, le monstre touche le
        joueur (à gérer par l'appelant : remise en jeu)."""
        self._refresh_path(target_x, target_y, dt, game_map)

        # Cible : le waypoint suivant du chemin, sinon le joueur.
        if self._path:
            tx, ty = self._path[0]
        else:
            tx, ty = target_x, target_y
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        if dist < 2.0:
            self._stop()
            return self.touches(player)

        # Orientation = direction du déplacement (comme le joueur).
        if abs(dx) > abs(dy):
            self.direction = "droite" if dx > 0 else "gauche"
        else:
            self.direction = "face" if dy > 0 else "dos"

        # Déplacement axe par axe (glisse le long des murs).
        step = self.speed * dt
        step_x = (dx / dist) * step
        step_y = (dy / dist) * step
        moved = False
        if game_map.can_stand_at(self.x + step_x, self.y, self.collision_radius):
            self.x += step_x
            moved = True
        if game_map.can_stand_at(self.x, self.y + step_y, self.collision_radius):
            self.y += step_y
            moved = True

        self._advance_animation(dt)

        # Retire le waypoint atteint.
        if self._path and moved:
            wx, wy = self._path[0]
            if math.hypot(self.x - wx, self.y - wy) < CELL_SIZE * 0.5:
                self._path.pop(0)

        return self.touches(player)

    def _advance_animation(self, dt):
        self.moving = True
        self.anim_timer += dt
        while self.anim_timer >= 1.0 / ANIMATION_FPS:
            self.anim_timer -= 1.0 / ANIMATION_FPS
            self.anim_index = (
                self.anim_index + 1
            ) % len(ANIMATION[self.direction])

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
