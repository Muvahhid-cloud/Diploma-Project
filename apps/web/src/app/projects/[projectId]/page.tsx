"use client";

import { useParams } from "next/navigation";

import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { ProjectEditor } from "@/features/editor/components/ProjectEditor";

export default function ProjectEditorPage() {
  const { projectId } = useParams<{ projectId: string }>();
  return (
    <RequireAuth>
      <ProjectEditor projectId={projectId} />
    </RequireAuth>
  );
}
