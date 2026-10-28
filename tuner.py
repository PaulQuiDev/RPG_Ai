"""Interface tkinter pour ajuster les settings de coupe de chaque
personnage (joueur ou NPC).

Un PNG de personnage est généré : la position et la hauteur du sprite
varient un peu d'une génération à l'autre. Ce tuner permet d'ajuster
manuellement, cadre par cadre, la fenêtre de coupe (taille + position dans
la feuille) et le point d'ancrage (les pieds du personnage), avec un
aperçu live. Le résultat est écrit dans ``asset/sprite_configs.json`` et
rechargé au démarrage du jeu (voir ``settings.apply_sprite_overrides``).

Usage :
    python tuner.py              # liste tous les personnages
    python tuner.py Femme        # ouvre directement sur "Femme"

La logique pure (lecture / écriture des overrides) est à la tête du
fichier et est testable sans GUI (tests/test_sprite_tuner.py).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pygame
import tkinter as tk

import settings
from sprite_loader import resolve_crop_config

# ---------------------------------------------------------------------------
# Layout : 4 lignes (directions) x 3 colonnes (frames).
# ---------------------------------------------------------------------------
SHEET_ROWS = ["face", "gauche", "droite", "dos"]
SHEET_COLS = [0, 1, 2]
SHEET_SCALE = 0.45      # échelle de la feuille dans le canvas de coupe
PREVIEW_SCALE = 1.0     # échelle de l'aperçu de frame (1:1 => précision)
PREVIEW_W = 380
PREVIEW_H = 520


# ---------------------------------------------------------------------------
# Logique pure (testable sans GUI) : lecture / écriture des overrides.
# ---------------------------------------------------------------------------

def load_overrides(path) -> dict:
    """Charguer un fichier d'overrides (JSON) vers
    ``{nom: {crop_size, crop_offsets, anchor_offsets}}``.

    Les clés de colonne sont des chaînes dans le JSON ; elles sont
    converties en ``int`` à la lecture. Les champs invalides / manquants
    sont ignorés (graceful). Renvoie ``{}`` si le fichier est absent,
    mal formé ou illisible.
    """
    path = Path(path)
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        print(f"AVERTISSEMENT : {path} illisible, overrides ignorés")
        return {}
    if not isinstance(data, dict):
        return {}
    out = {}
    for name, cfg in data.items():
        if not isinstance(cfg, dict):
            continue
        entry: dict = {}
        for field in ("crop_size", "crop_offsets"):
            parsed = {}
            for direction, cols in cfg.get(field, {}).items():
                if not isinstance(cols, dict):
                    continue
                parsed[direction] = {
                    int(col): tuple(v) for col, v in cols.items()
                }
            entry[field] = parsed
        anchor_offsets = {}
        for direction, value in cfg.get("anchor_offsets", {}).items():
            try:
                anchor_offsets[direction] = tuple(value)
            except TypeError:
                pass
        entry["anchor_offsets"] = anchor_offsets
        out[name] = entry
    return out


def save_overrides(path, overrides: dict) -> Path:
    """Écrire le dict ``{nom: {...}}`` dans ``path`` (JSON), de façon
    atomique (écriture dans un fichier temp puis renommage). Crée les
    dossiers parents."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(overrides, fh, indent=2, ensure_ascii=False)
    tmp.replace(path)
    return path


def _to_json_dict(obj: dict) -> dict:
    """Convertir ``{direction: {col(int): (v, ...)}}`` vers une structure
    JSON (clés de colonne en str)."""
    return {
        direction: {
            str(col): list(val) for col, val in sub.items()
        }
        for direction, sub in obj.items()
        if isinstance(sub, dict)
    }


def save_tuned(
    name: str,
    crop_size: dict,
    crop_offsets: dict,
    anchor_offsets: dict,
    path=None,
) -> Path:
    """Écrire la config effective du personnage ``name`` dans ``path``
    (par défaut ``settings.SPRITE_CONFIGS_PATH``), en fusionnant avec les
    autres personnages déjà présents. Les clés int -> str pour les colonnes ;
    à la lecture elles sont restaurées (voir ``settings.apply_sprite_overrides``).
    """
    overrides = load_overrides(settings.SPRITE_CONFIGS_PATH)
    overrides[name] = {
        "crop_size": _to_json_dict(crop_size),
        "crop_offsets": _to_json_dict(crop_offsets),
        "anchor_offsets": {d: list(v) for d, v in anchor_offsets.items()},
    }
    out = save_overrides(path or settings.SPRITE_CONFIGS_PATH, overrides)
    settings.SPRITE_OVERRIDES = load_overrides(out)
    return out


