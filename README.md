# Laws.Africa CLI

A command-line client for the Laws.Africa Knowledge Base API.

Install it in an isolated environment, then activate that environment before
running the command:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install .
export LAWSAFRICA_API_KEY='your-api-key'
lawsafrica places list
```

For local production access, keep the key in an untracked `prod.env` file and
load it without printing it:

```sh
set -a
source prod.env
set +a
lawsafrica places list
```

The CLI writes JSON and binary content to standard output, and diagnostics to
standard error. When `expression content --output FILE` succeeds, it confirms
the saved path, byte count, and format on standard error.

Start by finding the place code you need:

```sh
lawsafrica places list
lawsafrica places get za-cpt
```

There is no title search in the API. List commands return one page by default;
use `--all` when a workflow needs the complete result set. This can be large.

For an agent workflow concerning Cape Town, request a one-item page and read
the response's API-supplied `count`. The same filters apply to global and
place-specific expression listings:

```sh
lawsafrica expressions list --place za-cpt --page-size 1
lawsafrica expressions list --place za-cpt --uncommenced --page-size 1
lawsafrica expressions list --place za-cpt --repealed --principal --all
```

Run `lawsafrica expressions list --help` to see the full set of API
filters: created/updated timestamp ranges, commenced/uncommenced,
repealed/not-repealed, and principal/not-principal.

Fetch metadata, related data, or content using either a work or expression
FRBR URI. The API resolves a work URI to its current expression:

```sh
lawsafrica expression get /akn/za/act/1998/55
lawsafrica expression versions /akn/za/act/1998/55
lawsafrica expression toc /akn/za/act/1998/55
lawsafrica expression content /akn/za/act/1998/55 --format pdf --output act-55.pdf
```

For example, retrieve the current English South African Constitution PDF:

```sh
lawsafrica expression content /akn/za/act/1996/constitution --format pdf --output constitution-of-south-africa.pdf
```

Use `--api-base-url` to target a compatible non-production API during
development.

## Development

Create a virtual environment and install the package in editable mode with test
dependencies:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
```

Set an API key only for commands that talk to the live API. Unit tests use
mocked HTTPX responses and do not need credentials:

```sh
export LAWSAFRICA_API_KEY='your-api-key'
```

For local production testing, keep the key in `prod.env`. It is ignored by git:

```sh
set -a
source prod.env
set +a
```

Run the test suite from this directory:

```sh
PYTHONPATH=src ../.venv/bin/python -m unittest discover -s tests -v
```

If you installed the package in editable mode into the active virtual
environment, this shorter command is equivalent:

```sh
python -m unittest discover -s tests -v
```
