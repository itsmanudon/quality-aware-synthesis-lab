"""The one declared Study v3 dataset fetcher.

Usage::

    python -m study.v3.fetch meta  [KEY ...]   # OpenML description + qualities, no data
    python -m study.v3.fetch fetch [KEY ...]   # download the declared file

Rules (CLAUDE.md, "No mirrors, no guessed URLs"):

- Only keys declared in ``study/v3/sources.json`` are accepted; anything else is refused.
- Only OpenML is implemented. The download URL is taken from the OpenML API description
  of the declared dataset ID, never constructed or substituted.
- The declared name must equal OpenML's name for that ID, otherwise the source is
  recorded unavailable (``NAME_MISMATCH``) rather than silently accepted.
- Every download records URL, OpenML version, OpenML MD5 (verified) and SHA-256.
- A failed, empty or checksum-mismatched download is recorded ``unavailable`` with the
  reason; no other source is tried.
- KEEL dev files (approved by the user at Gate 0 in place of hand placement): the
  declared ``keel_href`` must appear verbatim as a link on the declared official
  ``keel_page``, and the archive URL is that link resolved against the page; nothing is
  constructed. Only the declared ``.dat`` member is extracted (by exact basename, never
  by archive path). When ``expected_dat_sha256`` is declared (the hash recorded for an
  earlier hand-placed copy), a different file is recorded ``unavailable``.

Raw files go to the gitignored ``study/v3/data/raw/``. Compact records are merged into
``study/v3/report/source-metadata.json`` (meta) and ``study/v3/report/acquisitions.json``
(fetch), both committed.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

HERE = Path(__file__).resolve().parent
SOURCES = HERE / "sources.json"
RAW_ROOT = HERE / "data" / "raw"
META_REPORT = HERE / "report" / "source-metadata.json"
ACQ_REPORT = HERE / "report" / "acquisitions.json"
OPENML_API = "https://www.openml.org/api/v1/json"
USER_AGENT = "rcqasyn-study-v3-fetcher/1"
QUALITIES = ("NumberOfInstances", "NumberOfFeatures", "NumberOfClasses",
             "MinorityClassSize", "MajorityClassSize", "NumberOfMissingValues",
             "NumberOfNumericFeatures", "NumberOfSymbolicFeatures")
FETCHABLE = ("openml", "keel")
KEEL_PAGES = ("https://sci2s.ugr.es/keel/imbalanced.php",)


class UndeclaredSource(KeyError):
    pass


def load_sources(path: Path = SOURCES) -> dict[str, dict[str, Any]]:
    declared = json.loads(path.read_text(encoding="utf-8"))
    entries = {entry["key"]: entry for entry in declared["datasets"]}
    if len(entries) != len(declared["datasets"]):
        raise ValueError("duplicate keys in sources.json")
    return entries


def resolve(keys: list[str] | None, sources: dict[str, dict[str, Any]],
            *, roles: tuple[str, ...]) -> list[dict[str, Any]]:
    if keys:
        missing = [key for key in keys if key not in sources]
        if missing:
            raise UndeclaredSource(f"not declared in sources.json, refused: {missing}")
        chosen = [sources[key] for key in keys]
    else:
        chosen = [entry for entry in sources.values() if entry["role"] in roles]
    for entry in chosen:
        if entry["source"] not in FETCHABLE:
            raise UndeclaredSource(
                f"{entry['key']}: source {entry['source']!r} is not fetchable here")
    return chosen


def _get_json(url: str, *, opener: Any = urllib.request.urlopen) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with opener(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    assert isinstance(payload, dict)
    return payload


def describe(entry: dict[str, Any], *, opener: Any = urllib.request.urlopen) -> dict[str, Any]:
    """Metadata only: OpenML description and qualities for one declared ID."""
    oid = int(entry["openml_id"])
    record: dict[str, Any] = {"key": entry["key"], "openml_id": oid,
                              "declared_name": entry["name"],
                              "queried_at": datetime.now(UTC).isoformat()}
    try:
        desc = _get_json(f"{OPENML_API}/data/{oid}", opener=opener)["data_set_description"]
        qual_raw = _get_json(f"{OPENML_API}/data/qualities/{oid}", opener=opener)
    except (OSError, urllib.error.URLError, KeyError, json.JSONDecodeError) as error:
        record.update(status="unavailable", reason=f"METADATA_FAILED: {error}")
        return record
    qualities = {
        item["name"]: item.get("value")
        for item in qual_raw.get("data_qualities", {}).get("quality", [])
        if item.get("name") in QUALITIES
    }
    record.update(
        openml_name=desc.get("name"), version=_int(desc.get("version")),
        status_openml=desc.get("status"), licence=desc.get("licence"),
        default_target=desc.get("default_target_attribute"),
        row_id_attribute=desc.get("row_id_attribute"),
        ignore_attribute=desc.get("ignore_attribute"),
        file_id=desc.get("file_id"), url=desc.get("url"), md5=desc.get("md5_checksum"),
        format=desc.get("format"), upload_date=desc.get("upload_date"),
        original_data_url=desc.get("original_data_url"),
        qualities={k: _num(v) for k, v in sorted(qualities.items())},
    )
    if desc.get("name") != entry["name"]:
        record.update(status="unavailable",
                      reason=f"NAME_MISMATCH: OpenML id {oid} is {desc.get('name')!r}")
    else:
        record["status"] = "ok"
    return record


def fetch(entry: dict[str, Any], *, opener: Any = urllib.request.urlopen,
          raw_root: Path = RAW_ROOT) -> dict[str, Any]:
    meta = describe(entry, opener=opener)
    record = {k: meta.get(k) for k in ("key", "openml_id", "declared_name", "openml_name",
                                       "version", "licence", "default_target", "url", "md5")}
    record["fetched_at"] = datetime.now(UTC).isoformat()
    if meta["status"] != "ok":
        record.update(status="unavailable", reason=meta.get("reason"))
        return record
    url = str(meta["url"])
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with opener(request, timeout=300) as response:
            body = response.read()
    except (OSError, urllib.error.URLError) as error:
        record.update(status="unavailable", reason=f"DOWNLOAD_FAILED: {error}")
        return record
    if not body:
        record.update(status="unavailable", reason="SOURCE_EMPTY: zero-byte response")
        return record
    md5 = hashlib.md5(body, usedforsecurity=False).hexdigest()
    if meta.get("md5") and md5 != meta["md5"]:
        record.update(status="unavailable", reason=f"MD5_MISMATCH: got {md5}")
        return record
    target_dir = raw_root / "openml" / str(entry["openml_id"])
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{entry['openml_id']}-v{meta.get('version')}.arff"
    target.write_bytes(body)
    record.update(status="ok", bytes=len(body), md5_verified=bool(meta.get("md5")),
                  sha256=hashlib.sha256(body).hexdigest(),
                  local_path=(target.relative_to(HERE).as_posix()
                              if target.is_relative_to(HERE) else str(target)))
    return record


def _download(url: str, opener: Any, timeout: float) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with opener(request, timeout=timeout) as response:
        return response.read()


def fetch_keel(entry: dict[str, Any], *, opener: Any = urllib.request.urlopen,
               raw_root: Path = RAW_ROOT) -> dict[str, Any]:
    """Download one declared KEEL archive via the link the official page itself gives."""
    page, href, dat_name = entry["keel_page"], entry["keel_href"], entry["dat_name"]
    record: dict[str, Any] = {"key": entry["key"], "declared_name": entry["name"],
                              "source": "keel", "keel_page": page, "keel_href": href,
                              "version": None, "fetched_at": datetime.now(UTC).isoformat()}
    if page not in KEEL_PAGES:
        record.update(status="unavailable", reason=f"UNDECLARED_PAGE: {page}")
        return record
    try:
        html = _download(page, opener, 60).decode("utf-8", errors="replace")
    except (OSError, urllib.error.URLError) as error:
        record.update(status="unavailable", reason=f"PAGE_FAILED: {error}")
        return record
    if f'href="{href}"' not in html:
        record.update(status="unavailable", reason="LINK_NOT_ON_PAGE")
        return record
    url = urllib.parse.urljoin(page, href)
    record["url"] = url
    try:
        body = _download(url, opener, 300)
    except (OSError, urllib.error.URLError) as error:
        record.update(status="unavailable", reason=f"DOWNLOAD_FAILED: {error}")
        return record
    if not body:
        record.update(status="unavailable", reason="SOURCE_EMPTY: zero-byte response")
        return record
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            members = [info for info in archive.infolist()
                       if PurePosixPath(info.filename).name == dat_name and not info.is_dir()]
            if len(members) != 1:
                record.update(status="unavailable",
                              reason=f"MEMBER_MISSING: {len(members)} members named {dat_name}")
                return record
            dat = archive.read(members[0])
    except zipfile.BadZipFile as error:
        record.update(status="unavailable", reason=f"BAD_ZIP: {error}")
        return record
    dat_sha = hashlib.sha256(dat).hexdigest()
    expected = entry.get("expected_dat_sha256")
    if expected and dat_sha != expected:
        record.update(status="unavailable", reason=f"SHA256_MISMATCH: got {dat_sha}")
        return record
    target_dir = raw_root / "keel" / entry["name"]
    target_dir.mkdir(parents=True, exist_ok=True)
    zip_name = PurePosixPath(urllib.parse.urlparse(url).path).name
    (target_dir / zip_name).write_bytes(body)
    (target_dir / dat_name).write_bytes(dat)
    local = target_dir / dat_name
    record.update(status="ok", bytes=len(body), sha256=hashlib.sha256(body).hexdigest(),
                  dat_bytes=len(dat), dat_sha256=dat_sha,
                  dat_sha256_matches_recorded=(dat_sha == expected) if expected else None,
                  local_path=(local.relative_to(HERE).as_posix()
                              if local.is_relative_to(HERE) else str(local)))
    return record


def _int(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _num(value: object) -> float | int | None:
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _merge(path: Path, records: list[dict[str, Any]]) -> None:
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for record in records:
        existing[record["key"]] = record
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("meta", "fetch"))
    parser.add_argument("keys", nargs="*")
    parser.add_argument("--roles", default="benchmark,candidate",
                        help="roles used when no keys are given")
    args = parser.parse_args(argv)
    sources = load_sources()
    entries = resolve(args.keys or None, sources, roles=tuple(args.roles.split(",")))
    records = []
    for entry in entries:
        if args.mode == "meta" and entry["source"] != "openml":
            continue  # KEEL has no metadata API; its record comes from fetch mode
        if args.mode == "meta":
            record = describe(entry)
        else:
            record = fetch_keel(entry) if entry["source"] == "keel" else fetch(entry)
        records.append(record)
        print(json.dumps({k: record.get(k) for k in ("key", "status", "reason", "openml_name",
                                                      "version", "bytes")}))
        time.sleep(0.5)  # be polite to the OpenML API
    _merge(META_REPORT if args.mode == "meta" else ACQ_REPORT, records)
    return 0 if all(r.get("status") == "ok" for r in records) else 1


if __name__ == "__main__":
    sys.exit(main())
