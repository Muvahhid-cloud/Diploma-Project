import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from app.modules.building.issues import Issue
from app.modules.catalog.loader import KnowledgeLoadError, read_knowledge
from app.modules.catalog.registry import KnowledgeRegistry
from tests.building.helpers import DATA_DIR

BOOK_PACK = "spds-georgievsky-2004@1"
BOOK_DIR = "packs/spds-georgievsky-2004.v1"
CORE_PACK = "core@1"
CORE_DIR = "packs/core.v1"


def copy_data(tmp_path: Path) -> Path:
    """A private copy of the knowledge and rules-profile data to mutate in a test."""
    data = tmp_path / "data"
    shutil.copytree(DATA_DIR / "knowledge", data / "knowledge")
    shutil.copytree(DATA_DIR / "rules-profiles", data / "rules-profiles")
    return data


def edit_yaml(data: Path, rel: str, change: Callable[[Any], None]) -> None:
    path = data / "knowledge" / rel
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(doc)
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")


def load_issues(data: Path, *, verify: bool = False) -> list[Issue]:
    try:
        read_knowledge(data, verify=verify)
    except KnowledgeLoadError as exc:
        return exc.issues
    return []


def codes(issues: list[Issue]) -> set[str]:
    return {i.code for i in issues}


def item(doc: dict[str, Any], item_id: str) -> dict[str, Any]:
    found: dict[str, Any] = next(i for i in doc["items"] if i["id"] == item_id)
    return found


def real_registry() -> KnowledgeRegistry:
    return read_knowledge(DATA_DIR)
