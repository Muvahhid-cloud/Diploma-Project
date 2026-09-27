"use client";

import Link from "next/link";

import { useProject } from "@/features/projects/api";
import { ApiError } from "@/lib/api/errors";

/**
 * Editor layout: model tree | 3D viewer | inspector.
 * Phase 0 renders the empty shell; the viewer and panels arrive in Phase 1.
 */
export function EditorShell({ projectId }: { projectId: string }) {
  const project = useProject(projectId);

  if (project.isPending) return <p className="p-6 text-sm text-neutral-500">Loading project…</p>;
  if (project.isError) {
    const notFound = project.error instanceof ApiError && project.error.status === 404;
    return (
      <div className="p-6">
        <p role="alert" className="text-sm text-red-600">
          {notFound ? "Project not found." : "Could not load project."}
        </p>
        <Link href="/projects" className="text-sm underline">
          Back to projects
        </Link>
      </div>
    );
  }

  const p = project.data;
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center gap-3 border-b border-neutral-200 px-4 py-2 dark:border-neutral-800">
        <Link href="/projects" className="text-sm text-neutral-500 hover:underline">
          Projects
        </Link>
        <span className="text-neutral-400">/</span>
        <h1 className="font-medium">{p.name}</h1>
        <span className="ml-auto text-xs text-neutral-500">
          {p.region_code} · {p.currency} · rules: {p.rules_profile_id}
        </span>
      </div>
      <div className="grid min-h-[480px] flex-1 grid-cols-[240px_1fr_300px]">
        <Panel title="Model tree">No building model yet.</Panel>
        <section
          aria-label="3D viewer"
          className="flex flex-col items-center justify-center gap-2 bg-neutral-100 text-sm text-neutral-500 dark:bg-neutral-900"
        >
          <p>
            This project has no building model yet — models are generated from specifications in
            Phase 2.
          </p>
          <Link href="/" className="text-blue-700 underline dark:text-blue-400">
            Open the procedural demo house
          </Link>
        </section>
        <Panel title="Inspector">Select an object to inspect its properties.</Panel>
      </div>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <aside
      aria-label={title}
      className="flex flex-col gap-2 border-neutral-200 p-3 text-sm first:border-r last:border-l dark:border-neutral-800"
    >
      <h2 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">{title}</h2>
      <p className="text-neutral-500">{children}</p>
    </aside>
  );
}
