from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from rcqasyn.utils.hashing import sha256_file


@dataclass(frozen=True, slots=True)
class PaperInventoryEntry:
    filename: str
    relative_path: str
    sha256: str
    size_bytes: int


def scan_pdfs(papers_dir: Path, project_root: Path | None = None) -> list[PaperInventoryEntry]:
    papers_dir = Path(papers_dir)
    root = Path(project_root).resolve() if project_root else papers_dir.resolve().parent.parent
    if not papers_dir.exists():
        return []
    entries: list[PaperInventoryEntry] = []
    for path in papers_dir.iterdir():
        if path.is_file() and path.suffix.lower() == ".pdf":
            relative = path.resolve().relative_to(root).as_posix()
            entries.append(
                PaperInventoryEntry(
                    filename=path.name,
                    relative_path=relative,
                    sha256=sha256_file(path),
                    size_bytes=path.stat().st_size,
                )
            )
    return sorted(entries, key=lambda item: (item.filename.casefold(), item.relative_path))


def write_inventory(entries: list[PaperInventoryEntry], output: Path) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=["filename", "relative_path", "sha256", "size_bytes"], lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(
            {
                "filename": entry.filename,
                "relative_path": entry.relative_path,
                "sha256": entry.sha256,
                "size_bytes": entry.size_bytes,
            }
            for entry in entries
        )


def build_inventory(papers_dir: Path, output: Path, project_root: Path | None = None) -> list[PaperInventoryEntry]:
    entries = scan_pdfs(papers_dir, project_root)
    write_inventory(entries, output)
    return entries
