"""Base commune des tests : fenêtre, tmp dir, sheet fake, mondes."""
import tempfile
import unittest

from .pygame_setup import init_display, make_sheet, write_sheet
from settings import MAPS
from world import World


def new_world():
    """Le monde RÉEL (village + forêt) — pour les tests d'intégration."""
    return World(MAPS)


class BaseTestCase(unittest.TestCase):
    """Fenêtre dummy + tmp dir + sheet fake partagés par classe."""

    @classmethod
    def setUpClass(cls):
        cls.screen = init_display()
        cls._tmp = tempfile.TemporaryDirectory()
        cls.fake_sheet_path = write_sheet(
            cls._tmp.name, make_sheet(), "fake_sheet.png")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "_tmp"):
            cls._tmp.cleanup()
