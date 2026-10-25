"""Personnages de carte (NPC) : PNG configurables, avec comportements
statiques ou en patrouille, collisions et interactions au contact.

Déclarés dans settings.py, dans la liste "npcs" de chaque carte :

    "npcs": [
        {
            "name": str,                     # nom (obligatoire)
            "sprite": path,                  # sheet PNG 4x3 (obligatoire)
            "pos": [x, y],                   # position des pieds (obligatoire)
            "behavior": "static" | "patrol", # comportement (défaut "static")
            "speed": float,                  # px/s en patrouille (défaut NPC_DEFAULT_SPEED)
            "points": [[x, y], ...],         # waypoints de la patrouille (boucle fermée)
            "action": str,                   # clé de behaviors.BEHAVIORS (optionnel)
            "message": str,                  # message par défaut affiché au contact
            "scale": float,                  # échelle (défaut CHARACTER_SCALE)
            "collision_radius": float,       # rayon de collision (défaut NPC_DEFAULT_COLLISION_RADIUS)
            "collide": bool,                 # True = bloque le joueur (défaut True)
        },
        ...
    ]

Comportements :
    - "static" : le personnage reste sur place (animation d'attente).
    - "patrol" : le personnage suit en boucle la liste des waypoints "points".
      S'il est bloqué (obstacle ou joueur), il essaie une déviation
      perpendiculaire, sinon il s'arrête.

Interaction :
    Au contact du joueur (distance <= NPC_CONTACT_RADIUS), l'interaction
    déclenche par défaut l'affichage de "message" (ou "...").
    Si "action" est défini, le comportement correspondant de
    behaviors.BEHAVIORS est exécuté (change_map, teleport, go_forest, ...).
    Un cooldown (NPC_INTERACT_COOLDOWN) évite les déclenchements répétés.

Collision :
    `GameMap.can_stand_at(x, y, r, ignore=None)` tient compte des NPC
    (rayon + collision_radius). Le joueur ne peut donc pas traverser un
    NPC si collide=True. `ignore=npc` est utilisé quand on déplace l'un
    d'eux (construction / patrouille).

Réutilisabilité :
    La classe Npc et la construction `_build_npcs` ne dépendent que du
    format des dicts et de `GameMap`/`World`/`behaviors` : on ajoute des
    PNG à n'importe quelle carte (village, forêt, ...) sans modifier le
    reste du code.
"""

import math

import pygame

from settings import (
    ANIMATION,
    ANIMATION_FPS,
    ANCHOR_OFFSETS,
    CHARACTER_SCALE,
    IDLE_COL,
    INTERACT_GLOW_ALPHA,
    INTERACT_GLOW_COLOR,
    NPC_CONTACT_RADIUS,
    NPC_DEFAULT_COLLISION_RADIUS,
    NPC_DEFAULT_SPEED,
    NPC_INTERACT_COOLDOWN,
    SPRITE_SCALE,
)
from sprite_loader import slice_sprite_sheet


