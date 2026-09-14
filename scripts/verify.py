"""Check the distributable outside its checkout and validate app file boundaries."""
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import tempfile
import zipfile

from jsonschema import Draft202012Validator
import automation

ROOT = Path(__file__).resolve().parent.parent


def app_check(folder):
    manifest = json.loads((folder / 'app.json').read_text(encoding='utf-8'))
    schema = json.loads((ROOT / 'scripts/manifest-v2.schema.json').read_text(encoding='utf-8'))
    Draft202012Validator(schema).validate(manifest)
    paths = [manifest['runtime']['static']['entry']]
    if manifest.get('icon'):
        paths.append(manifest['icon'])
    data = manifest.get('data', {})
    schemas = [data['schema']] if data.get('schema') else []
    if data.get('legacy', {}).get('schema'):
        schemas.append(data['legacy']['schema'])
    for action in manifest.get('actions', []):
        schemas.extend([action['inputSchema'], action['outputSchema']])
    for name in paths + schemas:
        path = (folder / name).resolve()
        assert path.is_relative_to(folder.resolve()) and path.is_file(), 'Missing/unsafe app file: ' + name
    for name in schemas:
        Draft202012Validator.check_schema(json.loads((folder / name).read_text(encoding='utf-8')))
    return manifest


def unpack_zip(path, destination):
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            parts = PurePosixPath(name)
            assert not parts.is_absolute() and '..' not in parts.parts and '\\' not in name
        archive.extractall(destination)


def main():
    config = automation.settings()
    automation.validate_assets(ROOT / 'dist', automation.current_version())
    archive = ROOT / 'dist' / automation.asset_names(automation.current_version())[0]
    with tempfile.TemporaryDirectory(prefix='vela-component-check-') as temporary:
        work = Path(temporary)
        if config['kind'] == 'npm':
            with tarfile.open(archive) as tar:
                assert not any('/node_modules/' in n or n.endswith('/host.js') or '/.git/' in n for n in tar.getnames())
                tar.extractall(work, filter='data')
            package = work / 'package'
            metadata = json.loads((package / 'package.json').read_text())
            assert metadata['version'] == automation.current_version()
            assert (package / 'LICENSE').is_file()
            if config['repository'] == 'vela-contracts':
                schema = json.loads((package / 'manifest-v2.schema.json').read_text())
                Draft202012Validator.check_schema(schema)
                assert schema['properties']['schemaVersion']['const'] == 2
            elif config['repository'] == 'vela-sdk':
                subprocess.run(['node', '--check', str(package / 'vela.js')], check=True)
                assert not (package / 'host.js').exists()
            else:
                for mode in ('hub', 'compact', 'seamless'):
                    app = work / mode
                    subprocess.run(['node', str(package / 'cli.mjs'), 'my-' + mode, str(app), mode], check=True)
                    assert app_check(app)['view']['chrome'] == mode
                    repeat = subprocess.run(['node', str(package / 'cli.mjs'), 'my-' + mode, str(app)], capture_output=True)
                    assert repeat.returncode != 0, 'Generator overwrote an existing folder'
        else:
            unpack_zip(archive, work)
            assert (work / 'LICENSE').is_file()
            if config['kind'] == 'app':
                assert app_check(work)['version'] == automation.current_version()
            elif config['kind'] == 'templates':
                for starter in (work / 'starters').iterdir():
                    app_check(starter)
            else:
                index = json.loads((work / 'index.json').read_text(encoding='utf-8'))
                assert index['schemaVersion'] == 1 and len(index['releases']) >= 1
                seen = set()
                import hashlib
                for release in index['releases']:
                    assert release['manifest']['id'] not in seen
                    seen.add(release['manifest']['id'])
                    app_archive = (work / release['archive']).resolve()
                    assert app_archive.is_relative_to(work.resolve())
                    assert hashlib.sha256(app_archive.read_bytes()).hexdigest() == release['sha256']
                    app = work / ('verified-' + release['manifest']['id'])
                    unpack_zip(app_archive, app)
                    assert app_check(app) == release['manifest']
    print('PASS: ' + config['repository'] + ' distributable validates outside its source checkout')


if __name__ == '__main__':
    main()
