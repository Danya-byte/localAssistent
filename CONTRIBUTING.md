# Contributing

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
python -m unittest discover -s tests -t .
```

## Development expectations

- Keep the app fully local by default.
- Preserve non-blocking UI behavior for all inference and disk operations.
- Add or update unit tests for storage, provider parsing, and service behavior when changing those layers.
- Prefer small, composable services over pushing logic into Qt widgets.

## Pull requests

- Include a concise change summary.
- Mention manual verification steps for UI-affecting changes.
- Keep Windows packaging scripts and GitHub workflows working unless the PR intentionally changes the release flow.
- If you change release artifacts or installer behavior, mention the expected output names and smoke-check results.
