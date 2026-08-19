from pathlib import Path

from rcqasyn.literature import scan_pdfs, write_inventory


def test_inventory_is_sorted_and_ignores_non_pdfs(tmp_path: Path) -> None:
    papers = tmp_path / "literature" / "papers"
    papers.mkdir(parents=True)
    (papers / "B.PDF").write_bytes(b"b")
    (papers / "a.pdf").write_bytes(b"a")
    (papers / "ignore.txt").write_text("x", encoding="utf-8")
    entries = scan_pdfs(papers, tmp_path)
    assert [entry.filename for entry in entries] == ["a.pdf", "B.PDF"]
    output = tmp_path / "inventory.csv"
    write_inventory(entries, output)
    first = output.read_bytes()
    write_inventory(scan_pdfs(papers, tmp_path), output)
    assert output.read_bytes() == first


def test_zero_pdfs_is_valid(tmp_path: Path) -> None:
    papers = tmp_path / "papers"
    papers.mkdir()
    assert scan_pdfs(papers, tmp_path) == []
