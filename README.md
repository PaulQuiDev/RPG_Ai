# RPG_AI — prototype de jeu 2D (Python + Pygame)

Prototype de jeu de rôle 2D : un personnage animé se déplace au clavier sur une carte
avec collision, changement de carte, objets interactifs et personnages **NPC**
(statiques ou en patrouille). Le nom « AI » désigne la **génération des assets par
image IA** (prompts dans `prompte_actelle.txt`, sorties dans `Nonranger/`) — pas
une logique de jeu par IA.

## 🤖 Contexte minimal (agent LLM)
Pour travailler sur ce code **sans charger tout le repo** (éviter les PNG et
l'`.venv/`), lis dans cet ordre :

1. Ce fichier — vue d'ensemble, structure, points à faire.
2. `settings.py` — toute la config (cartes, personnages, sprites, constants).
3. `main.py` — point d'entrée, boucle, options CLI (`--debug`, `--window`, `--fullscreen`).
4. `world.py` — registre des cartes, chargement, transitions, spawn.
5. `game_map.py` — fond + masque + couche FG, objets bleus, NPC, rendu.
6. `player.py` — personnage, mouvement, animation, collision.
7. `npc.py` — statique / patrouille, interaction.
8. `behaviors.py` — objets bleus + registre `BEHAVIORS`.
9. `sprite_loader.py` — découpe 4x3 des sheets.

Lancer : `.venv/bin/python main.py [--debug|--window|--fullscreen]`
Tests : `.venv/bin/python -m pytest tests/`
**NE pas charger** : `asset/*.png`, `Nonranger/*.png` (binaire, inutile à la logique).

## Lancer

```bash
cd ~/Bureau/RPG_Ai
.venv/bin/python main.py                 # jeu (fenêtre 960x720)
.venv/bin/python main.py --window 800x600 # fenêtre custom (résolution logique 960x720, smoothscale + letterbox)
.venv/bin/python main.py --fullscreen     # plein écran (960x720 étendue au moniteur)
.venv/bin/python main.py --debug          # + carte de collision, itboxes, position joueur,
                                          #   chemin A* prévu du monstre (ligne blanche + flèche)
.venv/bin/python main.py --save PATH      # chemin du fichier de sauvegarde (clé S)
.venv/bin/python main.py --load PATH      # reprise de partie : charge PATH au démarrage
.venv/bin/python smoke_npc.py             # test headless (7 vérifs, sans fenêtre)
```

## Comment ça marche (en bref)

| Fichier             | Rôle                                                                 |
|---------------------|----------------------------------------------------------------------|
| `main.py`           | boucle de jeu : input → update → interactions → rendu + HUD          |
| `game.py`           | orchestrateur « Game » : monde, joueur, monstre, drapeaux, HUD, sauvegarde/chargement |
| `world.py`          | registre des cartes, chargement, transitions (sorties), choix du spawn |
| `game_map.py`       | fond + masque de collision + couche FG, objets bleus, NPC, perspective |
| `monster.py`        | monstre hostile : A* pathfinding + anti-blocage                      |
| `player.py`         | personnage 4x3, mouvement, animation, collision                      |
| `npc.py`            | personnages de carte : statique / patrouille, collision, interaction  |
| `sprite_loader.py`  | découpe 4x3 des sheets, partagée par le joueur et les NPC            |
| `tuner.py`          | GUI tkinter : ajuster crops & anchors → `asset/sprite_configs.json`    |
| `behaviors.py`      | comportements des objets bleus + registre `BEHAVIORS`                |
| `settings.py`       | toute la config (cartes, personnages, sprites, constants)            |

Flux par frame : `player.update` → `game_map.update_npcs` → transitions (bords) →
détection des objets bleus au contact (action `BEHAVIORS`) + NPC au contact
(message/action) → `game_map.draw` (fond, masques, FG, objets, NPC, joueur).

## Structure

```
RPG_Ai/
├── main.py            # boucle de jeu, input → update → interactions → rendu
├── game.py            # orchestrateur « Game » : monde, joueur, monstre,
│                      #   drapeaux, HUD, sauvegarde/chargement
├── world.py           # registre des cartes, chargement, transitions, spawn
├── game_map.py        # fond + masque + couche FG, objets bleus, NPC, perspective
├── monster.py         # monstre hostile : A* pathfinding + transformation
├── player.py          # personnage : mouvement, animation, collision
├── npc.py             # personnages de carte : statique / patrouille
├── behaviors.py       # comportements des objets bleus + registre BEHAVIORS
├── settings.py        # toute la config (cartes, personnages, sprites, constants)
├── sprite_loader.py   # découpe 4x3 des sheets
├── tuner.py           # GUI tkinter : ajuster crops & anchors
├── smoke_npc.py       # test headless
├── prompte_actelle.txt # prompts de génération d'assets (IA)
├── asset/carater/     # sprites 4x3 (femme, monster, champignons, ...)
├── asset/world/       # cartes (fond, masques SEG, couches FG, boss)
├── adventures/        # aventures JSON (demo-test.json, forest-quest.json)
├── tests/             # suite pytest (205 tests, dont test_quest_config.py)
└── Nonranger/         # sorties d'assets IA (Krea2, Qwen)
```

## 📊 Rapport du projet

### Tâches (état)

| #  | Tâche | État |
|----|-------|------|
| P1 | Le flag `--debug` ne fonctionnait plus. | ✅ RESOLU — bug `interaction=None` corrigé + affichage du chemin A* du monstre en ligne blanche + flèche. |
| P2 | Pathfinding A* du monstre. | ✅ RESOLU — contourne les obstacles (bougies, rochers) ; rayon de pathfinding (8 px) distinct du rayon de collision réel (12 px) ; A* à « suppression paresseuse » ; recompute gated (distance > 50 px, chemin vide, joueur déplacé > 6 cases). |
| P2 | Le monstre peut rester bloqué dans un mur, un décor ou une bougie. | ✅ RESOLU — détection sur le **déplacement réel** (pas de mouvement pendant `STUCK_THRESHOLD` = 1,5 s) : `_back_up` (recul/poussée vers une case praticable) ou snap hors de l'obstacle (`_unstick`), puis recompute du chemin A*. Tests : `TestMonsterRecovery` (5 tests). |
| P4 | Après le boss fight, l'interaction avec le **siège** doit déclencher la transformation `monster2` du **joueur** (pas du monstre). | ✅ RESOLU (data-driven) — le trône lève `monster2_active` et transforme le **joueur** ; sprite & vitesse pris du bloc `quest` du JSON (`monster2.png` + 180), plus codés en dur. Détection dérivée du drapeau : synchronisée à chaque frame dans `update()` et re-appliquée au chargement ; les PNJ du village fuient le joueur-boss. Tests : `test_full_quest.py`, `test_monster.py` (`test_create_monster_always_normal`), `test_quest_config.py` (contrat data-driven + assets déclarés dans le JSON). |
| P5 | Revenir sur la scène après le combat ne doit PAS réaffronter le monstre déjà vaincu ; la carte doit rester celle du post-combat. | ✅ RESOLU — le spawn dans `_on_map_change` est gated par le flag `monster_defeated` (persistant), les bougies ne font plus rien (`_light_candle` no-op) et le HUD affiche « Monstre vaincu — combat terminé ». La victoire passe à « Post Combat » et la carte y reste (trône, transformation). Tests : `test_full_quest.py` (`test_full_quest_flow`, `test_real_navigation_no_respawn_after_victory`). |
| P6 | Objet « zone bleu » défini dans `settings` sans position doit retourner un warning/erreur ; ou position mal formée / hors carte. | ✅ RESOLU — validation globale au chargement (`_sanitize_interactions`) : position manquante / mal formée / non numérique => interaction **retirée** ; hors des bornes de la carte => conservée (format valide) mais signalée. Avertissements loggés à la création de la carte + dans `interaction_warnings` (visible en console). Tests : `TestInteractionPosSanitization` (10 tests). |
| P7 | **IA des ennemis** : étendre la patrouille vers une machine à états (patrouille → aggro → attaque → fuite). | ❌ À faire |
| —  | Clamping du bord (marge sprite). | ✅ RESOLU — les PNJ ne « disparaissent » plus contre le bord : position des pieds clampée à une marge **calculée** à partir de la taille réelle du sprite (facteur de perspective × `scale`) plutôt qu'à 5 px. Solution **globale** — tous les PNJ (statique/patrouille/fuite), toutes les cartes, tous les coins. Tests : `TestNpcEdgeClamp` (bords + 4 coins + patrouille). |
| —  | Adventures (JSON). | ✅ RESOLU — `adventures/*.json` externalisées + loader + écran de lancement. |
| —  | Type checking. | ✅ RESOLU — `Monster` accepte `str \| Path` pour `sprite_path` ; `assert path is not None` (Pyright) — plus d'erreurs rouges VSCode. |

### Dette technique (choix à réviser)
- **Collision par seuil de couleur fragile** : le masque praticable se base sur
  un seuil de couleur (R < 150). Remplacer par une map de collision **données**
  (tiles) + outil de calibration, pour ne pas casser la collision si l'art change.
- **Pas de gestion centralisée des assets** : centraliser chargement /
  validation / cache dans un manager d'assets.
- **Pipeline IA pour les assets** : lier la génération Krea2 / Qwen au projet
  (validation des sheets, découpe automatique, insertion dans `settings.py`).
- **Santé du monstre** : ajouter un système de santé (les interactions actuelles
  ne font que téléporter ou basculer d'actif).
- **Inventaire / quêtes** : les interactions actuelles ne font que téléporter
  ou basculer d'actif.

### Risques / problèmes futurs (à anticiper)
- La collision par seuil de couleur casse si l'art change (dette n°1).
- Performance de l'A* : recompute gated (distance > 50 px, chemin vide, joueur
  déplacé > 6 cases) ; le « monstre bloqué » est détecté sur le **déplacement
  réel** (pas de mouvement pendant `STUCK_THRESHOLD` = 1,5 s → débloquage,
  puis recompute) — à surveiller si des monstres supplémentaires sont ajoutés.
- Compatibilité du format de sauvegarde (v=1) entre versions du jeu.

### Idées imatures — à discuter (pas des priorités)
- **Dialogue** : l'interaction NPC affiche un simple message ; ajouter des
  arbres de dialogue.
- **Éditeur de niveau** : changer les couleurs de la segmentation + définir les
  objets à interagir (nom / comportement pour le JSON), voire afficher la map et
  la segmentation en transparence.
- **Debug humain** : comprendre facilement la situation dans la console
  (position joueur + seconde), voire afficher en transparence la map
  d'interaction et les hitboxes. Flag à ajouter au lancement.
- **Hébergement web** : migrer du GitHub Pages vers un hébergement web.

### Prochaines étapes
1. **P7** — IA des ennemis (machine à états : patrouille → aggro → attaque → fuite).

### Notes — ne pas oublier (optionnel / à discuter)
- **Contrat data-driven (`test_quest_config.py`)** — le cœur du jeu (`game.py`, `monster.py`, `npc.py`, `player.py`, `world.py`, `behaviors.py`) ne doit plus référencer d'asset d'aventure en dur. Le test `test_core_modules_have_no_orphan_hardcoded_assets` scanne ces 6 modules : **ajouter tout nouveau module de logique** à `CORE_MODULES` dans `TestNoHardcodedAdvantageAssets` s'il manipule des assets.
- **Constantes historiques de `game.py`** — `BOSS_COMBAT_MAP`, `POST_COMBAT_MAP`, `MONSTER_START`, `MONSTER_SPEED`, `MONSTER_SPEED2` sont conservées pour compatibilité mais ne servent plus qu'à l'export (alimentées par `QUEST_CONFIG`). Évaluer leur suppression.
- **Test de bout en bout (optionnel)** — vérifier que le sprite réellement *dessiné* (pygame) par le monstre transformé correspond à `monster2_sprite` du JSON.
