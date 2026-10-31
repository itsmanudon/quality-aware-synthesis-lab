"""Offline tests for the declared fetcher (fake opener; no network)."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from typing import Any, Self

import pytest

from study.v3 import fetch

BODY = b"@relation x\n@attribute a numeric\n@data\n1\n"
DESC = {"data_set_description": {
    "name": "toy", "version": "3", "status": "active", "licence": "CC0",
    "default_target_attribute": "y", "file_id": "9", "format": "ARFF",
    "url": "https://api.openml.org/data/v1/download/9/toy.arff",
    "md5_checksum": hashlib.md5(BODY, usedforsecurity=False).hexdigest()}}
QUAL = {"data_qualities": {"quality": [{"name": "MinorityClassSize", "value": "40.0"},
                                       {"name": "MajorityClassSize", "value": "160.0"}]}}


class Response(io.BytesIO):
    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def opener_for(body: bytes = BODY, desc: dict[str, Any] = DESC) -> Any:
    seen: list[str] = []

    def opener(request: Any, timeout: float) -> Response:
        url = request.full_url
        seen.append(url)
        if url.endswith("/data/qualities/7"):
            return Response(json.dumps(QUAL).encode())
        if url.endswith("/data/7"):
            return Response(json.dumps(desc).encode())
        if url == desc["data_set_description"]["url"]:
            return Response(body)
        raise AssertionError(f"undeclared URL requested: {url}")

    opener.seen = seen  # type: ignore[attr-defined]
    return opener


ENTRY = {"key": "openml-7", "source": "openml", "openml_id": 7, "name": "toy", "role": "benchmark"}


def test_undeclared_key_is_refused() -> None:
    with pytest.raises(fetch.UndeclaredSource, match="refused"):
        fetch.resolve(["openml-999"], {"openml-7": ENTRY}, roles=("benchmark",))


def test_keel_local_is_not_fetchable() -> None:
    keel = {"key": "keel-x", "source": "keel-local", "name": "x", "role": "dev"}
    with pytest.raises(fetch.UndeclaredSource, match="not fetchable"):
        fetch.resolve(["keel-x"], {"keel-x": keel}, roles=("dev",))


def test_fetch_records_url_version_md5_and_sha256(tmp_path: Path) -> None:
    opener = opener_for()
    record = fetch.fetch(ENTRY, opener=opener, raw_root=tmp_path)
    assert record["status"] == "ok" and record["md5_verified"] is True
    assert record["version"] == 3 and record["url"].endswith("toy.arff")
    assert record["sha256"] == hashlib.sha256(BODY).hexdigest()
    assert (tmp_path / "openml" / "7" / "7-v3.arff").read_bytes() == BODY
    # Only the API description, qualities and the URL it named were requested.
    assert len(opener.seen) == 3


def test_name_mismatch_is_unavailable(tmp_path: Path) -> None:
    record = fetch.fetch({**ENTRY, "name": "other"}, opener=opener_for(), raw_root=tmp_path)
    assert record["status"] == "unavailable" and "NAME_MISMATCH" in record["reason"]
    assert not (tmp_path / "openml").exists()


def test_empty_download_is_unavailable(tmp_path: Path) -> None:
    record = fetch.fetch(ENTRY, opener=opener_for(body=b""), raw_root=tmp_path)
    assert record["status"] == "unavailable" and record["reason"].startswith("SOURCE_EMPTY")


def test_checksum_mismatch_is_unavailable(tmp_path: Path) -> None:
    record = fetch.fetch(ENTRY, opener=opener_for(body=BODY + b"x"), raw_root=tmp_path)
    assert record["status"] == "unavailable" and record["reason"].startswith("MD5_MISMATCH")


def test_declared_sources_have_forty_benchmark_and_nine_dev() -> None:
    sources = fetch.load_sources()
    roles = [entry["role"] for entry in sources.values()]
    assert roles.count("benchmark") == 40 and roles.count("dev") == 9
    u2 = [e for e in sources.values() if e["group"] == "u2_core"]
    assert len(u2) == 30 and {e["u2_catalogue_number"] for e in u2}.isdisjoint({10, 26})
