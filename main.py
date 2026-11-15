"""Point d'entrée du jeu : initialisation pygame, sélection de l'aventure,
création de `Game`, boucle (clock → événements → update → render). Toute la
logique de jeu vit dans `game.Game`.

Le moteur est *data-driven* : chaque aventure = un JSON
(``adventures/<nom>.json`` : sprites/assets + hyperparamètres + quête)
**et** un fichier ``adventures/<nom>/logic.py`` (classe ``Adventure``) qui
orchestre les *briques* du moteur (monstre, bougies, transformation,
dévoration, fuite, redirection) sans en développer de nouvelle.

Options CLI :
  --debug       affiche la carte de collision, les boîtes d'interaction
                (itboxes) et la position du joueur (console + overlay)
  --window WxH  résolution de la fenêtre (ex. --window 800x600).
                Défaut : 960x720 (résolution logique du jeu).
  --fullscreen  plein écran : la résolution logique (960x720) est étendue
                au moniteur (aspect conservé, bandes noires si besoin).
                Mutuellement exclusif avec --window.
  --save PATH   chemin du fichier de sauvegarde (clé S).
                Défaut : <projet>/saves/game.json.
  --load PATH   fichier à charger au démarrage (reprise de partie).
                Défaut : sauvegarde par défaut.
  --adv PATH    chemin d'un fichier d'aventure (JSON) à lancer directement
                (bypass du menu de sélection).
  --list        liste les cartes, interactions et NPCs de l'aventure
                (sans lancer le jeu). Avec --adv : une aventure ; sans
                --adv : toutes les aventures.

Mode web (pygbag / WASM) :
  L'aventure par défaut (``settings.DEFAULT_ADVENTURE``) est lancée
  automatiquement. Le menu de sélection (police système) n'est montré que
  sur desktop, quand ``--adv`` n'est pas fourni.
"""
import argparse
import asyncio
import re
import sys
from pathlib import Path

import pygame

from settings import (
    ADVENTURES_DIR,
    COLLISIONS_ENABLED_DEFAULT,
    DEFAULT_ADVENTURE,
    load_adventure,
    WINDOW_BACKGROUND,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    WINDOW_WIDTH,
)
from game import Game
from adventure import load_adventure_logic

_WINDOW_RE = re.compile(r"^\s*(\d+)\s*[xXx×]\s*(\d+)\s*$")


def _make_font(size):
    """Création robuste d'une police : ``SysFont("sans")`` en priorité,
    fallback sur la police par défaut de pygame (``Font(None, size)``).

    Indispensable pour que le HUD et le menu s'affichent dans le runtime
    WASM (pygbag), où le système de polices ne résout pas toujours le nom
    "sans"."""
    try:
        return pygame.font.SysFont("sans", size)
    except Exception:
        return pygame.font.Font(None, size)


def _is_web():
    """Détecte le runtime web (pygbag / WASM).

    Le runtime web charge le jeu dans un VFS sous
    ``/data/data/<bundle>/assets/`` (l'index.html généré par pygbag fixe
    ``__file__`` = ``/data/data/<bundle>/assets/main.py``). Sur desktop,
    le chemin est une vraie racine du système.
    """
    candidates = []
    try:
        f = globals().get("__file__", "")
        if f:
            candidates.append(str(f))
    except Exception:
        pass
    try:
        argv0 = sys.argv[0] if sys.argv else ""
        if argv0:
            candidates.append(argv0)
    except Exception:
        pass
    for p in candidates:
        if "/data/data/" in p:
            return True
    return False


def _parse_window_size(value):
    """Parse `WxH` (ex. `800x600`) en (width, height).
    Lève ValueError si le format ou la valeur est invalide."""
    match = _WINDOW_RE.match(value)
    if not match:
        raise ValueError("Format attendu : WxH (ex. 800x600)")
    width, height = int(match.group(1)), int(match.group(2))
    if width <= 0 or height <= 0:
        raise ValueError("Résolution trop petite (WxH doit être > 0)")
    return width, height


def _build_parser():
    """Construit le parser d'options CLI."""
    parser = argparse.ArgumentParser(description="Jeu RPG (pygame)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--window",
        metavar="WxH",
        help="résolution de la fenêtre (ex. 800x600). Défaut : 960x720.",
    )
    group.add_argument(
        "--fullscreen",
        action="store_true",
        help="plein écran (résolution logique 960x720 étendue au moniteur).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="affiche la carte de collision, les boîtes d'interaction "
        "(itboxes) et la position du joueur (console + overlay)",
    )
    parser.add_argument(
        "--save",
        metavar="PATH",
        help="chemin du fichier de sauvegarde (utilisé par S et par défaut "
        "au chargement). Défaut : <projet>/saves/game.json.",
    )
    parser.add_argument(
        "--load",
        metavar="PATH",
        help="fichier à charger au démarrage (reprise de partie). "
        "Défaut : sauvegarde par défaut.",
    )
    parser.add_argument(
        "--adv",
        metavar="PATH",
        help="chemin d'un fichier d'aventure (JSON) à lancer directement "
        "(bypass du menu de sélection).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="liste les cartes, interactions et NPCs de l'aventure "
        "(sans lancer le jeu).",
    )
    return parser


