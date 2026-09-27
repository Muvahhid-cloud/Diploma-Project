"use client";

import type { SceneGraph } from "@/engine/scene/build-scene";
import type { CameraPresetId } from "@/engine/scene/camera-presets";
import { useBuildingStore } from "@/stores/building-store";
import { useSelectionStore } from "@/stores/selection-store";
import { useViewerStore } from "@/stores/viewer-store";

import { SegmentButton } from "./panel-ui";

export function ViewerToolbar({ scene }: { scene: SceneGraph }) {
  const requestCamera = useViewerStore((s) => s.requestCamera);
  const projection = useViewerStore((s) => s.projection);
  const setProjection = useViewerStore((s) => s.setProjection);
  const selectedId = useSelectionStore((s) => s.selectedId);
  const buildMs = useBuildingStore((s) => s.buildMs);
  const selected = selectedId ? scene.index.elementsById.get(selectedId) : undefined;

  const presets: [CameraPresetId, string][] = [
    ["exterior", "Exterior"],
    ["front", "Front"],
    ["rear", "Rear"],
    ["top", "Top"],
    ...scene.index.levels.map((l) => [`level:${l.id}`, l.name] as [CameraPresetId, string]),
    ["interior", "Interior"],
  ];

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-neutral-200 bg-white px-3 py-2 dark:border-neutral-800 dark:bg-neutral-950">
      <div className="flex flex-wrap items-center gap-1" role="group" aria-label="Camera presets">
        <span className="mr-1 text-[11px] font-semibold uppercase tracking-wider text-neutral-500">
          View
        </span>
        {presets.map(([id, label]) => (
          <SegmentButton key={id} onClick={() => requestCamera(id)}>
            {label}
          </SegmentButton>
        ))}
        <SegmentButton
          onClick={() => requestCamera("exterior")}
          title="Reset camera to the default exterior view"
        >
          Reset view
        </SegmentButton>
      </div>
      <div className="flex items-center gap-1" role="group" aria-label="Projection">
        <SegmentButton
          active={projection === "perspective"}
          onClick={() => setProjection("perspective")}
        >
          Perspective
        </SegmentButton>
        <SegmentButton
          active={projection === "orthographic"}
          onClick={() => setProjection("orthographic")}
        >
          Orthographic
        </SegmentButton>
      </div>
      <p className="ml-auto text-xs tabular-nums text-neutral-500" aria-live="polite">
        {selected ? (
          <>
            Selected{" "}
            <span className="font-medium text-neutral-800 dark:text-neutral-100">
              {selected.name}
            </span>{" "}
            · Esc to clear ·{" "}
          </>
        ) : (
          "Drag to orbit · right-drag to pan · scroll to zoom · "
        )}
        {scene.stats.elements} elements · {scene.stats.meshes} meshes ·{" "}
        {Math.round(scene.stats.triangles / 1000)}k triangles
        {buildMs !== null && ` · built in ${Math.round(buildMs)} ms`}
      </p>
    </div>
  );
}
