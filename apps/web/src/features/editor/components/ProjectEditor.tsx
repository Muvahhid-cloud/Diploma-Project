"use client";

import { type BuildingSpecification, buildingSpecificationSchema } from "@buildai/schema";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { materialCache } from "@/engine/materials/material-cache";
import { GenerationPanel } from "@/features/generation/components/GenerationPanel";
import { useProject } from "@/features/projects/api";
import { useImportDemo, useVersion, useVersions } from "@/features/versions/api";
import { ReportPanel } from "@/features/versions/components/ReportPanel";
import { ApiError } from "@/lib/api/errors";
import type { Version } from "@/lib/api/schemas";
import { useBuildingStore } from "@/stores/building-store";
import { useProjectStore } from "@/stores/project-store";
import { useSelectionStore } from "@/stores/selection-store";
import { useViewerStore } from "@/stores/viewer-store";

import { BuildingEditor } from "./BuildingEditor";

type Drawer = "none" | "generate" | "report";

/**
 * Project editor: shows one version of the project in the Phase 1 viewer. The model comes from
 * the stored version (validated by the generated schema in the building store); new versions
 * are generated from a specification by the layout engine.
 */
export function ProjectEditor({ projectId }: { projectId: string }) {
  const project = useProject(projectId);
  const versions = useVersions(projectId);
  const [chosen, setChosen] = useState<string | null>(null);
  const versionId = chosen ?? project.data?.current_version_id ?? null;
  const version = useVersion(projectId, versionId);
  const [drawer, setDrawer] = useState<Drawer>("none");
  const [justGenerated, setJustGenerated] = useState<string | null>(null);
  const status = useBuildingStore((s) => s.status);
  const scene = useBuildingStore((s) => s.scene);
  const buildError = useBuildingStore((s) => s.error);

  useEffect(() => {
    const data = version.data;
    if (!data) return;
    useBuildingStore.getState().load(data.model);
    const building = useBuildingStore.getState().index?.model.building;
    useProjectStore.getState().setProject({
      id: projectId,
      name: project.data?.name ?? building?.name ?? "Project",
      source: "project",
      description: building?.description ?? "",
    });
    useSelectionStore.getState().select(null);
    useViewerStore.getState().reset();
  }, [version.data, projectId, project.data?.name]);

  useEffect(
    () => () => {
      useBuildingStore.getState().clear();
      useProjectStore.getState().setProject(null);
      materialCache.dispose();
    },
    [],
  );

  const onGenerated = useCallback((id: string) => {
    setChosen(id);
    setJustGenerated(id);
    setDrawer("none");
  }, []);

  if (project.isPending) return <Centered>Loading project…</Centered>;
  if (project.isError) {
    const notFound = project.error instanceof ApiError && project.error.status === 404;
    return (
      <Centered tone="error">
        {notFound ? "Project not found." : "Could not load the project."}{" "}
        <Link href="/projects" className="underline">
          Back to projects
        </Link>
      </Centered>
    );
  }

  const p = project.data;
  const hasVersions = (versions.data?.length ?? 0) > 0;
  const spec = specOf(version.data);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-neutral-200 px-4 py-2 dark:border-neutral-800">
        <Link href="/projects" className="text-sm text-neutral-500 hover:underline">
          Projects
        </Link>
        <span className="text-neutral-400">/</span>
        <h1 className="font-medium">{p.name}</h1>
        {hasVersions && (
          <select
            aria-label="Version"
            className="rounded-md border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
            value={versionId ?? ""}
            onChange={(e) => {
              setChosen(e.target.value);
              setJustGenerated(null);
            }}
          >
            {versions.data?.map((v) => (
              <option key={v.id} value={v.id}>
                v{v.number} · {v.label}
                {v.id === p.current_version_id ? " (latest)" : ""}
              </option>
            ))}
          </select>
        )}
        <span className="text-xs text-neutral-500">
          {p.region_code} · {p.currency} · rules {p.rules_profile_id}
        </span>
        <div className="ml-auto flex items-center gap-2">
          {version.data && (
            <button
              type="button"
              onClick={() => setDrawer(drawer === "report" ? "none" : "report")}
              aria-pressed={drawer === "report"}
              className="rounded-md px-3 py-1 text-sm text-neutral-700 hover:bg-neutral-100 dark:text-neutral-200 dark:hover:bg-neutral-800"
            >
              Report
              {reportCount(version.data) > 0 && (
                <span className="ml-1 rounded-full bg-amber-100 px-1.5 text-xs text-amber-800">
                  {reportCount(version.data)}
                </span>
              )}
            </button>
          )}
          {hasVersions && (
            <button
              type="button"
              onClick={() => setDrawer(drawer === "generate" ? "none" : "generate")}
              aria-pressed={drawer === "generate"}
              className="rounded-md bg-blue-600 px-3 py-1 text-sm font-semibold text-white hover:bg-blue-700"
            >
              New design
            </button>
          )}
        </div>
      </div>

      {justGenerated && version.data?.id === justGenerated && (
        <GeneratedBanner
          version={version.data}
          onReport={() => setDrawer("report")}
          onDismiss={() => setJustGenerated(null)}
        />
      )}

      <div className="relative flex min-h-0 flex-1 flex-col">
        {versions.isPending ? (
          <Centered>Loading versions…</Centered>
        ) : !hasVersions ? (
          <StartView projectId={projectId} onGenerated={onGenerated} />
        ) : version.isError ? (
          <Centered tone="error">Could not load this version.</Centered>
        ) : status === "error" ? (
          <Centered tone="error">
            <span className="block font-medium">The building model is invalid</span>
            <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap text-xs">
              {buildError}
            </pre>
          </Centered>
        ) : !scene || !version.data ? (
          <Centered>Building the 3D model…</Centered>
        ) : (
          <BuildingEditor scene={scene} />
        )}

        {drawer !== "none" && (
          <aside
            aria-label={drawer === "generate" ? "Generate a new design" : "Design report"}
            className="absolute inset-y-0 right-0 z-10 flex w-full max-w-[520px] flex-col border-l border-neutral-200 bg-white shadow-xl dark:border-neutral-800 dark:bg-neutral-950"
          >
            {drawer === "generate" ? (
              <GenerationPanel
                projectId={projectId}
                initialSpec={spec}
                onGenerated={onGenerated}
                onClose={() => setDrawer("none")}
              />
            ) : version.data ? (
              <ReportPanel version={version.data} onClose={() => setDrawer("none")} />
            ) : null}
          </aside>
        )}
      </div>
    </div>
  );
}

