from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from typer.testing import CliRunner

from lawsafrica_cli.client import LawsAfricaAPIError
from lawsafrica_cli.cli import app


class FakeClient:
    instance = None

    def __init__(self):
        self.json_calls = []
        self.list_calls = []
        self.bytes_calls = []
        self.post_calls = []
        type(self).instance = self

    @classmethod
    def from_env(cls, base_url):
        instance = cls()
        instance.base_url = base_url
        return instance

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def get_json(self, path, params=None):
        self.json_calls.append((path, params))
        if path.endswith(".json"):
            return {"expression_frbr_uri": "/akn/za/act/1998/55/eng@1998-01-01", "points_in_time": []}
        return {"endpoint": path}

    def list_json(self, path, params=None, all_pages=False):
        self.list_calls.append((path, params, all_pages))
        return {"count": 0, "next": None, "previous": None, "results": []}

    def get_bytes(self, path, params=None):
        self.bytes_calls.append((path, params))
        return b"example-bytes"

    def post_json(self, path, payload):
        self.post_calls.append((path, payload))
        return {"results": []}


class CLITestCase(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        FakeClient.instance = None

    def test_expression_get_uses_expression_endpoint(self):
        with patch("lawsafrica_cli.cli.LawsAfricaAPIClient", FakeClient):
            result = self.runner.invoke(app, ["legislation", "expression", "get", "/akn/za/act/1998/55"])

        self.assertEqual(0, result.exit_code, result.output)
        self.assertEqual("akn/za/act/1998/55.json", FakeClient.instance.json_calls[0][0])
        self.assertEqual("/akn/za/act/1998/55/eng@1998-01-01", json.loads(result.output)["expression_frbr_uri"])

    def test_frbr_uri_arguments_and_options_reject_slashless_values_before_api_requests(self):
        with patch("lawsafrica_cli.cli.LawsAfricaAPIClient", FakeClient):
            argument_result = self.runner.invoke(app, ["legislation", "expression", "get", "akn/za/act/1998/55"])
            option_result = self.runner.invoke(app, ["kb", "retrieve", "za-legislation", "water", "--work-frbr-uri", "akn/za/act/1998/55"])

        self.assertNotEqual(0, argument_result.exit_code)
        self.assertNotEqual(0, option_result.exit_code)
        self.assertIn("must begin with '/'", argument_result.output)
        self.assertIn("must begin with '/'", option_result.output)
        self.assertIsNone(FakeClient.instance)

    def test_every_command_has_a_help_description(self):
        commands = {
            ("legislation", "places"): "List and inspect places.",
            ("legislation", "places", "list"): "List countries and localities available through the legislation API.",
            ("legislation", "places", "get"): "Fetch a place by its country or locality code.",
            ("legislation", "expressions"): "List expressions across all places, or filter to one place.",
            ("legislation", "expressions", "list"): "List expressions across all places, or filter to one place.",
            ("legislation", "expression", "get"): "Fetch an expression's JSON metadata.",
            ("legislation", "expression", "versions"): "Fetch all dated/language expressions listed by an expression's metadata.",
            ("legislation", "expression", "toc"): "Fetch an expression table of contents.",
            ("legislation", "expression", "commencements"): "Fetch commencement data.",
            ("legislation", "expression", "timeline"): "Fetch expression timeline data.",
            ("legislation", "expression", "content"): "Fetch expression content as XML, HTML, PDF, EPUB, or ZIP.",
            ("kb", "list"): "List the Knowledge Bases available to this API key.",
            ("kb", "get"): "Fetch a Knowledge Base's metadata by code.",
            ("kb", "retrieve"): "Retrieve the most relevant items from a Knowledge Base.",
        }
        for command, description in commands.items():
            with self.subTest(command=command):
                result = self.runner.invoke(app, [*command, "--help"])
                self.assertEqual(0, result.exit_code, result.output)
                self.assertIn(description, result.output)

    def test_listing_maps_documented_filters_and_all_pages(self):
        with patch("lawsafrica_cli.cli.LawsAfricaAPIClient", FakeClient):
            result = self.runner.invoke(app, [
                "legislation", "expressions", "list", "--place", "za-cpt", "--updated-after", "2026-01-01T00:00:00Z", "--page-size", "100", "--all"
            ])

        self.assertEqual(0, result.exit_code, result.output)
        path, params, all_pages = FakeClient.instance.list_calls[0]
        self.assertEqual("places/za-cpt/work-expressions", path)
        self.assertEqual("2026-01-01T00:00:00Z", params["updated_at__gte"])
        self.assertEqual(100, params["page_size"])
        self.assertTrue(all_pages)

    def test_listing_rejects_non_iso_timestamp_before_requesting_the_api(self):
        with patch("lawsafrica_cli.cli.LawsAfricaAPIClient", FakeClient):
            result = self.runner.invoke(app, [
                "legislation", "expressions", "list", "--created-before", "not-a-timestamp"
            ])

        self.assertNotEqual(0, result.exit_code)
        self.assertIn("must be an ISO 8601 timestamp", result.output)
        self.assertIsNone(FakeClient.instance)

    def test_listing_maps_boolean_filters(self):
        with patch("lawsafrica_cli.cli.LawsAfricaAPIClient", FakeClient):
            result = self.runner.invoke(app, [
                "legislation", "expressions", "list", "--uncommenced", "--repealed", "--not-principal"
            ])

        self.assertEqual(0, result.exit_code, result.output)
        _, params, _ = FakeClient.instance.list_calls[0]
        self.assertEqual({"commenced": False, "repealed": True, "principal": False}, params)

    def test_content_writes_binary_output_and_html_options(self):
        with (
            TemporaryDirectory() as directory,
            patch("lawsafrica_cli.cli.LawsAfricaAPIClient", FakeClient),
            patch("lawsafrica_cli.cli.typer.echo") as echo,
        ):
            output = Path(directory) / "expression.html"
            result = self.runner.invoke(app, [
                "legislation", "expression", "content", "/akn/za/act/1998/55", "--format", "html", "--output", str(output),
                "--resolver", "none", "--no-coverpage", "--standalone",
            ])
            content = output.read_bytes()

        self.assertEqual(0, result.exit_code, result.output)
        self.assertEqual(b"example-bytes", content)
        echo.assert_called_once_with(
            f"Saved HTML (13 bytes) to {output}",
            err=True,
        )
        path, params = FakeClient.instance.bytes_calls[0]
        self.assertEqual("akn/za/act/1998/55", path)
        self.assertEqual({"format": "html", "resolver": "none", "coverpage": "0", "standalone": "1"}, params)

    def test_versions_resolves_each_expression_in_metadata_order(self):
        class VersionClient(FakeClient):
            def get_json(self, path, params=None):
                self.json_calls.append((path, params))
                if path == "akn/za/act/1998/55.json":
                    return {
                        "points_in_time": [
                            {"expressions": [
                                {"expression_frbr_uri": "/akn/za/act/1998/55/eng@1998-01-01"},
                                {"expression_frbr_uri": "/akn/za/act/1998/55/afr@1998-01-01"},
                            ]},
                            {"expressions": [
                                {"expression_frbr_uri": "/akn/za/act/1998/55/eng@2000-01-01"},
                            ]},
                        ]
                    }
                return {"resolved": path}

        with patch("lawsafrica_cli.cli.LawsAfricaAPIClient", VersionClient):
            result = self.runner.invoke(app, ["legislation", "expression", "versions", "/akn/za/act/1998/55"])

        self.assertEqual(0, result.exit_code, result.output)
        self.assertEqual(
            [
                "akn/za/act/1998/55.json",
                "akn/za/act/1998/55/eng@1998-01-01.json",
                "akn/za/act/1998/55/afr@1998-01-01.json",
                "akn/za/act/1998/55/eng@2000-01-01.json",
            ],
            [path for path, _ in VersionClient.instance.json_calls],
        )
        self.assertEqual(3, len(json.loads(result.output)["expressions"]))

    def test_versions_reports_a_failed_nested_fetch(self):
        class FailingVersionClient(FakeClient):
            def get_json(self, path, params=None):
                self.json_calls.append((path, params))
                if path == "akn/za/act/1998/55.json":
                    return {"points_in_time": [{"expressions": [
                        {"expression_frbr_uri": "/akn/za/act/1998/55/eng@1998-01-01"},
                    ]}]}
                raise LawsAfricaAPIError("API request failed (404): Not found")

        with patch("lawsafrica_cli.cli.LawsAfricaAPIClient", FailingVersionClient):
            result = self.runner.invoke(app, ["legislation", "expression", "versions", "/akn/za/act/1998/55"])

        self.assertEqual(1, result.exit_code)
        self.assertIn("404", result.output)

    def test_kb_list_and_get_use_the_knowledge_base_api_client(self):
        with patch("lawsafrica_cli.cli.LawsAfricaAPIClient", FakeClient):
            result = self.runner.invoke(app, [
                "--kb-api-base-url", "https://kb.example.test/ai/v1",
                "kb", "list", "--page", "2", "--page-size", "25", "--all",
            ])
            list_client = FakeClient.instance
            get_result = self.runner.invoke(app, ["kb", "get", "za-legislation"])

        self.assertEqual(0, result.exit_code, result.output)
        self.assertEqual(0, get_result.exit_code, get_result.output)
        self.assertEqual(
            ("knowledge-bases", {"page": 2, "page_size": 25}, True),
            list_client.list_calls[0],
        )
        self.assertEqual("https://kb.example.test/ai/v1", list_client.base_url)
        self.assertEqual(("knowledge-bases/za-legislation", None), FakeClient.instance.json_calls[0])

    def test_kb_retrieve_posts_text_top_k_and_repeatable_schema_filters(self):
        with patch("lawsafrica_cli.cli.LawsAfricaAPIClient", FakeClient):
            result = self.runner.invoke(app, [
                "kb", "retrieve", "za-legislation", "water pollution", "--top-k", "5",
                "--work-frbr-uri", "/akn/za/act/1998/55",
                "--work-frbr-uri", "/akn/za/act/2008/1",
                "--work-frbr-uri", "/akn/za/act/2009/2",
                "--expression-frbr-uri", "/akn/za/act/1998/55/eng@2020-01-01",
                "--expression-frbr-uri", "/akn/za/act/2008/1/eng@2020-01-01",
                "--frbr-place", "za-cpt", "--frbr-place", "za-jhb",
                "--frbr-doctype", "act", "--frbr-doctype", "by-law",
                "--frbr-subtype", "provincial", "--frbr-subtype", "municipal",
                "--not-repealed", "--uncommenced", "--principal",
            ])

        self.assertEqual(0, result.exit_code, result.output)
        self.assertEqual("knowledge-bases/za-legislation/retrieve", FakeClient.instance.post_calls[0][0])
        self.assertEqual(
            {
                "text": "water pollution",
                "top_k": 5,
                "filters": {
                    "work_frbr_uri__in": ["/akn/za/act/1998/55", "/akn/za/act/2008/1", "/akn/za/act/2009/2"],
                    "expression_frbr_uri__in": ["/akn/za/act/1998/55/eng@2020-01-01", "/akn/za/act/2008/1/eng@2020-01-01"],
                    "frbr_place__in": ["za-cpt", "za-jhb"],
                    "frbr_doctype__in": ["act", "by-law"],
                    "frbr_subtype__in": ["provincial", "municipal"],
                    "repealed": False,
                    "commenced": False,
                    "principal": True,
                },
            },
            FakeClient.instance.post_calls[0][1],
        )

    def test_kb_retrieve_omits_empty_filters(self):
        with patch("lawsafrica_cli.cli.LawsAfricaAPIClient", FakeClient):
            result = self.runner.invoke(app, ["kb", "retrieve", "za-legislation", "water pollution"])

        self.assertEqual(0, result.exit_code, result.output)
        self.assertEqual(
            ("knowledge-bases/za-legislation/retrieve", {"text": "water pollution", "top_k": 10}),
            FakeClient.instance.post_calls[0],
        )
