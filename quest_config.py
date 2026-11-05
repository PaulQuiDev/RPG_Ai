"""Configuration de la quête (data-driven).

La quête du monstre (carte de combat : bougies, trône, transformation
joueur → monstre) n'est plus codée en dur dans le moteur de jeu : elle
est déclarée dans le JSON d'aventure (clé ``quest``) et chargée ici.
C'est ce qui garantit le contrat du projet :

    « importer l'aventure (JSON) + ses assets => une aventure jouable »

Ce module est pur (dataclass + fonctions) : il ne dépend ni de pygame
ni des assets. La résolution des chemins en ``Path`` est faite à
l'appelant, via ``base_dir``.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Défauts (retour arrière robuste si un JSON n'a pas de bloc ``quest``.
# Les aventures livrées le déclarent toujours — c'est vérifié par
# tests/test_quest_config.py).
DEFAULT_MONSTER_SPRITE = "asset/carater/monster.png"
DEFAULT_MONSTER2_SPRITE = "asset/carater/monster2.png"
DEFAULT_MONSTER_SPEED = 55.0
DEFAULT_MONSTER2_SPEED = 180.0
DEFAULT_MONSTER_SPAWN = (860.0, 540.0)
DEFAULT_CANDLE_TOTAL = 5


@dataclass(frozen=True)
class QuestConfig:
    """Tout ce que le moteur de jeu doit savoir sur la quête du monstre,
    tel qu'il est déclaré dans l'aventure (JSON).

    Les chemins d'assets sont des ``Path`` absolus (résolus relativement
    à ``base_dir`` au chargement).
    """

    monster_sprite: Path
    monster2_sprite: Path
    monster_speed: float
    monster2_speed: float
    monster_spawn: Tuple[float, float]
    candle_total: int
    boss_combat_map: Optional[str]
    post_combat_map: Optional[str]

    @property
    def has_quest(self) -> bool:
        """La quête est-elle jouable (carte de combat identifiée) ?"""
        return self.boss_combat_map is not None


def _name_of_map_with_action(maps: List[Dict[str, Any]], action: str) -> Optional[str]:
    """Nom de la première carte ayant au moins une interaction ``action``.

    ``None`` s'il n'y a aucune carte avec cette interaction.
    """
    for m in maps:
        interactions = m.get("interactions") or []
        if any((i or {}).get("action") == action for i in interactions):
            name = m.get("name")
            if name:
                return name
    return None


def load_quest(
    raw_quest: Optional[Dict[str, Any]],
    maps: List[Dict[str, Any]],
    base_dir: Path,
) -> QuestConfig:
    """Construit une ``QuestConfig`` à partir du bloc ``quest`` du JSON
    (``raw_quest``) et des cartes (pour dériver les noms de cartes et le
    total de bougies), avec des défauts robustes.

    Les chemins relatifs sont résolus relativement à ``base_dir``.
    """
    raw = raw_quest if isinstance(raw_quest, dict) else {}

    def _resolve(p: Optional[str]) -> Path:
        if p is None:
            return Path("")
        pp = Path(p)
        return pp if pp.is_absolute() else base_dir / pp

    # --- Noms de cartes (dérivés des interactions, pas en dur) ---
    boss_combat_map = _name_of_map_with_action(maps, "light_candle")
    post_combat_map = _name_of_map_with_action(maps, "transform_monster")

    # --- Total de bougies : explicite (JSON) ou dérivé de la carte ---
    candle_total = DEFAULT_CANDLE_TOTAL
    candle_total_raw = raw.get("candle_total")
    if isinstance(candle_total_raw, (int, float)):
        candle_total = int(candle_total_raw)
        if candle_total < 1:
            candle_total = DEFAULT_CANDLE_TOTAL
    else:
        # Dériver du nombre d'objets light_candle sur la carte de combat.
        total = 0
        if boss_combat_map:
            for m in maps:
                if m.get("name") == boss_combat_map:
                    total = sum(
                        1
                        for i in (m.get("interactions") or [])
                        if (i or {}).get("action") == "light_candle"
                    )
        if total > 0:
            candle_total = total

    # --- Spawn du monstre ---
    monster_spawn = DEFAULT_MONSTER_SPAWN
    spawn_raw = raw.get("monster_spawn")
    if isinstance(spawn_raw, (list, tuple)) and len(spawn_raw) == 2:
        try:
            monster_spawn = (float(spawn_raw[0]), float(spawn_raw[1]))
        except (TypeError, ValueError):
            pass

    # --- Vitesses ---
    try:
        monster_speed = float(raw.get("monster_speed", DEFAULT_MONSTER_SPEED))
    except (TypeError, ValueError):
        monster_speed = DEFAULT_MONSTER_SPEED
    try:
        monster2_speed = float(raw.get("monster2_speed", DEFAULT_MONSTER2_SPEED))
    except (TypeError, ValueError):
        monster2_speed = DEFAULT_MONSTER2_SPEED

    # --- Sprites (déclarés dans le JSON ; fallback robustes) ---
    monster_sprite = _resolve(raw.get("monster_sprite", DEFAULT_MONSTER_SPRITE))
    monster2_sprite = _resolve(
        raw.get("monster2_sprite", DEFAULT_MONSTER2_SPRITE)
    )

    return QuestConfig(
        monster_sprite=monster_sprite,
        monster2_sprite=monster2_sprite,
        monster_speed=monster_speed,
        monster2_speed=monster2_speed,
        monster_spawn=monster_spawn,
        candle_total=candle_total,
        boss_combat_map=boss_combat_map,
        post_combat_map=post_combat_map,
    )
