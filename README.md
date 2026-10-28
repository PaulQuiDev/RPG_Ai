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

Lancer : `.venv/bin/python main.py [--debug|--window WxH|--fullscreen]`
Tests : `.venv/bin/python -m pytest tests/`
**NE pas charger** : `asset/*.png`, `Nonranger/*.png` (binaire, inutile à la logique).

## Lancer

```bash
cd ~/Bureau/RPG_Ai
.venv/bin/python main.py                 # jeu (fenêtre 960x720)
.venv/bin/python main.py --window 800x600 # fenêtre custom (résolution logique 960x720, smoothscale + letterbox)
.venv/bin/python main.py --fullscreen     # plein écran (960x720 étendue au moniteur)
.venv/bin/python main.py --debug          # + carte de collision, itboxes, position joueur
.venv/bin/python smoke_npc.py             # test headless (7 vérifs, sans fenêtre)
```

## Comment ça marche (en bref)

| Fichier             | Rôle                                                                 |
|---------------------|----------------------------------------------------------------------|
| `main.py`           | boucle de jeu : input → update → interactions → rendu + HUD          |
| `world.py`          | registre des cartes, chargement, transitions (sorties), choix du spawn|
| `game_map.py`       | fond + masque de collision + couche FG, objets bleus, NPC, perspective|
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
├── main.py
├── settings.py
├── game_map.py
├── world.py
├── player.py
├── npc.py
├── sprite_loader.py
├── tuner.py              # GUI tkinter pour ajuster les crops/anchors
├── behaviors.py
├── smoke_npc.py            # test headless
├── prompte_actelle.txt     # prompts de génération d'assets (IA)
├── asset/
│   ├── carater/            # sprites 4x3 (femme, monster, champignons, ...)
│   └── world/              # cartes (fond, masques SEG, couches FG, boss)
└── Nonranger/              # sorties d'assets IA (Krea2, Qwen) + test legacy
```

## Prochaines étapes (priorité)

### 1. Architecture — dette technique à traiter
- **Démonolithiser `main.py`** : introduire un objet `Game`/`Scene` avec
  `update(dt)` / `render(screen)` découplés + une machine à états (pause, menus).
- ✅ **Coupe de sprite data-driven** (fait — voir « To do » #1) : les défauts
  `CROP_SIZE` / `CROP_OFFSETS` / `ANCHOR_OFFSETS` restent dans `settings.py` ;
  les overrides par personnage (joueur ou NPC) sont dans
  `asset/sprite_configs.json`, ajustables via `python tuner.py`, et rechargées
  au démarrage par `settings.apply_sprite_overrides`. Ajouter un personnage ne
  demande plus de retouche manuelle.
- **États mutés en mémoire** : `change_map_asset` / `cycle_map_variant` modifient
  `world.maps` à l'exécution sans persistance — formaliser l'état.
- **Couplage des systèmes** : ajouter un système d'événements / composants pour
  découpler interactions, transitions et NPC, et faciliter l'ajout (inventaire,
  quêtes, combat).

### 2. Fonctionnalités importantes à ajouter
- si obj defini mais pas de posion en plus au coorder indiquer retouren un warning ou erreur
- **IA des ennemis** : les monstres patrouillent seulement ; machine à états.
- **Dialogue** : l'interaction NPC affiche un simple message ; ajouter des arbres
  de dialogue.
- **Tests** : ✅ fait — suite unittest complète (`tests/`, 85 tests :
  mouvement, collision, transitions, interactions, intégration
  Village↔Forêt sur les assets réels). Filet en place avant la refactoring §1.
- **Debug humain** : permetter de conprendre facilement la situation dans la console position jeur x sconde , voire en transparence la map d'interation et les itbox en générale... flag a ajouter au lencement.

### 3. Simplifications possibles
- Machine à bascule d'actifs (`variants` + `change_map_asset` + `cycle_map_*`) :
  beaucoup de mécanisme pour un prototype → à conserver ou à retirer.
- Images IA `Nonranger/*.png` non référencées par le jeu → trier / archiver.
- Constants redondantes (`CHARACTER_SCALE`, `DISPLAY_SCALE`, `MOVE_SPEED`,
  `COLLISION_RADIUS`, déjà définies dans `CHARACTERS`) → consolider.
- Documentation agentic, si plus presise pour permetter au modle de ne pas avoire besoin de tout le code a chager. Si plus efficae par programme python affin d'obtimiser en contexte. 

### Progression des tâches à envisager (✅ = fait · ⬜ = à faire)

**Progression : 4 / 5** — ✅✅✅✅⬜

- ✅ Interface simple pour ajuster les settings de coupe de chaque personnage
  (joueur ou NPC) — la taille/position de la feuille varie suite à la génération
  d'image IA. `tuner.py` (tkinter) : glisser une boîte de coupe par cadre +
  point d'ancrage (pieds du personnage), aperçu live, écriture dans
  `asset/sprite_configs.json`. Usage : `python tuner.py` ou `python tuner.py Femme`.
- ✅ Debug humain : afficher la position du joueur + les zones d'interaction
  (carte de collision en transparence, itboxes) via un flag de lancement
  (`--debug`).
- ✅ Option pour contrôler la taille de l'écran (plein écran / résolution
  custom, ex. `--fullscreen` / `--window WxH`). Résolution logique du jeu
  fixe (960x720) ; la fenêtre est redimensionnée via une surface hors-écran
  + smoothscale + letterbox (aspect conservé, bandes noires si besoin).
- ✅ Maintenir la Doc : ne charger que ce qui aide le contexte LLM (éviter les
  détails inutiles à charger). Section « Contexte minimal (agent LLM) » : ordre
  de lecture des fichiers, commandes, et liste de ce qu'il ne faut **PAS** charger
  (PNGs, `.venv/`).
- ⬜ Sauvegarde / chargement exportable & importable : historique d'actions +
  assets, format JSON (sauvegarder / recharger l'état du jeu).

  ### Ne pas implémenter : a discuter pas certain voire comment faire, idée imature:
- **Collision par seuil de couleur fragile** : le masque praticable se base sur
  un seuil de couleur (R < 150). Remplacer par une map de collision **données**
  (tiles) + outil de calibration, pour ne pas casser la collision si l'art change.
- **Pas de gestion d'assets** : centraliser chargement/validation/cache dans un
  manager d'assets.
- **Sauvegarde / chargement** : aucune persistance d'état pour l'instant.
- **Pipeline IA pour les assets** : lier la génération Krea2/Qwen au projet
  (validation des sheets, découpe automatique, insertion dans `settings.py`).
- **IA des ennemis** :  ajouter santé.
 - **Inventaire / quêtes** : les interactions actuelles ne font que téléporter ou
  basculer d'actif.
- Basculer sur du web pour l'hoste sur internet et pk pas le git hub pages