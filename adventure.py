"""Briques et orchestration des aventures (data-driven).

Architecture du moteur :

- Le **moteur** (``game.Game`` + modules du projet) fournit toutes les
  *briques* : création du monstre, bougies, transformation du joueur,
  dévoration des PNJ, fuite des PNJ du village, redirection post-combat,
  etc.
- Une **aventure** = un fichier JSON (``adventures/<nom>.json``) qui porte
  tous les sprites/actifs + hyperparamètres, **et** un fichier
  ``adventures/<nom>/logic.py`` qui définit une classe ``Adventure``.
  Cette classe *n'orchestre que les briques* : elle ne développe jamais
  de nouvelle fonctionnalité (toutes les fonctionnalités sont dans le
  moteur).
- ``game.Game`` expose les briques et appelle les *hooks* de l'aventure
  (``on_map_change`` / ``on_tick`` / ``redirect_dest`` / ``on_interact``).
  Par défaut : la logique de l'aventure ``settings.DEFAULT_ADVENTURE``.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from settings import BASE_DIR


class Adventure:
    """Classe de base d'une aventure.

    Les méthodes sont les *hooks* appelés par le moteur. Par défaut no-op :
    une aventure ne surcharge que ce qu'elle utilise.

    L'objet ``game`` est une instance ``game.Game`` (le moteur). Les briques
    sont accessibles via ``game`` (attributs/méthodes) : ``game._monster``,
    ``game._setup_monster()``, ``game._reset_combat()``,
    ``game._apply_player_monster2()`` / ``game._reset_player_monster2()``,
    ``game._eat_npc(npc)``, ``game._apply_village_npc_flee()``,
    ``game._light_candle(focus)``, ``game.world.flag_get(...)``,
    ``game.quest`` (``QuestConfig`` chargé du JSON), ...
    """

    def on_map_change(self, game, prev_name, curr_name):
        """Appelé au changement de carte (après détection par le moteur).

        C'est le lieu de la réinitialisation de l'état de quête et du
        setup éventuel du monstre. ``prev_name`` est ``None`` à la première
        carte.
        """
        pass

    def on_tick(self, game, dt):
        """Appelé à chaque frame, après le update du monde/joueur/NPC.

        C'est le lieu de l'orchestration de la quête (monstre qui
        poursuit le joueur, transformation du joueur, dévoration des PNJ,
        fuite des PNJ du village, ...).
        """
        pass

    def on_interact(self, game, action, focus):
        """Appelé *avant* la résolution générique d'une interaction.

        Permet à l'aventure de consommer une interaction spécifique (en
        renvoyant ``True``) ou d'en ajouter. Par défaut : non-consommée
        (le moteur résout l'action générique : ``light_candle``, ``transform``,
        etc.).
        """
        return False

    def redirect_dest(self, game, destination_name, player):
        """Redirection de destination de transition (quêtes).

        Le moteur demande à l'aventure de rediriger une destination de
        transition (ex. : ``boss_combat_map`` vers ``post_combat_map`` après
        victoire). Renvoie un nom de carte (redirection) ou ``None``
        (aucune redirection).
        """
        return None


_ADV_CLS_CACHE: dict[str, type["Adventure"]] = {}


def load_adventure_logic(name: str) -> Adventure:
    """Charge la logique (fichier ``adventures/<name>/logic.py``) d'une
    aventure et renvoie une instance de sa classe ``Adventure``.

    ``name`` est le *stem* du JSON d'aventure (ex. ``"demo-test"`` pour
    ``adventures/demo-test.json``). La classe ``Adventure`` du module
    ``logic.py`` est instanciée et retournée.
    """
    name = str(name)
    if name in _ADV_CLS_CACHE:
        return _ADV_CLS_CACHE[name]()
    logic_file = BASE_DIR / "adventures" / name / "logic.py"
    if not logic_file.exists():
        raise FileNotFoundError(
            f"Logique d'aventure introuvable : {logic_file}"
            f" (attendu : aventure/<name>/logic.py)"
        )
    module_name = "adventure_logic_" + name.replace("-", "_").replace(".", "_")
    spec = importlib.util.spec_from_file_location(module_name, str(logic_file))
    if spec is None:
        raise RuntimeError(f"Impossible de charger le module {logic_file}")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    adv_cls = getattr(module, "Adventure", None)
    if adv_cls is None or not issubclass(adv_cls, Adventure):
        raise ValueError(
            f"Aucune classe ``Adventure`` (héritant de ``adventure.Adventure``) "
            f"trouvée dans {logic_file}"
        )
    _ADV_CLS_CACHE[name] = adv_cls
    return adv_cls()
