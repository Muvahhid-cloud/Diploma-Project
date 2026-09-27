// Zod schemas for API DTOs (auth, projects).
// Building contracts (spec/model) are GENERATED into @buildai/schema from Pydantic (Phase 1);
// these small transport DTOs are hand-written and must mirror apps/api/app/modules/*/schemas.py.
import { z } from "zod";

export const userSchema = z.object({
  id: z.uuid(),
  email: z.string(),
  display_name: z.string(),
  created_at: z.string(),
});
export type User = z.infer<typeof userSchema>;

export const tokenResponseSchema = z.object({
  access_token: z.string().min(1),
  token_type: z.literal("bearer"),
  expires_in: z.number().int().positive(),
  user: userSchema,
});
export type TokenResponse = z.infer<typeof tokenResponseSchema>;

export const projectSchema = z.object({
  id: z.uuid(),
  name: z.string(),
  description: z.string(),
  building_type: z.literal("single_family_house"),
  region_code: z.string(),
  currency: z.string().regex(/^[A-Z]{3}$/),
  rules_profile_id: z.string(),
  current_version_id: z.uuid().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type Project = z.infer<typeof projectSchema>;

export const projectListSchema = z.object({ items: z.array(projectSchema) });

// --- Issues, versions, jobs (mirror app/modules/{building/issues,versions,jobs,generation}) ---

export const issueSchema = z.object({
  severity: z.enum(["error", "warning"]),
  code: z.string(),
  path: z.string(),
  message: z.string(),
  suggestion: z.string().nullable().optional(),
  rule_ref: z.string().nullable().optional(),
  element_id: z.uuid().nullable().optional(),
});
export type Issue = z.infer<typeof issueSchema>;

export const modelSummarySchema = z.object({
  storeys: z.number().int(),
  gross_floor_area_m2: z.number(),
  net_floor_area_m2: z.number(),
  rooms: z.number().int(),
  bedrooms: z.number().int(),
  bathrooms: z.number().int(),
  wcs: z.number().int(),
  garage: z.boolean(),
  balconies: z.number().int(),
  terraces: z.number().int(),
  walls: z.number().int(),
  doors: z.number().int(),
  windows: z.number().int(),
  elements: z.number().int(),
});
export type ModelSummary = z.infer<typeof modelSummarySchema>;

export const versionSummarySchema = z.object({
  id: z.uuid(),
  project_id: z.uuid(),
  parent_version_id: z.uuid().nullable(),
  number: z.number().int(),
  label: z.string(),
  source: z.string(),
  schema_version: z.string(),
  engine_version: z.string(),
  rules_profile: z.string(),
  seed: z.number().int().nullable(),
  model_hash: z.string(),
  summary: modelSummarySchema,
  created_at: z.string(),
});
export type VersionSummary = z.infer<typeof versionSummarySchema>;

export const versionListSchema = z.object({ items: z.array(versionSummarySchema) });

export const generationReportSchema = z.object({
  warnings: z.array(issueSchema),
  notes: z.array(z.string()),
  metrics: z.record(z.string(), z.unknown()),
});
export type GenerationReport = z.infer<typeof generationReportSchema>;

export const versionSchema = versionSummarySchema.extend({
  prompt: z.string().nullable(),
  // Building documents are validated by the generated schemas where they are used
  // (spec: form; model: building store), so they stay opaque here.
  spec: z.unknown().nullable(),
  model: z.unknown(),
  report: generationReportSchema.nullable(),
  issues: z.array(issueSchema),
});
export type Version = z.infer<typeof versionSchema>;

export const jobSchema = z.object({
  id: z.uuid(),
  project_id: z.uuid(),
  kind: z.string(),
  status: z.enum(["queued", "running", "succeeded", "failed"]),
  stage: z.string().nullable(),
  progress: z.number(),
  result: z.record(z.string(), z.unknown()).nullable(),
  error: z
    .object({
      code: z.string(),
      message: z.string(),
      details: z.array(z.object({ message: z.string() }).loose()),
    })
    .nullable(),
  created_at: z.string(),
  started_at: z.string().nullable(),
  finished_at: z.string().nullable(),
});
export type Job = z.infer<typeof jobSchema>;

export const specValidationSchema = z.object({
  valid: z.boolean(),
  issues: z.array(issueSchema),
  rules_profile: z.string(),
});
export type SpecValidation = z.infer<typeof specValidationSchema>;

export const errorEnvelopeSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.array(z.object({ path: z.string().optional(), message: z.string() }).loose()),
  }),
});
export type ErrorDetail = z.infer<typeof errorEnvelopeSchema>["error"]["details"][number];
