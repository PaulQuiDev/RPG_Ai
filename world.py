
import pygame

from settings import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    COLLISION_RADIUS,
    MAPS,
)
from game_map import GameMap


class World:
    """Gère les cartes du jeu et les déplacements entre elles."""

    EXIT_MARGIN = 8
    SAFE_MARGIN = 10

    def __init__(self, maps):
        if not maps:
            raise ValueError("Aucune carte définie.")

        self.maps = maps
        self.map_index = 0
        self.game_map = self._load_map(0)
        # --- État global (quêtes) ---
        # Drapeaux booléens nommés, partagés entre toutes les cartes.
        self.flags = {}
        # Conditions nommées : nom -> fn(world, player) -> bool.
        # Évaluées au moment où une transition/interaction les demande.
        self.conditions = {}

    @property
    def current_map_data(self):
        return self.maps[self.map_index]

    def _load_map(self, index):
        """Chargement d'une carte (fonctionne hors jeu, pour le test)."""
        data = self.maps[index]

        return GameMap(
            data["background"],
            data["mask"],
            data.get("foreground"),
            data.get("perspective"),
            data.get("interactions"),
            data.get("npcs"),
        )

    def find_spawn(self, game_map, radius=COLLISION_RADIUS):
        """Cherche une position accessible, en privilégiant le centre."""
        center_x = WINDOW_WIDTH // 2
        center_y = WINDOW_HEIGHT // 2

        if game_map.can_stand_at(center_x, center_y, radius):
            return center_x, center_y

        # Recherche autour du centre, par cercles carrés successifs.
        for distance in range(10, max(WINDOW_WIDTH, WINDOW_HEIGHT), 10):
            candidates = []

            for x in range(center_x - distance, center_x + distance + 1, 10):
                candidates.append((x, center_y - distance))
                candidates.append((x, center_y + distance))

            for y in range(center_y - distance + 10,
                            center_y + distance, 10):
                candidates.append((center_x - distance, y))
                candidates.append((center_x + distance, y))

            for x, y in candidates:
                if (
                    0 <= x < WINDOW_WIDTH
                    and 0 <= y < WINDOW_HEIGHT
                    and game_map.can_stand_at(x, y, radius)
                ):
                    return x, y

        raise RuntimeError(
            f"Aucune position accessible sur {self.maps[self.map_index]['name']}."
        )

    # --- API d'état global (quêtes) : drapeaux + conditions ---
    def flag_set(self, name, value=True):
        """Déclare un drapeau global du jeu (état de la quête)."""
        self.flags[str(name)] = bool(value)

    def flag_get(self, name, default=False):
        """Valeur d'un drapeau (default si absent)."""
        return self.flags.get(str(name), default)

    def flag_reset(self, name=None):
        """Efface un drapeau (ou tous, si name est None)."""
        if name is None:
            self.flags.clear()
        else:
            self.flags.pop(str(name), None)

    def register_condition(self, name, fn):
        """Nomme une condition `fn(world, player) -> bool`."""
        self.conditions[str(name)] = fn

    def flag_condition(self, name, value=True):
        """Condition « le drapeau `name` vaut `value` » (retourne une fn).

        Un drapeau non défini est **non satisfait** (retourne False) —
        fail-closed, cohérent avec une condition inconnue.
        """
        def fn(world, player):
            if name not in world.flags:
                return False
            return world.flags[name] == value
        return fn

    def condition_holds(self, names, player=None):
        """Vrai si TOUTES les conditions de `names` sont remplies.

        `names` : None ou liste vide => True (pas de précondition).
        Une condition inconnue ou qui lève une erreur est **bloquante**
        (retourne False) et signalée dans la console (fail-closed).
        """
        if not names:
            return True
        for name in names:
            if not self._one_condition(name, player):
                return False
        return True

    def _one_condition(self, name, player):
        """Évalue une seule condition ; inconnue/erroneuse => False (bloquant)."""
        fn = self.conditions.get(str(name))
        if fn is None:
            print(f"Condition inconnue « {name} » — action/transition bloquée.")
            return False
        try:
            return bool(fn(self, player))
        except Exception as error:  # noqa: BLE001
            print(f"Condition « {name} » a lev\u00e9 : {error}")
            return False

    def change_map(self, destination_index, player, spawn=None):
        """Change de carte. Si aucun point d'arrivée n'est donné,
        cherche une position accessible.
        """
        try:
            new_map = self._load_map(destination_index)

            if spawn is None:
                spawn = self.find_spawn(
                    new_map,
                    getattr(player, "collision_radius", COLLISION_RADIUS),
                )

            spawn_x, spawn_y = spawn
            radius = getattr(
                player, "collision_radius", COLLISION_RADIUS
            )

            if not new_map.can_stand_at(spawn_x, spawn_y, radius):
                print(
                    f"Point d'arrivée bloqué : {self.maps[destination_index]['name']} "
                    f"({spawn_x}, {spawn_y}) — recherche d'un point alternatif."
                )
                # Fallback : point praticable le plus proche (gère les cas où
                # le spawn collé à un NPC serait bloqué).
                spawn_x, spawn_y = self.find_spawn(new_map, radius)
                if not new_map.can_stand_at(spawn_x, spawn_y, radius):
                    print(
                        f"Point d'arrivée inaccessible : "
                        f"{self.maps[destination_index]['name']} "
                        f"({spawn_x}, {spawn_y})"
                    )
                    return False

        except (RuntimeError, ValueError, KeyError, IndexError) as error:
            print(f"Changement de carte impossible : {error}")
            return False

        # Ne modifie l'état du monde qu'une fois la carte chargée.
        self.game_map = new_map
        self.map_index = destination_index
        player.x = float(spawn_x)
        player.y = float(spawn_y)

        print(f"Carte chargée : {self.current_map_data['name']}")
        return True

    def check_transition(self, player):
        """Détecte une sortie et effectue la transition si nécessaire."""
        x, y = player.x, player.y
        margin = self.EXIT_MARGIN

        if x >= WINDOW_WIDTH - margin:
            side = "right"
        elif x <= margin:
            side = "left"
        elif y <= margin:
            side = "top"
        elif y >= WINDOW_HEIGHT - margin:
            side = "bottom"
        else:
            return False

        exit_data = self.current_map_data.get("exits", {}).get(side)

        if exit_data is None:
            # Bord non connecté : on empêche de sortir de l'écran.
            player.x = max(
                self.SAFE_MARGIN,
                min(WINDOW_WIDTH - self.SAFE_MARGIN, player.x),
            )
            player.y = max(
                self.SAFE_MARGIN,
                min(WINDOW_HEIGHT - self.SAFE_MARGIN, player.y),
            )
            return False

        destination_name = exit_data["map"]

        destination_index = next(
            (
                i for i, data in enumerate(self.maps)
                if data["name"] == destination_name
            ),
            None,
        )

        if destination_index is None:
            print(f"Carte inconnue : {destination_name}")
            return False

        # Préconditions (quêtes) : sans elles, la transition est bloquée.
        # Le joueur reste au bord (la collision l'y maintient) ; on ne
        # change ni de carte ni de position — la collision le retient.
        if not self.condition_holds(exit_data.get("requires"), player):
            print(f"Transition bloquée ({side}) : conditions non remplies.")
            return False

        old_name = self.current_map_data["name"]

        changed = self.change_map(
            destination_index,
            player,
            exit_data.get("spawn"),
        )

        if changed:
            print(f"Transition : {old_name} -> {destination_name} ({side})")

        return changed

    def next_map(self, player):
        """Change manuellement vers la carte suivante (raccourci M)."""
        destination_index = (self.map_index + 1) % len(self.maps)
        return self.change_map(destination_index, player)
