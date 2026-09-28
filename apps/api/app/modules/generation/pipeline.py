"""Spec -> layout -> checks -> new version: the step shared by the spec-form job (Phase 2) and
AI generation (Phase 3). It never interprets language and contains no layout logic itself.

    layout engine (tier-3 feasibility + model invariants, in a worker thread)
      -> final model validation (errors abort) -> rules findings -> immutable version
"""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.auth.models import User
from app.modules.building.issues import Issue, errors
from app.modules.building.specification import BuildingSpecification
from app.modules.building.validation import validate_model
from app.modules.layout.engine import LayoutError, LayoutResult, generate_layout
from app.modules.projects.models import Project
from app.modules.rules.model_checks import check_model
from app.modules.versions.models import ProjectVersion
from app.modules.versions.schemas import GenerationProvenance, GenerationReport
from app.modules.versions.service import VersionService
from app.shared.data_files import material_ids, rules_profile

StageCallback = Callable[[str], Awaitable[None]]


@dataclass(frozen=True)
class PipelineResult:
    version: ProjectVersion
    report: GenerationReport
    layout: LayoutResult


async def _noop(_: str) -> None:
    return None


async def layout_and_save(
    session: AsyncSession,
    project: Project,
    user: User | None,
    *,
    spec: BuildingSpecification,
    seed: int,
    label: str,
    source: str,
    spec_warnings: list[Issue],
    extra_warnings: list[Issue] | None = None,
    prompt: str | None = None,
    provenance: GenerationProvenance | None = None,
    on_stage: StageCallback = _noop,
) -> PipelineResult:
    """Run the layout engine for `spec` and store the result as the project's new version.

    Raises LayoutError (LAYOUT_INFEASIBLE / LAYOUT_INVALID / MODEL_INVALID). Commits."""
    data_dir = get_settings().data_dir
    project_id: uuid.UUID = project.id
    profile = rules_profile(data_dir, project.rules_profile_id)
    materials = material_ids(data_dir)
    await on_stage("layout")
    result = await asyncio.to_thread(
        generate_layout,
        spec,
        profile,
        id_namespace=project_id,
        seed=seed,
        material_ids=materials,
    )
    await on_stage("checking")
    model_errors = errors(validate_model(result.model, material_ids=materials))
    if model_errors:  # the engine validates its candidates; this is a last line of defence
        raise LayoutError(
            "MODEL_INVALID", "The generated building model failed validation", model_errors
        )
    findings = check_model(result.model, profile)
    report = GenerationReport(
        warnings=(extra_warnings or []) + spec_warnings + result.warnings + findings,
        notes=result.notes,
        metrics=asdict(result.metrics) if result.metrics else {},
        generation=provenance,
    )
    await on_stage("saving")
    version = await VersionService(session).create(
        project,
        user,
        model=result.model,
        spec=spec,
        source=source,
        label=label,
        rules_profile_ref=profile.ref,
        prompt=prompt,
        report=report,
    )
    return PipelineResult(version=version, report=report, layout=result)
