"""Paquet de tests unitaires (stdlib unittest, sans dépendance externe).

Lancer la suite :
    cd /home/paul/Bureau/RPG_Ai
    python -m unittest discover -s tests -t test_ -v
"""
import os
import sys

# Racine du projet : garantit que `import settings / world / ...` fonctionne
# quel que soit le mode d'exécution (discover, module explicite, ...).
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

# Driver headless, positionné AVANT tout `import pygame` (dans ce paquet).
if os.environ.get("DISPLAY") is None and os.environ.get("SDL_VIDEODRIVER") is None:
    os.environ["SDL_VIDEODRIVER"] = "dummy"
