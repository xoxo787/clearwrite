"""Builds must preserve unknown files and detect stale generated contents."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('bundle_builder', ROOT / 'scripts/build_bundles.py')
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class BundleSyncTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp(prefix='clearwrite-bundle-test-'))
        self.source = self.directory / 'source'
        self.target = self.directory / 'target'
        self.source.mkdir()
        self.target.mkdir()
        (self.source / 'core.py').write_text('new content', encoding='utf-8')

    def test_unknown_files_are_preserved_before_any_update(self):
        (self.target / 'notes.txt').write_text('user notes', encoding='utf-8')
        (self.target / 'core.py').write_text('old content', encoding='utf-8')
        with self.assertRaises(ValueError):
            BUILDER.sync_tree(self.source, self.target)
        self.assertEqual((self.target / 'notes.txt').read_text(encoding='utf-8'), 'user notes')
        self.assertEqual((self.target / 'core.py').read_text(encoding='utf-8'), 'old content')

    def test_sync_is_repeatable_and_leaves_cache_files_alone(self):
        cache = self.target / '__pycache__'
        cache.mkdir()
        (cache / 'cache.pyc').write_bytes(b'cached')
        BUILDER.sync_tree(self.source, self.target)
        BUILDER.sync_tree(self.source, self.target)
        self.assertEqual((self.target / 'core.py').read_bytes(), (self.source / 'core.py').read_bytes())
        self.assertEqual((cache / 'cache.pyc').read_bytes(), b'cached')

    def test_check_detects_extra_files_and_reference_drift_without_writing(self):
        src = self.directory / 'src/clearwrite'
        skill = self.directory / 'skills/clearwrite'
        plugin_skill = self.directory / 'plugins/clearwrite/skills/clearwrite'
        for path in (src, skill / 'scripts/clearwrite', plugin_skill / 'scripts/clearwrite'):
            path.mkdir(parents=True)
            (path / 'core.py').write_text('same', encoding='utf-8')
        (skill / 'SKILL.md').write_text('original', encoding='utf-8')
        (plugin_skill / 'SKILL.md').write_text('out of date', encoding='utf-8')
        (plugin_skill / 'scripts/clearwrite/stale.py').write_text('old module', encoding='utf-8')
        hashes = self.directory / 'data/bundle-source-hashes.json'
        hashes.parent.mkdir()
        hashes.write_text(json.dumps({'core.py': 'wrong digest'}), encoding='utf-8')
        before = {p: p.read_bytes() for p in self.directory.rglob('*') if p.is_file()}
        with patch.object(BUILDER, 'ROOT', self.directory):
            differences = BUILDER.check_bundles()
        self.assertIn(str(plugin_skill / 'SKILL.md'), differences)
        self.assertIn(str(plugin_skill / 'scripts/clearwrite/stale.py'), differences)
        self.assertIn(str(hashes), differences)
        self.assertEqual(before, {p: p.read_bytes() for p in self.directory.rglob('*') if p.is_file()})


if __name__ == '__main__':
    unittest.main()
