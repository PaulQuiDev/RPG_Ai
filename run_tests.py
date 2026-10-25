#!/usr/bin/env python3
"""Lance la suite de tests (stdlib unittest, sans dépendance externe).

    python run_tests.py                # tous les tests
    python run_tests.py -k pattern     # filtre (sous-string dans l'id)

Chaque module test est chargé dans le PAQUET `tests` (tests.<nom>),
donc les imports relatifs (from .base import ...) fonctionnent.
"""
import argparse
import os
import re
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import unittest


def build_suite():
    """Baltit la suite à partir de tous les test_*.py du paquet tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    test_dir = os.path.join(_ROOT, "tests")
    for fn in sorted(os.listdir(test_dir)):
        if not (fn.startswith("test_") and fn.endswith(".py")):
            continue
        mod = fn[:-3]
        module_name = f"tests.{mod}"
        try:
            module = __import__(module_name, fromlist=[mod])
        except Exception as exc:  # module absent ou en erreur
            print(f"[skip] {module_name}: {exc}", file=sys.stderr)
            continue
        suite.addTests(loader.loadTestsFromModule(module))
    return suite


def _apply_filter(suite, pattern):
    """Filtre les tests dont l'id contient le pattern (comme pytest -k)."""
    if pattern is None:
        return suite
    out = []
    for t in suite:
        if isinstance(t, unittest.TestSuite):
            out.extend(_apply_filter(t, pattern))
        elif isinstance(t, unittest.TestCase):
            if pattern.search(t.id()):
                out.append(t)
    return unittest.TestSuite(out)


def main():
    ap = argparse.ArgumentParser(description="Suite de tests RPG_Ai")
    ap.add_argument("-k", help="Filtre (sous-string dans l'id du test)")
    args = ap.parse_args()
    suite = build_suite()
    if args.k:
        suite = _apply_filter(suite, re.compile(re.escape(args.k)))
    return unittest.TextTestRunner(verbosity=2).run(suite)


if __name__ == "__main__":
    raise SystemExit(0 if main().wasSuccessful() else 1)
