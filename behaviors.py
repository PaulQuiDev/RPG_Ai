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

Alternatives sans code :
    {"pos": [x, y], "dest": "<nom_de_carte>"}  -> téléport direct
        vers la carte donnée (voir go_to_map).
    {"pos": [x, y], "action": "cycle_map_seg"} -> masque SEG de la carte
        courante vers la variante suivante.
    {"pos": [x, y], "action": "cycle_map_bg"}  -> image de fond de la
        carte courante vers la variante suivante.
    {"pos": [x, y], "action": "cycle_map_fg"}  -> couche FG (idem).

Changement d'actifs (segmentation, fond, premier plan)
-------------------------------------------------------
Chaque carte peut déclarer, dans settings.py, des variantes de ses
actifs (clé "variants" : liste de chemins par type) :

    "variants": {
        "mask": [chemin1, chemin2],          # masques SEG alternatifs
        "background": [chemin1, chemin2],    # images de fond
        "foreground": [...],                 # couches de premier plan
    }

`cycle_map_variant` bascule vers le prochain actif de la liste et
recharge la carte si elle est la carte courante (sans modifier les
fichiers sur le disque). La position du joueur est réajustée si le
nouveau masque la rend impraticable. Si le nouveau actif est
incompatible (ex. taille différente du masque), l'état est restauré
et False est retourné.
"""


from pathlib import Path


def _find_map_index(world, name):
    """Index de la carte par nom (insensible à la casse), ou None."""
    target = (name or "").lower().strip()
    for i, data in enumerate(world.maps):
        if data.get("name", "").lower().strip() == target:
            return i
    return None


def go_to_map(player, world, name):
    """Déplace le joueur vers la carte `name` et l'implante à un point
    praticable. Retourne True si la carte existe et a été chargée,
    False sinon."""
    index = _find_map_index(world, name)
    if index is None:
        print(f"Comportement : carte « {name} » inconnue.")
        return False
    if world.change_map(index, player):
        print(f"Comportement : carte « {name} » chargée.")
        return True
    return False


def go_forest(player, world, game_map):
    return go_to_map(player, world, "Forêt")


def go_village(player, world, game_map):
    return go_to_map(player, world, "Village")


def change_map_asset(world, target_name, asset_key, new_path, player=None):
    """Changer un actif d'une carte (mask / background / foreground)
    à l'exécution.

    Met à jour `world.maps[index][asset_key]` et recharge la carte si
    elle est la carte courante (effet immédiat, objets bleus et couches
    FG re-extraits). Aucun fichier n'est modifié sur le disque.

    Retourne True si le changement a été appliqué, False sinon
    (carte inconnue, fichier introuvable, actif incompatible).
    """
    index = _find_map_index(world, target_name)
    if index is None:
        print(f"Comportement actif : carte « {target_name} » non trouvée.")
        return False

    new_path = new_path if isinstance(new_path, Path) else Path(new_path)
    if not new_path.exists():
        print(f"Comportement actif : fichier introuvable : {new_path}")
        return False

    data = world.maps[index]
    old_path = data.get(asset_key)

    data[asset_key] = new_path
    try:
        if index == world.map_index:
            world.game_map = world._load_map(index)
            print(
                f"Actif {asset_key} de {data['name']} changé : "
                f"{old_path.name} -> {new_path.name}"
            )
            # Si le joueur se retrouve sur du non-praticable, on le
            # réimplante sur une position accessible.
            if (
                player is not None
                and not world.game_map.can_stand_at(
                    player.x, player.y, player.collision_radius
                )
            ):
                spawn_x, spawn_y = world.find_spawn(
                    world.game_map, player.collision_radius
                )
                player.x, player.y = float(spawn_x), float(spawn_y)
                print("Position du joueur réajustée.")
        else:
            print(
                f"Actif {asset_key} de {data['name']} changé : "
                f"{old_path.name} -> {new_path.name} "
                f"(appliqué à la prochaine entrée sur la carte)."
            )
    except (RuntimeError, ValueError, KeyError, IndexError) as error:
        # Recharge impossible : on annule la modification.
        data[asset_key] = old_path
        if index == world.map_index:
            world.game_map = world._load_map(index)
        print(f"Comportement actif : recharge impossible : {error}")
        return False

    return True


def cycle_map_variant(world, target_name, asset_key, player=None):
    """Basculer vers la variante suivante de `asset_key` pour la carte
    `target_name`.

    La liste des variantes est dans settings.py (clé "variants" de la
    carte, sous-clé `asset_key`). Retourne True si le changement a été
    appliqué, False sinon (carte inconnue, actif inconnu, moins de
    deux variantes).
    """
    if asset_key not in ("mask", "background", "foreground"):
        print(f"Variante : type d'actif inconnu : {asset_key}")
        return False

    index = _find_map_index(world, target_name)
    if index is None:
        print(f"Variante : carte « {target_name} » non trouvée.")
        return False

    data = world.maps[index]
    variants = (data.get("variants") or {}).get(asset_key)
    if not variants or len(variants) < 2:
        print(
            f"Variante : la carte « {data['name']} » ne declare pas "
            f"de variantes {asset_key}."
        )
        return False

    current = data.get(asset_key)
    try:
        pos = variants.index(current)
    except ValueError:
        pos = 0

    target = variants[(pos + 1) % len(variants)]
    return change_map_asset(world, data["name"], asset_key, target, player)


def cycle_map_seg(player, world, game_map):
    """Bascule le masque SEG de la carte courante vers la variante
    suivante (liste "variants" -> "mask" de settings.py)."""
    return cycle_map_variant(world, world.current_map_data["name"],
                             "mask", player)


def cycle_map_bg(player, world, game_map):
    """Bascule l'image de fond de la carte courante vers la variante
    suivante (liste "variants" -> "background" de settings.py)."""
    return cycle_map_variant(world, world.current_map_data["name"],
                             "background", player)


def cycle_map_fg(player, world, game_map):
    """Bascule la couche de premier plan (FG) de la carte courante vers
    la variante suivante (liste "variants" -> "foreground")."""
    return cycle_map_variant(world, world.current_map_data["name"],
                             "foreground", player)


# Registre des comportements : la clé est la valeur attendue dans
# settings.py (clé "action" d'une interaction).
BEHAVIORS = {
    "go_forest": go_forest,
    "go_village": go_village,
    "cycle_map_seg": cycle_map_seg,
    "cycle_map_bg": cycle_map_bg,
    "cycle_map_fg": cycle_map_fg,
}
