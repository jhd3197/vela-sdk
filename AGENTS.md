# Working on vela-sdk

This repository belongs to the Vela ecosystem. Keep app, SDK, generator, catalog
and server responsibilities in their own repositories. Do not recreate the old monorepo.

Work on dev or a feature branch targeting dev. Maintainers review dev → main PRs;
main pushes automatically build, validate, version and publish GitHub downloads.
Do not publish npm packages without explicit authorization and confirmed scope access.
Keep routine version changes with the release automation; use a manual release
version input only for a deliberate major/minor change.

Update CHANGELOG.md under Unreleased for user, installation, compatibility,
documentation or contributor changes. Group meaningful entries under Added,
Changed, Deprecated, Removed, Fixed or Security. Do not invent releases, dates,
test results or contributor credits. The workflow moves notes into a dated release.

Keep plans under ignored plans/ and scratch output under .local/ or dist/.
Do not commit generated archives, credentials or app data. Preserve the MIT license,
existing donation destinations/QR images and actual contributor attribution.

Use disposable data. Run `python -m unittest discover -s tests`,
`python scripts/automation.py build`, and `python scripts/verify.py` for code or
packaging changes. Install scripts/requirements-check.txt first. Node 22 is needed
for npm components. For docs-only edits, check links and exclusions instead.
SDK/schema changes must also be reviewed and explicitly adopted by the Vela hub;
this repository cannot silently update the hub's vendored runtime.
