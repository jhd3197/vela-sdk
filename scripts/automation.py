"""Build and publish this Vela component after a reviewed main update."""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent.parent
def settings(root=None):
    return json.loads(((root or ROOT) / 'release.json').read_text(encoding='utf-8'))


def version_file(root=None):
    return settings(root)['version_file']


def current_version(root=None):
    return json.loads(((root or ROOT) / version_file(root)).read_text(encoding='utf-8'))['version']


def release_files():
    return (version_file(), 'CHANGELOG.md')



def version_tuple(value):
    if not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', value):
        raise ValueError('Version must be MAJOR.MINOR.PATCH, without a v prefix or suffix')
    return tuple(map(int, value.split('.')))


def next_version(current, tags, requested=''):
    version_tuple(current)
    versions = [version_tuple(tag[1:]) for tag in tags if re.fullmatch(r'v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', tag)]
    latest = max(versions, default=None)
    if requested:
        chosen = version_tuple(requested)
        if latest is not None and chosen <= latest:
            raise ValueError('A new release version must be greater than existing release tags')
        return requested
    if latest is None or version_tuple(current) > latest:
        return current
    return '.'.join(map(str, (*latest[:2], latest[2] + 1)))


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True, encoding='utf-8').strip()


def tag_source(tag):
    message = git('for-each-ref', f'refs/tags/{tag}', '--format=%(contents)')
    match = re.search(r'^Source-Commit: ([a-f0-9]{40})$', message, re.M)
    return match[1] if match else None


def prepare(requested=''):
    source = git('rev-parse', 'HEAD')
    tags = [tag for tag in git('tag', '--list', 'v*').splitlines()
            if re.fullmatch(r'v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', tag)]
    matches = [tag for tag in tags if tag_source(tag) == source or git('rev-parse', f'{tag}^{{commit}}') == source]
    if requested:
        version_tuple(requested)
        matches = [tag for tag in matches if tag == 'v' + requested]
    if matches:
        # A retry uses the original immutable release commit and version.
        tag = max(matches, key=lambda item: version_tuple(item[1:]))
        build_ref = git('rev-parse', f'{tag}^{{commit}}')
        source = tag_source(tag) or source
        changelog = git('show', f'{build_ref}:CHANGELOG.md')
        match = re.search(r'^## ' + re.escape(tag[1:]) + r' - (\d{4}-\d{2}-\d{2})$', changelog, re.M)
        if not match:
            raise ValueError('Existing tag has no matching release changelog; refusing to replace it')
        result = {'version': tag[1:], 'tag': tag, 'source': source, 'build_ref': build_ref, 'date': match[1]}
    else:
        current = current_version()
        version = next_version(current, tags, requested)
        result = {'version': version, 'tag': 'v' + version, 'source': source, 'build_ref': source,
                  'date': datetime.now(timezone.utc).date().isoformat()}
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
            for key, value in result.items():
                output.write(f'{key}={value}\n')
    print(json.dumps(result))
    return result


def stamp(root, version, release_date):
    version_tuple(version)
    date.fromisoformat(release_date)
    path = root / version_file(root)
    metadata = json.loads(path.read_text(encoding='utf-8'))
    metadata['version'] = version
    path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    path = root / 'CHANGELOG.md'
    text = path.read_text(encoding='utf-8')
    if re.search(r'^## ' + re.escape(version) + r' - ', text, re.M):
        return  # Rebuilding an existing release must not move newer Unreleased notes.
    match = re.search(r'^## Unreleased\s*\n', text, re.M)
    if not match:
        raise ValueError('CHANGELOG.md must have an Unreleased section')
    rest = text[match.end():]
    following = re.search(r'^## ', rest, re.M)
    body = rest[:following.start()].strip() if following else rest.strip()
    history = rest[following.start():] if following else ''
    if not body:
        body = 'No additional release notes were provided.'
    text = text[:match.start()] + f'## Unreleased\n\n## {version} - {release_date}\n\n{body}\n\n' + history
    path.write_text(text.rstrip() + '\n', encoding='utf-8', newline='\n')


def asset_names(version):
    config = settings()
    if config['kind'] == 'npm':
        package = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))
        names = [package['name'].lstrip('@').replace('/', '-') + '-' + version + '.tgz']
    elif config['kind'] == 'app':
        names = [config['app_dir'] + '-' + version + '.zip']
    else:
        names = [config['repository'] + '-' + version + '.zip']
        if config['kind'] == 'catalog':
            names.append('index.json')
    return names


def validate_assets(directory, version):
    version_tuple(version)
    expected_names = {name + suffix for name in asset_names(version) for suffix in ('', '.sha256')}
    if {path.name for path in directory.iterdir() if path.is_file()} != expected_names:
        raise ValueError('Release asset set does not match the expected names/version')
    for name in asset_names(version):
        asset = directory / name
        digest = hashlib.sha256(asset.read_bytes()).hexdigest()
        if (directory / (name + '.sha256')).read_text(encoding='utf-8').split() != [digest, name]:
            raise ValueError('Checksum or filename mismatch: ' + name)
    return [directory / name for name in sorted(expected_names)]


