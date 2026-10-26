"""Objet `Game` : encapsule le monde, le joueur, les cartes, les interactions
et la machine à états (RUNNING / PAUSED / QUIT). Découplage `update(dt)` /
`render(screen)` ; le point d'entrée (`main.py`) ne fait que piloter la
boucle.

L'état est extensible : ajouter une entrée dans `GameState` + un handler
clé est suffisant pour introduire un état (menu, etc.).
"""
import pygame

from settings import COLLISIONS_ENABLED_DEFAULT
from behaviors import BEHAVIORS, go_to_map
from player import Player
from world import World


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

        # Le monde : injecté (test) ou construit depuis `maps`.
        self.world = world if world is not None else World(maps)
        self.game_map = self.world.game_map
        spawn_x, spawn_y = self.world.find_spawn(self.game_map)
        self.player = Player(spawn_x, spawn_y, characters[character_index])

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

        # Préconditions (quêtes) : sans elles, l'action est bloquée.
        if not self.world.condition_holds(
            interaction.get("requires"), self.player
        ):
            print("Action indisponible : conditions non remplies.")
            return

        applied = False
        if focus.get("action") is not None:
            beh = BEHAVIORS.get(focus["action"])
            if beh is None:
                print(f"Comportement inconnu : {focus['action']}")
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

        # Personnage (NPC) de la carte : déplacement (patrouille).
        self.game_map.update_npcs(dt, self.player)

        self.player.update(
            dt, keys, self.game_map, self.collisions_enabled
        )

        self.world.check_transition(self.player)
        self.game_map = self.world.game_map

        # Interaction des NPC au contact : message + comportement custom.
        for npc in self.game_map.npcs_in_contact(self.player):
            if npc.can_interact():
                if npc.interact(self.player, self.world, self.game_map):
                    self.game_map = self.world.game_map

    # -- Rendu -----------------------------------------------------------------

    def render(self):
        """Affichage du monde, du joueur, du HUD et des overlays."""
        self._draw_world()
        self._draw_hud()
        if self.state == GameState.PAUSED:
            self._draw_pause_overlay()
        pygame.display.flip()

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
