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

# Rayon de collision utilisé UNIQUEMENT pour le calcul de chemin (A*).
# Plus petit que le rayon réel (12 px) afin que la grille de 16 px
# n'impose pas un chemin artificiellement long (détours / blocages).
PATHFINDING_RADIUS = 8.0

# --- Débloquage (P2) : le monstre ne doit pas rester coincé --------
# s'il se coille dans un mur, une bougie ou une impasse.
STUCK_THRESHOLD = 1.5      # s sans mouvement -> considéré bloqué
BACKUP_DISTANCE = 30.0     # px : distance de recul/poussée au débloquage
RECOVERY_COOLDOWN = 0.8    # s : délai entre deux tentatives de débloquage

class Monster:
    """Monstre qui fonce lentement sur le joueur."""

    def __init__(
        self,
        x: float,
        y: float,
        speed: float = 55.0,
        scale: float = 0.35,
        sprite_path: str | Path = MONSTER_SPRITE,
    ):
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

        # Débloquage (P2) : le monstre ne doit pas rester coincé dans un
        # mur / une bougie. `_stuck_since` compte les secondes sans
        # mouvement réel ; `_recovery_cooldown` espace les tentatives.
        self._last_heading = (0.0, 0.0)  # dernier sens de déplacement (unité)
        self._stuck_since = 0.0          # secondes sans mouvement réel
        self._recovery_cooldown = 0.0    # refroidissement du débloquage

    def _load_sheet(self, sprite_path: str | Path):
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

    def set_sprite(self, sprite_path: str | Path):
        """Change la feuille de sprites (transforme l'apparence, ex.
        monster -> monster2)."""
        self.sprite_path = sprite_path
        self._load_sheet(sprite_path)

    def touches(self, player):
        """True si le monstre est à `hit_radius` du centre du joueur."""
        return math.hypot(self.x - player.x, self.y - player.y) < self.hit_radius

    # -- Chemin A* ---------------------------------------------------------

    def _cell_walkable(self, cx, cy, game_map):
        """La cellule (cx, cy) est-elle praticable pour le monstre ?

        Utilise PATHFINDING_RADIUS (et non le rayon réel) : le calcul de
        chemin doit rester permissif pour ne pas forcer de détours, tandis
        que le déplacement réel garde le vrai rayon de collision."""
        wx = cx * CELL_SIZE + CELL_SIZE / 2.0
        wy = cy * CELL_SIZE + CELL_SIZE / 2.0
        return game_map.can_stand_at(wx, wy, PATHFINDING_RADIUS)

    def _compute_path(self, tx, ty, game_map):
        """A* : liste de waypoints pixel (position actuelle vers (tx, ty))
        ou None s'il n'y a aucun chemin."""

        def heuristic(a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        start = (int(self.x // CELL_SIZE), int(self.y // CELL_SIZE))
        # Si la cellule du centre n'est pas praticable (corps dans un
        # obstacle), chercher une cellule praticable proche, par cercles
        # concentriques (de plus en plus loin) : le premier trouvé est le
        # plus proche.
        found = False
        for dist in range(0, 12):
            if dist == 0:
                offsets = [(0, 0)]
            else:
                offsets = [
                    (dx, dy)
                    for dx in range(-dist, dist + 1)
                    for dy in range(-dist, dist + 1)
                    if max(abs(dx), abs(dy)) == dist
                ]
            for dx, dy in offsets:
                candidate = (start[0] + dx, start[1] + dy)
                if self._cell_walkable(candidate[0], candidate[1], game_map):
                    start = candidate
                    found = True
                    break
            if found:
                break
        if not found and not self._cell_walkable(start[0], start[1], game_map):
            return None
        target = (int(tx // CELL_SIZE), int(ty // CELL_SIZE))
        if start == target:
            return []
        # Si la cellule cible n'est pas praticable (le joueur peut y être,
        # mais pas le monstre), chercher la cellule praticable la plus
        # proche, par cercles concentriques.
        target_found = False
        for dist in range(0, 6):
            if dist == 0:
                offsets = [(0, 0)]
            else:
                offsets = [
                    (dx, dy)
                    for dx in range(-dist, dist + 1)
                    for dy in range(-dist, dist + 1)
                    if max(abs(dx), abs(dy)) == dist
                ]
            for dx, dy in offsets:
                candidate = (target[0] + dx, target[1] + dy)
                if self._cell_walkable(candidate[0], candidate[1], game_map):
                    target = candidate
                    target_found = True
                    break
            if target_found:
                break
        if not target_found:
            return None

        # A* à "suppression paresseuse" (lazy deletion) : on ne met jamais à
        # jour une entrée de la pile, on n'en ajoute de nouvelles ; au pop,
        # on ignore les entrées obsolètes (un meilleur chemin vers le nœud a
        # été trouvé depuis). La clé de priorité est f = g + h.
        open_set = [(heuristic(start, target), 0.0, 0, start)]  # (f, g, n, node)
        g_score = {start: 0.0}
        came_from = {}
        counter = 0
        while open_set:
            f, g, _, current = heapq.heappop(open_set)
            # Entrée obsolète (un meilleur chemin vers current trouvé depuis) ?
            if g > g_score.get(current, float("inf")) + 1e-9:
                continue
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
                tentative_g = g + 1.0
                if tentative_g < g_score.get(neighbor, float("inf")):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    counter += 1
                    open_set.append(
                        (
                            tentative_g + heuristic(neighbor, target),
                            tentative_g,
                            counter,
                            neighbor,
                        )
                    )
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

    # -- Débloquage (P2) -----------------------------------------------------

    def _is_stuck(self, target_x, target_y, game_map):
        """True si le monstre ne progresse plus (pas de mouvement pendant
        `STUCK_THRESHOLD`) alors qu'il n'est pas au contact du joueur, et
        si le débloquage est autorisé (refroidissement écoulé)."""
        dist = math.hypot(target_x - self.x, target_y - self.y)
        # Au contact (ou presque) du joueur : objectif atteint, on n'est pas
        # bloqué (l'interaction va se déclencher).
        if dist < self.hit_radius:
            self._stuck_since = 0.0
            return False
        if self._recovery_cooldown > 0.0:
            return False
        return self._stuck_since >= STUCK_THRESHOLD

    def _unstick(self, target_x, target_y, game_map):
        """Débloque le monstre : s'il est DANS un obstacle, on le pousse
        vers le point praticable le plus proche ; sinon, on le recule dans
        une direction praticable. Puis on re-calcule le chemin depuis la
        nouvelle position."""
        old = (self.x, self.y)

        if not game_map.can_stand_at(self.x, self.y, self.collision_radius):
            # Le monstre est dans un obstacle : on se snap sur le point
            # praticable le plus proche.
            try:
                nx, ny = game_map.find_nearest_walkable(
                    self.x, self.y, self.collision_radius
                )
                self.x, self.y = float(nx), float(ny)
            except RuntimeError:
                pass
        else:
            # Sur un point praticable mais bloqué : on recule.
            self._back_up(game_map)

        # Re-calcule le chemin depuis la nouvelle position (sauf si trop
        # proche du joueur : alors on le poursuit directement).
        dist = math.hypot(target_x - self.x, target_y - self.y)
        if dist >= 50.0:
            self._path = self._compute_path(target_x, target_y, game_map)
            if self._path is None:
                self._path = []
            self._path_anchor = (target_x, target_y)
        else:
            self._path = []
        if (self.x, self.y) != old:
            self._last_heading = (0.0, 0.0)
        self._stuck_since = 0.0
        self._recovery_cooldown = RECOVERY_COOLDOWN

    def _back_up(self, game_map):
        """Déplace le monstre dans une direction praticable : recul en
        priorité (inverse du dernier sens de déplacement), compas en
        secours. True s'il y a eu un mouvement."""
        directions = []
        # 1) Recul : inverse du dernier sens de déplacement.
        hx, hy = self._last_heading
        if hx or hy:
            directions.append((-hx, -hy))
        # 2) Compas : les 8 directions.
        for k in range(8):
            a = k * math.pi / 4.0
            directions.append((math.cos(a), math.sin(a)))

        for hx, hy in directions:
            for dist in (BACKUP_DISTANCE, BACKUP_DISTANCE * 0.6,
                         BACKUP_DISTANCE * 0.3, 6.0, 3.0):
                nx = self.x + hx * dist
                ny = self.y + hy * dist
                if game_map.can_stand_at(nx, ny, self.collision_radius):
                    self.x, self.y = float(nx), float(ny)
                    return True
        return False

    def _refresh_path(self, player_x, player_y, game_map):
        """Recalcule le chemin A* si nécessaire : pas de chemin, ou joueur
        éloigné de l'anchor. La détection de « bloqué » est séparée et
        se fait sur le déplacement réel (voir `_is_stuck` / `_unstick`)."""
        dist = math.hypot(player_x - self.x, player_y - self.y)
        # Trop proche du joueur : on le poursuit directement, pas besoin
        # d'un chemin A*.
        if dist < 50.0:
            self._path = []
            return
        if self._path is None or (isinstance(self._path, list) and not self._path):
            recompute = True
        else:
            recompute = False
            if self._path_anchor is not None:
                if (
                    abs(player_x - self._path_anchor[0]) > CELL_SIZE * 6
                    or abs(player_y - self._path_anchor[1]) > CELL_SIZE * 6
                ):
                    recompute = True
        if recompute:
            self._path = self._compute_path(player_x, player_y, game_map)
            if self._path is None:
                self._path = []
            self._path_anchor = (player_x, player_y)

    # -- Mouvement -----------------------------------------------------------

    def move_towards(self, target_x, target_y, dt, game_map, player):
        """Avance vers le joueur (ou vers le waypoint suivant du chemin
        A*). Retourne True si, après le déplacement, le monstre touche le
        joueur (à gérer par l'appelant : remise en jeu).

        Le monstre ne doit pas rester coincé dans un mur / une bougie :
        s'il ne progresse plus, on le recule ou on le pousse pour le
        débloquer (voir `_is_stuck` / `_unstick`)."""
        # Si bloqué, on se débloque ; sinon on (re)calcule le chemin.
        if self._is_stuck(target_x, target_y, game_map):
            self._unstick(target_x, target_y, game_map)
        else:
            self._refresh_path(target_x, target_y, game_map)

        # Cible : le waypoint suivant du chemin, sinon le joueur.
        if self._path:
            tx, ty = self._path[0]
        else:
            tx, ty = target_x, target_y
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        if dist < 2.0:
            self._stop()
            self._stuck_since = 0.0
            return self.touches(player)

        # Orientation = direction du déplacement (comme le joueur).
        if abs(dx) > abs(dy):
            self.direction = "droite" if dx > 0 else "gauche"
        else:
            self.direction = "face" if dy > 0 else "dos"

        # Déplacement axe par axe (glisse le long des murs).
        moved = self._step_towards(tx, ty, dt, game_map)

        if moved:
            self._last_heading = (dx / dist, dy / dist)
            self._stuck_since = 0.0
            self._advance_animation(dt)
        else:
            # Bloqué : on compte les secondes sans mouvement pour déclencher
            # le débloquage (voir `_is_stuck`).
            self._stuck_since += dt
            self._stop()

        # Retire le waypoint atteint (uniquement si on a avancé).
        if self._path and moved:
            wx, wy = self._path[0]
            if math.hypot(self.x - wx, self.y - wy) < CELL_SIZE:
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
