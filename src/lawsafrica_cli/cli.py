"""Typer command-line interface for the Laws.Africa Knowledge Base API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import click
import typer

from .client import DEFAULT_API_BASE_URL, ContentAPIClient, ContentAPIError, normalize_frbr_uri


app = typer.Typer(no_args_is_help=True, help="Use the Laws.Africa Knowledge Base API.")
places_app = typer.Typer(no_args_is_help=True, help="List and inspect places.")
expressions_app = typer.Typer(no_args_is_help=True, help="List expressions.")
expression_app = typer.Typer(no_args_is_help=True, help="Fetch an expression and related content.")
app.add_typer(places_app, name="places")
app.add_typer(expressions_app, name="expressions")
app.add_typer(expression_app, name="expression")


@app.callback()
def main(
    ctx: typer.Context,
    api_base_url: str = typer.Option(
        DEFAULT_API_BASE_URL,
        "--api-base-url",
        help="Content API v3 base URL.",
    ),
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["api_base_url"] = api_base_url


def _client(ctx: typer.Context) -> ContentAPIClient:
    return ContentAPIClient.from_env(ctx.obj["api_base_url"])


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
        with _client(ctx) as client:
            _emit_json(client.list_json("places", _page_params(page, page_size), all_pages=all_pages))
    except ContentAPIError as error:
        _exit_for_error(error)


@places_app.command("get")
def get_place(ctx: typer.Context, place: str) -> None:
    try:
        with _client(ctx) as client:
            _emit_json(client.get_json(f"places/{place}"))
    except ContentAPIError as error:
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
        with _client(ctx) as client:
            _emit_json(client.list_json(path, params, all_pages=all_pages))
    except ContentAPIError as error:
        _exit_for_error(error)


def _expression_json(client: ContentAPIClient, frbr_uri: str) -> Any:
    return client.get_json(f"{normalize_frbr_uri(frbr_uri)}.json")


@expression_app.command("get")
def get_expression(ctx: typer.Context, frbr_uri: str) -> None:
    try:
        with _client(ctx) as client:
            _emit_json(_expression_json(client, frbr_uri))
    except ContentAPIError as error:
        _exit_for_error(error)


@expression_app.command("versions")
def expression_versions(ctx: typer.Context, frbr_uri: str) -> None:
    """Fetch all dated/language expressions listed by an expression's metadata."""
    try:
        with _client(ctx) as client:
            metadata = _expression_json(client, frbr_uri)
            points_in_time = metadata.get("points_in_time", [])
            if not isinstance(points_in_time, list):
                raise ContentAPIError("Expression metadata contained invalid points_in_time data.")
            expressions = []
            for point in points_in_time:
                if not isinstance(point, dict) or not isinstance(point.get("expressions"), list):
                    raise ContentAPIError("Expression metadata contained invalid expression references.")
                for reference in point["expressions"]:
                    if not isinstance(reference, dict) or not isinstance(reference.get("expression_frbr_uri"), str):
                        raise ContentAPIError("Expression metadata contained an invalid expression FRBR URI.")
                    expressions.append(_expression_json(client, reference["expression_frbr_uri"]))
            _emit_json({"metadata": metadata, "expressions": expressions})
    except ContentAPIError as error:
        _exit_for_error(error)


def _expression_detail_command(name: str, endpoint: str, help_text: str) -> None:
    @expression_app.command(name, help=help_text)
    def detail(ctx: typer.Context, frbr_uri: str) -> None:
        try:
            with _client(ctx) as client:
                uri = normalize_frbr_uri(frbr_uri)
                _emit_json(client.get_json(f"{uri}/{endpoint}.json"))
        except ContentAPIError as error:
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
        with _client(ctx) as client:
            content = client.get_bytes(normalize_frbr_uri(frbr_uri), params)
        if output:
            output.write_bytes(content)
            typer.echo(f"Saved {format.upper()} ({len(content)} bytes) to {output}", err=True)
        else:
            stream = click.get_binary_stream("stdout")
            stream.write(content)
            stream.flush()
    except ContentAPIError as error:
        _exit_for_error(error)


if __name__ == "__main__":
    app()
