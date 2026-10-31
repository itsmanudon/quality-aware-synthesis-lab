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


PAGE = "https://sci2s.ugr.es/keel/imbalanced.php"
HREF = "keel-dataset/datasets/imbalanced/imb_IRlowerThan9/toy0.zip"
ZIP_URL = "https://sci2s.ugr.es/keel/keel-dataset/datasets/imbalanced/imb_IRlowerThan9/toy0.zip"
DAT = b"@relation toy0\n@attribute a real\n@attribute Class {positive,negative}\n@data\n1,positive\n"
KEEL = {"key": "keel-toy0", "source": "keel", "name": "toy0", "role": "dev",
        "keel_page": PAGE, "keel_href": HREF, "dat_name": "toy0.dat"}


def _zip(members: dict[str, bytes]) -> bytes:
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def keel_opener(page_html: str, body: bytes) -> Any:
    seen: list[str] = []

    def opener(request: Any, timeout: float) -> Response:
        seen.append(request.full_url)
        if request.full_url == PAGE:
            return Response(page_html.encode())
        if request.full_url == ZIP_URL:
            return Response(body)
        raise AssertionError(f"undeclared URL requested: {request.full_url}")

    opener.seen = seen  # type: ignore[attr-defined]
    return opener


def test_keel_uses_link_from_official_page_and_extracts_only_declared_member(
        tmp_path: Path) -> None:
    body = _zip({"../evil/toy0.dat": DAT, "other.txt": b"x"})
    opener = keel_opener(f'<a href="{HREF}">toy0</a>', body)
    record = fetch.fetch_keel(KEEL, opener=opener, raw_root=tmp_path)
    assert record["status"] == "ok" and record["url"] == ZIP_URL
    assert record["dat_sha256"] == hashlib.sha256(DAT).hexdigest()
    assert record["sha256"] == hashlib.sha256(body).hexdigest()
    # Written by basename under the dataset folder; the archive path is never used.
    assert (tmp_path / "keel" / "toy0" / "toy0.dat").read_bytes() == DAT
    assert not (tmp_path / "evil").exists() and not (tmp_path / "keel" / "other.txt").exists()
    assert opener.seen == [PAGE, ZIP_URL]


def test_keel_link_missing_from_page_is_unavailable(tmp_path: Path) -> None:
    opener = keel_opener("<html>no links</html>", _zip({"toy0.dat": DAT}))
    record = fetch.fetch_keel(KEEL, opener=opener, raw_root=tmp_path)
    assert record["status"] == "unavailable" and record["reason"] == "LINK_NOT_ON_PAGE"
    assert opener.seen == [PAGE]


def test_keel_recorded_hash_mismatch_is_unavailable(tmp_path: Path) -> None:
    entry = {**KEEL, "expected_dat_sha256": "0" * 64}
    opener = keel_opener(f'<a href="{HREF}">', _zip({"toy0.dat": DAT}))
    record = fetch.fetch_keel(entry, opener=opener, raw_root=tmp_path)
    assert record["status"] == "unavailable" and record["reason"].startswith("SHA256_MISMATCH")
    assert not (tmp_path / "keel").exists()


def test_keel_undeclared_page_is_refused(tmp_path: Path) -> None:
    entry = {**KEEL, "keel_page": "https://example.org/mirror.php"}
    record = fetch.fetch_keel(entry, opener=keel_opener("", b""), raw_root=tmp_path)
    assert record["status"] == "unavailable" and record["reason"].startswith("UNDECLARED_PAGE")


def test_declared_keel_entries_point_at_the_official_page() -> None:
    keel = [e for e in fetch.load_sources().values() if e["source"] == "keel"]
    assert len(keel) == 9
    assert all(e["keel_page"] in fetch.KEEL_PAGES and e["keel_href"].endswith(".zip")
               for e in keel)
