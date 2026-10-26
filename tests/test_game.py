"""Tests de la classe `game.Game` : machine à états (pause, quit) et
boucle headless (update + render) sans crash."""
import pygame
import unittest

from .base import BaseTestCase
from settings import CHARACTERS, MAPS
from game import Game, GameState


class TestGame(BaseTestCase):
    """Machine à états et boucle headless de `Game`."""

    def _make_game(self):
        return Game(
            self.screen,
            pygame.font.SysFont("sans", 18),
            CHARACTERS,
            MAPS,
        )

    def test_initial_state_running(self):
        """Un `Game` démarre en RUNNING, sans quitter."""
        game = self._make_game()
        self.assertEqual(game.state, GameState.RUNNING)
        self.assertFalse(game.should_quit)

    def test_esc_toggles_pause(self):
        """Échap bascule RUNNING ↔ PAUSED."""
        game = self._make_game()
        self.assertEqual(game.state, GameState.RUNNING)
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        game.handle_events()
        self.assertEqual(game.state, GameState.PAUSED)
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        game.handle_events()
        self.assertEqual(game.state, GameState.RUNNING)

    def test_quit_event(self):
        """Un événement QUIT met l'état en QUIT."""
        game = self._make_game()
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        game.handle_events()
        self.assertEqual(game.state, GameState.QUIT)
        self.assertTrue(game.should_quit)

    def test_paused_update_no_move(self):
        """En pause, `update` ne déplace pas le joueur (logique gelée)."""
        game = self._make_game()
        start = (game.player.x, game.player.y)
        # Met en pause, puis plusieurs mises à jour sans entrée.
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        game.handle_events()
        self.assertEqual(game.state, GameState.PAUSED)
        for _ in range(3):
            game.update(0.016)
        self.assertEqual((game.player.x, game.player.y), start)

    def test_headless_frames(self):
        """Quelques frames (update + render) en headless ne plantent pas."""
        game = self._make_game()
        dt = 0.016
        for _ in range(5):
            game.update(dt)
            game.render()
        self.assertEqual(game.state, GameState.RUNNING)
