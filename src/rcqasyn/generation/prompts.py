from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PromptTemplate:
    version: str
    path: Path
    text: str
    sha256: str

    def render(self, **values: object) -> str:
        return self.text.format(**values)


def load_prompt(kind: str, version: str = "v1", project_root: Path | None = None) -> PromptTemplate:
    root = (project_root or Path.cwd()).resolve()
    path = root / "prompts" / kind / f"{version}.txt"
    if not path.is_file():
        raise FileNotFoundError(f"prompt template not found: {path}")
    text = path.read_text(encoding="utf-8")
    return PromptTemplate(version=f"{kind}-{version}", path=path, text=text, sha256=hashlib.sha256(text.encode()).hexdigest())
