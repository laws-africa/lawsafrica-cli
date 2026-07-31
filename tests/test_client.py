from __future__ import annotations

import json
import unittest

import httpx

from lawsafrica_cli.client import LawsAfricaAPIClient, LawsAfricaAPIError, normalize_frbr_uri


class LawsAfricaAPIClientTestCase(unittest.TestCase):
    def make_client(self, handler):
        return LawsAfricaAPIClient(
            "test-token",
            "https://api.example.test/v3",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )

    def test_validates_normalizes_and_encodes_frbr_uri(self):
        self.assertEqual("akn/za/act/1998/55", normalize_frbr_uri("/akn/za/act/1998/55"))
        client = self.make_client(lambda request: httpx.Response(200, json={}))
        self.assertEqual(
            "https://api.example.test/v3/akn/za/act/1998/55/eng@2014-01-17/!main~sec_3",
            client.path_url("/akn/za/act/1998/55/eng@2014-01-17/!main~sec_3"),
        )
        with self.assertRaisesRegex(LawsAfricaAPIError, "must begin with '/'"):
            normalize_frbr_uri("za/act/1998/55")
        with self.assertRaisesRegex(LawsAfricaAPIError, r"Invalid FRBR URI: '/akn/'"):
            normalize_frbr_uri("/akn/")

    def test_sends_bearer_api_key_and_follows_next_page(self):
        requests = []

        def handler(request):
            requests.append(request)
            if request.url.params.get("page") == "2":
                return httpx.Response(200, json={"count": 2, "next": None, "previous": "ignored", "results": [{"id": 2}]})
            return httpx.Response(200, json={
                "count": 2,
                "next": "https://api.example.test/v3/places?page=2",
                "previous": None,
                "results": [{"id": 1}],
            })

        with self.make_client(handler) as client:
            result = client.list_json("places", {"page_size": 1}, all_pages=True)

        self.assertEqual([{"id": 1}, {"id": 2}], result["results"])
        self.assertIsNone(result["next"])
        self.assertEqual("Bearer test-token", requests[0].headers["authorization"])
        self.assertEqual("1", requests[0].url.params["page_size"])

    def test_non_json_and_api_errors_are_safe(self):
        with self.make_client(lambda request: httpx.Response(200, text="not json")) as client:
            with self.assertRaisesRegex(LawsAfricaAPIError, "not valid JSON"):
                client.get_json("places")

        with self.make_client(lambda request: httpx.Response(403, json={"detail": "Forbidden"})) as client:
            with self.assertRaisesRegex(LawsAfricaAPIError, r"403.*Forbidden") as error:
                client.get_json("places")
        self.assertNotIn("test-token", str(error.exception))

    def test_missing_api_key_is_rejected(self):
        with self.assertRaisesRegex(LawsAfricaAPIError, "LAWSAFRICA_API_KEY"):
            LawsAfricaAPIClient("")

    def test_posts_json_with_bearer_api_key(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(200, json={"results": []})

        with self.make_client(handler) as client:
            result = client.post_json("knowledge-bases/za-legislation/retrieve", {"text": "water", "top_k": 3})

        self.assertEqual({"results": []}, result)
        self.assertEqual("POST", requests[0].method)
        self.assertEqual("Bearer test-token", requests[0].headers["authorization"])
        self.assertEqual({"text": "water", "top_k": 3}, json.loads(requests[0].content))
