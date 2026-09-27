import type { BuildingSpecification } from "@buildai/schema";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { emptySpec, nextRoomKey, SPEC_PRESETS } from "../spec-presets";
import { checkSpecShape, SpecForm } from "./SpecForm";

function Harness({
  initial,
  onSpec,
}: {
  initial: BuildingSpecification;
  onSpec: (s: BuildingSpecification) => void;
}) {
  const [spec, setSpec] = useState(initial);
  const [seed, setSeed] = useState(0);
  return (
    <SpecForm
      spec={spec}
      onChange={(s) => {
        setSpec(s);
        onSpec(s);
      }}
      seed={seed}
      onSeedChange={setSeed}
      issues={[]}
    />
  );
}

function setup(initial = emptySpec()) {
  let last = initial;
  render(<Harness initial={initial} onSpec={(s) => (last = s)} />);
  return () => last;
}

describe("SpecForm", () => {
  it("presets are the shared reference specs and pass the generated schema", () => {
    expect(SPEC_PRESETS.length).toBeGreaterThanOrEqual(4);
    for (const p of SPEC_PRESETS) expect(checkSpecShape(p.spec)).toEqual([]);
    expect(SPEC_PRESETS[0].spec.targets.gross_floor_area_m2).toBe(280);
  });

  it("loads a preset", async () => {
    const spec = setup();
    await userEvent.selectOptions(screen.getByLabelText(/reference specification/i), "family-280");
    expect(spec().name).toBe("Modern family house");
    expect(spec().features?.garage?.cars).toBe(2);
    expect(screen.getByLabelText("Name")).toHaveValue("Modern family house");
  });

  it("edits storeys, area and rooms", async () => {
    const spec = setup();
    await userEvent.click(screen.getByRole("button", { name: "3" }));
    expect(spec().targets.storeys).toBe(3);

    const area = screen.getByLabelText(/floor area/i);
    await userEvent.clear(area);
    await userEvent.type(area, "240");
    expect(spec().targets.gross_floor_area_m2).toBe(240);
    await userEvent.clear(area);
    expect(spec().targets.gross_floor_area_m2).toBeNull(); // blank = derived by the engine

    const before = spec().rooms.length;
    await userEvent.click(screen.getByRole("button", { name: "+ Add room" }));
    expect(spec().rooms).toHaveLength(before + 1);
    expect(new Set(spec().rooms.map((r) => r.key)).size).toBe(before + 1); // keys stay unique

    await userEvent.click(screen.getByRole("button", { name: "Remove room 1" }));
    expect(spec().rooms).toHaveLength(before);
  });

  it("offers en-suite only for bedrooms", async () => {
    const spec = setup();
    const bedroomRow = spec().rooms.findIndex((r) => r.type === "bedroom");
    const enSuites = screen.getAllByLabelText("En-suite");
    expect(enSuites).toHaveLength(1);
    await userEvent.click(enSuites[0]);
    expect(spec().rooms[bedroomRow].features).toEqual(["en_suite"]);
  });

  it("balcony needs two floors", async () => {
    const spec = setup();
    await userEvent.click(screen.getByLabelText(/^Balcony/));
    expect(spec().features?.balconies).toEqual([{ level: 1 }]);
    await userEvent.click(screen.getByRole("button", { name: "1" }));
    expect(screen.getByLabelText(/^Balcony/)).toBeDisabled();
  });
});

describe("spec helpers", () => {
  it("nextRoomKey avoids collisions", () => {
    const spec = emptySpec();
    expect(nextRoomKey(spec, "study")).toBe("study");
    expect(nextRoomKey(spec, "bedroom")).toBe("bedroom_2");
  });

  it("checkSpecShape reports schema problems with JSON pointers", () => {
    const bad = { ...emptySpec(), targets: { storeys: 5 } } as BuildingSpecification;
    const issues = checkSpecShape(bad);
    expect(issues.length).toBeGreaterThan(0);
    expect(issues[0].path).toBe("/targets/storeys");
  });
});
