"""Typer command-line interface for the Laws.Africa APIs."""

from __future__ import annotations

import json
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
)


app = typer.Typer(no_args_is_help=True, help="Use the Laws.Africa legislation and Knowledge Base APIs.")
legislation_app = typer.Typer(no_args_is_help=True, help="Explore legislation through the Content API.")
places_app = typer.Typer(no_args_is_help=True, help="List and inspect places.")
expressions_app = typer.Typer(no_args_is_help=True, help="List expressions.")
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


def _page_params(page: Optional[int], page_size: Optional[int]) -> dict[str, int]:
    return _optional_params(page=page, page_size=page_size)


@places_app.command("list")
def list_places(
    ctx: typer.Context,
    page: Optional[int] = typer.Option(None, min=1),
    page_size: Optional[int] = typer.Option(None, min=1),
    all_pages: bool = typer.Option(False, "--all", help="Fetch every result page."),
) -> None:
    try:
        with _legislation_client(ctx) as client:
            _emit_json(client.list_json("places", _page_params(page, page_size), all_pages=all_pages))
    except LawsAfricaAPIError as error:
        _exit_for_error(error)


@places_app.command("get")
def get_place(ctx: typer.Context, place: str) -> None:
    try:
        with _legislation_client(ctx) as client:
            _emit_json(client.get_json(f"places/{place}"))
    except LawsAfricaAPIError as error:
        _exit_for_error(error)


@expressions_app.command("list")
def list_expressions(
    ctx: typer.Context,
    place: Optional[str] = typer.Option(None, "--place", help="Country or locality code."),
    created_at: Optional[str] = typer.Option(None),
    created_at_gte: Optional[str] = typer.Option(None, "--created-at-gte"),
    created_at_lte: Optional[str] = typer.Option(None, "--created-at-lte"),
    updated_at: Optional[str] = typer.Option(None),
    updated_at_gte: Optional[str] = typer.Option(None, "--updated-at-gte"),
    updated_at_lte: Optional[str] = typer.Option(None, "--updated-at-lte"),
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
    params = _optional_params(
        created_at=created_at,
        created_at__gte=created_at_gte,
        created_at__lte=created_at_lte,
        updated_at=updated_at,
        updated_at__gte=updated_at_gte,
        updated_at__lte=updated_at_lte,
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
def get_expression(ctx: typer.Context, frbr_uri: str) -> None:
    try:
        with _legislation_client(ctx) as client:
            _emit_json(_expression_json(client, frbr_uri))
    except LawsAfricaAPIError as error:
        _exit_for_error(error)


@expression_app.command("versions")
def expression_versions(ctx: typer.Context, frbr_uri: str) -> None:
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
    def detail(ctx: typer.Context, frbr_uri: str) -> None:
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
    frbr_uri: str,
    format: str = typer.Option(..., "--format", help="One of: xml, html, pdf, epub, zip."),
    output: Optional[Path] = typer.Option(None, "--output", help="Write bytes to this file."),
    resolver: Optional[str] = typer.Option(None, help="HTML reference resolver URL or 'none'."),
    media_url: Optional[str] = typer.Option(None, "--media-url", help="HTML embedded-media URL prefix."),
    coverpage: Optional[bool] = typer.Option(None, "--coverpage/--no-coverpage", help="Include an HTML cover page."),
    standalone: bool = typer.Option(False, "--standalone", help="Generate standalone HTML."),
) -> None:
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
    work_frbr_uri: Optional[str],
    work_frbr_uri_in: list[str],
    expression_frbr_uri: Optional[str],
    expression_frbr_uri_in: list[str],
    frbr_place: Optional[str],
    frbr_place_in: list[str],
    frbr_doctype: Optional[str],
    frbr_doctype_in: list[str],
    frbr_subtype: Optional[str],
    frbr_subtype_in: list[str],
    repealed: Optional[bool],
    commenced: Optional[bool],
    principal: Optional[bool],
) -> dict[str, Any]:
    """Build the Knowledge Base API's optional nested filters object."""
    filters = _optional_params(
        work_frbr_uri=work_frbr_uri,
        expression_frbr_uri=expression_frbr_uri,
        frbr_place=frbr_place,
        frbr_doctype=frbr_doctype,
        frbr_subtype=frbr_subtype,
        repealed=repealed,
        commenced=commenced,
        principal=principal,
    )
    for name, values in {
        "work_frbr_uri__in": work_frbr_uri_in,
        "expression_frbr_uri__in": expression_frbr_uri_in,
        "frbr_place__in": frbr_place_in,
        "frbr_doctype__in": frbr_doctype_in,
        "frbr_subtype__in": frbr_subtype_in,
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
    work_frbr_uri: Optional[str] = typer.Option(None, help="Only this work FRBR URI."),
    work_frbr_uri_in: list[str] = typer.Option([], help="One of these work FRBR URIs; repeat the option."),
    expression_frbr_uri: Optional[str] = typer.Option(None, help="Only this expression FRBR URI."),
    expression_frbr_uri_in: list[str] = typer.Option([], help="One of these expression FRBR URIs; repeat the option."),
    frbr_place: Optional[str] = typer.Option(None, help="Only this FRBR place code."),
    frbr_place_in: list[str] = typer.Option([], help="One of these FRBR place codes; repeat the option."),
    frbr_doctype: Optional[str] = typer.Option(None, help="Only this FRBR document type."),
    frbr_doctype_in: list[str] = typer.Option([], help="One of these FRBR document types; repeat the option."),
    frbr_subtype: Optional[str] = typer.Option(None, help="Only this FRBR document subtype."),
    frbr_subtype_in: list[str] = typer.Option([], help="One of these FRBR document subtypes; repeat the option."),
    repealed: Optional[bool] = typer.Option(None, "--repealed/--not-repealed", help="Filter legislation by repeal status."),
    commenced: Optional[bool] = typer.Option(None, "--commenced/--uncommenced", help="Filter legislation by commencement status."),
    principal: Optional[bool] = typer.Option(None, "--principal/--not-principal", help="Filter legislation by principal-work status."),
) -> None:
    """Retrieve the most relevant items from a Knowledge Base."""
    filters = _kb_filters(
        work_frbr_uri=work_frbr_uri,
        work_frbr_uri_in=work_frbr_uri_in,
        expression_frbr_uri=expression_frbr_uri,
        expression_frbr_uri_in=expression_frbr_uri_in,
        frbr_place=frbr_place,
        frbr_place_in=frbr_place_in,
        frbr_doctype=frbr_doctype,
        frbr_doctype_in=frbr_doctype_in,
        frbr_subtype=frbr_subtype,
        frbr_subtype_in=frbr_subtype_in,
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
