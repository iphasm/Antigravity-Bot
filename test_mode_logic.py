import os
import unittest
from unittest.mock import MagicMock
from utils.trading_manager import TradingSession, SessionManager

class TestModeLogic(unittest.TestCase):
    def setUp(self):
        self.session = TradingSession("123", "key", "secret")
        # Mock client to avoid init error
        self.session.client = MagicMock()
        
    def test_default_mode(self):
        self.assertEqual(self.session.mode, 'WATCHER')
        
    def test_set_mode(self):
        self.assertTrue(self.session.set_mode('COPILOT'))
        self.assertEqual(self.session.mode, 'COPILOT')
        
        self.assertTrue(self.session.set_mode('PILOT'))
        self.assertEqual(self.session.mode, 'PILOT')
        
        self.assertFalse(self.session.set_mode('INVALID'))
        self.assertEqual(self.session.mode, 'PILOT') # Should not change

    def test_config_persistence_simulation(self):
        # Set mode first
        self.session.set_mode('PILOT')
        
        # Simulate saving/loading
        cfg = self.session.get_configuration()
        self.assertEqual(cfg['mode'], 'PILOT')
        
        # New session from config
        new_session = TradingSession("123", "key", "secret", config=cfg)
        self.assertEqual(new_session.mode, 'PILOT')

if __name__ == '__main__':
    unittest.main()
