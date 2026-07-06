# Contributing

## Development setup

```bash
git clone <repo-url>
cd branchsync
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Common commands

```bash
pytest
branchsync --help
```

## Pull requests

- Keep changes focused
- Add or update tests when behavior changes
- Update `README.md` when CLI usage changes
- Update `CHANGELOG.md` for user-facing changes

