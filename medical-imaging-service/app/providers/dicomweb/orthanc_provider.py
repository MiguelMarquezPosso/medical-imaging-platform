"""Orthanc DICOMweb provider — talks to a private Orthanc behind a secure tunnel.

We never expose Orthanc directly to the internet. The configured base URL is
expected to resolve only through the private network (Tailscale, WireGuard,
SSH tunnel, Cloudflare Tunnel, etc.).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config.dicomweb_config import (
    DICOMwebConfig,
    DICOMwebConfigStore,
    get_dicomweb_config_store,
)
from app.core.errors import DICOMwebError, NotFoundError
from app.core.logging import get_logger

log = get_logger("dicomweb.orthanc")


class OrthancDICOMwebProvider:
    """Concrete DICOMwebProvider for Orthanc."""

    def __init__(self, store: DICOMwebConfigStore | None = None) -> None:
        self._store = store or get_dicomweb_config_store()

    # ---------- HTTP plumbing ----------
    def _build_client(self, cfg: DICOMwebConfig, *, accept: str | None = None) -> httpx.AsyncClient:
        headers: dict[str, str] = {}
        if accept:
            headers["Accept"] = accept

        auth: httpx.Auth | None = None
        if cfg.auth_type == "basic" and cfg.username:
            auth = httpx.BasicAuth(cfg.username, cfg.password)
        elif cfg.auth_type == "bearer" and cfg.bearer_token:
            headers["Authorization"] = f"Bearer {cfg.bearer_token}"

        # httpx strips the base_url's path when the request path starts with '/'.
        # Ensure base_url ends with '/' and we use relative paths (no leading '/').
        base = cfg.base_url if cfg.base_url.endswith("/") else cfg.base_url + "/"
        return httpx.AsyncClient(
            base_url=base,
            timeout=cfg.timeout_seconds,
            verify=cfg.verify_tls,
            headers=headers,
            auth=auth,
        )

    @staticmethod
    def _raise_for(resp: httpx.Response) -> None:
        if resp.status_code == 404:
            raise NotFoundError("Resource not found in PACS")
        if resp.status_code >= 400:
            raise DICOMwebError(
                f"Upstream returned {resp.status_code}",
                details={"status": resp.status_code, "body": resp.text[:500]},
            )

    # ---------- QIDO-RS ----------
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.3, max=2),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def search_studies(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        cfg = self._store.get()
        async with self._build_client(cfg, accept="application/dicom+json") as client:
            resp = await client.get("studies", params=query)
            if resp.status_code == 204:
                return []
            self._raise_for(resp)
            return resp.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.3, max=2),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def search_series(self, study_uid: str, query: dict[str, Any]) -> list[dict[str, Any]]:
        cfg = self._store.get()
        async with self._build_client(cfg, accept="application/dicom+json") as client:
            resp = await client.get(f"studies/{study_uid}/series", params=query)
            if resp.status_code == 204:
                return []
            self._raise_for(resp)
            return resp.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.3, max=2),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def search_instances(
        self, study_uid: str, series_uid: str, query: dict[str, Any]
    ) -> list[dict[str, Any]]:
        cfg = self._store.get()
        async with self._build_client(cfg, accept="application/dicom+json") as client:
            resp = await client.get(
                f"studies/{study_uid}/series/{series_uid}/instances",
                params=query,
            )
            if resp.status_code == 204:
                return []
            self._raise_for(resp)
            return resp.json()

    # ---------- WADO-RS — streaming binary -----------
    async def _stream(self, path: str, *, accept: str) -> AsyncIterator[bytes]:
        cfg = self._store.get()
        client = self._build_client(cfg, accept=accept)
        try:
            async with client.stream("GET", path) as resp:
                if resp.status_code == 404:
                    raise NotFoundError("Resource not found in PACS")
                if resp.status_code >= 400:
                    body = await resp.aread()
                    raise DICOMwebError(
                        f"Upstream returned {resp.status_code}",
                        details={"status": resp.status_code, "body": body[:500].decode("utf-8", "replace")},
                    )
                async for chunk in resp.aiter_bytes(chunk_size=64 * 1024):
                    yield chunk
        finally:
            await client.aclose()

    async def retrieve_study(self, study_uid: str) -> AsyncIterator[bytes]:
        return self._stream(
            f"studies/{study_uid}",
            accept='multipart/related; type="application/dicom"; transfer-syntax=*',
        )

    async def retrieve_series(self, study_uid: str, series_uid: str) -> AsyncIterator[bytes]:
        return self._stream(
            f"studies/{study_uid}/series/{series_uid}",
            accept='multipart/related; type="application/dicom"; transfer-syntax=*',
        )

    async def retrieve_instance(
        self, study_uid: str, series_uid: str, instance_uid: str
    ) -> AsyncIterator[bytes]:
        return self._stream(
            f"studies/{study_uid}/series/{series_uid}/instances/{instance_uid}",
            accept='multipart/related; type="application/dicom"; transfer-syntax=*',
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.3, max=2),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def retrieve_metadata(self, study_uid: str) -> list[dict[str, Any]]:
        cfg = self._store.get()
        async with self._build_client(cfg, accept="application/dicom+json") as client:
            resp = await client.get(f"studies/{study_uid}/metadata")
            self._raise_for(resp)
            return resp.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.3, max=2),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def retrieve_series_metadata(
        self, study_uid: str, series_uid: str
    ) -> list[dict[str, Any]]:
        cfg = self._store.get()
        async with self._build_client(cfg, accept="application/dicom+json") as client:
            resp = await client.get(f"studies/{study_uid}/series/{series_uid}/metadata")
            self._raise_for(resp)
            return resp.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.3, max=2),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def retrieve_instance_metadata(
        self, study_uid: str, series_uid: str, instance_uid: str
    ) -> list[dict[str, Any]]:
        cfg = self._store.get()
        async with self._build_client(cfg, accept="application/dicom+json") as client:
            resp = await client.get(
                f"studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/metadata"
            )
            self._raise_for(resp)
            return resp.json()

    # ---------- STOW-RS ----------
    async def store_instances(
        self,
        body: bytes,
        *,
        content_type: str,
        study_uid: str | None = None,
    ) -> dict[str, Any]:
        cfg = self._store.get()
        path = f"studies/{study_uid}" if study_uid else "studies"
        async with self._build_client(cfg, accept="application/dicom+json") as client:
            headers = {"Content-Type": content_type}
            resp = await client.post(path, content=body, headers=headers)
            if resp.status_code not in (200, 202):
                self._raise_for(resp)
            try:
                return resp.json()
            except ValueError:
                return {"status": resp.status_code}

    # ---------- Health ----------
    async def healthcheck(self) -> bool:
        cfg = self._store.get()
        try:
            async with self._build_client(cfg) as client:
                resp = await client.get("studies", params={"limit": 1})
                return resp.status_code < 500
        except Exception as exc:  # noqa: BLE001
            log.warning("dicomweb_healthcheck_failed", error=str(exc))
            return False
