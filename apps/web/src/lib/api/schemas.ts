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

export const errorEnvelopeSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.array(z.object({ path: z.string().optional(), message: z.string() }).loose()),
  }),
});
export type ErrorDetail = z.infer<typeof errorEnvelopeSchema>["error"]["details"][number];
