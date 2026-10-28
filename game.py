"""Objet `Game` : encapsule le monde, le joueur, les cartes, les interactions
et la machine à états (RUNNING / PAUSED / QUIT). Découplage `update(dt)` /
`render(screen)` ; le point d'entrée (`main.py`) ne fait que piloter la
boucle.

L'état est extensible : ajouter une entrée dans `GameState` + un handler
clé est suffisant pour introduire un état (menu, etc.).
"""
import math
import pygame

from settings import BASE_DIR, COLLISIONS_ENABLED_DEFAULT
from behaviors import BEHAVIORS, go_to_map
from player import Player
from world import World
from monster import Monster


# --- Quête du monstre (Boss Combat) ------------------------------------------
# Nom des cartes du combat (settings.MAPS).
BOSS_COMBAT_MAP = "Boss Combat"
POST_COMBAT_MAP = "Post Combat"
# Point de départ du monstre (monster.png) dans la pièce de combat.
MONSTER_START = (860, 540)
# Vitesse du monstre (px/s) — lente, pour laisser le joueur allumer les 5 bougies.
MONSTER_SPEED = 55.0
# Vitesse du monstre transformé (monster2.png) — plus rapide.
MONSTER_SPEED2 = 180.0


class GameState:
    """États de la machine à états."""

    RUNNING = "running"
    PAUSED = "paused"
    QUIT = "quit"


