"""Typer command-line interface for the Laws.Africa APIs."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import click
import typer

from .client import (
    DEFAULT_KB_API_BASE_URL,
    DEFAULT_LEGISLATION_API_BASE_URL,
    LawsAfricaAPIClient,
    LawsAfricaAPIError,
    normalize_frbr_uri,
    parse_frbr_uri,
)


app = typer.Typer(no_args_is_help=True, help="Use the Laws.Africa legislation and Knowledge Base APIs.")
legislation_app = typer.Typer(no_args_is_help=True, help="Explore legislation through the Content API.")
places_app = typer.Typer(no_args_is_help=True, help="List and inspect places.")
expressions_app = typer.Typer(no_args_is_help=True, help="List expressions across all places, or filter to one place.")
expression_app = typer.Typer(no_args_is_help=True, help="Fetch an expression and related content.")
kb_app = typer.Typer(no_args_is_help=True, help="Explore and query Knowledge Bases.")
legislation_app.add_typer(places_app, name="places")
legislation_app.add_typer(expressions_app, name="expressions")
legislation_app.add_typer(expression_app, name="expression")
app.add_typer(legislation_app, name="legislation")
app.add_typer(kb_app, name="kb")


@app.callback()
def main(
    ctx: typer.Context,
    legislation_api_base_url: str = typer.Option(
        DEFAULT_LEGISLATION_API_BASE_URL,
        "--api-base-url",
        "--legislation-api-base-url",
        help="Legislation Content API v3 base URL.",
    ),
    kb_api_base_url: str = typer.Option(
        DEFAULT_KB_API_BASE_URL,
        "--kb-api-base-url",
        help="Knowledge Base API v1 base URL.",
    ),
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["legislation_api_base_url"] = legislation_api_base_url
    ctx.obj["kb_api_base_url"] = kb_api_base_url


def _legislation_client(ctx: typer.Context) -> LawsAfricaAPIClient:
    return LawsAfricaAPIClient.from_env(ctx.obj["legislation_api_base_url"])


def _kb_client(ctx: typer.Context) -> LawsAfricaAPIClient:
    return LawsAfricaAPIClient.from_env(ctx.obj["kb_api_base_url"])


def _emit_json(value: Any) -> None:
    typer.echo(json.dumps(value, ensure_ascii=False, indent=2))


def _exit_for_error(error: Exception) -> None:
    typer.echo(f"Error: {error}", err=True)
    raise typer.Exit(code=1)


def _optional_params(**values: Any) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _iso8601_timestamp(ctx: click.Context, param: click.Parameter, value: Optional[str]) -> Optional[str]:
    """Validate a flexible ISO 8601 timestamp while preserving its input form."""
    if value is None:
        return None
    try:
        datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError as error:
        raise typer.BadParameter("must be an ISO 8601 timestamp", ctx=ctx, param=param) from error
    return value


def _frbr_uri_argument(ctx: click.Context, param: click.Parameter, value: Optional[str]) -> Optional[str]:
    """Validate an FRBR URI before constructing an API client."""
    if value is None:
        return None
    try:
        return parse_frbr_uri(value)
    except LawsAfricaAPIError as error:
        raise typer.BadParameter(str(error), ctx=ctx, param=param) from error


def _frbr_uri_options(ctx: click.Context, param: click.Parameter, values: list[str]) -> list[str]:
    """Validate repeated FRBR URI options before constructing an API client."""
    try:
        return [parse_frbr_uri(value) for value in values]
    except LawsAfricaAPIError as error:
        raise typer.BadParameter(str(error), ctx=ctx, param=param) from error


def _page_params(page: Optional[int], page_size: Optional[int]) -> dict[str, int]:
    return _optional_params(page=page, page_size=page_size)


@places_app.command("list")
def list_places(
    ctx: typer.Context,
    page: Optional[int] = typer.Option(None, min=1),
    page_size: Optional[int] = typer.Option(None, min=1),
    all_pages: bool = typer.Option(False, "--all", help="Fetch every result page."),
) -> None:
    """List countries and localities available through the legislation API."""
    try:
        with _legislation_client(ctx) as client:
            _emit_json(client.list_json("places", _page_params(page, page_size), all_pages=all_pages))
    except LawsAfricaAPIError as error:
        _exit_for_error(error)


@places_app.command("get")
def get_place(ctx: typer.Context, place: str) -> None:
    """Fetch a place by its country or locality code."""
    try:
        with _legislation_client(ctx) as client:
            _emit_json(client.get_json(f"places/{place}"))
    except LawsAfricaAPIError as error:
        _exit_for_error(error)


@expressions_app.command("list")
def list_expressions(
    ctx: typer.Context,
    place: Optional[str] = typer.Option(None, "--place", help="Country or locality code."),
    created_at: Optional[str] = typer.Option(None, callback=_iso8601_timestamp, help="Exact ISO 8601 timestamp."),
    created_after: Optional[str] = typer.Option(None, "--created-after", callback=_iso8601_timestamp, help="ISO 8601 timestamp, inclusive."),
    created_before: Optional[str] = typer.Option(None, "--created-before", callback=_iso8601_timestamp, help="ISO 8601 timestamp, inclusive."),
    updated_at: Optional[str] = typer.Option(None, callback=_iso8601_timestamp, help="Exact ISO 8601 timestamp."),
    updated_after: Optional[str] = typer.Option(None, "--updated-after", callback=_iso8601_timestamp, help="ISO 8601 timestamp, inclusive."),
    updated_before: Optional[str] = typer.Option(None, "--updated-before", callback=_iso8601_timestamp, help="ISO 8601 timestamp, inclusive."),
    commenced: Optional[bool] = typer.Option(
        None, "--commenced/--uncommenced", help="Filter by a work's commencement status."
    ),
    repealed: Optional[bool] = typer.Option(
        None, "--repealed/--not-repealed", help="Filter by whether a work has been repealed."
    ),
    principal: Optional[bool] = typer.Option(
        None, "--principal/--not-principal", help="Filter by whether a work is principal."
    ),
    page: Optional[int] = typer.Option(None, min=1),
    page_size: Optional[int] = typer.Option(None, min=1),
    all_pages: bool = typer.Option(False, "--all", help="Fetch every result page."),
) -> None:
    """List expressions across all places, or filter to one place."""
    params = _optional_params(
        created_at=created_at,
        created_at__gte=created_after,
        created_at__lte=created_before,
        updated_at=updated_at,
        updated_at__gte=updated_after,
        updated_at__lte=updated_before,
        commenced=commenced,
        repealed=repealed,
        principal=principal,
        **_page_params(page, page_size),
    )
    path = f"places/{place}/work-expressions" if place else "work-expressions"
    try:
        with _legislation_client(ctx) as client:
            _emit_json(client.list_json(path, params, all_pages=all_pages))
    except LawsAfricaAPIError as error:
        _exit_for_error(error)


def _expression_json(client: LawsAfricaAPIClient, frbr_uri: str) -> Any:
    return client.get_json(f"{normalize_frbr_uri(frbr_uri)}.json")


@expression_app.command("get")
def get_expression(
    ctx: typer.Context,
    frbr_uri: str = typer.Argument(..., callback=_frbr_uri_argument, help="Absolute FRBR URI beginning with '/akn/'."),
) -> None:
    """Fetch an expression's JSON metadata."""
    try:
        with _legislation_client(ctx) as client:
            _emit_json(_expression_json(client, frbr_uri))
    except LawsAfricaAPIError as error:
        _exit_for_error(error)


