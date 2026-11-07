#!/usr/bin/env python3
"""Éditeur de cartes graphiques (pygame) pour RPG_Ai.

Interface graphique pour éditer les cartes de RPG_Ai :
  * superposition de l'image de fond + du masque de segmentation
    (transparence du masque ajustable) ;
  * peinture / remplissage du masque avec la palette de segmentation
    (sol vert / objet bleu / mur rouge / neutre) ;
  * définition des objets interactifs (ajouter, déplacer, supprimer,
    nommer, action) ;
  * enregistrement dans le JSON d'aventure (objets, noms, actions) et
    dans le PNG du masque (segmentation), avec sauvegarde de sécurité
    (<masque>_backup.png).

Lancement :
    python map_editor.py [chemin/vers/aventure.json]
  (défaut : adventures/<DEFAULT_ADVENTURE>.json)

Touches :
  P peindre   F remplir   A ajouter   M déplacer   D supprimer
  Z annuler   S enregistrer   Entrée (valide champ)   Échap (quitte)
  < > changer de carte
"""

import argparse
import json
import os
from copy import deepcopy
from pathlib import Path

import pygame

from settings import ADVENTURES_DIR, BASE_DIR, DEFAULT_ADVENTURE, WINDOW_HEIGHT, WINDOW_WIDTH

# ---------------------------------------------------------------------------
# Palette de segmentation (couleurs réelles des masques)
# ---------------------------------------------------------------------------
SEGMENT_PALETTE = [
    ("Sol — vert, traversable", (82, 193, 17)),
    ("Objet — bleu+vert, inter.", (0, 112, 255)),
    ("Mur — rouge, bloqué", (255, 22, 19)),
    ("Neutre — gris", (60, 60, 60)),
]

# ---------------------------------------------------------------------------
# Layout / couleurs de l'UI
# ---------------------------------------------------------------------------
EDITOR_WINDOW_W = 1360
EDITOR_WINDOW_H = 760
SIDEBAR_W = 320
TOP_H = 46
BOTTOM_H = 30
MARGIN = 12

WHITE = (242, 242, 247)
BLACK = (16, 17, 22)
DARK = (30, 32, 40)
GRAY_LIGHT = (150, 153, 166)
ACCENT = (80, 190, 255)
SELECT = (80, 110, 235)
RED = (240, 110, 110)
YELLOW = (240, 220, 110)

MAX_FILL_PX = 900000
FILL_TOL = 18
UNDO_MAX = 40
BRUSH_MIN, BRUSH_MAX = 2, 40


