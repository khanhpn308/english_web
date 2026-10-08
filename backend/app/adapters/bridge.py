import json
from time import monotonic
from typing import Any

import httpx
from backend.app.platform.bridge_port import (
    BridgeAuthError,
    BridgeConfigError,
    BridgeInvalidResponseError,
    BridgePort,
    BridgeProfile,
    BridgeUnavailableError,
)

MAX_RESPONSE_BYTES = 4_194_304
BRIDGE_BASE_URL = "http://127.0.0.1:8045/v1"


class BridgeAdapter(BridgePort):
    def __init__(
        self,
        api_key: str | None,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Any = monotonic,
    ) -> None:
        self._api_key = api_key
        self._transport = transport
        self._clock = clock
        self._base_url = BRIDGE_BASE_URL

    def _get_timeout(self, deadline: float) -> httpx.Timeout:
        remaining = deadline - self._clock()
        if remaining <= 0:
            raise BridgeUnavailableError("Operation deadline exceeded")
        return httpx.Timeout(remaining)

    def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            transport=self._transport,
            trust_env=False,
            follow_redirects=False,
            # Each outbound stage supplies its own remaining operation budget.
            timeout=None,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )

    async def _read_bounded(self, response: httpx.Response) -> bytes:
        content_length = response.headers.get("content-length")
        if content_length is not None:
            if not content_length.isdecimal():
                raise BridgeInvalidResponseError("Invalid Content-Length header")
            if int(content_length) > MAX_RESPONSE_BYTES:
                raise BridgeInvalidResponseError("Response exceeded maximum size")

        body_bytes = bytearray()
        async for chunk in response.aiter_bytes(chunk_size=8192):
            body_bytes.extend(chunk)
            if len(body_bytes) > MAX_RESPONSE_BYTES:
                raise BridgeInvalidResponseError("Response exceeded maximum size")
        return bytes(body_bytes)

    async def preflight(self, deadline: float) -> BridgeProfile:
        try:
            async with self._get_client() as client:
                # Stage 1: No-key request
                async with client.stream(
                    "GET", "/models", headers={}, timeout=self._get_timeout(deadline)
                ) as response:
                    if response.status_code == 200:
                        raise BridgeConfigError("Unsafe proxy configuration (no key required)")
                    if response.status_code in (301, 302, 303, 307, 308):
                        raise BridgeUnavailableError(f"Unexpected redirect: {response.status_code}")
                    if response.status_code != 401:
                        raise BridgeUnavailableError(
                            f"Unexpected status without key: {response.status_code}"
                        )

                if not self._api_key:
                    raise BridgeConfigError("Missing proxy credentials")

                # Stage 2: Keyed request
                async with client.stream(
                    "GET",
                    "/models",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=self._get_timeout(deadline),
                ) as response:
                    if response.status_code in (401, 403):
                        raise BridgeAuthError("Proxy rejected credentials")
                    if response.status_code >= 300:
                        raise BridgeUnavailableError(f"Unexpected status: {response.status_code}")
                    body_bytes = await self._read_bounded(response)

            data = json.loads(body_bytes.decode("utf-8"))
            if not isinstance(data, dict) or "data" not in data:
                raise BridgeInvalidResponseError("Malformed models response schema")
            if not isinstance(data["data"], list):
                raise BridgeInvalidResponseError("Malformed models response schema")

            return BridgeProfile(models=data["data"], raw_response=data)

        except (httpx.RequestError, httpx.TimeoutException) as e:
            raise BridgeUnavailableError("Proxy connection failed or timed out") from e
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise BridgeInvalidResponseError("Malformed JSON response") from e

    async def dispatch_chat(self, payload: dict[str, Any], deadline: float) -> dict[str, Any]:
        if not self._api_key:
            raise BridgeConfigError("Missing proxy credentials")

        try:
            async with (
                self._get_client() as client,
                client.stream(
                    "POST",
                    "/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                    timeout=self._get_timeout(deadline),
                ) as response,
            ):
                if response.status_code in (401, 403):
                    raise BridgeAuthError("Proxy rejected credentials")
                if response.status_code >= 300:
                    raise BridgeUnavailableError(f"Unexpected status: {response.status_code}")
                body_bytes = await self._read_bounded(response)

            data = json.loads(body_bytes.decode("utf-8"))
            if not isinstance(data, dict):
                raise BridgeInvalidResponseError("Malformed chat response schema")

            return data

        except (httpx.RequestError, httpx.TimeoutException) as e:
            raise BridgeUnavailableError("Proxy connection failed or timed out") from e
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise BridgeInvalidResponseError("Malformed JSON response") from e
