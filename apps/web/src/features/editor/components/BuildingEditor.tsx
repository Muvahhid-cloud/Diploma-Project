"use client";

import { useEffect } from "react";

import type { SceneGraph } from "@/engine/scene/build-scene";
import { useSelectionStore } from "@/stores/selection-store";
import { BuildingViewer } from "@/viewer/BuildingViewer";

import { LeftPanel } from "./LeftPanel";
import { PropertiesPanel } from "./PropertiesPanel";
import { ViewerToolbar } from "./ViewerToolbar";

const PANEL = "border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-950";

/**
 * Editor layout. Large screens: controls (left) · 3D viewport (center) · properties (right),
 * tools under the viewport. Narrow screens: the viewport comes first, panels stack below.
 */
export function BuildingEditor({ scene }: { scene: SceneGraph }) {
  const select = useSelectionStore((s) => s.select);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") select(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [select]);

  return (
    <div className="flex flex-1 flex-col lg:min-h-[480px] lg:flex-row lg:overflow-hidden">
      <div className="order-1 flex h-[72vh] min-h-[360px] min-w-0 flex-col lg:order-2 lg:h-auto lg:flex-1">
        <div className="relative min-h-0 flex-1">
          <div className="absolute inset-0">
            <BuildingViewer scene={scene} />
          </div>
        </div>
        <ViewerToolbar scene={scene} />
      </div>
      <aside
        className={`order-2 border-t lg:order-1 lg:w-56 lg:shrink-0 lg:overflow-y-auto lg:border-t-0 lg:border-r xl:w-60 ${PANEL}`}
      >
        <LeftPanel index={scene.index} sectionMax={Math.max(1, Math.ceil(scene.bounds.max.z))} />
      </aside>
      <aside
        className={`order-3 border-t lg:w-72 lg:shrink-0 lg:overflow-y-auto lg:border-t-0 lg:border-l xl:w-80 ${PANEL}`}
      >
        <PropertiesPanel index={scene.index} />
      </aside>
    </div>
  );
}
