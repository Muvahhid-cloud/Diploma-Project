"use client";

import { DISCLAIMER } from "@/lib/disclaimer";
import type { Issue, Version } from "@/lib/api/schemas";
import { useSelectionStore } from "@/stores/selection-store";

/**
 * What the engine reported for this version (deviations from the spec, notes) and the rules
 * findings evaluated on read against the version's rules profile. Nothing is hidden: every
 * departure from the request is listed.
 */
export function ReportPanel({ version, onClose }: { version: Version; onClose: () => void }) {
  const select = useSelectionStore((s) => s.select);
  const report = version.report;
  const deviations = report?.warnings.filter((w) => !w.rule_ref) ?? [];
  const rules = version.issues.filter((i) => i.rule_ref);
  const model = version.issues.filter((i) => !i.rule_ref);
  const metrics = report?.metrics ?? {};

  return (
    <div className="flex h-full min-h-0 flex-col text-sm">
      <div className="flex items-start justify-between border-b border-neutral-200 px-4 py-3 dark:border-neutral-800">
        <div>
          <h2 className="font-semibold">Design report · v{version.number}</h2>
          <p className="text-xs text-neutral-500">
            {version.engine_version} · rules {version.rules_profile}
            {version.seed !== null && ` · seed ${version.seed}`}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close report"
          className="rounded-md px-2 text-lg leading-none text-neutral-400 hover:text-neutral-700"
        >
          ×
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
        <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
          <dt className="text-neutral-500">Gross floor area</dt>
          <dd className="text-right tabular-nums">
            {version.summary.gross_floor_area_m2} m²
            {typeof metrics.target_gross_floor_area_m2 === "number" &&
              ` (asked ${metrics.target_gross_floor_area_m2} m²)`}
          </dd>
          <dt className="text-neutral-500">Net room area</dt>
          <dd className="text-right tabular-nums">{version.summary.net_floor_area_m2} m²</dd>
          <dt className="text-neutral-500">Floors · rooms</dt>
          <dd className="text-right tabular-nums">
            {version.summary.storeys} · {version.summary.rooms}
          </dd>
          <dt className="text-neutral-500">Bedrooms · bathrooms · WCs</dt>
          <dd className="text-right tabular-nums">
            {version.summary.bedrooms} · {version.summary.bathrooms} · {version.summary.wcs}
          </dd>
          {typeof metrics.candidates_evaluated === "number" && (
            <>
              <dt className="text-neutral-500">Layout candidates</dt>
              <dd className="text-right tabular-nums">{metrics.candidates_evaluated}</dd>
            </>
          )}
        </dl>

        <Group
          title="Differences from the specification"
          issues={deviations}
          onSelect={select}
          empty="None — the layout matches the request."
        />
        {report && report.notes.length > 0 && (
          <section className="mt-4">
            <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-neutral-500">
              Engine notes
            </h3>
            <ul className="list-disc pl-4 text-xs text-neutral-600 dark:text-neutral-300">
              {report.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          </section>
        )}
        <Group
          title={`Rules check · ${version.rules_profile}`}
          issues={rules}
          onSelect={select}
          empty="No findings under the active rules profile."
        />
        {model.length > 0 && (
          <Group title="Model checks" issues={model} onSelect={select} empty="" />
        )}
        <p className="mt-4 rounded-md bg-amber-50 p-2 text-[11px] leading-snug text-amber-900 dark:bg-amber-950 dark:text-amber-200">
          Rules profiles perform conceptual checks only; they are not a building-code compliance
          check. {DISCLAIMER}
        </p>
      </div>
    </div>
  );
}

function Group({
  title,
  issues,
  onSelect,
  empty,
}: {
  title: string;
  issues: Issue[];
  onSelect: (id: string | null) => void;
  empty: string;
}) {
  return (
    <section className="mt-4">
      <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-neutral-500">
        {title} {issues.length > 0 && <span className="tabular-nums">({issues.length})</span>}
      </h3>
      {issues.length === 0 ? (
        <p className="text-xs text-neutral-500">{empty}</p>
      ) : (
        <ul className="flex flex-col gap-1">
          {issues.map((issue, i) => (
            <li key={`${issue.code}-${issue.path}-${i}`} className="text-xs">
              {issue.element_id ? (
                <button
                  type="button"
                  className="text-left text-amber-800 hover:underline dark:text-amber-300"
                  onClick={() => onSelect(issue.element_id ?? null)}
                >
                  {issue.message}
                </button>
              ) : (
                <span className="text-amber-800 dark:text-amber-300">{issue.message}</span>
              )}
              {issue.rule_ref && (
                <span className="ml-1 font-mono text-[10px] text-neutral-400">
                  {issue.rule_ref}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