function specOf(version: Version | undefined): BuildingSpecification | null {
  if (!version?.spec) return null;
  const parsed = buildingSpecificationSchema.safeParse(version.spec);
  return parsed.success ? parsed.data : null;
}

function reportCount(version: Version): number {
  const deviations = version.report?.warnings.filter((w) => !w.rule_ref).length ?? 0;
  return deviations + version.issues.length;
}

function StartView({
  projectId,
  onGenerated,
}: {
  projectId: string;
  onGenerated: (versionId: string) => void;
}) {
  const importDemo = useImportDemo(projectId);
  return (
    <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
      <div className="flex min-h-0 flex-1 flex-col border-neutral-200 lg:max-w-[560px] lg:border-r dark:border-neutral-800">
        <GenerationPanel projectId={projectId} onGenerated={onGenerated} />
      </div>
      <div className="flex flex-1 flex-col items-center justify-center gap-4 bg-neutral-50 p-8 text-center dark:bg-neutral-900">
        <p className="max-w-md text-sm text-neutral-600 dark:text-neutral-300">
          This project has no design yet. Fill in the specification — or start from a reference
          preset — and generate a house. Each generation is saved as a new version you can open,
          inspect and compare.
        </p>
        <button
          type="button"
          onClick={() => importDemo.mutate(undefined, { onSuccess: (v) => onGenerated(v.id) })}
          disabled={importDemo.isPending}
          className="rounded-md border border-neutral-300 px-3 py-1.5 text-sm hover:bg-white disabled:opacity-50 dark:border-neutral-700 dark:hover:bg-neutral-800"
        >
          {importDemo.isPending ? "Importing…" : "Or import the hand-authored demo house"}
        </button>
        {importDemo.isError && (
          <p role="alert" className="text-sm text-red-600">
            {importDemo.error.message}
          </p>
        )}
      </div>
    </div>
  );
}

function GeneratedBanner({
  version,
  onReport,
  onDismiss,
}: {
  version: Version;
  onReport: () => void;
  onDismiss: () => void;
}) {
  const s = version.summary;
  const count = reportCount(version);
  return (
    <div
      role="status"
      className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-green-200 bg-green-50 px-4 py-2 text-sm text-green-900 dark:border-green-900 dark:bg-green-950 dark:text-green-200"
    >
      <span className="font-semibold">Generated v{version.number}</span>
      <span className="tabular-nums">
        {s.storeys} floor{s.storeys > 1 ? "s" : ""} · {s.gross_floor_area_m2} m² · {s.rooms} rooms ·{" "}
        {s.bedrooms} bedrooms · {s.bathrooms} bathrooms
      </span>
      {count > 0 && (
        <button type="button" onClick={onReport} className="underline">
          {count} note{count > 1 ? "s" : ""} to review
        </button>
      )}
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss"
        className="ml-auto text-green-700 hover:text-green-900"
      >
        ×
      </button>
    </div>
  );
}

function Centered({ children, tone }: { children: React.ReactNode; tone?: "error" }) {
  return (
    <div className="flex flex-1 items-center justify-center p-8">
      <div
        role={tone === "error" ? "alert" : "status"}
        className={"max-w-xl text-sm " + (tone === "error" ? "text-red-600" : "text-neutral-500")}
      >
        {children}
      </div>
    </div>
  );
}
