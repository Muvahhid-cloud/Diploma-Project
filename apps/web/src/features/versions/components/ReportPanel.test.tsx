import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { issueSchema, versionSchema, type Issue, type Version } from "@/lib/api/schemas";
import { useSelectionStore } from "@/stores/selection-store";

import { ReportPanel } from "./ReportPanel";

const WINDOW_ID = "5b0d4a1e-8c2f-4e3a-9d1b-2f6e7a8c9d01";
const WALL_ID = "5b0d4a1e-8c2f-4e3a-9d1b-2f6e7a8c9d02";

// A geometric finding as the API sends it (app/modules/building/geometry_checks.py).
const geometric: Issue = issueSchema.parse({
  severity: "error",
  code: "OPENING_OUTSIDE_WALL",
  path: "/elements/42/dimensions/width",
  message: "WN-G01 extends 0.100 m beyond the end of W-G01 (12.100 m of a 12.000 m wall)",
  suggestion: null,
  rule_ref: null,
  element_id: WINDOW_ID,
  constraint: "opening.within_length",
  related_ids: [WALL_ID],
  measure: { quantity: "opening_end", actual: 12.1, limit: 12.0, unit: "m" },
});

function version(issues: Issue[]): Version {
  return versionSchema.parse({
    id: "5b0d4a1e-8c2f-4e3a-9d1b-2f6e7a8c9d10",
    project_id: "5b0d4a1e-8c2f-4e3a-9d1b-2f6e7a8c9d11",
    parent_version_id: null,
    number: 3,
    label: "Generated",
    source: "layout",
    schema_version: "1.1.0",
    engine_version: "layout@1.2.0",
    rules_profile: "generic-residential@1",
    seed: 0,
    model_hash: "0".repeat(64),
    summary: {
      storeys: 2, gross_floor_area_m2: 240, net_floor_area_m2: 200, rooms: 12, bedrooms: 3,
      bathrooms: 2, wcs: 0, garage: false, balconies: 1, terraces: 0, walls: 30, doors: 12,
      windows: 20, elements: 150,
    }, // prettier-ignore
    created_at: "2026-09-29T00:00:00Z",
    prompt: null,
    spec: null,
    model: {},
    report: null,
    issues,
  });
}

beforeEach(() => useSelectionStore.getState().select(null));

describe("ReportPanel geometry checks", () => {
  it("says so when every element fits its geometry", () => {
    render(<ReportPanel version={version([])} onClose={vi.fn()} />);
    expect(screen.getByText("Geometry checks")).toBeInTheDocument();
    expect(
      screen.getByText(/every opening, wall, room, stair, slab and roof fits/),
    ).toBeInTheDocument();
  });

  it("lists geometric findings with their constraint and selects the element", async () => {
    render(<ReportPanel version={version([geometric])} onClose={vi.fn()} />);
    expect(screen.getByText("opening.within_length")).toBeInTheDocument();
    expect(screen.queryByText("Model checks")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /extends 0.100 m beyond/ }));
    expect(useSelectionStore.getState().selectedId).toBe(WINDOW_ID);
  });

  it("still accepts findings from before K2.5 (no constraint fields)", () => {
    const legacy = issueSchema.parse({
      severity: "warning",
      code: "ROOM_NOT_ON_SLAB",
      path: "/elements/3",
      message: "Balcony is not fully supported by a slab",
    });
    render(<ReportPanel version={version([legacy])} onClose={vi.fn()} />);
    expect(screen.getByText("Model checks")).toBeInTheDocument();
  });
});
