# RPG_AI — prototype de jeu 2D (Python + Pygame)

Prototype de jeu de rôle 2D : un personnage animé se déplace au clavier sur une carte
avec collision, changement de carte, objets interactifs et personnages **NPC**
(statiques ou en patrouille). Le nom « AI » désigne la **génération des assets par
image IA** (prompts dans `prompte_actelle.txt`, sorties dans `Nonranger/`) — pas
une logique de jeu par IA.

## Lancer

```bash
cd ~/Bureau/RPG_Ai
.venv/bin/python main.py        # lancer le jeu (fenêtre)
.venv/bin/python smoke_npc.py   # test headless (7 vérifs, sans fenêtre)
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
- **Coupe de sprite 4x3 hardcodée** : `CROP_OFFSETS` / `CROP_SIZE` /
  `ANCHOR_OFFSETS` sont des nombres magiques par personnage. Rendre data-driven
  (config par actif) pour que l'ajout d'un personnage ne demande pas de retouche
  manuelle. (Besoin d'un interfacte pour trouvet c'est setting ou nouveaux sitemme, génération d'image fluctue leur position )
- **États mutés en mémoire** : `change_map_asset` / `cycle_map_variant` modifient
  `world.maps` à l'exécution sans persistance — formaliser l'état.
- **Couplage des systèmes** : ajouter un système d'événements / composants pour
  découpler interactions, transitions et NPC, et faciliter l'ajout (inventaire,
  quêtes, combat).

### 2. Fonctionnalités importantes à ajouter
- **Combat** : les actifs `bossecombat` / `bossepasscombat` existent dans
  `asset/world/` mais ne sont ni déclarés dans `MAPS` ni associés à une logique
  de combat (santé, attaques, IA des ennemis).
- **IA des ennemis** : les monstres patrouillent seulement ; machine à états.
- **Dialogue** : l'interaction NPC affiche un simple message ; ajouter des arbres
  de dialogue.
- **Inventaire / quêtes** : les interactions actuelles ne font que téléporter ou
  basculer d'actif.
- **Tests** : ajouter des tests unitaires (mouvement, collision, transitions,
  interactions) — aujourd'hui seulement `smoke_npc.py`.
- **Debug humain** : permetter de conprendre facilement la situation dans la console position jeur x sconde , voire en transparence la map d'interation et les itbox en générale... flag a ajouter au lencement.

### 3. Simplifications possibles
- Machine à bascule d'actifs (`variants` + `change_map_asset` + `cycle_map_*`) :
  beaucoup de mécanisme pour un prototype → à conserver ou à retirer.
- Images IA `Nonranger/*.png` non référencées par le jeu → trier / archiver.
- Constants redondantes (`CHARACTER_SCALE`, `DISPLAY_SCALE`, `MOVE_SPEED`,
  `COLLISION_RADIUS`, déjà définies dans `CHARACTERS`) → consolider.
- Documentation agentic, si plus presise pour permetter au modle de ne pas avoire besoin de tout le code a chager. Si plus efficae par programme python affin d'obtimiser en contexte. 

  ### a discuter pas certain voire comment faire:
- **Collision par seuil de couleur fragile** : le masque praticable se base sur
  un seuil de couleur (R < 150). Remplacer par une map de collision **données**
  (tiles) + outil de calibration, pour ne pas casser la collision si l'art change.
- **Pas de gestion d'assets** : centraliser chargement/validation/cache dans un
  manager d'assets.
- **Sauvegarde / chargement** : aucune persistance d'état pour l'instant.
- **Pipeline IA pour les assets** : lier la génération Krea2/Qwen au projet
  (validation des sheets, découpe automatique, insertion dans `settings.py`).
  - **IA des ennemis** :  ajouter santé.