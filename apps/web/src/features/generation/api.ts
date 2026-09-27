import type { BuildingSpecification } from "@buildai/schema";
import { useMutation, useQuery } from "@tanstack/react-query";

import { apiRequest } from "@/lib/api/client";
import { jobSchema, specValidationSchema } from "@/lib/api/schemas";

const project = (projectId: string) => `/projects/${encodeURIComponent(projectId)}`;

export function useValidateSpec(projectId: string) {
  return useMutation({
    mutationFn: (spec: BuildingSpecification) =>
      apiRequest(`${project(projectId)}/spec/validate`, specValidationSchema, {
        method: "POST",
        body: { spec },
      }),
  });
}

export interface GenerateInput {
  spec: BuildingSpecification;
  seed: number;
  label?: string;
}

export function useStartGeneration(projectId: string) {
  return useMutation({
    mutationFn: (input: GenerateInput) =>
      apiRequest(`${project(projectId)}/generate`, jobSchema, { method: "POST", body: input }),
  });
}

/** Polls a job until it finishes (the layout engine usually takes well under a few seconds). */
export function useJob(jobId: string | null) {
  return useQuery({
    queryKey: ["jobs", jobId],
    queryFn: () => apiRequest(`/jobs/${encodeURIComponent(jobId ?? "")}`, jobSchema),
    enabled: jobId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "succeeded" || status === "failed" ? false : 400;
    },
  });
}

/** Real job stages in order (mirrors STAGES in app/modules/generation/service.py). */
export const GENERATION_STAGES = [
  { id: "queued", label: "Validating the specification" },
  { id: "layout", label: "Planning the layout" },
  { id: "checking", label: "Checking building rules" },
  { id: "saving", label: "Saving the new version" },
] as const;
