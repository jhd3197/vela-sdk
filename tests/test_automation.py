"""Version publication is exercised against a disposable Git remote."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('component_automation', Path(__file__).resolve().parents[1] / 'scripts/automation.py')
automation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(automation)


def project(root):
    root.mkdir()
    (root / 'release.json').write_text(json.dumps({'repository': 'vela-sdk', 'kind': 'npm', 'version_file': 'package.json'}))
    (root / 'package.json').write_text('{"name":"@vela/sdk","version":"0.5.0"}')
    (root / 'CHANGELOG.md').write_text('# Changelog\n\n## Unreleased\n\n### Added\n\n- First package.\n')


def assets(root):
    root.mkdir()
    artifact = root / 'vela-sdk-0.5.0.tgz'
    artifact.write_bytes(b'tested package')
    (root / (artifact.name + '.sha256')).write_text(hashlib.sha256(artifact.read_bytes()).hexdigest() + '  ' + artifact.name + '\n')


class AutomationTests(unittest.TestCase):
    def test_semver_order_and_validation(self):
        self.assertEqual(automation.next_version('0.5.0', []), '0.5.0')
        self.assertEqual(automation.next_version('0.5.0', ['v0.9.9', 'v0.10.0']), '0.10.1')
        for value in ('0.05.0', 'v0.5.1', '0.4.0', '1.2.3;bad'):
            with self.assertRaises(ValueError):
                automation.next_version('0.5.0', ['v0.5.0'], value)

    def test_stamp_preserves_history_and_retry_date(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'repo'
            project(root)
            automation.stamp(root, '0.5.0', '2026-09-14')
            old = (root / 'CHANGELOG.md').read_bytes()
            automation.stamp(root, '0.5.0', '2026-09-15')
            self.assertEqual(old, (root / 'CHANGELOG.md').read_bytes())
            automation.stamp(root, '0.5.1', '2026-09-15')
            self.assertIn('## 0.5.0 - 2026-09-14', (root / 'CHANGELOG.md').read_text())
            self.assertEqual(automation.current_version(root), '0.5.1')

    def test_changed_asset_or_missing_checksum_cannot_publish(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'repo'
            project(root)
            downloads = Path(temp) / 'downloads'
            assets(downloads)
            with patch.object(automation, 'ROOT', root):
                self.assertEqual(len(automation.validate_assets(downloads, '0.5.0')), 2)
                (downloads / 'vela-sdk-0.5.0.tgz').write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'Checksum'):
                    automation.validate_assets(downloads, '0.5.0')
                (downloads / 'vela-sdk-0.5.0.tgz.sha256').unlink()
                with self.assertRaisesRegex(ValueError, 'asset set'):
                    automation.validate_assets(downloads, '0.5.0')

    def test_published_retry_preserves_tag_and_does_not_upload_again(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'repo'
            project(root)
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=root, text=True).strip()
            git('init', '-b', 'main')
            git('config', 'user.name', 'Fixture')
            git('config', 'user.email', 'fixture@example.test')
            git('add', '.')
            git('commit', '-m', 'Initial fixture')
            remote = Path(temp) / 'remote.git'
            git('init', '--bare', str(remote))
            git('remote', 'add', 'origin', str(remote))
            git('push', '-u', 'origin', 'main')
            source = git('rev-parse', 'HEAD')
            downloads = Path(temp) / 'downloads'
            assets(downloads)
            real_run = subprocess.run
            mutations = []
            def run(args, **kwargs):
                if args[0] == 'gh':
                    mutations.append(args)
                    return subprocess.CompletedProcess(args, 0)
                return real_run(args, **kwargs)
            with patch.object(automation, 'ROOT', root), patch.dict(os.environ, {'GITHUB_REF': 'refs/heads/main', 'GITHUB_REPOSITORY': 'fixture/repo'}), patch.object(automation, 'release_state', return_value=None), patch.object(automation.subprocess, 'run', side_effect=run):
                automation.stamp(root, '0.5.0', '2026-09-14')
                automation.publish('0.5.0', source, downloads)
                result = automation.prepare()
                self.assertEqual(result['source'], source)
                self.assertEqual(result['version'], '0.5.0')
                self.assertEqual([call[2] for call in mutations], ['create', 'upload', 'edit'])
                mutations.clear()
                with patch.object(automation, 'release_state', return_value={'isDraft': False, 'url': 'https://example.test'}):
                    automation.publish('0.5.0', source, downloads)
                self.assertEqual(mutations, [])
                self.assertEqual(git('rev-list', '--count', 'HEAD'), '2')

    def test_dev_cannot_publish(self):
        with patch.dict(os.environ, {'GITHUB_REF': 'refs/heads/dev'}), self.assertRaisesRegex(ValueError, 'main'):
            automation.publish('0.5.0', 'a' * 40, Path('unused'))