def _blit_rect(game_w, game_h, win_w, win_h):
    """Retourne (x, y, bw, bh) : le plus grand rectangle centré de la
    fenêtre qui contient le jeu (ratio aspect game_w x game_h) sans le
    déformer (letterbox)."""
    scale = min(win_w / game_w, win_h / game_h)
    bw = max(1, round(game_w * scale))
    bh = max(1, round(game_h * scale))
    return ((win_w - bw) // 2, (win_h - bh) // 2, bw, bh)


def _list_adventures(adv_dir):
    """Retourne la liste des aventures disponibles :
    [(Path vers le fichier JSON, titre), ...], triés par nom."""
    if not adv_dir.exists():
        return []
    results = []
    for f in sorted(adv_dir.glob("*.json")):
        try:
            with f.open("r", encoding="utf-8") as fh:
                import json

                data = json.load(fh)
            title = data.get("title", f.stem)
        except (OSError, ValueError):
            title = f.stem
        results.append((f, title))
    return results


def _print_adventure_summary(config_path: Path) -> None:
    """Liste toutes les cartes et objets d'une aventure (mode --list)."""
    import json

    with config_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    title = data.get("title", config_path.stem)
    start_map = data.get("start_map", data.get("name", ""))
    maps = data.get("maps", [])
    quest = data.get("quest", {})

    print(f"Aventure : {title}")
    if start_map:
        print(f"Départ     : {start_map}")
    if quest:
        print(f"Quête      : {dict(quest)}")
    print("-" * 60)

    for i, m in enumerate(maps, 1):
        name = m.get("name", f"Carte {i}")
        requires = m.get("requires") or []
        req_suf = f"  [requiert: {', '.join(requires)}]" if requires else ""
        print(f"[{i}] {name}{req_suf}")

        interactions = m.get("interactions", [])
        if interactions:
            for it in interactions:
                action = it.get("action", "?")
                pos = it.get("pos", [])
                desc = it.get("description", "")
                pos_s = f"({pos[0] if len(pos) > 0 else 0}, " \
                    f"{pos[1] if len(pos) > 1 else 0})"
                line = f"    Interaction : {action} @ {pos_s}"
                if desc:
                    line += f" — {desc}"
                print(line)

        npcs = m.get("npcs", [])
        if npcs:
            for n in npcs:
                name_np = n.get("name", "?")
                pos = n.get("pos", [])
                behav = n.get("behavior", "?")
                visible = n.get("visible", True)
                pos_s = f"({pos[0] if len(pos) > 0 else 0}, " \
                    f"{pos[1] if len(pos) > 1 else 0})"
                vis_s = " [masqué]" if not visible else ""
                print(f"    NPC : {name_np} @ {pos_s} "
                      f"[behavior={behav}]{vis_s}")
        print()


def _show_error_window(screen, font, message):
    """Écran d'erreur plein écran (fond rouge). Retourne après une
    interaction (touche, clic ou fermeture)."""
    screen.fill((90, 20, 20))
    y = 40
    for line in message.splitlines():
        surf = font.render(line, True, (255, 255, 255))
        screen.blit(surf, (40, y))
        y += 32
    pygame.display.flip()


async def _await_input(screen):
    """Attend une interaction (touche / clic / fermeture)."""
    running = True
    while running:
        for event in pygame.event.get():
            if event.type in (pygame.QUIT, pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                running = False
        await asyncio.sleep(0)


async def select_adventure(screen, font):
    """Menu de sélection des aventures (desktop).

    Retourne le ``Path`` du fichier JSON choisi, ou ``None`` pour quitter.
    Navigation : flèches ↑/↓ | Entrée : lancer | Échap : quitter.
    """
    small = _make_font(16)
    entries = _list_adventures(ADVENTURES_DIR)
    if not entries:
        print("Aucune aventure trouvée dans", ADVENTURES_DIR, "— sortie.",
              flush=True)
        return None

    selected = 0
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_UP:
                    selected = (selected - 1) % len(entries)
                elif event.key == pygame.K_DOWN:
                    selected = (selected + 1) % len(entries)
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    return entries[selected][0]

        screen.fill((30, 30, 40))
        title_surf = font.render("Choisir une aventure", True,
                                 (240, 240, 240))
        screen.blit(title_surf, (40, 70))
        sub_surf = small.render(
            "Flèches : naviguer | Entrée : lancer | Échap : quitter",
            True,
            (150, 150, 160),
        )
        screen.blit(sub_surf, (40, 120))
        y = 170
        for i, (path, title) in enumerate(entries):
            color = (255, 220, 100) if i == selected else (160, 160, 170)
            surf = font.render(f"{i + 1}. {title}", True, color)
            screen.blit(surf, (40, y))
            y += 46
        pygame.display.flip()
        await asyncio.sleep(0)

    return None


async def main():
    args = _build_parser().parse_args()

    # Mode debug depuis la page web : ouvrir la page avec le paramètre
    # URL ``?debug`` (ou ``?debug=1``) active le debug overlay
    # (masque de collision, boîtes d'interaction, positions joueur/NPC,
    #  chemins NPC et A* du monstre). Sur le web, ``sys.argv`` est
    # contrôlé par le runtime ; on lit la requête de l'URL à la place
    # de la ligne de commande.
    if _is_web() and not args.debug:
        search = ""
        try:
            import sys as _sys

            # Le runtime web expose le module de plateforme (window,
            # document) sous ``__EMSCRIPTEN__`` ; on retombe sur
            # ``platform`` si celui-ci est déjà importé.
            mod = (
                _sys.modules.get("__EMSCRIPTEN__")
                or _sys.modules.get("platform")
            )
            if mod is None:
                try:
                    import platform as _pbag

                    mod = _pbag
                except Exception:
                    mod = None
            loc = getattr(getattr(mod, "window", None), "location", None)
            if loc is not None:
                search = str(loc.search)
            if "debug" in search:
                args.debug = True
                print("Mode debug activé via l'URL (?debug).", flush=True)
        except Exception:
            pass

    if args.list:
        if args.adv is not None:
            _print_adventure_summary(Path(str(args.adv)))
        else:
            for path, title in _list_adventures(ADVENTURES_DIR):
                _print_adventure_summary(path)
                print()
        return

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
    font = _make_font(18)

    # --- Sélection de l'aventure -------------------------------------------
    if args.adv is not None:
        config_path = Path(str(args.adv))
        print(f"Chargement de l'aventure : {config_path}", flush=True)
    elif _is_web():
        config_path = ADVENTURES_DIR / f"{DEFAULT_ADVENTURE}.json"
        print(f"Mode web : aventure par défaut = "
              f"{config_path.name}", flush=True)
    else:
        config_path = await select_adventure(screen, font)
        if config_path is None:
            print("Aventure annulée, sortie.", flush=True)
            return
        config_path = Path(config_path)

    # --- Chargement de l'aventure (avec affichage d'erreur visible) ---
    try:
        characters, maps, meta = load_adventure(config_path)
        adventure = load_adventure_logic(config_path.stem)
    except Exception as error:
        console_msg = (
            f"Erreur : impossible de charger l'aventure "
            f"{config_path} — {type(error).__name__} : {error}"
        )
        print(console_msg, file=sys.stderr, flush=True)
        message = (
            "ERREUR : impossible de charger l'aventure.\n"
            f"fichier : {config_path}\n"
            f"raison  : {type(error).__name__} : {error}\n"
            "(Appuyez sur une touche pour quitter.)"
        )
        _show_error_window(screen, font, message)
        await _await_input(screen)
        return
    pygame.display.set_caption(meta.get("window_title", WINDOW_TITLE))

    if not characters:
        print(
            f"Erreur : l'aventure {config_path} ne contient aucun "
            f"personnage.",
            file=sys.stderr,
            flush=True,
        )
        _show_error_window(
            screen,
            font,
            (
                "ERREUR : l'aventure chargée ne contient aucun personnage.\n"
                f"fichier : {config_path}\n"
                "(Appuyez sur une touche pour quitter.)"
            ),
        )
        await _await_input(screen)
        return
    if not maps:
        print(
            f"Erreur : l'aventure {config_path} ne contient aucune carte.",
            file=sys.stderr,
            flush=True,
        )
        _show_error_window(
            screen,
            font,
            (
                "ERREUR : l'aventure chargée ne contient aucune carte.\n"
                f"fichier : {config_path}\n"
                "(Appuyez sur une touche pour quitter.)"
            ),
        )
        await _await_input(screen)
        return

    quest = meta.get("quest")

    game_surface = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
    try:
        game = Game(
            game_surface,
            font,
            characters,
            maps,
            collisions_enabled=COLLISIONS_ENABLED_DEFAULT,
            debug=args.debug,
            save_path=args.save,
            quest=quest,
            adventure=adventure,
            mobile=_is_web(),
        )
    except Exception as error:
        console_msg = (
            f"Erreur : impossible d'initialiser le jeu — "
            f"{type(error).__name__} : {error}"
        )
        print(console_msg, file=sys.stderr, flush=True)
        message = (
            "ERREUR : impossible d'initialiser le jeu.\n"
            f"raison  : {type(error).__name__} : {error}\n"
            "(Appuyez sur une touche pour quitter.)"
        )
        _show_error_window(screen, font, message)
        await _await_input(screen)
        return

    print("Jeu initialisé, lancement...", flush=True)

    if args.load:
        if not game.load(args.load):
            print("Avertissement : sauvegarde ignorée, partie fraîche.")

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
        await asyncio.sleep(0)

    print("Fin de la partie.", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
