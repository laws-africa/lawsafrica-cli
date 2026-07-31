# Laws.Africa CLI

`lawsafrica` is a command-line client for the Laws.Africa legislation Content
API and Knowledge Base API. It is designed for AI agents and shell automation:
API responses are emitted as raw JSON on standard output, while diagnostics go
to standard error.

Install it in an isolated environment:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install .
export LAWSAFRICA_API_KEY='your-api-key'
```

For local production access, keep the key in an untracked `prod.env` file and
load it without printing it:

```sh
set -a
source prod.env
set +a
```

## Legislation

All Content API commands are under `lawsafrica legislation`. The API resolves a
work FRBR URI to its current expression where necessary, but the CLI calls the
returned resources expressions.

Start by finding the applicable place code:

```sh
lawsafrica legislation places list
lawsafrica legislation places get za-cpt
```

List commands fetch one page by default. For a quick count, ask for one result
and use the API's `count` field. Use `--all` only when the whole result set is
needed; it follows every API-supplied pagination link.

```sh
lawsafrica legislation expressions list --place za-cpt --page-size 1
lawsafrica legislation expressions list --place za-cpt --uncommenced --page-size 1
lawsafrica legislation expressions list --place za-cpt --repealed --principal --all
```

Expression listings support exact ISO 8601 timestamps with `--created-at` and
`--updated-at`, and inclusive timestamp ranges with `--created-after`,
`--created-before`, `--updated-after`, and `--updated-before`. The CLI
validates these timestamps before contacting the API. Listings also support
`--commenced`/`--uncommenced`,
`--repealed`/`--not-repealed`, and `--principal`/`--not-principal`. Run
`lawsafrica legislation expressions list --help` for the full option list.

Fetch expression metadata, related JSON, or content with either a work or
expression FRBR URI. FRBR URIs must be absolute and begin with `/akn/`; the
CLI validates them with Cobalt before contacting the API:

```sh
lawsafrica legislation expression get /akn/za/act/1998/55
lawsafrica legislation expression versions /akn/za/act/1998/55
lawsafrica legislation expression toc /akn/za/act/1998/55
lawsafrica legislation expression content /akn/za/act/1996/constitution --format pdf --output constitution-of-south-africa.pdf
```

Content bytes stream to standard output by default. `--output FILE` writes
unchanged bytes to the file and confirms the saved path on standard error.

## Knowledge Bases

Knowledge Base commands are under `lawsafrica kb`. First list the bases this
API key may use, then inspect a base's code and send a retrieval query:

```sh
lawsafrica kb list --page-size 1
lawsafrica kb get za-legislation
lawsafrica kb retrieve za-legislation "water pollution" --top-k 5
```

`kb retrieve` exposes every filter in the API schema as an option. Each
resource filter accepts one or more values by repeating the same option; the
CLI sends those as an API `__in` filter, even for a single value:

```sh
lawsafrica kb retrieve za-legislation "municipal water services" \
  --frbr-place za-cpt --frbr-place za-jhb \
  --frbr-doctype act --uncommenced --not-repealed
```

The repeatable filters are work FRBR URI, expression FRBR URI, FRBR place,
document type, and document subtype. Work and expression FRBR URI values must
be absolute `/akn/...` URIs. The legislation-only boolean
filters are commenced, repealed, and principal. Retrieval returns the API's raw
`results` payload, including item content, metadata, and similarity score.

## API base URLs

Production endpoints are the defaults. For a compatible non-production
service, pass a base URL before the command:

```sh
lawsafrica --api-base-url https://api.example.test/v3 legislation places list
lawsafrica --kb-api-base-url https://api.example.test/ai/v1 kb list
```

`--api-base-url` is retained as an alias for `--legislation-api-base-url`.

## Development

Create a virtual environment and install the package in editable mode with test
dependencies:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
```

Unit tests use mocked HTTPX responses and never need live credentials or
network access. Run them from this directory:

```sh
PYTHONPATH=src ../.venv/bin/python -m unittest discover -s tests -v
```

If the package is installed editable in the active environment, the shorter
equivalent is:

```sh
python -m unittest discover -s tests -v
```