@expression_app.command("versions")
def expression_versions(
    ctx: typer.Context,
    frbr_uri: str = typer.Argument(..., callback=_frbr_uri_argument, help="Absolute FRBR URI beginning with '/akn/'."),
) -> None:
    """Fetch all dated/language expressions listed by an expression's metadata."""
    try:
        with _legislation_client(ctx) as client:
            metadata = _expression_json(client, frbr_uri)
            points_in_time = metadata.get("points_in_time", [])
            if not isinstance(points_in_time, list):
                raise LawsAfricaAPIError("Expression metadata contained invalid points_in_time data.")
            expressions = []
            for point in points_in_time:
                if not isinstance(point, dict) or not isinstance(point.get("expressions"), list):
                    raise LawsAfricaAPIError("Expression metadata contained invalid expression references.")
                for reference in point["expressions"]:
                    if not isinstance(reference, dict) or not isinstance(reference.get("expression_frbr_uri"), str):
                        raise LawsAfricaAPIError("Expression metadata contained an invalid expression FRBR URI.")
                    expressions.append(_expression_json(client, reference["expression_frbr_uri"]))
            _emit_json({"metadata": metadata, "expressions": expressions})
    except LawsAfricaAPIError as error:
        _exit_for_error(error)


def _expression_detail_command(name: str, endpoint: str, help_text: str) -> None:
    @expression_app.command(name, help=help_text)
    def detail(
        ctx: typer.Context,
        frbr_uri: str = typer.Argument(..., callback=_frbr_uri_argument, help="Absolute FRBR URI beginning with '/akn/'."),
    ) -> None:
        try:
            with _legislation_client(ctx) as client:
                uri = normalize_frbr_uri(frbr_uri)
                _emit_json(client.get_json(f"{uri}/{endpoint}.json"))
        except LawsAfricaAPIError as error:
            _exit_for_error(error)


_expression_detail_command("toc", "toc", "Fetch an expression table of contents.")
_expression_detail_command("commencements", "commencements", "Fetch commencement data.")
_expression_detail_command("timeline", "timeline", "Fetch expression timeline data.")


