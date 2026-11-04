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

## 📊 Rapport du projet

### État actuel
| Domaine | État |
|---------|------|
| **Monstre — pathfinding (A\*)** | ✅ Le monstre contourne les obstacles (bougies,
  rochers) et n'est plus bloqué en haut de carte. Rayon de pathfinding (8 px)
  distinct du rayon de collision réel (12 px) ; recherche des cases de départ /
  cible par cercles concentriques ; A* à « suppression paresseuse » ; recompute
  gated (pas de recompute par timer). |
| **Monstre — anti-blocage (P2)** | ✅ Le monstre ne reste plus coincé dans
  un mur, un décor ou une bougie (impasse) : pas de mouvement pendant
  `STUCK_THRESHOLD` = 1,5 s → recul/poussée vers une case praticable
  (`_back_up`) ou snap hors de l'obstacle (`_unstick`), puis recompute du
  chemin A*. Détection sur le **déplacement réel**. Tests : `TestMonsterRecovery`
  (5 tests). |
| **Transformation monster2 (P4)** | ✅ Le **siège** lève `monster2_active` et transforme le **JOUEUR** en\n  boss (`monster2.png` + vitesse 180) — **pas le monstre** (celui-ci reste\n  normal). Détection dérivée du drapeau : synchronisée à chaque frame dans\n  `update()` et re-appliquée au chargement ; les PNJ du village fuient le\n  joueur-boss. Tests : `test_full_quest.py` (trône → flag → joueur transformé),\n  `test_monster.py` (`test_create_monster_always_normal`). |
| **Quête complète (P5)** | ✅ RESOLU — la boucle complète Village → Forêt → Boss Combat (5 bougies) → Post Combat (trône) → Village (transformation + fuite des PNJ) → re-entrée Boss Combat (nouveau monstre, bougies à zéro) fonctionne, y compris via la navigation réelle (exits) ; la carte reste celle du post-combat ; le reset complet (monstre recréé, bougies à zéro) est appliqué à chaque entrée dans le Boss Combat. Tests : `test_full_quest.py` (`test_full_quest_flow`, `test_real_navigation_respawn`). |
| **Clamping du bord (marge sprite)** | ✅ Les PNJ ne «
  disparaissent » plus contre le bord de la carte : la position des pieds
  est clampée à une marge **calculée** à partir de la taille réelle du
  sprite (facteur de perspective × `scale`) plutôt qu'à 5 px. Solution
  **globale** — tous les PNJ (static/patrouille/fuite), toutes les
  cartes, tous les coins. Tests : `TestNpcEdgeClamp` (bords + 4 coins +
  patrouille). |
| **Aventures (JSON)** | ✅ `adventures/*.json` externalisées + loader +
  écran de lancement. |
| **Validation des positions (P6)** | ✅ Chaque interaction (objet «
  bleu ») est validée avant traitement : position manquante / mal
  formée / non numérique => interaction retirée ; hors des bornes de la
  carte => conservée (format valide) mais signalée. Avertissements loggés
  à la création de la carte et dans `interaction_warnings` (visible en
  console). Tests : `TestInteractionPosSanitization` (10 tests). |

| **Type checking** | ✅ `Monster` accepte `str \| Path` pour `sprite_path` ;
  `assert path is not None` (Pyright détecte non-`None`) — plus d'erreurs
  rouges VSCode. |

### Structure (complète)
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
├── prompte_actelle.txt# prompts de génération d'assets (IA)
├── asset/carater/     # sprites 4x3 (femme, monster, champignons, ...)
├── asset/world/       # cartes (fond, masques SEG, couches FG, boss)
├── adventures/        # aventures JSON (demo-test.json, forest-quest.json)
├── tests/             # suite pytest (197 tests)
└── Nonranger/         # sorties d'assets IA (Krea2, Qwen)
```

### Problèmes restants (bugs) — ordre de priorité
| P | Problème | État |
|---|----------|------|
| P1 | Flag `--debug` ne marche plus et le mettre dans les testes il doit marcher si maudification sytemme | ✅ RESOLU (bug `interaction=None` corrigé + affichage du chemin A* du monstre en ligne blanche + flèche) |
| P2 | Le monstre peut toujours se bloquer dans un **mur, un décor ou une bougie** (en marchant dans l'impasse). Le faire reculer ou le pousser pour le débloquer ; il ne doit plus rester coincé. | ✅ RESOLU — détection sur le **déplacement réel** (pas de mouvement pendant `STUCK_THRESHOLD` = 1,5 s) : `_back_up` (recul/poussée vers une case praticable) ou snap hors de l'obstacle (`_unstick`), puis recompute du chemin A*. Tests : `TestMonsterRecovery`. |
| P4 | Après le boss fight, l'interaction avec le **siège** doit déclencher la transformation `monster2` du **joueur** (pas du monstre). | ✅ RESOLU — le trône lève `monster2_active` et transforme le **joueur** (monster2.png + vitesse 180) ; le monstre reste normal (monster.png, MONSTER_SPEED). Les PNJ du village fuient le joueur-boss. Tests : `test_full_quest.py`, `test_monster.py` (`test_create_monster_always_normal`). |
| P5 | Revenir sur la scène après le combat doit permettre de **refaire le
      combat** (monstre respawné) ; la carte doit rester celle du
      post-combat (re-entrée par la forêt). | ✅ RESOLU — reset complet
      (monstre recréé, bougies à zéro) appliqué à chaque entrée dans le
      Boss Combat via `_on_map_change` ; la victoire passe à « Post Combat
      » (`_defeat_monster`) et la carte y reste (trône, transformation).
      Tests : `test_full_quest.py` (`test_full_quest_flow`,
      `test_real_navigation_respawn`). |
| P6 | Objet « zone bleu » défini dans `settings` sans position doit retourner
      un warning / erreur ; ou position non correcte (hors carte). | ✅ RESOLU —
      validation globale au chargement (`_sanitize_interactions`) :
      position manquante / mal formée / non numérique => interaction
      **retirée** ; hors des bornes de la carte => conservée (format
      valide) mais signalée. Avertissements loggés à la création de la
      carte + dans `interaction_warnings`. Tests :
      `TestInteractionPosSanitization` (10 tests). |
| P7 | **IA des ennemis** : étendre la patrouille vers une machine à états
      (patrouille → aggro → attaque → fuite). | ❌ à faire |


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

### Prochains étapes (ordre de priorité)
1. **P6** ✅ RESOLU — validation des objets bleus (warning / erreur si
   position manquante, mal formée, non numérique ou hors carte).
2. **P7** — IA des ennemis (machine à états : patrouille → aggro → attaque → fuite).