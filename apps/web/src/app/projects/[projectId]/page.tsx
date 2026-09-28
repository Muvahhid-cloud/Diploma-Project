"use client";

import { useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { ProjectEditor } from "@/features/editor/components/ProjectEditor";

function Editor() {
  const { projectId } = useParams<{ projectId: string }>();
  // ?generation=<id>: follow an AI generation started from the projects dashboard.
  const generationId = useSearchParams().get("generation");
  return <ProjectEditor key={projectId} projectId={projectId} generationId={generationId} />;
}

export default function ProjectEditorPage() {
  return (
    <RequireAuth>
      <Suspense fallback={<p className="p-8 text-sm text-neutral-500">Loading…</p>}>
        <Editor />
      </Suspense>
    </RequireAuth>
  );
}
