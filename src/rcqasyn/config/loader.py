from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .models import Config, ResolvedConfig


def discover_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file() or (candidate / "configs" / "base.yaml").is_file():
            return candidate
    return current


def load_config(
    config_path: Path | None = None, project_root: Path | None = None
) -> ResolvedConfig:
    root = Path(project_root).expanduser().resolve() if project_root else None
    if root is None:
        root = discover_project_root(Path(config_path).parent if config_path else None)
    raw_path = Path(config_path) if config_path else Path("configs/base.yaml")
    path = raw_path.expanduser()
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"config file not found: {path}")
    with path.open("r", encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    if not isinstance(raw, dict):
        raise ValueError("config must contain a YAML mapping")  # noqa: TRY004
    try:
        config = Config.model_validate(raw)
    except ValidationError as error:
        raise ValueError(f"invalid config {path}: {error}") from error
    return ResolvedConfig(
        project=config.project,
        artifacts=type(config.artifacts)(root=_resolve(root, config.artifacts.root)),
        literature=type(config.literature)(
            papers_dir=_resolve(root, config.literature.papers_dir),
            notes_dir=_resolve(root, config.literature.notes_dir),
        ),
        project_root=root,
        config_path=path,
    )


def _resolve(root: Path, value: Path) -> Path:
    return value if value.is_absolute() else (root / value).resolve()
