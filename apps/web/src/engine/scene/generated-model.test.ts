import { describe, expect, it } from "vitest";

import { parseBuildingModel } from "../model/parse";
import { generatedModelJson } from "../test-fixtures";
import { buildScene } from "./build-scene";
import { cameraPose } from "./camera-presets";

/**
 * Phase 2: models produced by the layout engine (not hand-authored) go through the unchanged
 * Phase 1 geometry engine. Fixture: data/fixtures/generated-house.model.json (`pnpm golden`).
 */
describe("generated BuildingModel through the 3D engine", () => {
  const index = parseBuildingModel(generatedModelJson());
  const scene = buildScene(index);

  it("comes from the layout engine", () => {
    expect(index.model.metadata.source).toBe("layout");
    expect(index.model.engine_version).toMatch(/^layout@/);
    expect(index.levels.map((l) => l.name)).toEqual(["Floor 1", "Floor 2"]);
  });

  it("builds every element into finite geometry that maps back to it", () => {
    for (const el of index.model.elements) {
      const parts = scene.byElement.get(el.id) ?? [];
      expect(parts.length, `${el.type} ${el.name}`).toBeGreaterThan(0);
      for (const d of parts) {
        expect(d.elementId).toBe(el.id);
        const pos = d.geometry.getAttribute("position").array as Float32Array;
        expect(pos.length).toBeGreaterThan(0);
        expect(Array.from(pos).every(Number.isFinite), `${el.name} has NaN vertices`).toBe(true);
      }
    }
  });

  it("contains the requested program", () => {
    const rooms = index.model.elements.filter((e) => e.type === "room");
    const types = rooms.map((r) => (r.type === "room" ? r.properties.room_type : ""));
    expect(types.filter((t) => t === "bedroom")).toHaveLength(4);
    expect(types).toContain("garage");
    expect(types).toContain("balcony");
    expect(index.model.elements.some((e) => e.type === "stair")).toBe(true);
  });

  it("has sensible bounds and a floor camera preset for every level", () => {
    expect(scene.bounds.max.x - scene.bounds.min.x).toBeGreaterThan(12);
    expect(scene.bounds.max.z).toBeGreaterThan(5.5);
    for (const level of index.levels) {
      const pose = cameraPose(`level:${level.id}`, scene.bounds, index);
      expect(pose.levelFilter).toBe(level.id);
    }
    expect(cameraPose("interior", scene.bounds, index).position.z).toBeGreaterThan(1);
  });
});
