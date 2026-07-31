# AGENTS.md

## Project Purpose

This is a standalone Python command-line client for the Laws.Africa Knowledge
Base API. The Python distribution is `lawsafrica-cli`, the import package is
`lawsafrica_cli`, and the installed executable is `lawsafrica`.

Use expression terminology consistently. The API may resolve a work FRBR URI to
the latest expression, but CLI commands should describe the returned resources
as expressions.

## Environment

Use Python 3.10 or newer. From this directory, either create a local virtual
environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
```

## API Credentials

The CLI reads live API credentials only from `LAWSAFRICA_API_KEY`. Do not add
token flags, prompt for keys, or print key values in logs, errors, tests, or
examples.

`prod.env` may contain a production key for local manual testing. It is ignored
by git. Load it without printing it:

```bash
set -a
source prod.env
set +a
```

Unit tests must not require live credentials or network access.

## Commands And Output

Keep the `lawsafrica` command friendly to AI agents and shell automation:

- JSON responses go to stdout.
- Binary content streams to stdout unless `--output FILE` is provided.
- Diagnostics and save confirmations go to stderr.
- List commands fetch one page by default and use `--all` to follow pagination.
- API filters should be exposed as normal options on the relevant listing
  command, not hidden behind custom summary commands.
- Preserve API field names and raw JSON shape unless the command explicitly
  documents otherwise.

## Testing

Run the focused test suite from this directory:

```bash
PYTHONPATH=src ../.venv/bin/python -m unittest discover -s tests -v
```

If the package is installed in editable mode in the active virtual environment,
this is equivalent:

```bash
python -m unittest discover -s tests -v
```

For CLI changes, cover command routing, query parameters, pagination, error
messages, and stdout/stderr behaviour with mocked HTTPX responses.

## Git

This directory is its own git repository. Do not commit unless the user asks.
Do not add `prod.env`, caches, downloaded content, generated PDFs, or other
manual testing artifacts.
