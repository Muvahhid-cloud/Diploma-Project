"use client";

import { useParams } from "next/navigation";

import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { EditorShell } from "@/features/editor/components/EditorShell";

export default function ProjectEditorPage() {
  const { projectId } = useParams<{ projectId: string }>();
  return (
    <RequireAuth>
      <EditorShell projectId={projectId} />
    </RequireAuth>
  );
}
