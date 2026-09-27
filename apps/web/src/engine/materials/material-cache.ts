// One THREE material per (material id, variant), created lazily and shared by every mesh.
import { Color, FrontSide, MeshStandardMaterial } from "three";

import { MATERIAL_PRESETS, materialPreset } from "./library";

export type MaterialVariant = "default" | "selected" | "ghost";

const SELECTION_EMISSIVE = new Color("#2f6fed");

export class MaterialCache {
  private readonly materials = new Map<string, MeshStandardMaterial>();
  private readonly missing = new Set<string>();

  get(id: string, variant: MaterialVariant = "default"): MeshStandardMaterial {
    const key = `${id}|${variant}`;
    let material = this.materials.get(key);
    if (!material) {
      material = this.create(id, variant);
      this.materials.set(key, material);
    }
    return material;
  }

  /** Material ids requested by geometry that are not in the library. */
  get missingIds(): string[] {
    return [...this.missing].sort();
  }

  get size(): number {
    return this.materials.size;
  }

  dispose(): void {
    for (const m of this.materials.values()) m.dispose();
    this.materials.clear();
    this.missing.clear();
  }

  private create(id: string, variant: MaterialVariant): MeshStandardMaterial {
    if (!MATERIAL_PRESETS.has(id)) this.missing.add(id);
    const p = materialPreset(id);
    const opacity = p.opacity ?? 1;
    const material = new MeshStandardMaterial({
      name: `${id}:${variant}`,
      color: new Color(p.color),
      roughness: p.roughness,
      metalness: p.metalness,
      side: FrontSide,
      transparent: opacity < 1,
      opacity,
      depthWrite: opacity >= 1,
    });
    if (variant === "selected") {
      material.emissive = SELECTION_EMISSIVE;
      material.emissiveIntensity = 0.45;
    } else if (variant === "ghost") {
      material.transparent = true;
      material.opacity = Math.min(opacity, 0.12);
      material.depthWrite = false;
    }
    return material;
  }
}

/** App-wide cache: materials are reused across meshes and scene rebuilds. */
export const materialCache = new MaterialCache();