def zip_files(destination, files):
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(files):
            if path.is_symlink():
                raise ValueError('Release source contains a symlink: ' + str(path))
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def build():
    config = settings()
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    names = asset_names(current_version())
    if config['kind'] == 'npm':
        subprocess.run([shutil.which('npm.cmd' if os.name == 'nt' else 'npm'), 'pack', '--pack-destination', str(output)], cwd=ROOT, check=True)
    elif config['kind'] == 'app':
        source = ROOT / config['app_dir']
        files = [(str(path.relative_to(source).as_posix()), path) for path in source.rglob('*') if path.is_file()]
        files.append(('LICENSE', ROOT / 'LICENSE'))
        zip_files(output / names[0], files)
    elif config['kind'] == 'templates':
        files = [(str(path.relative_to(ROOT).as_posix()), path) for folder in ('starters', 'recipes') for path in (ROOT / folder).rglob('*') if path.is_file()]
        files.extend((name, ROOT / name) for name in ('LICENSE', 'README.md'))
        zip_files(output / names[0], files)
    elif config['kind'] == 'catalog':
        subprocess.run([os.sys.executable, str(ROOT / 'build_catalog.py'), '--build'], cwd=ROOT, check=True)
        site = output / 'site'
        zip_files(output / names[0], [(str(path.relative_to(site).as_posix()), path) for path in site.rglob('*') if path.is_file()])
        shutil.copy2(site / 'index.json', output / 'index.json')
    else:
        raise ValueError('Unknown release kind')
    for name in names:
        digest = hashlib.sha256((output / name).read_bytes()).hexdigest()
        (output / (name + '.sha256')).write_text(digest + '  ' + name + '\n', encoding='utf-8')
    validate_assets(output, current_version())


def release_state(repo, tag):
    result = subprocess.run(['gh', 'release', 'view', tag, '--repo', repo, '--json', 'isDraft,url'],
                            capture_output=True, text=True, encoding='utf-8')
    if result.returncode == 0:
        return json.loads(result.stdout)
    if 'release not found' in result.stderr.lower() or 'HTTP 404' in result.stderr:
        return None
    raise RuntimeError(result.stderr.strip())


def publish(version, source, directory):
    if os.environ.get('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('Releases may only be published from main')
    repo = os.environ['GITHUB_REPOSITORY']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo) or not re.fullmatch('[a-f0-9]{40}', source):
        raise ValueError('Invalid repository or source commit')
    assets = validate_assets(directory, version)
    tag = 'v' + version
    git('fetch', 'origin', 'main', '--tags')
    existing = tag in git('tag', '--list', tag).splitlines()
    if existing:
        if tag_source(tag) != source:
            raise ValueError('Existing tag belongs to another source commit; refusing to move it')
        if git('rev-parse', 'HEAD') != git('rev-parse', f'{tag}^{{commit}}'):
            raise ValueError('Retry must use the existing release commit')
    else:
        if git('rev-parse', 'origin/main') != source:
            raise ValueError('main advanced during the build; run the workflow on current main')
        git('config', 'user.name', 'github-actions[bot]')
        git('config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
        git('add', *release_files())
        git('commit', '-m', f'chore(release): {tag} [skip ci]')
        git('tag', '-a', tag, '-m', f'Vela {tag}\n\nSource-Commit: {source}')
        # Atomically update both refs; never force main or move an existing tag.
        git('push', '--atomic', 'origin', 'HEAD:main', f'refs/tags/{tag}')
    state = release_state(repo, tag)
    if state and not state['isDraft']:
        print('Already published; leaving release assets unchanged: ' + state['url'])
        return
    changelog = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    match = re.search(r'^## ' + re.escape(version) + r' - [^\n]+\n(.*?)(?=^## |\Z)', changelog, re.M | re.S)
    if not match:
        raise ValueError('Release changelog section is missing')
    notes = ROOT / '.local/release-notes.md'
    notes.parent.mkdir(exist_ok=True)
    downloads = '\n'.join(f'- [{asset.name}](https://github.com/{repo}/releases/download/{tag}/{asset.name})'
                          for asset in assets if not asset.name.endswith('.sha256'))
    config = settings()
    instructions = ('Download the app ZIP and import it through Vela Library. Review its permissions before installing.'
                    if config['kind'] == 'app' else
                    'Download the package archive. See the repository README for installation and usage. npm registry publication is separate.'
                    if config['kind'] == 'npm' else
                    'Download the archive and follow the repository README. Checksums are attached for verification.')
    notes.write_text(f"# {config['repository']} {tag}\n\n{match[1].strip()}\n\n## Downloads\n\n{downloads}\n\n{instructions}\n", encoding='utf-8')
    def gh(*args):
        subprocess.run(['gh', 'release', *args, '--repo', repo], check=True)
    if state is None:
        gh('create', tag, '--verify-tag', '--draft', '--title', f"{config['repository']} {tag}", '--notes-file', str(notes))
    gh('upload', tag, *map(str, assets), '--clobber')  # Only a draft can reach this point.
    gh('edit', tag, '--notes-file', str(notes), '--draft=false', '--latest')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('build')
    commands.add_parser('prepare').add_argument('--version', default='')
    stamp_parser = commands.add_parser('stamp')
    stamp_parser.add_argument('--version', required=True)
    stamp_parser.add_argument('--date', required=True)
    publish_parser = commands.add_parser('publish')
    publish_parser.add_argument('--version', required=True)
    publish_parser.add_argument('--source', required=True)
    publish_parser.add_argument('--artifacts', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'build':
        build()
    elif args.command == 'prepare':
        prepare(args.version)
    elif args.command == 'stamp':
        stamp(ROOT, args.version, args.date)
    else:
        publish(args.version, args.source, args.artifacts)


if __name__ == '__main__':
    main()
