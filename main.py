"""Point d'entrée du jeu : initialisation pygame, création de `Game`,
boucle (clock → événements → update → render). Toute la logique de jeu
vit dans `game.Game`.

Options :
  --debug       affiche la carte de collision, les boîtes d'interaction
                (itboxes) et la position du joueur (console + overlay)
  --window WxH  résolution de la fenêtre (ex. --window 800x600).
                Défaut : 960x720 (résolution logique du jeu).
  --fullscreen  plein écran : la résolution logique (960x720) est étendue
                au moniteur (aspect conservé, bandes noires si besoin).
                Mutuellement exclusif avec --window.
"""
import argparse
import re

import pygame

from settings import (
    COLLISIONS_ENABLED_DEFAULT,
    CHARACTERS,
    MAPS,
    WINDOW_BACKGROUND,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    WINDOW_WIDTH,
)
from game import Game

_WINDOW_RE = re.compile(r"^\s*(\d+)\s*[xXx×]\s*(\d+)\s*$")


def _parse_window_size(value):
    """Parse `WxH` (ex. `800x600`, `800X600`, `800x600`, `800×600`) en
    (width, height). Lève ValueError si le format ou la valeur est invalide."""
    match = _WINDOW_RE.match(value)
    if not match:
        raise ValueError("Format attendu : WxH (ex. 800x600)")
    width, height = int(match.group(1)), int(match.group(2))
    if width <= 0 or height <= 0:
        raise ValueError("Résolution trop petite (WxH doit être > 0)")
    return width, height


def _blit_rect(game_w, game_h, win_w, win_h):
    """Retourne (x, y, bw, bh) : le plus grand rectangle centré de la
    fenêtre qui contient le jeu (ratio d'aspect game_w x game_h) sans le
    déformer (letterbox). bw/bh = taille ciblée du smoothscale,
    (x, y) = position de ce rectangle dans la fenêtre."""
    scale = min(win_w / game_w, win_h / game_h)
    bw = max(1, round(game_w * scale))
    bh = max(1, round(game_h * scale))
    return ((win_w - bw) // 2, (win_h - bh) // 2, bw, bh)


def main():
    if not CHARACTERS:
        raise SystemExit("Aucun personnage défini dans settings.py.")
    if not MAPS:
        raise SystemExit("Aucune carte définie dans settings.py.")

    parser = argparse.ArgumentParser(description="Jeu RPG (pygame)")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="affiche la carte de collision, les boîtes d'interaction "
        "(itboxes) et la position du joueur (console + overlay)",
    )
    parser.add_argument(
        "--window",
        metavar="WxH",
        help="résolution de la fenêtre (ex. 800x600). Défaut : 960x720.",
    )
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        help="plein écran (résolution logique 960x720 étendue au moniteur).",
    )
    args = parser.parse_args()

    if args.window and args.fullscreen:
        parser.error("--window et --fullscreen sont incompatibles")

    pygame.init()

    if args.fullscreen:
        info = pygame.display.Info()
        display_w = info.current_w or WINDOW_WIDTH
        display_h = info.current_h or WINDOW_HEIGHT
        display_flags = pygame.FULLSCREEN
    elif args.window:
        display_w, display_h = _parse_window_size(args.window)
        display_flags = 0
    else:
        display_w, display_h = WINDOW_WIDTH, WINDOW_HEIGHT
        display_flags = 0

    screen = pygame.display.set_mode((display_w, display_h), display_flags)
    pygame.display.set_caption(WINDOW_TITLE)
    font = pygame.font.SysFont("sans", 18)

    # Le jeu s'exécute à la résolution logique (960x720) sur une surface
    # hors-écran ; main.py blitte (smoothscale + letterbox) cette surface
    # dans la fenêtre. Toute la logique de jeu (coordonnées, HUD, sprites,
    # collisions) reste en 960x720 : changer la fenêtre ne casse rien.
    game_surface = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
    try:
        game = Game(
            game_surface,
            font,
            CHARACTERS,
            MAPS,
            collisions_enabled=COLLISIONS_ENABLED_DEFAULT,
            debug=args.debug,
        )
    except (RuntimeError, ValueError, KeyError) as error:
        pygame.quit()
        raise SystemExit(str(error)) from error

    # Le jeu est blitté en conservant son ratio d'aspect (letterbox).
    # Fast path : fenêtre de la résolution logique -> blit 1:1 (pas de
    # smoothscale). Sinon, smoothscale + bandes noires.
    blit_x, blit_y, blit_w, blit_h = _blit_rect(
        WINDOW_WIDTH, WINDOW_HEIGHT, display_w, display_h
    )
    direct = (
        display_w == WINDOW_WIDTH
        and display_h == WINDOW_HEIGHT
        and blit_x == 0
        and blit_y == 0
        and blit_w == WINDOW_WIDTH
        and blit_h == WINDOW_HEIGHT
    )

    clock = pygame.time.Clock()
    while not game.should_quit:
        dt = min(clock.tick(60) / 1000.0, 0.05)
        game.handle_events()
        game.update(dt)
        game.render()
        if direct:
            screen.blit(game_surface, (blit_x, blit_y))
        else:
            screen.fill(WINDOW_BACKGROUND)
            screen.blit(
                pygame.transform.smoothscale(
                    game_surface, (blit_w, blit_h)
                ),
                (blit_x, blit_y),
            )
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
