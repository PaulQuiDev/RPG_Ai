
import math

import pygame

from settings import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    INTERACT_COLOR,
    INTERACT_BASE_ALPHA,
    INTERACT_GLOW_COLOR,
    INTERACT_GLOW_ALPHA,
    INTERACT_GLOW_PAD,
    INTERACT_MAX_SCALE,
    INTERACT_PROXIMITY,
    INTERACT_CONTACT,
    INTERACT_BLUE_THRESHOLD,
    INTERACT_MIN_AREA,
    FG_MIN_AREA,
)


class GameMap:
    def __init__(self, background_path, mask_path,
                 foreground_path=None, perspective=None):
        self.perspective = perspective or {
            "enabled": False,
            "top_scale": 1.0,
            "bottom_scale": 1.0,
        }

        try:
            original = pygame.image.load(
                str(background_path)
            ).convert()

            mask_original = pygame.image.load(
                str(mask_path)
            ).convert()

        except (pygame.error, FileNotFoundError) as error:
            raise RuntimeError(
                f"Impossible de charger la carte : {error}"
            ) from error

        if original.get_size() != mask_original.get_size():
            raise ValueError(
                "Le masque doit avoir la même taille que le fond."
            )

        self.background = pygame.transform.smoothscale(
            original, (WINDOW_WIDTH, WINDOW_HEIGHT)
        )

        self.collision_mask = pygame.transform.scale(
            mask_original, (WINDOW_WIDTH, WINDOW_HEIGHT)
        )

        self.width = WINDOW_WIDTH
        self.height = WINDOW_HEIGHT

        # Couche de premier plan (FG) : optionnelle par carte.
        # Chargée avec sa transparence, alignée sur le fond
        # (même dimensions et positions que vil1.png).
        self._fg_surface = None
        if foreground_path is not None:
            try:
                fg_src = pygame.image.load(
                    str(foreground_path)
                ).convert_alpha()

                if fg_src.get_size() != (WINDOW_WIDTH, WINDOW_HEIGHT):
                    fg_src = pygame.transform.smoothscale(
                        fg_src, (WINDOW_WIDTH, WINDOW_HEIGHT)
                    )

                self._fg_surface = fg_src
            except (pygame.error, FileNotFoundError) as error:
                print(
                    "Couche FG ignorée (fichier introuvable) : "
                    f"{error}"
                )

        # Objets interactifs (pixels bleus du masque) : extraits et
        # pré-rendus au chargement pour ne rien calculer par frame.
        self.interact_layer, self.interact_objects = self._extract_interactables()

        # Éléments de premier plan (composantes de la FG) : extraits et
        # pré-rendus (surface tight, alpha conservé).
        self.fg_elements = self._extract_fg_elements()

    def draw(self, screen, player=None, collisions=True):
        """Fond + couche de premier plan DERHIERE le joueur.

        La couche interaction (teint bleu + halo) est redessée plus bas
        dans draw_top, au-dessus du joueur et de la FG, pour garantir que
        la couleur d'interaction reste toujours visible.
        """
        screen.blit(self.background, (0, 0))
        self._draw_fg_back(screen, player)

    def draw_top(self, screen, player, time_ms=0, collisions=True):
        """Éléments de premier plan DEVANT le joueur + couche interaction."""
        self._draw_fg_front(screen, player, collisions)
        self._draw_interaction_layer(screen, player, time_ms)

    def _draw_fg_back(self, screen, player):
        """Éléments de FG derrière le joueur (box.bottom <= player.y).

        Sans joueur, aucun élément n'est "devant" : on dessine tout."""
        if not self.fg_elements:
            return

        if player is None:
            for el in self.fg_elements:
                screen.blit(el["surf"], (el["x0"], el["y0"]))
            return

        py = player.y
        for el in self.fg_elements:
            if not (el["box"].bottom > py):
                screen.blit(el["surf"], (el["x0"], el["y0"]))

    def _draw_fg_front(self, screen, player, collisions):
        """Éléments de FG devant le joueur (box.bottom > player.y).

        En mode sans collisions, le joueur est toujours devant : on ne
        dessine aucun élément de FG au-dessus de lui.
        """
        if not collisions or player is None or not self.fg_elements:
            return

        py = player.y
        for el in self.fg_elements:
            if el["box"].bottom > py:
                screen.blit(el["surf"], (el["x0"], el["y0"]))

    def _draw_interaction_layer(self, screen, player, time_ms=0):
        """Teint bleu + halos agrandis.

        Redessé au-dessus du joueur et de la FG pour garantir que la
        couleur d'interaction reste visible, y compris pour les éléments
        de premier plan.
        """
        screen.blit(self.interact_layer, (0, 0))

        if player is None or not self.interact_objects:
            return

        t = time_ms * 0.004
        px, py = player.x, player.y

        for i, obj in enumerate(self.interact_objects):
            strength = self._proximity_strength(obj["box"], px, py)
            if strength <= 0.0:
                continue

            pulse = 0.70 + 0.30 * math.sin(t + i * 0.7)
            alpha = round(255 * strength * pulse)
            if alpha > 0:
                obj["glow"].set_alpha(alpha)
                screen.blit(obj["glow"], obj["glow_pos"])

    def is_walkable(self, x, y):
        x = int(x)
        y = int(y)

        if not (0 <= x < self.width and 0 <= y < self.height):
            return False

        color = self.collision_mask.get_at((x, y))

        # Vert = zone praticable
        return color.g > color.r and color.g > color.b

    def can_stand_at(self, x, y, radius=5):
        """Vérifie que le personnage reste dans une zone praticable."""
        points = [
            (x - radius, y - radius),
            (x + radius, y - radius),
            (x - radius, y + radius),
            (x + radius, y + radius),
        ]

        return all(
            self.is_walkable(px, py)
            for px, py in points
        )

    def get_perspective_scale(self, y):
        perspective = self.perspective

        if not perspective["enabled"]:
            return 1.0

        top = perspective["top_scale"]
        bottom = perspective["bottom_scale"]

        t = max(0.0, min(1.0, y / self.height))

        return top + (bottom - top) * t

    def _proximity_strength(self, box, px, py):
        """0 loin de l'objet, 1 au contact, lissage linéaire entre."""
        dx = max(box.left - px, px - box.right, 0.0)
        dy = max(box.top - py, py - box.bottom, 0.0)
        d = math.hypot(dx, dy)

        if d <= INTERACT_CONTACT:
            return 1.0
        if d >= INTERACT_PROXIMITY:
            return 0.0
        return (INTERACT_PROXIMITY - d) / (
            INTERACT_PROXIMITY - INTERACT_CONTACT
        )

    def _extract_interactables(self):
        """Extrait les pixels bleus du masque (objets interactifs) à
        l'échelle de la fenêtre et pré-rend leurs couches visuelles.

        Retourne (base_layer, objects) :
        - base_layer : surface SRCALPHA (taille fenêtre) avec le teint
          bleu constant sur tous les objets.
        - objects : liste de dict {
            "box" : Rect de l'objet,
            "glow" : halo pré-rendu (forme agrandie, bords souples),
            "glow_pos" : (x, y) de blit du halo,
        }
        """
        from collections import deque

        mask = self.collision_mask
        w, h = mask.get_size()

        base_layer = pygame.Surface((w, h), pygame.SRCALPHA)
        base_layer.fill((0, 0, 0, 0))

        seen = set()
        objects = []

        for y in range(h):
            for x in range(w):
                if (x, y) in seen or mask.get_at((x, y))[2] <= INTERACT_BLUE_THRESHOLD:
                    continue

                # Parcours en largeur de la zone bleue connectée.
                pixels = []
                q = deque([(x, y)])
                seen.add((x, y))
                x0, x1 = x, x
                y0, y1 = y, y

                while q:
                    cx, cy = q.popleft()
                    pixels.append((cx, cy))
                    if cx < x0:
                        x0 = cx
                    elif cx > x1:
                        x1 = cx
                    if cy < y0:
                        y0 = cy
                    elif cy > y1:
                        y1 = cy

                    for nx, ny in ((cx + 1, cy), (cx - 1, cy),
                                    (cx, cy + 1), (cx, cy - 1)):
                        if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen:
                            if mask.get_at((nx, ny))[2] > INTERACT_BLUE_THRESHOLD:
                                seen.add((nx, ny))
                                q.append((nx, ny))

                if len(pixels) < INTERACT_MIN_AREA:
                    continue

                bw = x1 - x0 + 1
                bh = y1 - y0 + 1

                # Teint bleu constant (visibilité de base, toujours visible).
                base = pygame.Surface((bw, bh), pygame.SRCALPHA)
                base.fill((0, 0, 0, 0))
                for px, py in pixels:
                    base.set_at(
                        (px - x0, py - y0),
                        INTERACT_COLOR + (INTERACT_BASE_ALPHA,),
                    )
                base_layer.blit(base, (x0, y0))

                # Forme binaire pour le halo agrandi à bords souples.
                shape = pygame.Surface((bw, bh), pygame.SRCALPHA)
                shape.fill((0, 0, 0, 0))
                for px, py in pixels:
                    shape.set_at((px - x0, py - y0), (255, 255, 255, 255))

                # Halo : forme agrandie de (1 + INTERACT_MAX_SCALE), bords
                # adoucis par smoothscale, sur fond transparent.
                gs = 1.0 + INTERACT_MAX_SCALE
                esw = max(bw, round(bw * gs))
                esh = max(bh, round(bh * gs))
                enlarged = pygame.transform.smoothscale(shape, (esw, esh))

                gw = esw + 2 * INTERACT_GLOW_PAD
                gh = esh + 2 * INTERACT_GLOW_PAD
                glow = pygame.Surface((gw, gh), pygame.SRCALPHA)
                glow.fill((0, 0, 0, 0))
                for yy in range(esh):
                    for xx in range(esw):
                        a = enlarged.get_at((xx, yy))[3]
                        if a > 8:
                            glow.set_at(
                                (xx + INTERACT_GLOW_PAD, yy + INTERACT_GLOW_PAD),
                                (
                                    INTERACT_GLOW_COLOR[0],
                                    INTERACT_GLOW_COLOR[1],
                                    INTERACT_GLOW_COLOR[2],
                                    round(a * INTERACT_GLOW_ALPHA / 255.0),
                                ),
                            )

                cx = x0 + bw / 2.0
                cy = y0 + bh / 2.0
                glow_pos = (round(cx - gw / 2.0), round(cy - gh / 2.0))

                objects.append({
                    "box": pygame.Rect(x0, y0, bw, bh),
                    "glow": glow,
                    "glow_pos": glow_pos,
                })

        return base_layer, objects

    def _extract_fg_elements(self):
        """Extrait les composantes connectées de la couche de premier
        plan et pré-rend chaque élément (surface tight, alpha conservé).

        Retourne une liste de dict :
        {
            "box" : Rect (bbox de l'élément en coords fenêtre),
            "surf" : surface SRCALPHA tight (pixels opaques, bords conservés),
            "x0" : coordonnée x de blit,
            "y0" : coordonnée y de blit,
        }
        """
        if self._fg_surface is None:
            return []

        fg = self._fg_surface
        w, h = fg.get_size()

        # Grille d'alpha pour un accès rapide pendant le BFS.
        alpha_grid = []
        for y in range(h):
            row = []
            for x in range(w):
                row.append(fg.get_at((x, y))[3])
            alpha_grid.append(row)

        from collections import deque

        seen = set()
        elements = []

        for y in range(h):
            for x in range(w):
                if (x, y) in seen or alpha_grid[y][x] <= 12:
                    continue

                # Parcours en largeur de la composante connectée.
                pixels = []
                q = deque([(x, y)])
                seen.add((x, y))
                x0, x1 = x, x
                y0, y1 = y, y

                while q:
                    cx, cy = q.popleft()
                    pixels.append((cx, cy))
                    if cx < x0:
                        x0 = cx
                    elif cx > x1:
                        x1 = cx
                    if cy < y0:
                        y0 = cy
                    elif cy > y1:
                        y1 = cy

                    for nx, ny in ((cx + 1, cy), (cx - 1, cy),
                                    (cx, cy + 1), (cx, cy - 1)):
                        if (
                            0 <= nx < w
                            and 0 <= ny < h
                            and (nx, ny) not in seen
                            and alpha_grid[ny][nx] > 12
                        ):
                            seen.add((nx, ny))
                            q.append((nx, ny))

                if len(pixels) < FG_MIN_AREA:
                    continue

                bw = x1 - x0 + 1
                bh = y1 - y0 + 1

                # Surface tight avec les couleurs/alpha d'origine.
                surf = pygame.Surface((bw, bh), pygame.SRCALPHA)
                surf.fill((0, 0, 0, 0))
                for px, py in pixels:
                    surf.set_at((px - x0, py - y0), fg.get_at((px, py)))

                elements.append({
                    "box": pygame.Rect(x0, y0, bw, bh),
                    "surf": surf,
                    "x0": x0,
                    "y0": y0,
                })

        return elements
