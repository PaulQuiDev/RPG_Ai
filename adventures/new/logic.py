"""Squelette de logique d'aventure (modèle) pour ``new``.

Copiez ce fichier dans une nouvelle aventure et complétez les hooks pour
décrire SA logique. Le moteur (``game.Game`` + modules du projet) fournit
TOUTES les fonctionnalités (monstre, bougies, transformation, dévoration,
fuite, redirection). Ici on **n'orchestre que les briques** : on ne
développe PAS de nouvelle fonctionnalité.

Hooks disponibles :
- ``on_map_change(game, prev_name, curr_name)`` : réinitialisation de l'état
  de quête + setup du monstre à chaque changement de carte.
- ``on_tick(game, dt)`` : orchestration par frame de la quête (monstre,
  transformation, dévoration des PNJ, fuite des PNJ du village, ...).
- ``on_interact(game, action, focus)`` : consommer une interaction spécifique
  (renvoyer ``True`` = le moteur ne résout plus l'action générique).
- ``redirect_dest(game, destination_name, player)`` : rediriger une transition
  (ex. ``boss_combat_map`` ``→`` ``post_combat_map`` après victoire).

Les valeurs (cartes, vitesses, bougies, flags, ...) proviennent de
``game.quest`` (``QuestConfig`` chargée du JSON ``adventures/new.json``).
"""
from adventure import Adventure as AdventureBase


class Adventure(AdventureBase):
    """Logique de l'aventure ``new`` (à personnaliser)."""

    def on_map_change(self, game, prev_name, curr_name):
        # À compléter : réinitialiser l'état de quête à chaque carte.
        # Exemple (copié depuis demo-test/forest-quest) :
        # game._monster = None
        # game._candle_lit = set()
        # game._candle_lit_count = 0
        # game._npc_flee_applied = False
        # if (
        #     curr_name == game.quest.boss_combat_map
        #     and not game.world.flag_get("monster_defeated")
        # ):
        #     game._setup_monster()
        pass

    def on_tick(self, game, dt):
        # À compléter : orchestration de la quête.
        # Exemple (monstre qui poursuit le joueur + transformation +
        # dévoration des PNJ + fuite des PNJ du village) :
        # if (
        #     game._monster is not None
        #     and game.world.current_map_data.get("name")
        #     == game.quest.boss_combat_map
        # ):
        #     if game._monster.move_towards(
        #         game.player.x, game.player.y, dt,
        #         game.game_map, game.player,
        #     ):
        #         game._reset_combat()
        # if game.world.flag_get("monster2_active"):
        #     game._apply_player_monster2()
        # else:
        #     game._reset_player_monster2()
        # if game.world.flag_get("monster2_active"):
        #     for npc in game.game_map.npcs_in_contact(game.player):
        #         game._eat_npc(npc)
        # if (
        #     game.world.current_map_data.get("name") == "Village"
        #     and not game._npc_flee_applied
        #     and game.world.flag_get("monster2_active")
        # ):
        #     game._apply_village_npc_flee()
        pass

    def redirect_dest(self, game, destination_name, player):
        # À compléter : redirection post-combat.
        # Exemple :
        # if not game.world.flag_get("monster_defeated"):
        #     return None
        # if destination_name != game.quest.boss_combat_map:
        #     return None
        # return game.quest.post_combat_map
        return None