@expression_app.command("content")
def expression_content(
    ctx: typer.Context,
    frbr_uri: str = typer.Argument(..., callback=_frbr_uri_argument, help="Absolute FRBR URI beginning with '/akn/'."),
    format: str = typer.Option(..., "--format", help="One of: xml, html, pdf, epub, zip."),
    output: Optional[Path] = typer.Option(None, "--output", help="Write bytes to this file."),
    resolver: Optional[str] = typer.Option(None, help="HTML reference resolver URL or 'none'."),
    media_url: Optional[str] = typer.Option(None, "--media-url", help="HTML embedded-media URL prefix."),
    coverpage: Optional[bool] = typer.Option(None, "--coverpage/--no-coverpage", help="Include an HTML cover page."),
    standalone: bool = typer.Option(False, "--standalone", help="Generate standalone HTML."),
) -> None:
    """Fetch expression content as XML, HTML, PDF, EPUB, or ZIP."""
    format = format.lower()
    if format not in {"xml", "html", "pdf", "epub", "zip"}:
        raise typer.BadParameter("must be one of: xml, html, pdf, epub, zip", param_hint="--format")
    params = {"format": format}
    if format == "html":
        params.update(_optional_params(resolver=resolver, **{"media-url": media_url}))
        if coverpage is not None:
            params["coverpage"] = "1" if coverpage else "0"
        if standalone:
            params["standalone"] = "1"
    try:
        with _legislation_client(ctx) as client:
            content = client.get_bytes(normalize_frbr_uri(frbr_uri), params)
        if output:
            output.write_bytes(content)
            typer.echo(f"Saved {format.upper()} ({len(content)} bytes) to {output}", err=True)
        else:
            stream = click.get_binary_stream("stdout")
            stream.write(content)
            stream.flush()
    except LawsAfricaAPIError as error:
        _exit_for_error(error)


@kb_app.command("list")
def list_knowledge_bases(
    ctx: typer.Context,
    page: Optional[int] = typer.Option(None, min=1),
    page_size: Optional[int] = typer.Option(None, min=1),
    all_pages: bool = typer.Option(False, "--all", help="Fetch every result page."),
) -> None:
    """List the Knowledge Bases available to this API key."""
    try:
        with _kb_client(ctx) as client:
            _emit_json(client.list_json("knowledge-bases", _page_params(page, page_size), all_pages=all_pages))
    except LawsAfricaAPIError as error:
        _exit_for_error(error)


@kb_app.command("get")
def get_knowledge_base(ctx: typer.Context, code: str) -> None:
    """Fetch a Knowledge Base's metadata by code."""
    try:
        with _kb_client(ctx) as client:
            _emit_json(client.get_json(f"knowledge-bases/{code}"))
    except LawsAfricaAPIError as error:
        _exit_for_error(error)


def _kb_filters(
    *,
    work_frbr_uris: list[str],
    expression_frbr_uris: list[str],
    frbr_places: list[str],
    frbr_doctypes: list[str],
    frbr_subtypes: list[str],
    repealed: Optional[bool],
    commenced: Optional[bool],
    principal: Optional[bool],
) -> dict[str, Any]:
    """Build the Knowledge Base API's optional nested filters object."""
    filters = _optional_params(
        repealed=repealed,
        commenced=commenced,
        principal=principal,
    )
    for name, values in {
        "work_frbr_uri__in": work_frbr_uris,
        "expression_frbr_uri__in": expression_frbr_uris,
        "frbr_place__in": frbr_places,
        "frbr_doctype__in": frbr_doctypes,
        "frbr_subtype__in": frbr_subtypes,
    }.items():
        if values:
            filters[name] = values
    return filters


@kb_app.command("retrieve")
def retrieve_knowledge_base(
    ctx: typer.Context,
    code: str = typer.Argument(help="Knowledge Base code."),
    text: str = typer.Argument(help="Text to find matching items for."),
    top_k: int = typer.Option(10, min=1, max=100, help="Number of results to return."),
    work_frbr_uri: list[str] = typer.Option([], callback=_frbr_uri_options, help="Limit to these work FRBR URIs; repeat the option."),
    expression_frbr_uri: list[str] = typer.Option([], callback=_frbr_uri_options, help="Limit to these expression FRBR URIs; repeat the option."),
    frbr_place: list[str] = typer.Option([], help="Limit to these FRBR place codes; repeat the option."),
    frbr_doctype: list[str] = typer.Option([], help="Limit to these FRBR document types; repeat the option."),
    frbr_subtype: list[str] = typer.Option([], help="Limit to these FRBR document subtypes; repeat the option."),
    repealed: Optional[bool] = typer.Option(None, "--repealed/--not-repealed", help="Filter legislation by repeal status."),
    commenced: Optional[bool] = typer.Option(None, "--commenced/--uncommenced", help="Filter legislation by commencement status."),
    principal: Optional[bool] = typer.Option(None, "--principal/--not-principal", help="Filter legislation by principal-work status."),
) -> None:
    """Retrieve the most relevant items from a Knowledge Base."""
    filters = _kb_filters(
        work_frbr_uris=work_frbr_uri,
        expression_frbr_uris=expression_frbr_uri,
        frbr_places=frbr_place,
        frbr_doctypes=frbr_doctype,
        frbr_subtypes=frbr_subtype,
        repealed=repealed,
        commenced=commenced,
        principal=principal,
    )
    payload: dict[str, Any] = {"text": text, "top_k": top_k}
    if filters:
        payload["filters"] = filters
    try:
        with _kb_client(ctx) as client:
            _emit_json(client.post_json(f"knowledge-bases/{code}/retrieve", payload))
    except LawsAfricaAPIError as error:
        _exit_for_error(error)


if __name__ == "__main__":
    app()
