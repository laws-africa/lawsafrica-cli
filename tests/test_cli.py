from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from typer.testing import CliRunner

from lawsafrica_cli.client import ContentAPIError
from lawsafrica_cli.cli import app


class FakeClient:
    instance = None

    def __init__(self):
        self.json_calls = []
        self.list_calls = []
        self.bytes_calls = []
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


class CLITestCase(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_expression_get_uses_expression_endpoint(self):
        with patch("lawsafrica_cli.cli.ContentAPIClient", FakeClient):
            result = self.runner.invoke(app, ["expression", "get", "/akn/za/act/1998/55"])

        self.assertEqual(0, result.exit_code, result.output)
        self.assertEqual("akn/za/act/1998/55.json", FakeClient.instance.json_calls[0][0])
        self.assertEqual("/akn/za/act/1998/55/eng@1998-01-01", json.loads(result.output)["expression_frbr_uri"])

    def test_listing_maps_documented_filters_and_all_pages(self):
        with patch("lawsafrica_cli.cli.ContentAPIClient", FakeClient):
            result = self.runner.invoke(app, [
                "expressions", "list", "--place", "za-cpt", "--updated-at-gte", "2026-01-01T00:00:00Z", "--page-size", "100", "--all"
            ])

        self.assertEqual(0, result.exit_code, result.output)
        path, params, all_pages = FakeClient.instance.list_calls[0]
        self.assertEqual("places/za-cpt/work-expressions", path)
        self.assertEqual("2026-01-01T00:00:00Z", params["updated_at__gte"])
        self.assertEqual(100, params["page_size"])
        self.assertTrue(all_pages)

    def test_listing_maps_boolean_filters(self):
        with patch("lawsafrica_cli.cli.ContentAPIClient", FakeClient):
            result = self.runner.invoke(app, [
                "expressions", "list", "--uncommenced", "--repealed", "--not-principal"
            ])

        self.assertEqual(0, result.exit_code, result.output)
        _, params, _ = FakeClient.instance.list_calls[0]
        self.assertEqual({"commenced": False, "repealed": True, "principal": False}, params)

    def test_content_writes_binary_output_and_html_options(self):
        with (
            TemporaryDirectory() as directory,
            patch("lawsafrica_cli.cli.ContentAPIClient", FakeClient),
            patch("lawsafrica_cli.cli.typer.echo") as echo,
        ):
            output = Path(directory) / "expression.html"
            result = self.runner.invoke(app, [
                "expression", "content", "akn/za/act/1998/55", "--format", "html", "--output", str(output),
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

        with patch("lawsafrica_cli.cli.ContentAPIClient", VersionClient):
            result = self.runner.invoke(app, ["expression", "versions", "akn/za/act/1998/55"])

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
                raise ContentAPIError("API request failed (404): Not found")

        with patch("lawsafrica_cli.cli.ContentAPIClient", FailingVersionClient):
            result = self.runner.invoke(app, ["expression", "versions", "akn/za/act/1998/55"])

        self.assertEqual(1, result.exit_code)
        self.assertIn("404", result.output)