class Npc:
    """Personnage de carte (PNG) avec comportement, collision et interaction.

    _SIDESTEP_DELAY : délai (s) pendant lequel le NPC attend calmement
    quand il est bloqué (joueur/obstacle), avant de tenter de contourner
    l'obstacle. Ça évite le zigzag de direction quand le joueur bloque.
    """

    _SIDESTEP_DELAY = 0.6

    def __init__(self, data: dict, index: int):
        if "name" not in data:
            raise ValueError("NPC : champ 'name' manquant.")
        if "sprite" not in data:
            raise ValueError("NPC : champ 'sprite' manquant.")
        behavior = data.get("behavior", "static")
        if behavior == "patrol" and not data.get("points"):
            raise ValueError(
                "NPC : comportement 'patrol' nécessite la liste 'points'."
            )
        # Position initiale : explicite, ou (en patrouille) le premier
        # waypoint (solution générale : une patrouille commence par son
        # premier point).
        if "pos" in data:
            pos = data["pos"]
        elif behavior == "patrol" and data.get("points"):
            pos = list(data["points"][0])
        else:
            raise ValueError("NPC : champ 'pos' manquant.")

        self.index = index
        self.name = str(data["name"])
        self.sprite_path = data["sprite"]
        self.behavior = behavior
        self.speed = float(data.get("speed", NPC_DEFAULT_SPEED))
        self.scale = float(data.get("scale", CHARACTER_SCALE))
        self.collision_radius = float(
            data.get("collision_radius", NPC_DEFAULT_COLLISION_RADIUS)
        )
        self.collide = bool(data.get("collide", True))
        self.action = data.get("action")
        self.message = data.get("message")
        self.base_scale = SPRITE_SCALE * self.scale

        # Chargement du sheet (format 4x3, identique au joueur).
        sheet = pygame.image.load(str(self.sprite_path)).convert_alpha()
        sheet_w, sheet_h = sheet.get_size()
        self.frames = slice_sprite_sheet(sheet, sheet_w, sheet_h)

        # Position des pieds (réécrite par la carte, snapée au point praticable).
        self.x = float(pos[0])
        self.y = float(pos[1])

        # Patrouille : waypoints de la boucle fermée.
        self.path = [(float(px), float(py)) for (px, py) in data.get("points", [])]
        self.path_index = 0

        # Animation.
        self.direction = "face"
        self.anim_index = 0
        self.anim_timer = 0.0
        self.moving = False

        # Interaction.
        self.interact_cooldown = 0.0
        self.last_player = None

        # Patrouille : délai d'attente (s) quand le NPC est bloqué.
        self._stuck_time = 0.0

        # Halo de contact (pré-rendu, réutilisé à chaque frame).
        self.contact_glow = _make_contact_glow()

    # ------------------- Comportement -------------------

    def update(self, dt: float, game_map, player):
        """Met à jour le comportement et le cooldown d'interaction."""
        self.last_player = player
        self.interact_cooldown = max(0.0, self.interact_cooldown - dt)
        if self.behavior == "patrol" and self.path:
            self._patrol(dt, game_map, player)

    def _patrol(self, dt: float, game_map, player):
        """Avance vers le waypoint courant, en boucle fermée.

        Bloqué (joueur ou obstacle) : le NPC attend calmement (sans
        changer de direction) pendant `_SIDESTEP_DELAY`. Ensuite il tente
        une déviation perpendiculaire pour contourner l'obstacle ; s'il
        reste bloqué, il s'arrête.
        """
        target = self.path[self.path_index]

        # Atteint : passe au waypoint suivant.
        if math.hypot(self.x - target[0], self.y - target[1]) <= 6.0:
            self.path_index = (self.path_index + 1) % len(self.path)
            target = self.path[self.path_index]

        dx = target[0] - self.x
        dy = target[1] - self.y
        d = math.hypot(dx, dy)
        if d <= 0.01:
            self._stop()
            self._stuck_time = 0.0
            return

        ux, uy = dx / d, dy / d
        step = self.speed * dt

        # 1) Vers le but.
        cand_x, cand_y = ux * step, uy * step
        nx = max(5.0, min(game_map.width - 5.0, self.x + cand_x))
        ny = max(5.0, min(game_map.height - 5.0, self.y + cand_y))
        if not self._is_blocked(nx, ny, game_map, player):
            self._move_to(nx, ny, cand_x, cand_y, dt)
            self._stuck_time = 0.0
            return

        # 2) Bloqué : on attend calmement, sans changer de direction.
        self._stuck_time += dt
        if self._stuck_time < self._SIDESTEP_DELAY:
            self._stop()
            return

        # 3) Délai écoulé : on tente de contourner (déviations perpendiculaires).
        self._stuck_time = 0.0
        for sign in (1.0, -1.0):
            cand_x = (-uy * sign) * step * 0.7
            cand_y = (ux * sign) * step * 0.7
            nx = max(5.0, min(game_map.width - 5.0, self.x + cand_x))
            ny = max(5.0, min(game_map.height - 5.0, self.y + cand_y))
            if not self._is_blocked(nx, ny, game_map, player):
                self._move_to(nx, ny, cand_x, cand_y, dt)
                return
        self._stop()

    def _move_to(self, nx: float, ny: float, move_x: float,
                 move_y: float, dt: float):
        """Déplace vers (nx, ny) et met à jour direction + animation."""
        self.x, self.y = nx, ny
        self.moving = True
        self._set_direction(move_x, move_y)
        self._advance_animation(dt)

    def _is_blocked(self, nx, ny, game_map, player):
        # Masque + autres personnages (ignore = pas soi-même).
        if not game_map.can_stand_at(
            nx, ny, self.collision_radius, ignore=self
        ):
            return True
        # Joueur : un NPC ne traverse jamais le joueur.
        if player is not None:
            if math.hypot(
                nx - player.x,
                ny - player.y,
            ) < self.collision_radius + player.collision_radius:
                return True
        return False

    def _set_direction(self, dx, dy):
        """Direction d'animation selon le mouvement effectif."""
        if abs(dx) > abs(dy):
            self.direction = "droite" if dx > 0 else "gauche"
        else:
            self.direction = "face" if dy > 0 else "dos"

    def _advance_animation(self, dt):
        self.anim_timer += dt
        sequence = ANIMATION.get(self.direction, [0, 1, 2, 1])
        while self.anim_timer >= 1.0 / ANIMATION_FPS:
            self.anim_timer -= 1.0 / ANIMATION_FPS
            self.anim_index = (self.anim_index + 1) % len(sequence)

    def _stop(self):
        self.moving = False
        self.anim_index = 0
        self.anim_timer = 0.0

    # ------------------- Interaction -------------------

    def in_contact(self, player, radius=NPC_CONTACT_RADIUS):
        """Vrai si le joueur est dans la portée d'interaction."""
        if player is None:
            return False
        return math.hypot(
            self.x - player.x,
            self.y - player.y,
        ) <= radius

    def can_interact(self):
        """Vrai si l'action est disponible (cooldown écoulé)."""
        return self.interact_cooldown <= 0.0

    def interact(self, player, world, game_map):
        """
        Déclenche l'action au contact :
        - message par défaut,
        - puis le comportement `action` de behaviors.BEHAVIORS si défini.
        Renvoie True si la carte a changé (à réassigner par main.py).
        """
        if not self.in_contact(player):
            return False

        # Message par défaut.
        text = self.message if self.message else "..."
        print(f"[{self.name}] {text}")

        changed = False
        if self.action:
            try:
                from behaviors import BEHAVIORS
            except ImportError:  # noqa: BLE001
                BEHAVIORS = {}
            behavior = BEHAVIORS.get(self.action)
            if behavior is None:
                print(
                    f"Comportement inconnu pour {self.name} : {self.action} "
                    "(clé absente dans behaviors.BEHAVIORS)"
                )
            else:
                changed = bool(behavior(player, world, game_map))

        self.interact_cooldown = NPC_INTERACT_COOLDOWN
        return changed

    # ------------------- Affichage -------------------

    def draw(self, screen, game_map, player=None):
        """Rend le personnage + halo si au contact du joueur."""
        if self.moving:
            col = ANIMATION[self.direction][self.anim_index]
        else:
            col = IDLE_COL

        perspective_scale = game_map.get_perspective_scale(self.y)
        final_scale = self.base_scale * perspective_scale

        frame = self.frames[self.direction][col]
        w = max(1, round(frame.get_width() * final_scale))
        h = max(1, round(frame.get_height() * final_scale))
        sprite = pygame.transform.scale(frame, (w, h))

        x = round(self.x - w / 2)
        y = round(self.y - h)
        ax, ay = ANCHOR_OFFSETS.get(self.direction, (0, 0))
        x += round(ax * final_scale)
        y += round(ay * final_scale)

        # Halo au contact (retour visuel de l'interaction).
        if player is not None and self.in_contact(player):
            glow = self.contact_glow
            gx = round(self.x - glow.get_width() / 2)
            gy = round(self.y - glow.get_height() / 2)
            screen.blit(glow, (gx, gy))

        screen.blit(sprite, (x, y))


def _make_contact_glow():
    """Halo circulaire pré-rendu (alpha), pour le retour visuel du contact."""
    radius = 24
    size = radius * 2 + 8
    glow = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = cy = size // 2
    for r in range(radius + 1, 0, -1):
        alpha = max(1, int(INTERACT_GLOW_ALPHA * r / radius))
        pygame.draw.circle(glow, (*INTERACT_GLOW_COLOR, alpha), (cx, cy), r)
    return glow
