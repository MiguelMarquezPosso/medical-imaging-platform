"""FastAPI dependency injectors for provider singletons.

Providers are constructed lazily and cached. Keeping the wiring here means
domain modules never import concrete provider classes — they receive them
through `Depends(...)` and stay testable.
"""

from __future__ import annotations

from functools import lru_cache

from app.providers.crypto import AesGcmCrypto, SyncCrypto
from app.providers.dicomweb import DICOMwebProvider, OrthancDICOMwebProvider
from app.providers.storage import FilesystemStorageProvider, StorageProvider


@lru_cache(maxsize=1)
def _dicomweb_singleton() -> DICOMwebProvider:
    return OrthancDICOMwebProvider()


@lru_cache(maxsize=1)
def _storage_singleton() -> StorageProvider:
    # The choice of backend (filesystem / s3) is driven by the STORAGE_BACKEND env var.
    # Filesystem is the default — wire an S3 implementation here when needed.
    return FilesystemStorageProvider()


@lru_cache(maxsize=1)
def _crypto_singleton() -> SyncCrypto:
    return AesGcmCrypto()


def get_dicomweb_provider() -> DICOMwebProvider:
    return _dicomweb_singleton()


def get_storage_provider() -> StorageProvider:
    return _storage_singleton()


def get_sync_crypto() -> SyncCrypto:
    return _crypto_singleton()
