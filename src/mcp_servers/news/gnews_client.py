from __future__ import annotations

import logging

import httpx

from .models import SearchResponse

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS: float = 10.0
DEFAULT_LANG: str = "en"
DEFAULT_MAX_RESULTS: int = 5


class GNewsAPIError(Exception):
    """Raised when the GNews API returns a non-success status code."""


class GNewsClient:
    """HTTP client for the GNews.io API. Reuses a single httpx.AsyncClient."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://gnews.io/api/v4",
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._http = httpx.AsyncClient(timeout=timeout)

    async def search(
        self,
        query: str,
        lang: str = DEFAULT_LANG,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> SearchResponse:
        """Search for news articles by keyword."""
        params = {
            "q": query,
            "lang": lang,
            "max": max_results,
            "apikey": self._api_key,
        }
        return await self._request("/search", params)

    async def top_headlines(
        self,
        category: str | None = None,
        country: str | None = None,
        lang: str = DEFAULT_LANG,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> SearchResponse:
        """Get top headlines, optionally filtered by category or country."""
        params: dict[str, str | int] = {
            "lang": lang,
            "max": max_results,
            "apikey": self._api_key,
        }
        if category is not None:
            params["category"] = category
        if country is not None:
            params["country"] = country
        return await self._request("/top-headlines", params)

    async def _request(
        self, endpoint: str, params: dict[str, str | int]
    ) -> SearchResponse:
        """Make a GET request and parse the response."""
        url = f"{self._base_url}{endpoint}"
        try:
            response = await self._http.get(url, params=params)
        except httpx.HTTPError as exc:
            logger.error("HTTP request failed for %s: %s", url, exc)
            raise GNewsAPIError(f"Request failed: {exc}") from exc

        if response.status_code != 200:
            logger.error(
                "GNews API error %d for %s: %s",
                response.status_code,
                url,
                response.text,
            )
            raise GNewsAPIError(
                f"GNews API returned {response.status_code}: {response.text}"
            )

        return SearchResponse.from_gnews(response.json())

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()
