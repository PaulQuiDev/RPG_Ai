"""Comportements interactifs.

Chaque objet bleu d'une carte peut être associé à un comportement
défini dans settings.py (liste "interactions" de la carte). Un
comportement est une fonction :

    def <nom>(player, world, game_map) -> bool

Elle reçoit le joueur, le monde et la carte courante, et retourne
True si l'action a été appliquée, False sinon.

Pour ajouter un comportement :
    1. Définir une fonction ici.
    2. L'ajouter au dictionnaire BEHAVIORS.
    3. La citer dans settings.py (clé "action" d'une interaction).

Alternative sans code (simple téléportation) :
    {"pos": [x, y], "dest": "Forêt"}  ->  va sur la carte nommée.
"""


def go_to_map(player, world, name):
    """Changement de carte par nom de carte (insensible à la casse).

    Retourne True si la carte a été chargée.
    """
    target = (name or "").lower().strip()
    for i, data in enumerate(world.maps):
        if data.get("name", "").lower().strip() == target:
            return world.change_map(i, player)
    print(f"Comportement : carte « {name} » non trouvée.")
    return False


def go_forest(player, world, game_map):
    """Test : teleporte le joueur sur la carte Forêt."""
    return go_to_map(player, world, "Forêt")


def go_village(player, world, game_map):
    """Test : teleporte le joueur sur la carte Village."""
    return go_to_map(player, world, "Village")


# Registre des comportements (clé -> fonction).
BEHAVIORS = {
    "go_forest": go_forest,
    "go_village": go_village,
}
