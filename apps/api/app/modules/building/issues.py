"""The single issue shape used by spec validation, rules evaluation and model validation.

`path` is a JSON pointer into the validated document (spec or model) so the UI can point at the
offending field; `rule_ref` (e.g. `generic-residential@1:stairs.riser_m`) makes every rules
finding traceable to the exact rule that produced it.
"""

import uuid
from typing import Literal

from app.modules.building.primitives import Frozen

Severity = Literal["error", "warning"]


class Issue(Frozen):
    severity: Severity
    code: str
    path: str
    message: str
    suggestion: str | None = None
    rule_ref: str | None = None
    element_id: uuid.UUID | None = None


def errors[T: Issue](issues: list[T]) -> list[T]:
    return [i for i in issues if i.severity == "error"]


def pointer(*parts: str | int) -> str:
    """Build a JSON pointer, escaping `~` and `/` in segments."""
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts) or ""
