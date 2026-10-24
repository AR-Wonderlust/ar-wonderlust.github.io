import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from instructions import load_instructions


class InstructionsTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'ASSISTANT_CONFIG_DIR': str(self.root)})
        self.env.start()
        self.addCleanup(self.env.stop)
        (self.root / 'skills').mkdir()

    def test_edits_and_deletions_apply_without_restart(self):
        path = self.root / 'personality.md'
        path.write_text('Hola 你好', encoding='utf-8')
        self.assertIn('你好', load_instructions())
        path.write_text('Hello', encoding='utf-8')
        self.assertIn('Hello', load_instructions())
        self.assertNotIn('你好', load_instructions())
        path.unlink()
        self.assertEqual('', load_instructions())

    def test_skill_folder_and_disabled_files(self):
        folder = self.root / 'skills' / 'traslados'
        folder.mkdir()
        (folder / 'SKILL.md').write_text('Traslados')
        (folder / 'run.py').write_text('raise Exception("must not execute")')
        (self.root / 'skills' / 'old.md.disabled').write_text('Disabled')
        self.assertIn('Traslados', load_instructions())
        self.assertNotIn('Disabled', load_instructions())

    def test_reject_oversized_file(self):
        (self.root / 'personality.md').write_text('x' * 20001)
        with self.assertRaises(ValueError):
            load_instructions()

    def test_reject_external_symlink(self):
        with TemporaryDirectory() as external:
            secret = Path(external) / 'outside.md'
            secret.write_text('Do not read')
            (self.root / 'skills' / 'link.md').symlink_to(secret)
            with self.assertRaises(ValueError):
                load_instructions()

if __name__ == '__main__':
    unittest.main()
