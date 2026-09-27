"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { ApiError } from "@/lib/api/errors";

import { useCreateProject, useDeleteProject, useProjects } from "../api";

export function ProjectsDashboard() {
  const projects = useProjects();
  const create = useCreateProject();
  const remove = useDeleteProject();
  const [name, setName] = useState("");

  function onCreate(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    create.mutate({ name }, { onSuccess: () => setName("") });
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 p-6">
      <h1 className="text-2xl font-semibold">Projects</h1>

      <form onSubmit={onCreate} className="flex gap-2">
        <label htmlFor="new-project" className="sr-only">
          New project name
        </label>
        <input
          id="new-project"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="New project name, e.g. Family house in Almaty"
          className="flex-1 rounded-md border border-neutral-300 bg-transparent px-3 py-2 dark:border-neutral-700"
        />
        <button
          type="submit"
          disabled={create.isPending || !name.trim()}
          className="rounded-md bg-neutral-900 px-4 py-2 text-white disabled:opacity-50 dark:bg-white dark:text-neutral-900"
        >
          Create
        </button>
      </form>
      {create.error instanceof ApiError && (
        <p role="alert" className="text-sm text-red-600">
          {create.error.message}
        </p>
      )}

      {projects.isPending && <p className="text-sm text-neutral-500">Loading projects…</p>}
      {projects.isError && (
        <p role="alert" className="text-sm text-red-600">
          Could not load projects.
        </p>
      )}
      {projects.data?.length === 0 && (
        <p className="text-sm text-neutral-500">No projects yet. Create your first one above.</p>
      )}

      <ul className="flex flex-col divide-y divide-neutral-200 dark:divide-neutral-800">
        {projects.data?.map((p) => (
          <li key={p.id} className="flex items-center justify-between py-3">
            <Link href={`/projects/${p.id}`} className="flex flex-col">
              <span className="font-medium">{p.name}</span>
              <span className="text-xs text-neutral-500">
                {p.region_code} · {p.currency} · {p.rules_profile_id}
              </span>
            </Link>
            <button
              type="button"
              onClick={() => {
                if (window.confirm(`Delete project "${p.name}"?`)) remove.mutate(p.id);
              }}
              className="text-sm text-neutral-500 hover:text-red-600"
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
