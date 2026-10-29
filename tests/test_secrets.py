import os
import unittest
from pathlib import Path
from unittest.mock import patch
from voyage.openrouter import load_settings


class SecretsTests(unittest.TestCase):
    def test_cloud_secrets_work_without_local_file(self):
        with patch('voyage.openrouter.SECRETS', Path('missing-test-secrets.toml')), patch('voyage.openrouter.st.secrets', {'OPENROUTER_API_KEY': 'test-cloud-key'}), patch.dict(os.environ, {}, clear=True):
            self.assertEqual(load_settings(), ('test-cloud-key', 'openrouter/free'))

    def test_missing_key_explains_cloud_setup(self):
        with patch('voyage.openrouter.SECRETS', Path('missing-test-secrets.toml')), patch('voyage.openrouter.st.secrets', {}), patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'App settings > Secrets'):
                load_settings()