def read_character_config(name: str):
    """Retourner ``(name, data, kind)`` d'un personnage du nom ``name`` dans
    ``settings`` (joueur ou NPC) après application des overrides et des
    défauts. Renvoie ``None`` si inconnu. ``kind`` ∈ {"joueur", "npc"}.
    """
    for char in settings.CHARACTERS:
        if char.get("name") == name:
            return (name, char, "joueur")
    for m in settings.MAPS:
        for npc in m.get("npcs", []):
            if npc.get("name") == name:
                return (name, npc, "npc")
    return None


def list_characters():
    """Liste ``[(name, kind, sprite_path)]`` de tous les personnages
    ajustables (joueur + NPC), dedupliqués par nom."""
    result = []
    seen = set()
    for char in settings.CHARACTERS:
        name = char.get("name")
        if name and name not in seen:
            seen.add(name)
            result.append((name, "joueur", str(char.get("sprite"))))
    for m in settings.MAPS:
        for npc in m.get("npcs", []):
            name = npc.get("name")
            if name and name not in seen:
                seen.add(name)
                result.append((name, "npc", str(npc.get("sprite"))))
    return result


def cell_bounds(sheet_w: int, sheet_h: int, direction: str, col: int):
    """Borne du cell ``(x0, y0, x1, y1)`` dans la feuille."""
    row = SHEET_ROWS.index(direction)
    col_x0 = int(col * sheet_w / len(SHEET_COLS))
    col_x1 = int((col + 1) * sheet_w / len(SHEET_COLS))
    row_y0 = int(row * sheet_h / len(SHEET_ROWS))
    row_y1 = int((row + 1) * sheet_h / len(SHEET_ROWS))
    return (col_x0, row_y0, col_x1, row_y1)


def _clamp_rect(rect, bounds):
    """Clamer un rect ``(x, y, w, h)`` dans un cell ``(x0, y0, x1, y1)``."""
    x0, y0, x1, y1 = bounds
    x, y, w, h = rect
    w = max(1, min(w, x1 - x0))
    h = max(1, min(h, y1 - y0))
    x = max(x0, min(x, x1 - w))
    y = max(y0, min(y, y1 - h))
    return (int(round(x)), int(round(y)), int(round(w)), int(round(h)))


