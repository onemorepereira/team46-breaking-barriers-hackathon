"""Read and write archive objects under a `file://` or `s3://` URI (design: Data and contracts)."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse


def s3_config(config_cls: Any) -> Any:
    """S3 reads and writes: 5 s connect, 30 s read, 3 standard-mode attempts (design: Data and contracts)."""
    return config_cls(connect_timeout=5, read_timeout=30, retries={"mode": "standard", "max_attempts": 3})


class Store(Protocol):
    uri: str

    def read_text(self, key: str) -> str | None: ...
    def write_text(self, key: str, text: str) -> None: ...
    def list(self, prefix: str) -> list[str]: ...


class FileStore:
    def __init__(self, uri: str) -> None:
        self.uri = uri
        parsed = urlparse(uri)
        # file://./archive -> ./archive ; file:///abs/dir -> /abs/dir
        self.root = Path(parsed.netloc + parsed.path)

    def _path(self, key: str) -> Path:
        return self.root / key

    def read_text(self, key: str) -> str | None:
        p = self._path(key)
        return p.read_text(encoding="utf-8") if p.is_file() else None

    def write_text(self, key: str, text: str) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def list(self, prefix: str) -> list[str]:
        base = self._path(prefix)
        if not base.is_dir():
            return []
        return sorted(str(p.relative_to(self.root)) for p in base.iterdir() if p.is_file())


_shared_client: Any = None
_client_lock = threading.Lock()


def _s3_client() -> Any:
    """One S3 client per process (boto3 clients are thread-safe); creating one per run cost ~100 ms each."""
    global _shared_client
    with _client_lock:
        if _shared_client is None:
            import boto3
            from botocore.config import Config

            _shared_client = boto3.client("s3", config=s3_config(Config))
        return _shared_client


class S3Store:
    def __init__(self, uri: str, client: Any = None) -> None:
        self.uri = uri
        parsed = urlparse(uri)
        self.bucket = parsed.netloc
        self.prefix = parsed.path.lstrip("/")
        self.client = client or _s3_client()

    def _key(self, key: str) -> str:
        return f"{self.prefix.rstrip('/')}/{key}" if self.prefix else key

    def read_text(self, key: str) -> str | None:
        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=self._key(key))
        except self.client.exceptions.NoSuchKey:
            return None
        body: bytes = obj["Body"].read()
        return body.decode("utf-8")

    def write_text(self, key: str, text: str) -> None:
        self.client.put_object(Bucket=self.bucket, Key=self._key(key), Body=text.encode("utf-8"))

    def list(self, prefix: str) -> list[str]:
        """List one directory level under prefix (a single run's folder; bounded)."""
        full = self._key(prefix).rstrip("/") + "/"
        out: list[str] = []
        token: str | None = None
        while True:
            kwargs: dict[str, Any] = {"Bucket": self.bucket, "Prefix": full, "Delimiter": "/"}
            if token:
                kwargs["ContinuationToken"] = token
            resp = self.client.list_objects_v2(**kwargs)
            for item in resp.get("Contents", []):
                key = item["Key"]
                out.append(key[len(self.prefix.rstrip("/")) + 1 :] if self.prefix else key)
            if not resp.get("IsTruncated"):
                return sorted(out)
            token = resp["NextContinuationToken"]


def open_store(uri: str) -> Store:
    scheme = urlparse(uri).scheme
    if scheme == "file":
        return FileStore(uri)
    if scheme == "s3":
        return S3Store(uri)
    raise ValueError(f"unsupported archive URI {uri!r}; use file:// or s3://")
