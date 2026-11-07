"""Logique d'aventure ``forest-quest`` : quête du monstre.

Ce fichier est la logique d'aventure (data-driven) : elle ne développe
AUCUNE nouvelle fonctionnalité, elle orchestre seulement les *briques*
exposées par le moteur (``game.Game`` + modules du projet) :

- ``game._setup_monster()`` / ``game._reset_combat()`` /
  ``game._monster.move_towards(...)``
- ``game._apply_player_monster2()`` / ``game._reset_player_monster2()``
  (transformation du joueur)
- ``game._eat_npc(npc)`` (dévoration des PNJ par le joueur-boss)
- ``game._apply_village_npc_flee()`` (fuite des PNJ du village)
- ``redirect_dest`` (redirection post-combat ``boss_combat_map``
  ``→`` ``post_combat_map``)

Toutes les valeurs (cartes, vitesses, nombres de bougies, flags de
transformation, ...) viennent de ``game.quest`` (``QuestConfig`` chargée
depuis le JSON ``forest-quest.json``). Le code Python d'aventure ne doit
pas ajouter de fonctionnalité : il ne séquence que les briques.
"""
from adventure import Adventure as AdventureBase


class Adventure(AdventureBase):
    """Quête du monstre : bougies, trône, transformation du joueur,
    dévoration des PNJ, fuite des PNJ du village, redirection post-combat.
    """

    def on_map_change(self, game, prev_name, curr_name):
        # Réinitialisation de l'état de quête à chaque changement de carte.
        game._monster = None
        game._candle_lit = set()
        game._candle_lit_count = 0
        game._npc_flee_applied = False
        # Sur la carte de combat du boss, (ré)initialiser le monstre s'il
        # n'est pas déjà vaincu.
        if (
            curr_name == game.quest.boss_combat_map
            and not game.world.flag_get("monster_defeated")
        ):
            game._setup_monster()

    def on_tick(self, game, dt):
        # --- Quête du monstre : le boss poursuit le joueur ---
        if (
            game._monster is not None
            and game.world.current_map_data.get("name")
            == game.quest.boss_combat_map
        ):
            if game._monster.move_towards(
                game.player.x,
                game.player.y,
                dt,
                game.game_map,
                game.player,
            ):
                game._reset_combat()

        # --- Transformation du joueur (monstre 2) ---
        if game.world.flag_get("monster2_active"):
            game._apply_player_monster2()
        else:
            game._reset_player_monster2()

        # --- Dévoration des PNJ par le joueur (boss) ---
        if game.world.flag_get("monster2_active"):
            for npc in game.game_map.npcs_in_contact(game.player):
                game._eat_npc(npc)

        # --- PNJ du village : fuient le joueur (boss) ---
        if (
            game.world.current_map_data.get("name") == "Village"
            and not game._npc_flee_applied
            and game.world.flag_get("monster2_active")
        ):
            game._apply_village_npc_flee()

    def redirect_dest(self, game, destination_name, player):
        # Après avoir vaincu le monstre, une transition depuis la carte de
        # combat du boss vers ``post_combat_map`` (si elle existe).
        if not game.world.flag_get("monster_defeated"):
            return None
        if destination_name != game.quest.boss_combat_map:
            return None
        post_name = game.quest.post_combat_map
        for md in game.world.maps:
            if md.get("name") == post_name:
                return post_name
        return None