class TextEdit:
    """Champ de texte minimal. Le clavier est géré par la boucle principale
    (un seul champ actif à la fois : 'name' ou 'action')."""

    def __init__(self, rect, font, color=WHITE):
        self.rect = rect
        self.font = font
        self.color = color
        self.text = ""
        self.active = False

    def set_text(self, s):
        self.text = str(s)

    def draw(self, screen):
        pygame.draw.rect(screen, DARK, self.rect, border_radius=4)
        pygame.draw.rect(screen, SELECT if self.active else (70, 73, 88),
                         self.rect, 1, border_radius=4)
        t = self.font.render(self.text, True, self.color)
        screen.blit(t, (self.rect.x + 6,
                        self.rect.y + (self.rect.h - self.font.get_height()) // 2))


class MapEditor:
    TOOLS = ("paint", "fill", "add", "move", "delete")
    TOOL_LABELS = {
        "paint": "Peindre le masque (P)",
        "fill": "Remplir une zone (F)",
        "add": "Ajouter un objet (A)",
        "move": "Déplacer un objet (M)",
        "delete": "Supprimer un objet (D)",
    }

    def __init__(self, adventure_path, headless=False):
        if headless:
            os.environ["SDL_VIDEODRIVER"] = "dummy"
        pygame.init()
        self.screen = pygame.display.set_mode((EDITOR_WINDOW_W, EDITOR_WINDOW_H))
        pygame.display.set_caption("RPG_Ai — Éditeur de cartes")
        self.font_s = pygame.font.Font(None, 20)
        self.font_s_bold = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 15)

        self._adventure_path = Path(adventure_path)
        self.data = {}
        self.map_idx = 0
        self.tool = "paint"
        self.paint_color = SEGMENT_PALETTE[2][1]
        self.mask_alpha = 120
        self.brush = 14
        self.selected_obj = None
        self.name_input = None
        self.action_input = None
        self.map_entry = None
        self.map_bg_path = self.map_mask_path = None
        self.bg_orig = self.mask_src = self.mask_display = self.bg_display = None
        self.mask_orig_backup = None
        self._dirty_mask = False
        self._dirty_json = False
        self.orig_w = self.orig_h = 0
        self.win_w, self.win_h = WINDOW_WIDTH, WINDOW_HEIGHT
        self.scale = self.off_x = self.off_y = 0
        self.display_w = self.display_h = 0
        self.status = "Chargement…"
        self.interact_warning = ""
        self.undo_stack = []
        self._mouse_down = False
        self._drag_obj = None
        self.running = True

        self._load_adventure()
        self._select_map(0)
        self._init_fields()
        self._push_undo()

    # -------------------------------------------------------------------
    # Chargement
    # -------------------------------------------------------------------
    def _load_adventure(self):
        p = self._adventure_path
        if not p.exists():
            raise FileNotFoundError(f"Aventure introuvable : {p}")
        with p.open("r", encoding="utf-8") as fh:
            self.data = json.load(fh)
        if not isinstance(self.data, dict) or not self.data.get("maps"):
            raise ValueError(f"Aventure invalide (pas de 'maps') : {p}")
        self.status = f"Aventure : {p.name} — {len(self.data['maps'])} carte(s)"

    def _select_map(self, idx):
        idx = max(0, min(idx, len(self.data["maps"]) - 1))
        if idx == self.map_idx and self.mask_src is not None:
            return
        self.map_idx = idx
        self.selected_obj = None
        self._load_map_assets(idx)
        self.status = f"Carte : {self.data['maps'][idx].get('name', '?')}"

    def _load_map_assets(self, idx):
        me = self.data["maps"][idx]
        bg_rel, mask_rel = me.get("background"), me.get("mask")
        if not bg_rel or not mask_rel:
            self.status = "Cette carte n'a ni 'background' ni 'mask'."
            return
        self.map_bg_path = BASE_DIR / bg_rel
        self.map_mask_path = BASE_DIR / mask_rel
        if not self.map_bg_path.exists() or not self.map_mask_path.exists():
            self.status = f"Fichiers manquants : {self.map_bg_path.name}"
            return
        self.bg_orig = pygame.image.load(str(self.map_bg_path)).convert()
        self.mask_src = pygame.image.load(str(self.map_mask_path)).convert()
        self.mask_orig_backup = self.mask_src.copy()
        self.orig_w, self.orig_h = self.bg_orig.get_size()
        self.map_entry = me
        self._fit_image()

    def _fit_image(self):
        cw = EDITOR_WINDOW_W - SIDEBAR_W - MARGIN * 2
        ch = EDITOR_WINDOW_H - TOP_H - BOTTOM_H - MARGIN * 2
        s = min(cw / max(1, self.orig_w), ch / max(1, self.orig_h), 1.0)
        self.scale = s
        self.bg_display = pygame.transform.smoothscale(
            self.bg_orig, (max(1, int(self.orig_w * s)), max(1, int(self.orig_h * s))))
        self.mask_display = pygame.transform.smoothscale(
            self.mask_src, (max(1, int(self.orig_w * s)), max(1, int(self.orig_h * s))))
        self.display_w = self.bg_display.get_width()
        self.display_h = self.bg_display.get_height()
        self.off_x = SIDEBAR_W + (cw - self.display_w) // 2
        self.off_y = TOP_H + (ch - self.display_h) // 2

    # -------------------------------------------------------------------
    # Coordonnées
    # -------------------------------------------------------------------
    def _canvas_local(self, pos):
        return (pos[0] - self.off_x, pos[1] - self.off_y)

    def _in_canvas(self, pos):
        cx, cy = self._canvas_local(pos)
        return 0 <= cx < self.display_w and 0 <= cy < self.display_h

    def canvas_local_to_win(self, cx, cy):
        ox, oy = cx / self.scale, cy / self.scale
        return ox * self.win_w / self.orig_w, oy * self.win_h / self.orig_h

    def win_to_canvas_local(self, wx, wy):
        ox, oy = wx * self.orig_w / self.win_w, wy * self.orig_h / self.win_h
        return ox * self.scale, oy * self.scale

    def _object_at(self, cx, cy, tol=32):
        best, best_d = None, float("inf")
        for i, obj in enumerate(self.data["maps"][self.map_idx].get("interactions", [])):
            pos = obj.get("pos", [0, 0])
            ox, oy = self.win_to_canvas_local(pos[0], pos[1])
            d = ((ox - cx) ** 2 + (oy - cy) ** 2) ** 0.5
            if d < best_d:
                best, best_d = i, d
        return best if best_d <= tol else None

    # -------------------------------------------------------------------
    # Undo / dirty
    # -------------------------------------------------------------------
    def _push_undo(self):
        self.undo_stack.append(
            (self.map_idx, deepcopy(self.data),
             self.mask_src.copy() if self.mask_src is not None else None,
             self._dirty_mask, self._dirty_json))
        self.undo_stack = self.undo_stack[-UNDO_MAX:]

    def _pop_undo(self):
        if not self.undo_stack:
            self.status = "Rien à annuler."
            return False
        m_idx, data, mask, dmask, djson = self.undo_stack.pop()
        self.data = data
        self.map_idx = m_idx
        me = data["maps"][self.map_idx]
        bg_rel = me.get("background")
        if bg_rel:
            bg = pygame.image.load(str(BASE_DIR / bg_rel)).convert()
            self.bg_orig = bg
            self.orig_w, self.orig_h = self.bg_orig.get_size()
        if mask is not None:
            self.mask_src = mask
            self.mask_orig_backup = mask.copy()
        self.map_entry = me
        self.map_mask_path = BASE_DIR / me.get("mask")
        if self.bg_orig is not None and self.mask_src is not None:
            self._fit_image()
        self.selected_obj = None
        self.interact_warning = ""
        self._dirty_mask = dmask
        self._dirty_json = djson
        self.status = "Annulation effectuée."
        return True

    def _set_dirty_mask(self):
        self._dirty_mask = True

    def _set_dirty_json(self):
        self._dirty_json = True

    # -------------------------------------------------------------------
    # Masque
    # -------------------------------------------------------------------
    def _paint_brush(self, cx, cy):
        ox, oy = cx / self.scale, cy / self.scale
        ix, iy = int(round(ox)), int(round(oy))
        r = max(1, int(round(self.brush / self.scale)))
        if self.mask_src is not None and 0 <= ix < self.orig_w and 0 <= iy < self.orig_h:
            pygame.draw.circle(self.mask_src, self.paint_color, (ix, iy), r)
            self._set_dirty_mask()

    def _fill_region(self, cx, cy):
        if self.mask_src is None:
            return
        ox, oy = int(round(cx / self.scale)), int(round(cy / self.scale))
        ox = max(0, min(ox, self.orig_w - 1))
        oy = max(0, min(oy, self.orig_h - 1))
        target = tuple(self.mask_src.get_at((ox, oy))[:3])
        if target == tuple(self.paint_color):
            self.status = "Zone déjà à cette couleur — rien à remplir."
            return
        stack, seen, pixels = [(ox, oy)], set(), []
        w, h = self.orig_w, self.orig_h
        while stack and len(pixels) < MAX_FILL_PX:
            x, y = stack.pop()
            if (x, y) in seen or not (0 <= x < w and 0 <= y < h):
                continue
            seen.add((x, y))
            c = tuple(self.mask_src.get_at((x, y))[:3])
            d = abs(c[0] - target[0]) + abs(c[1] - target[1]) + abs(c[2] - target[2])
            if d > FILL_TOL:
                continue
            pixels.append((x, y))
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if (nx, ny) not in seen:
                    stack.append((nx, ny))
        if not pixels:
            self.status = "Aucun pixel à remplir ici."
            return
        if len(pixels) > MAX_FILL_PX:
            self.status = f"Région trop grande ({len(pixels)} px) — remplissage annulé."
            return
        for x, y in pixels:
            self.mask_src.set_at((x, y), (*self.paint_color, 255))
        self._set_dirty_mask()
        self.status = f"Remplissage : {len(pixels)} px -> {tuple(self.paint_color)}."

    # -------------------------------------------------------------------
    # Objets
    # -------------------------------------------------------------------
    def _add_object(self, wx, wy):
        me = self.data["maps"][self.map_idx]
        n = len(me.get("interactions", []))
        me.setdefault("interactions", []).append(
            {"pos": [round(wx), round(wy)], "name": f"Objet {n + 1}", "action": ""})
        self.selected_obj = len(me["interactions"]) - 1
        self._set_dirty_json()
        self.status = f"Objet ajouté ({round(wx)}, {round(wy)}) — nommez-le."
        self._check_warning()

    def _move_object(self, wx, wy):
        if self.selected_obj is None:
            return
        me = self.data["maps"][self.map_idx]
        me["interactions"][self.selected_obj]["pos"] = [round(wx), round(wy)]
        self._check_warning()

    def _delete_object(self):
        if self.selected_obj is None:
            return
        self.data["maps"][self.map_idx]["interactions"].pop(self.selected_obj)
        self.selected_obj = None
        self._set_dirty_json()
        self.status = "Objet supprimé."

    def _set_obj_name(self, name):
        if self.selected_obj is None:
            return
        self.data["maps"][self.map_idx]["interactions"][self.selected_obj]["name"] = name
        self._set_dirty_json()

    def _set_obj_action(self, action):
        if self.selected_obj is None:
            return
        self.data["maps"][self.map_idx]["interactions"][self.selected_obj]["action"] = action
        self._set_dirty_json()

    def _check_warning(self):
        self.interact_warning = ""
        if self.selected_obj is None or self.mask_src is None or not self.map_entry:
            return
        wx, wy = self.map_entry["interactions"][self.selected_obj]["pos"]
        ox, oy = wx * self.orig_w / self.win_w, wy * self.win_h / self.win_h
        ox, oy = int(round(ox)), int(round(oy))
        if 0 <= ox < self.orig_w and 0 <= oy < self.orig_h:
            r, g, b = self.mask_src.get_at((ox, oy))[:3]
            if not (b > 100 and r < 60 and g > 50):
                self.interact_warning = ("⚠ Ce point n'est PAS un objet bleu traversable "
                                         "(peignez-le « Objet »).")

    def _selected_text(self):
        if self.selected_obj is None or not self.map_entry:
            return "", ""
        obj = self.map_entry["interactions"][self.selected_obj]
        return obj.get("name", ""), obj.get("action", "")

    # -------------------------------------------------------------------
    # Sauvegarde
    # -------------------------------------------------------------------
    def _save_mask_if_dirty(self):
        if not self._dirty_mask or self.map_mask_path is None or self.mask_src is None:
            return False
        bkp = self.map_mask_path.parent / (self.map_mask_path.stem + "_backup.png")
        if not bkp.exists() and self.mask_orig_backup is not None:
            try:
                pygame.image.save(self.mask_orig_backup, str(bkp))
            except Exception:
                pass
        try:
            pygame.image.save(self.mask_src, str(self.map_mask_path))
        except Exception as e:
            raise RuntimeError(f"Impossible d'enregistrer le masque : {e}")
        self._dirty_mask = False
        return True

    def _save_json_if_dirty(self):
        if not self._dirty_json:
            return False
        p = self._adventure_path
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(self.data, fh, indent=2, ensure_ascii=False)
            tmp.rename(p)
        except Exception as e:
            raise RuntimeError(f"Impossible d'enregistrer le JSON : {e}")
        self._dirty_json = False
        return True

    def save_all(self):
        m = self._save_mask_if_dirty()
        j = self._save_json_if_dirty()
        if m and j:
            self.status = "Sauvegarde OK (JSON + masque). Secours : <masque>_backup.png"
        elif m:
            self.status = "Masque enregistré (JSON sans changement)."
        elif j:
            self.status = "JSON enregistré."
        else:
            self.status = "Aucun changement à enregistrer."
        return m or j

    # -------------------------------------------------------------------
    # Layout sidebar (source unique : dessin + clics)
    # -------------------------------------------------------------------
    def _layout(self):
        top = TOP_H + 2
        y = top + 26
        map_row = pygame.Rect(18, y, SIDEBAR_W - 36, 24)
        y += 30
        tools = {}
        for t in self.TOOLS:
            tools[t] = pygame.Rect(18, y, SIDEBAR_W - 36, 28)
            y += 31
        palette = {}
        for i in range(len(SEGMENT_PALETTE)):
            palette[i] = pygame.Rect(60, y, SIDEBAR_W - 46, 23)
            y += 25
        brush_slider = pygame.Rect(18, y + 18, SIDEBAR_W - 36, 14)
        y += 30
        alpha_slider = pygame.Rect(18, y + 18, SIDEBAR_W - 36, 14)
        y += 30
        panel = pygame.Rect(18, y, SIDEBAR_W - 36, 172)
        y += 186
        return dict(top=top, map_row=map_row, tools=tools, palette=palette,
                    brush_slider=brush_slider, alpha_slider=alpha_slider,
                    panel=panel,
                    save_btn=pygame.Rect(18, y, 90, 28),
                    revert_btn=pygame.Rect(114, y, 90, 28),
                    undo_btn=pygame.Rect(210, y, 90, 28))

    def _field_rects(self, panel):
        if self.selected_obj is None or not self.map_entry:
            return None
        return {
            "name": pygame.Rect(panel.x + 10, panel.y + 50, panel.w - 20, 24),
            "action": pygame.Rect(panel.x + 10, panel.y + 80, panel.w - 20, 24),
            "delete": pygame.Rect(panel.x + 10, panel.y + 116, panel.w - 20, 26),
        }

    # -------------------------------------------------------------------
    # Dessin
    # -------------------------------------------------------------------
    def _draw_canvas(self, screen):
        if self.bg_display is None:
            return
        screen.blit(self.bg_display, (self.off_x, self.off_y))
        if self.mask_display is not None:
            ov = self.mask_display.copy()
            ov.set_alpha(self.mask_alpha)
            screen.blit(ov, (self.off_x, self.off_y))
        self._draw_markers(screen)
        pygame.draw.rect(screen, GRAY_LIGHT, (self.off_x, self.off_y,
                                             self.display_w, self.display_h), 1, border_radius=2)

    def _draw_markers(self, screen):
        me = self.data["maps"][self.map_idx]
        for i, obj in enumerate(me.get("interactions", [])):
            wx, wy = obj["pos"]
            cx, cy = self.win_to_canvas_local(wx, wy)
            sel = i == self.selected_obj
            pygame.draw.circle(screen, RED if sel else (255, 210, 90), (int(cx), int(cy)), 8)
            pygame.draw.circle(screen, BLACK, (int(cx), int(cy)), 8, 1)
            t = self.font_small.render(obj.get("name", f"O{i + 1}"), True, WHITE)
            screen.blit(t, (int(cx) + 10, int(cy) - 4))

    def _btn(self, screen, rect, label, active=False, accent=ACCENT):
        pygame.draw.rect(screen, accent if active else DARK, rect, border_radius=6)
        pygame.draw.rect(screen, WHITE if active else (80, 83, 96), rect, 1, border_radius=6)
        t = self.font_s.render(label, True, WHITE if active else GRAY_LIGHT)
        screen.blit(t, (rect.x + 8, rect.y + (rect.h - t.get_height()) // 2))

    def _slider(self, screen, rect, value, min_v, max_v):
        pygame.draw.rect(screen, (70, 73, 88), rect)
        f = (value - min_v) / (max_v - min_v + 1e-6)
        pygame.draw.rect(screen, ACCENT,
                         pygame.Rect(rect.x, rect.y + rect.h // 2 - 3, int(rect.w * f), rect.h - 6), 2)
        pygame.draw.circle(screen, WHITE, (int(rect.x + f * rect.w), rect.y + rect.h // 2), 6)

    def _draw_sidebar(self, screen, L):
        self._btn(screen, pygame.Rect(18, L["top"], 44, 22), "Éditeur de cartes")
        self._btn(screen, L["map_row"], self.data["maps"][self.map_idx].get("name", "?"))
        # < > autour de la ligne carte
        self._btn(screen, pygame.Rect(L["map_row"].x, L["map_row"].y, 40, L["map_row"].h), "<")
        self._btn(screen, pygame.Rect(L["map_row"].x + L["map_row"].w - 40, L["map_row"].y, 40, L["map_row"].h), ">")
        # outils
        for tname, r in L["tools"].items():
            self._btn(screen, r, self.TOOL_LABELS[tname], active=(self.tool == tname))
        # palette
        self.font_small.render("Couleur :", True, GRAY_LIGHT)
        screen.blit(self.font_s.render("Couleur :", True, GRAY_LIGHT), (18, L["palette"][0].y - 18))
        for i, r in L["palette"].items():
            pygame.draw.rect(screen, SEGMENT_PALETTE[i][1],
                             pygame.Rect(r.x - 44, r.y + 2, 30, r.h - 4), border_radius=3)
            self._btn(screen, r, SEGMENT_PALETTE[i][0][:38],
                      active=(self.paint_color == SEGMENT_PALETTE[i][1]))
        # pinceau / transparence
        yb = L["brush_slider"].y - 18
        screen.blit(self.font_small.render(f"Pinceau {self.brush} px", True, GRAY_LIGHT), (18, yb))
        self._slider(screen, L["brush_slider"], self.brush, BRUSH_MIN, BRUSH_MAX)
        ya = L["alpha_slider"].y - 18
        screen.blit(self.font_small.render(f"Transparence masque {self.mask_alpha}", True, GRAY_LIGHT), (18, ya))
        self._slider(screen, L["alpha_slider"], self.mask_alpha, 0, 255)
        # panneau objet
        self._btn(screen, L["panel"], "Objet sélectionné")
        fr = self._field_rects(L["panel"])
        if fr is None:
            t = self.font_small.render("(aucun — « Ajouter » ou cliquez un objet)", True, GRAY_LIGHT)
            screen.blit(t, (L["panel"].x + 10, L["panel"].y + 50))
        else:
            # Ne pas écraser le texte en cours d'édition : on re-synchronise
            # uniquement quand le champ n'est pas actif (sinon le clavier
            # serait brouillé à chaque frame).
            if not (self.name_input.active or self.action_input.active):
                self.name_input.set_text(self._selected_text()[0])
                self.action_input.set_text(self._selected_text()[1])
            self.name_input.draw(screen)
            self.action_input.draw(screen)
            pos = self.map_entry["interactions"][self.selected_obj]["pos"]
            t = self.font_small.render(f"Pos : {pos} (fenêtre {self.win_w}×{self.win_h})", True, GRAY_LIGHT)
            screen.blit(t, (L["panel"].x + 10, L["panel"].y + 150))
            self._btn(screen, fr["delete"], "Supprimer l'objet", accent=RED)
        self._btn(screen, L["save_btn"], "Enregistrer", accent=(90, 210, 120))
        self._btn(screen, L["revert_btn"], "Carte préc.")
        self._btn(screen, L["undo_btn"], "Recharger")
        if self.selected_obj is not None and self.interact_warning:
            t = self.font_small.render(self.interact_warning, True, RED)
            screen.blit(t, (18, L["panel"].y + L["panel"].h + 6))

    def _draw(self, screen):
        screen.fill(BLACK)
        self._draw_canvas(screen)
        L = self._layout()
        self._draw_sidebar(screen, L)
        # top bar
        pygame.draw.rect(screen, DARK, (0, 0, EDITOR_WINDOW_W, TOP_H))
        t = self.font_s_bold.render("RPG_Ai — Éditeur de cartes (fond + segmentation)", True, WHITE)
        screen.blit(t, (12, (TOP_H - t.get_height()) // 2))
        self._slider(screen, pygame.Rect(EDITOR_WINDOW_W - 240, (TOP_H - 18) // 2 + 4, 150, 16),
                     self.mask_alpha, 0, 255)
        # bottom
        pygame.draw.rect(screen, DARK, (0, EDITOR_WINDOW_H - BOTTOM_H, EDITOR_WINDOW_W, BOTTOM_H))
        st = self.status + ("  [M]" if self._dirty_mask else "") + ("  [J]" if self._dirty_json else "")
        t = self.font_small.render(st, True, YELLOW)
        screen.blit(t, (12, (BOTTOM_H - t.get_height()) // 2))
        pygame.display.flip()

    def _draw_cursor(self, screen):
        pos = pygame.mouse.get_pos()
        if self._in_canvas(pos):
            pygame.draw.circle(screen, WHITE, pos, 2)
        pygame.display.flip()

    # -------------------------------------------------------------------
    # Champs texte
    # -------------------------------------------------------------------
    def _init_fields(self):
        L = self._layout()
        fr = self._field_rects(L["panel"])
        self.name_input = TextEdit(fr["name"] if fr else pygame.Rect(0, 0, 0, 24),
                                   self.font_s)
        self.action_input = TextEdit(fr["action"] if fr else pygame.Rect(0, 0, 0, 24),
                                     self.font_s)

    def _sync_fields(self):
        L = self._layout()
        fr = self._field_rects(L["panel"])
        if fr is None:
            self.name_input.active = False
            self.action_input.active = False
        else:
            self.name_input.rect = fr["name"]
            self.action_input.rect = fr["action"]
            if not self.name_input.active and not self.action_input.active:
                n, a = self._selected_text()
                self.name_input.set_text(n)
                self.action_input.set_text(a)

    def _commit_fields(self, which):
        if which == "name":
            self._push_undo()
            self._set_obj_name(self.name_input.text)
        else:
            self._push_undo()
            self._set_obj_action(self.action_input.text)
        self.name_input.active = self.action_input.active = False

    # -------------------------------------------------------------------
    # Événements
    # -------------------------------------------------------------------
    def _handle_event(self, event, L):
        if event.type == pygame.QUIT:
            self.running = False
            return
        # champ texte (priorité)
        if (self.name_input.active or self.action_input.active):
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._commit_fields("name" if self.name_input.active else "action")
                    return
                if event.key == pygame.K_BACKSPACE:
                    if self.name_input.active:
                        self.name_input.text = self.name_input.text[:-1]
                    else:
                        self.action_input.text = self.action_input.text[:-1]
                    return
                if event.key == pygame.K_ESCAPE:
                    self._sync_fields()
                    self.name_input.active = self.action_input.active = False
                    return
                if event.key == pygame.K_SPACE:
                    return
            elif event.type == pygame.TEXTINPUT and event.text:
                (self.name_input if self.name_input.active else self.action_input).text += event.text
                return
            return
        # touches globales
        if event.type == pygame.KEYDOWN:
            k = event.key
            if k == pygame.K_ESCAPE:
                self.running = False
                return
            if k == pygame.K_z:
                self._pop_undo()
                return
            if k == pygame.K_s:
                self.save_all()
                return
            if k == pygame.K_p: self.tool = "paint"
            elif k == pygame.K_f: self.tool = "fill"
            elif k == pygame.K_a: self.tool = "add"
            elif k == pygame.K_m: self.tool = "move"
            elif k == pygame.K_d: self.tool = "delete"
            return
        # clics
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if self._in_canvas(pos):
                cx, cy = self._canvas_local(pos)
                if self.tool == "paint":
                    self._mouse_down = True
                    self._push_undo()
                    self._paint_brush(cx, cy)
                    self.status = f"Peint ({self.paint_color})"
                elif self.tool == "fill":
                    self._push_undo()
                    self._fill_region(cx, cy)
                elif self.tool == "add":
                    wx, wy = self.canvas_local_to_win(cx, cy)
                    self._push_undo()
                    self._add_object(wx, wy)
                elif self.tool == "move":
                    idx = self._object_at(cx, cy)
                    self.selected_obj = idx
                    self._drag_obj = idx
                    if idx is not None:
                        self._push_undo()
                    else:
                        self.status = "Aucun objet ici."
                    self._check_warning()
                elif self.tool == "delete":
                    idx = self._object_at(cx, cy)
                    if idx is not None:
                        self.selected_obj = idx
                        self._push_undo()
                        self._delete_object()
                    else:
                        self.status = "Aucun objet ici."
                return
            # sidebar
            if L["map_row"].x <= pos[0] < L["map_row"].x + 40:
                if self.map_idx > 0:
                    self._select_map(self.map_idx - 1)
                return
            if L["map_row"].x + L["map_row"].w - 40 <= pos[0] < L["map_row"].x + L["map_row"].w:
                if self.map_idx < len(self.data["maps"]) - 1:
                    self._select_map(self.map_idx + 1)
                return
            for tname, r in L["tools"].items():
                if r.collidepoint(pos):
                    self.tool = tname
                    self.selected_obj = None
                    self.status = self.TOOL_LABELS[tname]
                    return
            for i, r in L["palette"].items():
                if r.collidepoint(pos) or pygame.Rect(r.x - 44, r.y, 34, r.h).collidepoint(pos):
                    self.paint_color = SEGMENT_PALETTE[i][1]
                    self.status = f"Couleur : {SEGMENT_PALETTE[i][0]}"
                    return
            if L["save_btn"].collidepoint(pos):
                self.save_all()
                return
            if L["revert_btn"].collidepoint(pos):
                if self.map_idx > 0:
                    self._select_map(self.map_idx - 1)
                return
            if L["undo_btn"].collidepoint(pos):
                self._pop_undo()
                return
            fr = self._field_rects(L["panel"])
            if fr is not None and fr["delete"].collidepoint(pos):
                self._push_undo()
                self._delete_object()
                return
            f = None
            if fr is not None:
                if fr["name"].collidepoint(pos):
                    f = "name"
                elif fr["action"].collidepoint(pos):
                    f = "action"
            if f:
                self._sync_fields()
                if f == "name":
                    self.name_input.active = True
                    self.action_input.active = False
                else:
                    self.name_input.active = True
                    self.action_input.active = False
                self.name_input.active = (f == "name")
                self.action_input.active = (f == "action")
                self.status = f"Édition : {f}"
                return
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            pos = event.pos
            if self._drag_obj is not None and self._in_canvas(pos):
                cx, cy = self._canvas_local(pos)
                wx, wy = self.canvas_local_to_win(cx, cy)
                self._move_object(wx, wy)
                self._check_warning()
                self.status = f"Objet déplacé vers ({round(wx)}, {round(wy)})"
            self._drag_obj = None
            self._mouse_down = False
            if self._field_active():
                if not (self.name_input.rect.collidepoint(pos)
                        or self.action_input.rect.collidepoint(pos)):
                    self._commit_fields("name" if self.name_input.active else "action")
                else:
                    self._sync_fields()
                self.name_input.active = self.action_input.active = False
            return
        if event.type == pygame.MOUSEMOTION:
            pos = event.pos
            if self._mouse_down and self.tool == "paint" and self._in_canvas(pos):
                cx, cy = self._canvas_local(pos)
                self._paint_brush(cx, cy)
            if self._drag_obj is not None and self._in_canvas(pos):
                cx, cy = self._canvas_local(pos)
                wx, wy = self.canvas_local_to_win(cx, cy)
                self.data["maps"][self.map_idx]["interactions"][self._drag_obj]["pos"] = [
                    round(wx), round(wy)]
                self._check_warning()
            if self._in_canvas(pos):
                cx, cy = self._canvas_local(pos)
                wx, wy = self.canvas_local_to_win(cx, cy)
                ox, oy = cx / self.scale, cy / self.scale
                self.status = (f"O({int(round(ox)), int(round(oy))})  "
                                f"W({round(wx, 1)}, {round(wy, 1)})  outil={self.tool}")
            if self._field_active():
                self._draw_cursor(self.screen)

    def _field_active(self):
        return self.name_input.active or self.action_input.active

    # -------------------------------------------------------------------
    # Boucle
    # -------------------------------------------------------------------
    def run(self, max_frames=None):
        clock = pygame.time.Clock()
        frame = 0
        while self.running:
            if max_frames is not None and frame >= max_frames:
                break
            self._sync_fields()
            for event in pygame.event.get():
                self._handle_event(event, self._layout())
            self._draw(self.screen)
            self._draw_cursor(self.screen)
            clock.tick(60)
            frame += 1
        pygame.quit()


def main():
    ap = argparse.ArgumentParser(description="Éditeur de cartes (pygame) pour RPG_Ai.")
    ap.add_argument("adventure", nargs="?",
                    default=str(ADVENTURES_DIR / (DEFAULT_ADVENTURE + ".json")))
    ap.add_argument("--headless", action="store_true", help="Mode sans écran (test).")
    ap.add_argument("--frames", type=int, default=0, help="Frames max (test).")
    args = ap.parse_args()
    editor = MapEditor(args.adventure, headless=args.headless)
    editor.run(max_frames=args.frames if args.frames else None)


if __name__ == "__main__":
    main()
