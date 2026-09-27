import { describe, expect, it } from "vitest";

import { bySemanticKey, demoIndex } from "@/engine/test-fixtures";

import { describeElement } from "./describe-element";

const index = demoIndex();
const rows = (key: string) => {
  const d = describeElement(bySemanticKey(index.model, key), index);
  return {
    d,
    row: (label: string) => d.sections.flatMap((s) => s.rows).find((r) => r.label === label)?.value,
  };
};

describe("describeElement", () => {
  it("describes a wall from the model (dimensions, material, identity)", () => {
    const wall = bySemanticKey(index.model, "wall:G-S");
    const { d, row } = rows("wall:G-S");
    expect(d.title).toBe("W-G01");
    expect(d.typeLabel).toBe("Exterior wall");
    expect(row("Length")).toBe("12 m");
    expect(row("Height")).toBe("2.8 m");
    expect(row("Thickness")).toBe("0.3 m");
    expect(row("Material")).toBe("Brick");
    expect(row("Left face finish")).toBe("Interior plaster (white)");
    expect(row("Load-bearing")).toBe("Yes");
    expect(row("ID")).toBe(wall.id);
    expect(row("Level")).toBe("Floor 1 (+0 m)");
  });

  it("describes rooms with area and type", () => {
    const { d, row } = rows("room:living");
    expect(d.typeLabel).toBe("Room · Living");
    expect(row("Area")).toBe("29.6 m²");
    expect(row("Boundary")).toBe("4 points");
    expect(row("Floor finish")).toBe("Oak parquet");
  });

  it("lists relationships with clickable targets", () => {
    const { d } = rows("door:front");
    const rels = d.sections.find((s) => s.title.startsWith("Relationships"))!.rows;
    expect(rels.map((r) => r.label)).toEqual(["Hosted by", "Connects"]);
    expect(rels[0].value).toBe("W-G01 (Exterior wall)");
    expect(rels[1].targetId).toBe(bySemanticKey(index.model, "room:entrance").id);
  });

  it("resolves level references in stair properties", () => {
    const { row } = rows("stair:main");
    expect(row("From level")).toBe("Floor 1");
    expect(row("To level")).toBe("Floor 2");
    expect(row("Risers")).toBe("16");
  });
});
