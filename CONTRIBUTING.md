# Contributing to vela-sdk

Start a focused branch from dev and open your PR into dev. Describe the problem,
the resulting behavior and what you verified. Add meaningful tests when behavior
changes, and update CHANGELOG.md under Unreleased. Keep credentials, user data,
build output and local plans out of commits.

Install Python 3.12 and, for developer packages, Node.js 22. Then run:

```text
python -m pip install -r scripts/requirements-check.txt
python -m unittest discover -s tests
python scripts/automation.py build
python scripts/verify.py
```

Maintainers promote dev to main through a PR. The first release uses the existing
component version; later releases choose the next patch unless source or the
manual workflow input specifies a larger version. After validation, Actions commits
version/changelog metadata, creates a tag and publishes downloads with checksums.
Sync dev with main after each release. A failed run can resume its tagged version;
published assets are never overwritten. npm publication is a separate decision.

Report bugs through [issues](https://github.com/jhd3197/vela-sdk/issues).
Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).
Contributions remain under the [MIT license](LICENSE); preserve third-party notices.
See [CONTRIBUTORS.md](CONTRIBUTORS.md) and [AGENTS.md](AGENTS.md).
