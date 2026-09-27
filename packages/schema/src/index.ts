// Public entry of @buildai/schema. The canonical schema lives in Pydantic
// (apps/api/app/modules/building); everything under ./generated and ../generated is produced
// by `pnpm schema`. See docs/building-model.md §8 and CLAUDE.md rule 7.
import { z } from "zod";

import buildingModelJsonSchema from "../generated/building-model.schema.json";
import type { BuildingModel } from "./generated/building-model";

export type * from "./generated/building-model";
export { buildingModelJsonSchema };

type JsonSchemaInput = Parameters<typeof z.fromJSONSchema>[0];

/**
 * Runtime validator derived from the same JSON Schema as the TS types, so the two can't drift.
 * Structural validation only — cross-element invariants live in the API (validation.py) and
 * in the web engine's model index.
 */
export const buildingModelSchema = z.fromJSONSchema(
  buildingModelJsonSchema as JsonSchemaInput,
) as z.ZodType<BuildingModel>;