class Game:
    """Moteur de jeu : monde + joueur + cartes + interactions + HUD."""

    def __init__(
        self,
        screen,
        font,
        characters,
        maps,
        collisions_enabled=COLLISIONS_ENABLED_DEFAULT,
        character_index=0,
        world=None,
        debug=False,
    ):
        """
        Args:
            screen: Surface pygame de jeu.
            font: Font pygame pour le HUD.
            characters: Liste des dict de personnages (settings.CHARACTERS).
            maps: Liste des dict de cartes (settings.MAPS).
            collisions_enabled: Brouille des collisions (E).
            character_index: Index du personnage initial.
            world: Optionnel — monde déjà construit (injection de dépendance,
                test). Si `None`, on en construit un à partir de `maps`.
        """
        self.screen = screen
        self.font = font
        self.characters = characters
        self.character_index = character_index
        self.collisions_enabled = collisions_enabled
        self.state = GameState.RUNNING

        # Debug : overlay (--debug) + position dans la console.
        self.debug = debug
        self._debug_mask = None
        self._debug_mask_map = None
        self._last_console_print = 0

        # Le monde : injecté (test) ou construit depuis `maps`.
        self.world = world if world is not None else World(maps)
        self.game_map = self.world.game_map
        spawn_x, spawn_y = self.world.find_spawn(self.game_map)
        self.player = Player(spawn_x, spawn_y, characters[character_index])

        # --- État de la quête (monstre / bougies / transformation) ---
        self._monster = None                  # Monster vivant sur la carte de combat
        self._candle_lit = set()             # centres (x, y) des bougies allumées
        self._candle_lit_count = 0           # nombre de bougies allumées
        self._monster2_transformed = False   # transformation du village appliquée ?
        self._prev_map_name = self.world.current_map_data.get("name")
        self._reset_message_until = 0.0      # timestamp (ms) du prochain reset message

        # Conditions globales (quêtes) : drapeaux -> conditions.
        self.world.register_condition(
            "monster_defeated",
            lambda w, p: w.flags.get("monster_defeated", False),
        )
        self.world.register_condition(
            "monster2_active",
            lambda w, p: w.flags.get("monster2_active", False),
        )

    # -- Propriétés publics ---------------------------------------------------

    @property
    def should_quit(self):
        """La boucle de jeu doit-elle s'arrêter ?"""
        return self.state == GameState.QUIT

    # -- Événements (machine à états) -----------------------------------------

    def handle_events(self):
        """Traitement des événements pygame ; retourne l'état courant."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.state = GameState.QUIT
            elif event.type == pygame.KEYDOWN:
                handler = self._key_handler_for(self.state)
                if handler is not None:
                    handler(event.key)
        return self.state

    def _key_handler_for(self, state):
        """Handler de clés selon l'état (extensible)."""
        if state == GameState.RUNNING:
            return self._handle_running_key
        if state == GameState.PAUSED:
            return self._handle_paused_key
        return None

    def _handle_running_key(self, key):
        if key == pygame.K_ESCAPE:
            self.state = GameState.PAUSED
        elif key == pygame.K_e:
            self.collisions_enabled = not self.collisions_enabled
        elif key == pygame.K_p:
            self._change_character()
        elif key == pygame.K_m:
            self.world.next_map(self.player)
            self.game_map = self.world.game_map
        elif key == pygame.K_i:
            self._interact()

    def _handle_paused_key(self, key):
        if key == pygame.K_ESCAPE:
            self.state = GameState.RUNNING

    def _change_character(self):
        """Changer de personnage en conservant la position."""
        next_index = (self.character_index + 1) % len(self.characters)
        character_data = self.characters[next_index]
        try:
            self.player = Player(
                self.player.x, self.player.y, character_data
            )
            self.character_index = next_index
        except (RuntimeError, ValueError) as error:
            print(
                "Changement de personnage impossible : " f"{error}"
            )

    def _interact(self):
        """Interagir avec l'objet focalisé (le plus proche à portée)."""
        focus = self.game_map.get_focused_object(self.player)
        if focus is None:
            print("Aucun objet interactif à portée (I).")
            return

        interaction = focus.get("interaction") or {}
        action = focus.get("action")

        # Préconditions (quêtes) : sans elles, l'action est bloquée.
        if not self.world.condition_holds(
            interaction.get("requires"), self.player
        ):
            print("Action indisponible : conditions non remplies.")
            return

        # Comportements "spéciaux" gérés par la Game (état des bougies et du
        # monstre) : pas de clé dans BEHAVIORS.
        if action == "light_candle":
            self._light_candle(focus)
            return
        if action == "transform_monster":
            flag_name = interaction.get("flag", "monster2_active")
            flag_value = interaction.get("flag_value", True)
            self.world.flag_set(flag_name, flag_value)
            print(
                f"Trône : monstre transformé "
                f"(flag {flag_name} = {flag_value})."
            )
            return

        # Déclencher le comportement (go_forest, cycle_map_seg, ...) si défini.
        applied = False
        if action is not None:
            beh = BEHAVIORS.get(action)
            if beh is None:
                print(f"Comportement inconnu : {action}")
                return
            applied = bool(beh(self.player, self.world, self.game_map))
        elif focus.get("dest") is not None:
            applied = bool(
                go_to_map(self.player, self.world, focus["dest"])
            )

        if not applied:
            return

        self.game_map = self.world.game_map

        # Drapeau global à poser après la réussite (déclaratif).
        flag_name = interaction.get("flag")
        if flag_name is not None:
            self.world.flag_set(
                flag_name, interaction.get("flag_value", True)
            )

    # -- Mise à jour ------------------------------------------------------------

    def update(self, dt):
        """Mise à jour logique (uniquement en état RUNNING)."""
        if self.state != GameState.RUNNING:
            return
        keys = pygame.key.get_pressed()
        self.game_map = self.world.game_map

        # Détection de changement de carte : on réinitialise l'état
        # dépendant de la carte (monstre, bougies, transformation).
        self._on_map_change()

        # Personnage (NPC) de la carte : déplacement (patrouille / fuite).
        self.game_map.update_npcs(dt, self.player)

        self.player.update(
            dt, keys, self.game_map, self.collisions_enabled
        )

        self.world.check_transition(self.player)
        self.game_map = self.world.game_map

        # Quête du monstre : si combat en cours et monstre vivant.
        if (
            self._monster is not None
            and self.world.current_map_data.get("name") == BOSS_COMBAT_MAP
        ):
            if self._monster.move_towards(
                self.player.x,
                self.player.y,
                dt,
                self.game_map,
                self.player,
            ):
                self._reset_combat()

        # Post-victoire : au village, transformer le monstre + fuite.
        if (
            self.world.current_map_data.get("name") == "Village"
            and self._monster2_transformed is False
            and self.world.flag_get("monster2_active")
        ):
            self._apply_village_monster2()

        # Interaction des NPC au contact : message + comportement custom.
        for npc in self.game_map.npcs_in_contact(self.player):
            if npc.can_interact():
                if npc.interact(self.player, self.world, self.game_map):
                    self.game_map = self.world.game_map

        # Debug : position du joueur + objet focalisé dans la console
        # (tous les 500 ms, pour ne pas noyer la sortie).
        if self.debug:
            now = pygame.time.get_ticks()
            if now - self._last_console_print > 500:
                self._last_console_print = now
                focus = self.game_map.get_focused_object(self.player)
                target = (
                    focus.get("action")
                    or (focus.get("interaction") or {}).get("label", "")
                ) if focus else ""
                print(
                    f"[debug] {self.player.name} "
                    f"pos=({round(self.player.x)}, {round(self.player.y)}) "
                    f"focus={target or '-'}"
                )

    # -- Rendu -----------------------------------------------------------------

    def render(self):
        """Affichage du monde, du joueur, du HUD et des overlays."""
        self._draw_world()
        self._draw_monster()
        self._draw_candle_state()
        self._draw_combat_hud()
        self._draw_hud()
        if self.debug:
            self._draw_debug_overlay()
        if self.state == GameState.PAUSED:
            self._draw_pause_overlay()
        pygame.display.flip()

    def _draw_monster(self):
        """Affiche le monstre (si vivant et sur la carte de combat)."""
        if (
            self._monster is None
            or self.world.current_map_data.get("name") != BOSS_COMBAT_MAP
        ):
            return
        self._monster.draw(self.screen, self.game_map)

    def _draw_world(self):
        """Fond + FG derrière, joueur, FG devant + couche interaction."""
        self.game_map.draw(
            self.screen, self.player, self.collisions_enabled
        )
        self.player.draw(self.screen, self.game_map)
        self.game_map.draw_top(
            self.screen,
            self.player,
            pygame.time.get_ticks(),
            self.collisions_enabled,
        )

    def _draw_hud(self):
        """Affichage des informations (top-left)."""
        character_name = self.characters[self.character_index]["name"]
        map_name = self.world.current_map_data["name"]
        focus = self.game_map.get_focused_object(self.player)

        if focus is not None:
            target = focus.get("action") or focus.get("dest")
            focus_line = f"  -> agir (I) sur : {target}"
        else:
            focus_line = None

        # Premier NPC au contact du joueur (pour l'information).
        npc_in_contact = None
        for npc in self.game_map.npcs_in_contact(self.player):
            npc_in_contact = npc
            break

        info = [
            f"Personnage : {character_name} (P pour changer)",
            f"Carte : {map_name} (M pour changer)",
            "Flèches : déplacer | E : collisions | I : interagir",
            (
                "Collisions : "
                f"{'ACTIVÉES' if self.collisions_enabled else 'DÉSACTIVÉES'}"
            ),
            f"Personnages : {len(self.game_map.npcs)} sur cette carte",
            "Objets bleus : interactifs (I : agir sur le plus proche)",
            "Prémiplan (FG) : devant le joueur derrière un élément",
            "Échap : pause",
        ]

        if npc_in_contact is not None:
            if npc_in_contact.can_interact():
                npc_line = (
                    f"  -> contact avec : {npc_in_contact.name} "
                    "(message affiché automatiquement)"
                )
            else:
                npc_line = (
                    f"  -> en contact : {npc_in_contact.name} "
                    f"(cooldown {npc_in_contact.interact_cooldown:.1f}s)"
                )
            info.insert(len(info) - 1, npc_line)

        if focus_line is not None:
            info.insert(len(info) - 1, focus_line)

        for i, line in enumerate(info):
            label = self.font.render(line, True, (255, 255, 255))
            label_bg = pygame.Surface(
                (label.get_width() + 12, label.get_height() + 8),
                pygame.SRCALPHA,
            )
            label_bg.fill((0, 0, 0, 150))
            self.screen.blit(label_bg, (8, 8 + i * 30))
            self.screen.blit(label, (14, 12 + i * 30))

    def _draw_pause_overlay(self):
        """Voile sombre + texte centre en pause."""
        overlay = pygame.Surface(
            self.screen.get_size(), pygame.SRCALPHA
        )
        overlay.fill((0, 0, 0, 140))
        self.screen.blit(overlay, (0, 0))
        text = self.font.render(
            "PAUSE — Échap pour reprendre", True, (255, 255, 255)
        )
        w, h = self.screen.get_size()
        self.screen.blit(text, ((w - text.get_width()) // 2, (h - text.get_height()) // 2))

    # -- Debug (--debug) ------------------------------------------------------

    def _build_debug_mask(self, gmap):
        """Surface de debug du masque de collision : vert = praticable,
        rouge = bloqué (alpha => transparence sur l'écran)."""
        surf = pygame.Surface((gmap.width, gmap.height), pygame.SRCALPHA)
        for y in range(gmap.height):
            for x in range(gmap.width):
                c = gmap.collision_mask.get_at((x, y))
                if c.g > c.r and c.g > c.b:
                    surf.set_at((x, y), (90, 255, 140, 150))
                else:
                    surf.set_at((x, y), (255, 110, 110, 150))
        return surf

    def _draw_debug_overlay(self):
        """Overlay de debug (flag --debug) : carte de collision en transparence,
        boîtes d'interaction (itboxes), position du joueur + marqueurs des NPCs.
        Le texte de position est en bas à gauche (le HUD est en haut à gauche)."""
        screen = self.screen
        gmap = self.game_map
        player = self.player

        # Masque de collision (transparence), recomposé si la carte change.
        if self._debug_mask is None or self._debug_mask_map is not gmap:
            self._debug_mask = self._build_debug_mask(gmap)
            self._debug_mask_map = gmap
        screen.blit(self._debug_mask, (0, 0))

        # Boîtes d'interaction (itboxes) + nom de l'action.
        for obj in gmap.interact_objects:
            box = obj["box"]
            pygame.draw.rect(screen, (255, 255, 0), box, 2)
            action = (
                obj.get("action")
                or (obj.get("interaction") or {}).get("label", "")
                or ""
            )
            if action:
                txt = self.font.render(str(action), True, (255, 255, 0))
                screen.blit(txt, (box.centerx - txt.get_width() // 2,
                                 box.bottom + 4))

        # Position du joueur : cercle (rayon de collision) + texte bas-gauche.
        if player is not None:
            px, py = int(player.x), int(player.y)
            r = max(player.collision_radius, 4) + 3
            pygame.draw.circle(screen, (0, 255, 255), (px, py), r, 2)
            w, h = self.screen.get_size()
            pos_txt = self.font.render(
                f"pos : ({round(player.x)}, {round(player.y)})",
                True, (0, 255, 255)
            )
            screen.blit(pos_txt, (8, h - 24))

        # NPCs : point + rayon de collision + nom + position.
        for npc in gmap.npcs:
            nx, ny = int(npc.x), int(npc.y)
            pygame.draw.circle(screen, (255, 120, 120), (nx, ny),
                               max(npc.collision_radius, 3), 1)
            n_txt = self.font.render(
                f"{npc.name} ({round(npc.x)},{round(npc.y)})",
                True, (255, 120, 120)
            )
            screen.blit(n_txt, (nx + 6, ny - 24))

    # -- Quête du monstre (Boss Combat) -------------------------------------

    def _on_map_change(self):
        """Appelé à chaque changement de carte (détection dans update).
        Réinitialise l'état dépendant de la carte (monstre, bougies,
        transformation) et crée le monstre sur la carte de combat."""
        prev = getattr(self, "_prev_map_name", None)
        curr = self.world.current_map_data.get("name")
        if curr != prev:
            self._prev_map_name = curr
            self._monster = None
            self._candle_lit = set()
            self._candle_lit_count = 0
            self._monster2_transformed = False
            if curr == BOSS_COMBAT_MAP:
                self._setup_monster()

    def _get_monster_spawn(self):
        """Retourne une position walkable proche de MONSTER_START
        pour le monstre (collision_radius=12)."""
        x, y = MONSTER_START
        if not self.game_map.can_stand_at(x, y, 12):
            nx, ny = self.game_map.find_nearest_walkable(x, y, 12)
            print(f"Spawn monstre ajusté : ({x},{y}) -> ({nx},{ny})")
            return nx, ny
        return x, y

    def _setup_monster(self):
        """Crée le monstre (monster.png) au spawn de la carte de combat."""
        x, y = self._get_monster_spawn()
        self._monster = Monster(
            float(x),
            float(y),
            speed=MONSTER_SPEED,
        )

    def _reset_combat(self):
        """Touché par le monstre : remise en scène (monstre + bougies à zéro).
        Le joueur retourne au centre de la carte, le monstre à son spawn."""
        # Repositionner le joueur au centre de la carte (praticable).
        nearest = self.game_map.find_nearest_walkable(
            500, 360, self.player.collision_radius
        )
        if nearest:
            self.player.x, self.player.y = nearest
        # Remettre le monstre à sa position spawn (walkable).
        if self._monster is not None:
            sx, sy = self._get_monster_spawn()
            self._monster.x, self._monster.y = float(sx), float(sy)
        self._candle_lit = set()
        self._candle_lit_count = 0
        self._reset_message_until = pygame.time.get_ticks() + 2500
        print(
            "Tu as été touché ! Remise en scène : monstre et bougies à zéro."
        )

    def _light_candle(self, focus):
        """Allume une bougie (centre de l'objet focalisé). Les 5 bougies
        allumées -> le monstre meurt et on bascule sur la carte Post Combat."""
        cx = round(focus["box"].centerx)
        cy = round(focus["box"].centery)
        key = (cx, cy)
        if key in self._candle_lit:
            remaining = 5 - self._candle_lit_count
            print(
                f"Bougie déjà allumée (allumées : {self._candle_lit_count}/5). "
                f"{remaining} restante(s)."
            )
            return
        self._candle_lit.add(key)
        self._candle_lit_count += 1
        print(f"Bougie allumée ({cx},{cy}) — {self._candle_lit_count}/5.")
        if self._candle_lit_count >= 5:
            self._defeat_monster()

    def _defeat_monster(self):
        """Le monstre meurt : on le retire, on pose le drapeau
        monster_defeated et on bascule sur la carte Post Combat."""
        self._monster = None
        self.world.flag_set("monster_defeated", True)
        world = self.world
        target_index = None
        for i, md in enumerate(world.maps):
            if md["name"] == POST_COMBAT_MAP:
                target_index = i
                break
        if target_index is None:
            print("Carte 'Post Combat' introuvable.")
            return
        world.change_map(target_index, self.player, (500, 360))
        self.game_map = world.game_map
        self._on_map_change()
        print("Monstre vaincu ! Passage à la carte 'Post Combat'.")

    def _apply_village_monster2(self):
        """Au village, après le trône (flag monster2_active) : transforme
        le monstre du village en monster2.png et fait fuir tous les PNJ
        du village (sauf le monstre, qui reste)."""
        village_data = self.world.current_map_data.get("npcs", [])
        for data in village_data:
            npc = None
            for existing in self.game_map.npcs:
                if existing.name == data["name"]:
                    npc = existing
                    break
            if npc is None:
                continue
            # Le "Monstre" du village : on transforme son sprite en
            # monster2.png (il reste, c'est LUI le monstre).
            if data["name"] == "Monstre":
                try:
                    npc.set_sprite(str(BASE_DIR / "asset/carater/monster2.png"))
                except RuntimeError as error:
                    print(f"Transformation du monstre impossible : {error}")
                continue
            # Tous les autres PNJ du village : ils fuient.
            npc.behavior = "flee"
            if not hasattr(npc, "speed") or npc.speed is None or npc.speed < 20:
                npc.speed = 45.0
        self._monster2_transformed = True
        print(
            "Monstre transformé (monster2.png) ! Tous les PNJ du village fuient."
        )

    def _draw_candle_state(self):
        """Affiche une flamme (triangle) au-dessus de chaque bougie allumée
        (sur la couche de dessus, pour la voir au-dessus du joueur)."""
        if (
            not self._candle_lit
            or self.world.current_map_data.get("name") != BOSS_COMBAT_MAP
        ):
            return
        now = pygame.time.get_ticks()
        # Phase pour l'animation (flamme qui vacille).
        phase = math.sin((now / 1000.0) * 2.0)
        for (cx, cy) in self._candle_lit:
            flame = pygame.Surface((14, 22), pygame.SRCALPHA)
            flame.fill((0, 0, 0, 0))
            # Triangle jaune (flamme).
            pygame.draw.polygon(flame, (255, 200, 50), [(7, 0), (0, 22), (14, 22)])
            # Intérieur (plus clair).
            pygame.draw.polygon(flame, (255, 255, 150), [(7, 6), (3, 20), (11, 20)])
            # Légère vacillation (décalage horizontal selon phase).
            offset = int(phase * 2)
            self.screen.blit(flame, (cx - 7 + offset, cy - 24))

    def _draw_combat_hud(self):
        """Affiche l'état du combat (compteur de bougies + message reset)."""
        if self.world.current_map_data.get("name") != BOSS_COMBAT_MAP:
            return
        w, h = self.screen.get_size()
        # Compteur de bougies (haut à droite).
        count = self._candle_lit_count
        total = len(self.game_map.interact_objects)
        label = self.font.render(
            f"Bougies : {count}/{total}", True, (255, 255, 150)
        )
        label_bg = pygame.Surface(
            (label.get_width() + 12, label.get_height() + 8), pygame.SRCALPHA
        )
        label_bg.fill((0, 0, 0, 150))
        self.screen.blit(label_bg, (w - label.get_width() - 20, 8))
        self.screen.blit(label, (w - label.get_width() - 8, 12))
        # Message de reset (si applicable).
        if self._reset_message_until and pygame.time.get_ticks() < self._reset_message_until:
            reset_msg = self.font.render(
                "Remise en scène ! Retour au départ.",
                True, (255, 150, 150),
            )
            reset_bg = pygame.Surface(
                (reset_msg.get_width() + 12, reset_msg.get_height() + 8),
                pygame.SRCALPHA,
            )
            reset_bg.fill((0, 0, 0, 150))
            self.screen.blit(reset_bg, (8, 130))
            self.screen.blit(reset_msg, (14, 134))
