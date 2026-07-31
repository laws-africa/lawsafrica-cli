"""HTTP client and pagination helpers for Laws.Africa APIs."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

import httpx
from cobalt import FrbrUri


DEFAULT_LEGISLATION_API_BASE_URL = "https://api.laws.africa/v3"
DEFAULT_KB_API_BASE_URL = "https://api.laws.africa/ai/v1"
API_KEY_ENVIRONMENT_VARIABLE = "LAWSAFRICA_API_KEY"
ACCOUNT_URL = "https://platform.laws.africa/"
API_KEYS_URL = "https://platform.laws.africa/api-keys/"


class LawsAfricaAPIError(RuntimeError):
    """An expected client-side or API error suitable for presentation by the CLI."""


def parse_frbr_uri(frbr_uri: str) -> str:
    """Validate and canonicalise an absolute FRBR URI with Cobalt."""
    if not frbr_uri.startswith("/"):
        raise LawsAfricaAPIError(
            "FRBR URI must begin with '/'. Example: '/akn/za/act/1998/55'."
        )
    try:
        return str(FrbrUri.parse(frbr_uri))
    except ValueError as error:
        raise LawsAfricaAPIError(
            f"Invalid FRBR URI: {frbr_uri!r}. Use an absolute URI such as "
            "'/akn/za/act/1998/55'."
        ) from error


def normalize_frbr_uri(frbr_uri: str) -> str:
    """Return a Cobalt-validated FRBR URI for use in an API path."""
    return parse_frbr_uri(frbr_uri).lstrip("/")


class LawsAfricaAPIClient:
    """A synchronous authenticated client for a Laws.Africa API base URL."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_LEGISLATION_API_BASE_URL,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise LawsAfricaAPIError(
                f"{API_KEY_ENVIRONMENT_VARIABLE} is required. Create a free account at "
                f"{ACCOUNT_URL} and create an API key at {API_KEYS_URL}."
            )
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=30.0)
        self._client.headers["Authorization"] = f"Bearer {api_key}"

    @classmethod
    def from_env(cls, base_url: str = DEFAULT_LEGISLATION_API_BASE_URL) -> "LawsAfricaAPIClient":
        return cls(os.environ.get(API_KEY_ENVIRONMENT_VARIABLE, ""), base_url)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "LawsAfricaAPIClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def path_url(self, path: str) -> str:
        """Build a URL while retaining valid FRBR punctuation in the path."""
        return f"{self.base_url}/{quote(path.lstrip('/'), safe='/!~:@-.')}"

    def get_json(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        return self._json_response(self._request("GET", self.path_url(path), params=params))

    def post_json(self, path: str, payload: Mapping[str, Any]) -> Any:
        """POST a JSON request body and return a JSON response."""
        return self._json_response(self._request("POST", self.path_url(path), json=payload))

    def get_bytes(self, path: str, params: Mapping[str, Any] | None = None) -> bytes:
        return self._request("GET", self.path_url(path), params=params).content

    def list_json(
        self,
        path: str,
        params: Mapping[str, Any] | None = None,
        *,
        all_pages: bool = False,
    ) -> dict[str, Any]:
        """Fetch a paginated response, optionally following each ``next`` URL."""
        page = self.get_json(path, params)
        self._validate_page(page)
        if not all_pages:
            return page

        results = list(page["results"])
        count = page["count"]
        next_url = page["next"]
        while next_url:
            response = self._request("GET", next_url)
            next_page = self._json_response(response)
            self._validate_page(next_page)
            results.extend(next_page["results"])
            next_url = next_page["next"]

        return {"count": count, "next": None, "previous": None, "results": results}

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
    ) -> httpx.Response:
        try:
            response = self._client.request(method, url, params=params, json=json)
        except httpx.HTTPError as error:
            raise LawsAfricaAPIError(f"API request failed: {error}") from error
        if response.is_error:
            raise LawsAfricaAPIError(self._error_message(response))
        return response

    @staticmethod
    def _json_response(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError as error:
            raise LawsAfricaAPIError("API response was not valid JSON.") from error

    @staticmethod
    def _validate_page(page: Any) -> None:
        if not isinstance(page, dict) or not isinstance(page.get("results"), list):
            raise LawsAfricaAPIError("API response was not a paginated result set.")
        if "count" not in page or "next" not in page or "previous" not in page:
            raise LawsAfricaAPIError("API pagination response was incomplete.")

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        detail = ""
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            candidate = payload.get("detail") or payload.get("message")
            if isinstance(candidate, str):
                detail = candidate
            elif candidate is None:
                field_errors = []
                for field, messages in payload.items():
                    if isinstance(messages, list) and all(isinstance(message, str) for message in messages):
                        field_errors.append(f"{field}: {', '.join(messages)}")
                detail = "; ".join(field_errors)
        if not detail:
            detail = response.reason_phrase or "Request failed"
        message = f"API request failed ({response.status_code}): {detail}"
        if response.status_code in {401, 403}:
            message += f" Check {API_KEY_ENVIRONMENT_VARIABLE} and API access at {API_KEYS_URL}."
        return message


# Kept as import-compatible names while this CLI grows from the Content API.
ContentAPIClient = LawsAfricaAPIClient
ContentAPIError = LawsAfricaAPIError
DEFAULT_API_BASE_URL = DEFAULT_LEGISLATION_API_BASE_URL