def _ppm_bytes(surface: pygame.Surface) -> bytes:
    """Convertir une surface pygame (RGBA) en PPM binaire (P6)."""
    data = pygame.image.tobytes(surface, "RGBA")
    w, h = surface.get_size()
    ppm = bytearray(f"P6\n{w} {h}\n255\n".encode())
    for i in range(0, len(data), 4):
        ppm += bytes(data[i:i + 3])
    return bytes(ppm)


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class SpriteTunerWindow:
    def __init__(self, root: tk.Tk, initial_name: str | None = None):
        self.root = root
        self.root.title("Ajusteur de sprites (tuner)")
        self.root.resizable(False, False)

        self.sheet = None
        self.sheet_w = 0
        self.sheet_h = 0
        self.crops: dict = {}                       # {(d, col): (x,y,w,h)}
        self.anchors: dict = {}                    # {d: (ax, ay)}
        self.active = ("face", 1)                  # (direction, col)
        self.mode = "crop"                         # "crop" ou "anchor"
        self.frames: dict = {}                     # {d: {col: Surface}}
        self.character_name = ""
        self.character_data = None

        self._sheet_image = None
        self._prev_image = None
        self._prev_cache_key = None
        self._drag_start = None
        self._last_pos = (0, 0)
        self._drag_box_item = None
        self._prev_drag = False
        self._suppress_char = False

        self._build_ui()
        if initial_name:
            self.select_character(initial_name)

        self.sheet_canvas.bind("<Button-1>", self._on_sheet_press)
        self.sheet_canvas.bind("<B1-Motion>", self._on_sheet_drag)
        self.sheet_canvas.bind("<ButtonRelease-1>", self._on_sheet_release)
        self.prev_canvas.bind("<Button-1>", self._on_prev_press)
        self.prev_canvas.bind("<B1-Motion>", self._on_prev_drag)
        self.prev_canvas.bind("<ButtonRelease-1>", self._on_prev_release)

    # ---------------- UI ----------------
    def _list_names(self):
        return [f"{n} ({kind})" for n, kind, _ in list_characters()]

    def _build_ui(self):
        self.character_var = tk.StringVar(value="—")
        self.status_var = tk.StringVar(value="Sélectionnez un personnage.")

        top = tk.Frame(self.root)
        top.pack(fill="x")
        tk.Label(top, text="Personnage :").pack(side="left", padx=(12, 6), pady=8)
        self.character_var.trace_add("write", lambda *_: self._on_char_changed())
        self.char_menu = tk.OptionMenu(top, self.character_var, *self._list_names())
        self.char_menu.pack(side="left", padx=4, pady=8)

        btns = tk.Frame(top)
        btns.pack(side="right", padx=8, pady=8)
        tk.Button(btns, text="Réinitialiser", command=self.reset_character).pack(side="left", padx=(0, 4))
        tk.Button(btns, text="Enregistrer", command=self.save).pack(side="left", padx=(0, 4))
        tk.Button(btns, text="Quitter", command=self.root.destroy).pack(side="left", padx=4)

        mode = tk.Frame(self.root)
        mode.pack(fill="x", pady=2)
        self.crop_btn = tk.Button(
            mode, text="Cutter : glisser une boîte sur la feuille",
            command=lambda: self._set_mode("crop"))
        self.crop_btn.pack(side="left", padx=(8, 4))
        self.anchor_btn = tk.Button(
            mode, text="Anchor : glisser le point rouge sur l'aperçu",
            command=lambda: self._set_mode("anchor"))
        self.anchor_btn.pack(side="left", padx=4)
        self._set_mode("crop")

        mid = tk.Frame(self.root)
        mid.pack(fill="both", expand=True)
        self.sheet_canvas = tk.Canvas(mid, highlightthickness=1, bg="gray80")
        self.sheet_canvas.pack(side="left", padx=(8, 4), pady=(4, 4), fill="both", expand=True)
        self.prev_canvas = tk.Canvas(
            mid, width=PREVIEW_W, height=PREVIEW_H,
            highlightthickness=1, bg="white")
        self.prev_canvas.pack(side="right", padx=(4, 8), pady=(4, 4))

        info = tk.Frame(self.root)
        info.pack(fill="x", padx=12, pady=(0, 4))
        self.info_var = tk.StringVar(value="")
        tk.Label(info, textvariable=self.info_var, anchor="w",
                 bg="white", relief="sunken").pack(fill="x")

        status = tk.Frame(self.root, height=26, bg="gray60")
        status.pack(fill="x")
        tk.Label(status, textvariable=self.status_var, anchor="w").pack(
            fill="x", padx=8, pady=4)

    # ---------------- Character selection ----------------
    def _on_char_changed(self):
        if self._suppress_char:
            return
        label = self.character_var.get()
        if not label or label == "—":
            return
        self.select_character(label.split(" (")[0])

    def select_character(self, name: str) -> None:
        self._suppress_char = True
        try:
            info = read_character_config(name)
            if info is None:
                self.status_var.set("Personnage inconnu.")
                return
            self.character_name, self.character_data, kind = info
            self.character_var.set(f"{name} ({kind})")
            sprite_path = self.character_data.get("sprite")
            if not sprite_path:
                self.status_var.set("Personnage sans feuille de sprite.")
                return
            try:
                self.sheet = pygame.image.load(sprite_path)
            except Exception as e:
                self.sheet = None
                self.status_var.set(f"Impossible de charger la feuille : {e}")
                return
            self.sheet_w, self.sheet_h = self.sheet.get_size()
            cs, co, ao = resolve_crop_config(self.character_data)
            self._recompute_crops_and_anchors(cs, co, ao)
            self._build_frames()
            self._render_static()
            self._update_info()
            self.status_var.set(f"Chargé {name} ({kind}) — feuille {self.sheet_w}x{self.sheet_h}.")
        finally:
            self._suppress_char = False

    # ---------------- Crop / anchor state ----------------
    def _recompute_crops_and_anchors(self, cs, co, ao):
        self.crops = {}
        for direction in SHEET_ROWS:
            for col in SHEET_COLS:
                bounds = cell_bounds(self.sheet_w, self.sheet_h, direction, col)
                cw, ch = cs.get(direction, {}).get(
                    col, settings.CROP_SIZE.get(direction, {}).get(col, (200, 300)))
                ox, oy = co.get(direction, {}).get(
                    col, settings.CROP_OFFSETS.get(direction, {}).get(col, (0, 0)))
                rect = _clamp_rect(
                    (int(bounds[0]) + int(ox), int(bounds[1]) + int(oy),
                     int(cw), int(ch)), bounds)
                self.crops[(direction, col)] = rect
        self.anchors = {
            d: (int(ao.get(d, (0, 0))[0]), int(ao.get(d, (0, 0))[1]))
            for d in SHEET_ROWS
        }

    def _build_frames(self):
        self.frames = {d: {} for d in SHEET_ROWS}
        if self.sheet is None:
            return
        for direction in SHEET_ROWS:
            for col in SHEET_COLS:
                x, y, w, h = self.crops[(direction, col)]
                if w <= 0 or h <= 0 or x < 0 or y < 0:
                    self.frames[direction][col] = pygame.Surface((1, 1))
                    continue
                self.frames[direction][col] = self.sheet.subsurface((x, y, w, h)).copy()

    def _set_mode(self, mode: str) -> None:
        self.mode = mode
        if mode == "crop":
            self.crop_btn.config(relief="sunken")
            self.anchor_btn.config(relief="flat")
            self.status_var.set("Mode CUTTER : glissez une boîte sur la feuille.")
        else:
            self.anchor_btn.config(relief="sunken")
            self.crop_btn.config(relief="flat")
            self.status_var.set("Mode ANCHOR : glissez le point rouge sur l'aperçu.")

    # ---------------- Sheet interactions ----------------
    def _select_cell_at(self, cx: int, cy: int) -> None:
        sx = cx / SHEET_SCALE
        sy = cy / SHEET_SCALE
        col = int(sx / self.sheet_w * len(SHEET_COLS))
        col = max(0, min(col, len(SHEET_COLS) - 1))
        row = int(sy / self.sheet_h * len(SHEET_ROWS))
        row = max(0, min(row, len(SHEET_ROWS) - 1))
        self.active = (SHEET_ROWS[row], col)
        self._render_static()
        self._update_info()
        self.status_var.set(f"Cellule active : {self.active[0]} [{self.active[1]}]")

    def _on_sheet_press(self, event) -> None:
        if self.sheet is None:
            return
        if self.mode == "crop":
            self._select_cell_at(event.x, event.y)
            self._drag_start = (event.x, event.y)
            self._last_pos = (event.x, event.y)
            self._redraw_drag_box()
        else:
            self._select_cell_at(event.x, event.y)

    def _on_sheet_drag(self, event) -> None:
        if self.mode != "crop" or self._drag_start is None:
            return
        self._last_pos = (event.x, event.y)
        self._redraw_drag_box()

    def _on_sheet_release(self, event) -> None:
        if self._drag_start is None or self.mode != "crop":
            self._drag_start = None
            return
        sx, sy = self._drag_start
        self._drag_start = None
        def to_sheet(px, py):
            return int(round(px / SHEET_SCALE)), int(round(py / SHEET_SCALE))
        ax, ay = to_sheet(sx, sy)
        bx, by = to_sheet(event.x, event.y)
        x, y = min(ax, bx), min(ay, by)
        w, h = abs(bx - ax), abs(by - ay)
        if w < 4 or h < 4:
            self._render_static()
            return
        bounds = cell_bounds(self.sheet_w, self.sheet_h, *self.active)
        x, y, w, h = _clamp_rect((x, y, w, h), bounds)
        self.crops[self.active] = (x, y, w, h)
        self._build_frames()
        self._render_static()
        self._update_info()
        self.status_var.set(
            f"Cadre ajusté : {self.active[0]} [{self.active[1]}] = ({x},{y}) {w}x{h}")

    def _redraw_drag_box(self) -> None:
        if getattr(self, "_drag_box_item", None) is not None:
            self.sheet_canvas.delete(self._drag_box_item)
            self._drag_box_item = None
        if self._drag_start is None or self.mode != "crop":
            return
        sx, sy = self._drag_start
        mx, my = self._last_pos
        self._drag_box_item = self.sheet_canvas.create_rectangle(
            min(sx, mx), min(sy, my), max(sx, mx), max(sy, my),
            outline="blue", width=2)

    # ---------------- Preview / anchor ----------------
    def _prev_top_left(self, w, h):
        pw = int(w * PREVIEW_SCALE)
        ph = int(h * PREVIEW_SCALE)
        cx = PREVIEW_W // 2
        cy = PREVIEW_H - 30
        return cx - pw // 2, cy - ph

    def _render_preview(self) -> None:
        self.prev_canvas.delete("all")
        x, y, w, h = self.crops.get(self.active, (0, 0, 1, 1))
        frame = self.frames.get(self.active[0], {}).get(self.active[1])
        pw = int(w * PREVIEW_SCALE)
        ph = int(h * PREVIEW_SCALE)
        tx, ty = self._prev_top_left(w, h)
        key = (id(frame) if frame is not None else None, w, h)
        if frame is not None:
            if self._prev_cache_key != key:
                self._prev_cache_key = key
                disp = pygame.transform.scale(frame, (max(1, pw), max(1, ph)))
                self._prev_image = tk.PhotoImage(data=_ppm_bytes(disp))
            if self._prev_image is not None:
                self.prev_canvas.create_image(tx, ty, image=self._prev_image, anchor="nw")
        else:
            self.prev_canvas.create_text(
                PREVIEW_W // 2, PREVIEW_H // 2,
                text="frame inconnue", fill="red")
        # Référence : bottom-center du frame (anchor = 0)
        rx = tx + pw // 2
        ry = ty + ph
        self.prev_canvas.create_line(rx - 5, ry, rx + 5, ry, fill="green", width=1)
        self.prev_canvas.create_line(rx, ry - 5, rx, ry + 5, fill="green", width=1)
        # Anchage : croix rouge (les pieds)
        ax, ay = self.anchors.get(self.active[0], (0, 0))
        feet_x = w / 2 - ax
        feet_y = h - ay
        fx = tx + feet_x * PREVIEW_SCALE
        fy = ty + feet_y * PREVIEW_SCALE
        r = 7
        self.prev_canvas.create_oval(fx - r, fy - r, fx + r, fy + r, outline="red", width=2)
        self.prev_canvas.create_line(fx - 5, fy, fx + 5, fy, fill="red", width=2)
        self.prev_canvas.create_line(fx, fy - 5, fx, fy + 5, fill="red", width=2)
        # Étiquette
        self.prev_canvas.create_text(
            10, 10, anchor="nw",
            text=f"{self.active[0]} [{self.active[1]}]\ncrop=({x},{y}) {w}x{h}\nanchor=({ax},{ay})",
            font=("Courier", 9, "bold"))

    def _apply_anchor(self, mx: int, my: int) -> None:
        direction = self.active[0]
        x, y, w, h = self.crops[self.active]
        tx, ty = self._prev_top_left(w, h)
        feet_x = (mx - tx) / PREVIEW_SCALE
        feet_y = (my - ty) / PREVIEW_SCALE
        ax = int(round(w / 2 - feet_x))
        ay = int(round(h - feet_y))
        self.anchors[direction] = (ax, ay)
        self._render_preview()
        self._update_info()
        self.status_var.set(f"Anchor {direction} = ({ax}, {ay})")

    def _on_prev_press(self, event):
        if self.mode != "anchor":
            return
        self._prev_drag = True
        if self.active[1] in self.frames.get(self.active[0], {}):
            self._apply_anchor(event.x, event.y)

    def _on_prev_drag(self, event) -> None:
        if not self._prev_drag or self.mode != "anchor":
            return
        self._apply_anchor(event.x, event.y)

    def _on_prev_release(self, event) -> None:
        self._prev_drag = False

    # ---------------- Rendering ----------------
    def _render_sheet(self) -> None:
        if self.sheet is None:
            self.sheet_canvas.delete("all")
            return
        ds_w = int(round(self.sheet_w * SHEET_SCALE))
        ds_h = int(round(self.sheet_h * SHEET_SCALE))
        self.sheet_canvas.config(width=ds_w + 8, height=ds_h + 8)
        self.sheet_canvas.delete("all")
        disp = pygame.transform.scale(self.sheet, (ds_w, ds_h))
        self._sheet_image = tk.PhotoImage(data=_ppm_bytes(disp))
        self.sheet_canvas.create_image(4, 4, image=self._sheet_image, anchor="nw")
        for i in range(len(SHEET_COLS) + 1):
            x = int(i * self.sheet_w / len(SHEET_COLS)) * SHEET_SCALE + 4
            self.sheet_canvas.create_line(x, 4, x, ds_h + 4, fill="orange", width=1)
        for i in range(len(SHEET_ROWS) + 1):
            y = int(i * self.sheet_h / len(SHEET_ROWS)) * SHEET_SCALE + 4
            self.sheet_canvas.create_line(4, y, ds_w + 4, y, fill="orange", width=1)
        for (d, col), (x, y, w, h) in self.crops.items():
            active = (d, col) == self.active
            color = "red" if active else "cyan"
            self.sheet_canvas.create_rectangle(
                x * SHEET_SCALE + 4, y * SHEET_SCALE + 4,
                (x + w) * SHEET_SCALE + 4, (y + h) * SHEET_SCALE + 4,
                outline=color, width=3 if active else 1)
        x0, y0, x1, y1 = cell_bounds(self.sheet_w, self.sheet_h, *self.active)
        self.sheet_canvas.create_rectangle(
            x0 * SHEET_SCALE + 4, y0 * SHEET_SCALE + 4,
            x1 * SHEET_SCALE + 4, y1 * SHEET_SCALE + 4,
            outline="magenta", width=2)

    def _render_static(self) -> None:
        self._render_sheet()
        self._render_preview()

    def _update_info(self) -> None:
        x, y, w, h = self.crops.get(self.active, (0, 0, 1, 1))
        ax, ay = self.anchors.get(self.active[0], (0, 0))
        self.info_var.set(
            f"Cellule active : {self.active[0]} [{self.active[1]}]   "
            f"Cutte (x,y,w,h) : {x},{y} {w}x{h}   "
            f"Anchor : ({ax}, {ay})   "
            f"Feuille {self.sheet_w}x{self.sheet_h}, mode={self.mode}")

    # ---------------- Actions ----------------
    def reset_character(self) -> None:
        name = self.character_name
        if not name or self.sheet is None:
            return
        cs = {d: {col: settings.CROP_SIZE[d][col] for col in SHEET_COLS} for d in SHEET_ROWS}
        co = {d: {col: settings.CROP_OFFSETS[d][col] for col in SHEET_COLS} for d in SHEET_ROWS}
        ao = {d: (0, 0) for d in SHEET_ROWS}
        overrides = load_overrides(settings.SPRITE_CONFIGS_PATH)
        overrides.pop(name, None)
        save_overrides(settings.SPRITE_CONFIGS_PATH, overrides)
        self._recompute_crops_and_anchors(cs, co, ao)
        self._build_frames()
        self._render_static()
        self._update_info()
        self.status_var.set(f"{name} : overrides supprimés, coupes réinitialisées.")

    def save(self) -> Path:
        name = self.character_name
        if not name:
            return settings.SPRITE_CONFIGS_PATH
        crop_size = {}
        crop_offsets = {}
        for direction in SHEET_ROWS:
            crop_size[direction] = {}
            crop_offsets[direction] = {}
            for col in SHEET_COLS:
                x, y, w, h = self.crops[(direction, col)]
                x0, y0, _, _ = cell_bounds(self.sheet_w, self.sheet_h, direction, col)
                crop_size[direction][col] = (w, h)
                crop_offsets[direction][col] = (x - x0, y - y0)
        anchor_offsets = {d: self.anchors[d] for d in SHEET_ROWS}
        out = save_tuned(name, crop_size, crop_offsets, anchor_offsets)
        self.status_var.set(f"✓ {name} sauvegardé dans {Path(out).name}")
        return out


def main(argv: list[str] | None = None) -> None:
    argv = argv or sys.argv[1:]
    pygame.display.init()
    root = tk.Tk()
    initial = argv[0] if argv else None
    SpriteTunerWindow(root, initial_name=initial)
    root.mainloop()
    pygame.quit()


if __name__ == "__main__":
    main()
