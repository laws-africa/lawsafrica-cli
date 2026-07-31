# Laws.Africa CLI

[![PyPI](https://img.shields.io/pypi/v/lawsafrica-cli.svg)](https://pypi.org/project/lawsafrica-cli/)

`lawsafrica` is a command-line client for the [Laws.Africa Legal Knowledge Platform](https://laws.africa/platform/).

This CLI covers the Legislation Content API and Knowledge Base API. It is designed for AI agents and shell automation:
API responses are emitted as raw JSON on standard output, while diagnostics go to standard error.

## Get started

Create a free account at [platform.laws.africa](https://platform.laws.africa/),
then create an API key in the [API keys page](https://platform.laws.africa/api-keys/).

Install the CLI from PyPI with pip:

```sh
python -m pip install --upgrade lawsafrica-cli
```

Or run it without installing anything permanently, using [uv](https://docs.astral.sh/uv/):

```sh
uvx --from lawsafrica-cli lawsafrica --help
```

Set the API key in your shell before making API requests:

```sh
export LAWSAFRICA_API_KEY='your-api-key'
lawsafrica --help
```

With `uvx`, the same command is:

```sh
uvx --from lawsafrica-cli lawsafrica places list
```

Run `lawsafrica docs` for a short explanation of works, expressions, FRBR URIs, and links to the official developer
documentation. Command-group help also links to the relevant API reference.

## Places

Places are shared by the legislation and Knowledge Base APIs. List them to find a country or locality code, then pass it
as `--place` when listing legislation expressions or as `--frbr-place` when retrieving Knowledge Base passages:

```sh
lawsafrica places list
lawsafrica places get za-cpt
```

## Legislation

All Content API commands are under `lawsafrica legislation`. The API resolves a work FRBR URI to its current expression
where necessary, but the CLI calls the returned resources expressions.

List commands fetch one page by default. For a quick count, ask for one result and use the API's `count` field. Use
`--all` only when the whole result set is needed; it follows every API-supplied pagination link.

```sh
lawsafrica legislation expressions list --place za-cpt --page-size 1
lawsafrica legislation expressions list --place za-cpt --uncommenced --page-size 1
lawsafrica legislation expressions list --place za-cpt --repealed --principal --all
```

Expression listings support exact ISO 8601 timestamps with `--created-at` and `--updated-at`, and inclusive timestamp
ranges with `--created-after`, `--created-before`, `--updated-after`, and `--updated-before`. The CLI validates these
timestamps before contacting the API.

Listings also support `--commenced`/`--uncommenced`, `--repealed`/ `--not-repealed`, and `--principal`/
`--not-principal`. Run `lawsafrica legislation expressions list --help` for the full option list.

Fetch expression metadata, related JSON, or content with either a work or expression FRBR URI. FRBR URIs must be
absolute and begin with `/akn/`; the CLI validates them with Cobalt before contacting the API:

```sh
lawsafrica legislation expression get /akn/za/act/1998/55
lawsafrica legislation expression versions /akn/za/act/1998/55
lawsafrica legislation expression toc /akn/za/act/1998/55
lawsafrica legislation expression content /akn/za/act/1996/constitution --format pdf --output constitution-of-south-africa.pdf
```

Content bytes stream to standard output by default. `--output FILE` writes unchanged bytes to the file and confirms the
saved path on standard error.

## Knowledge Bases

Knowledge Base commands are under `lawsafrica kb`. First list the bases this API key may use, then inspect a base's code
and send a retrieval query:

```sh
lawsafrica kb list --page-size 1
lawsafrica kb get za-legislation
lawsafrica kb retrieve za-legislation "water pollution" --commenced --not-repealed --top-k 5
```

`kb retrieve` defaults to five results to keep a natural-language retrieval focused. Use `--top-k` to request from 1 to
100 results, or pass `-` as the query text to read it from standard input:

```sh
printf '%s' 'water services' | lawsafrica kb retrieve za-legislation - --top-k 3
```

The query text is a keyword or phrase search, not a question-answering prompt. Use focused text such as `water services`
or `municipal water supply`, rather than `What are the rules for water services?`. The API returns relevant passages for
the caller to interpret; it does not produce an answer.

For current-law research in a legislation Knowledge Base, normally add
`--commenced --not-repealed`. This excludes uncommenced and repealed
legislation. Omit these filters only when researching historical legislation,
drafts, or a known uncommenced instrument.

### Refine a search to its matching works

After a broad search, read the work FRBR URIs in `results[].metadata.work_frbr_uri`. Repeat `--work-frbr-uri` in a
follow-up search to limit results to those works:

```sh
lawsafrica kb retrieve za-legislation 'water services' --commenced --not-repealed --top-k 3

lawsafrica kb retrieve za-legislation 'commencement' \
  --commenced --not-repealed \
  --work-frbr-uri /akn/za/act/1997/108 \
  --work-frbr-uri /akn/za/act/1998/55
```

The filter accepts one or more work URIs and is useful for iteratively narrowing a legal research task without
introducing a title-search dependency.

`kb retrieve` exposes every filter in the API schema as an option. Each resource filter accepts one or more values by
repeating the same option; the CLI sends those as an API `__in` filter, even for a single value:

```sh
lawsafrica kb retrieve za-legislation "municipal water services" \
  --commenced --not-repealed \
  --frbr-place za-cpt --frbr-place za-jhb \
  --frbr-doctype act
```

The repeatable filters are work FRBR URI, expression FRBR URI, FRBR place, document type, and document subtype. Work and
expression FRBR URI values must be absolute `/akn/...` URIs. The legislation-only boolean filters are commenced,
repealed, and principal. Retrieval returns the API's raw `results` payload, including item content, metadata, and
similarity score.

## API base URLs

Production endpoints are the defaults. For a compatible non-production service, pass a base URL before the command:

```sh
lawsafrica --api-base-url https://api.example.test/v3 places list
lawsafrica --kb-api-base-url https://api.example.test/ai/v1 kb list
```

`--api-base-url` is retained as an alias for `--legislation-api-base-url`.

## Development

The package requires Python 3.12 or newer. Create a virtual environment and install the package in editable mode:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Unit tests use mocked HTTPX responses and never need live credentials or network access.

```sh
python -m unittest discover -s tests -v
```

## Releases

Each release uses the version in `pyproject.toml`. Before releasing, update it to the
intended [PEP 440](https://peps.python.org/pep-0440/) version, run the test suite above, and commit the release changes.

To create a release:

- update and commit the version, and push to GitHub.
- create a GitHub Release using a tag `v<version>` that matches the version in `pyproject.toml`.
- creating the release runs the publish workflow, which builds an sdist and wheel and uploads them to PyPI.
