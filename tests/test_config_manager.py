"""
tests/test_config_manager.py
=============================
Unit tests for ConfigManager 3-layer configuration management, .env preservation, and API key updates.
"""

import os
import unittest
import tempfile
import json
from ECD.config_manager import ConfigManager, get_config, get_user_config_path


class TestConfigManager(unittest.TestCase):

    def setUp(self):
        self.config_manager = get_config()
        self.user_config_file = get_user_config_path()

    def tearDown(self):
        # Restore defaults after tests finish to ensure real .env keys are preserved for the application UI
        self.config_manager.restore_defaults()

    def test_singleton(self):
        c1 = ConfigManager()
        c2 = ConfigManager()
        self.assertIs(c1, c2)

    def test_save_and_load_config(self):
        test_creds = {
            "groq_api_key": "test_groq_key_123",
            "gemini_api_key": "test_gemini_key_456"
        }
        ok, err = self.config_manager.save_config(test_creds)
        self.assertTrue(ok)
        self.assertEqual(err, "")

        self.assertEqual(self.config_manager.groq_key(), "test_groq_key_123")
        self.assertEqual(self.config_manager.gemini_key(), "test_gemini_key_456")

        # Verify persisted on disk in %AppData%\ECD\config.json
        self.assertTrue(os.path.isfile(self.user_config_file))
        with open(self.user_config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["ai"]["groq_api_key"], "test_groq_key_123")
        self.assertEqual(data["ai"]["gemini_api_key"], "test_gemini_key_456")

    def test_restore_defaults(self):
        # Save custom overrides
        self.config_manager.save_config({
            "groq_api_key": "override_key",
            "gemini_api_key": "override_key"
        })
        self.assertEqual(self.config_manager.groq_key(), "override_key")

        # Restore defaults
        self.config_manager.restore_defaults()
        # Verify user config override was cleared
        self.assertNotEqual(self.config_manager.groq_key(), "override_key")


if __name__ == "__main__":
    unittest.main()
