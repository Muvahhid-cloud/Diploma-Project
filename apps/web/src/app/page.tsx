import Link from "next/link";

export default function Home() {
  return (
    <div className="mx-auto flex max-w-2xl flex-1 flex-col justify-center gap-6 p-8">
      <h1 className="text-4xl font-semibold tracking-tight">BuildAI 3D</h1>
      <p className="text-lg text-neutral-600 dark:text-neutral-400">
        Describe a house in plain language and get an editable 3D building model with material
        quantities and a preliminary construction cost.
      </p>
      <div className="flex gap-3">
        <Link
          href="/projects"
          className="rounded-md bg-neutral-900 px-4 py-2 text-white dark:bg-white dark:text-neutral-900"
        >
          Open projects
        </Link>
        <Link href="/register" className="rounded-md border border-neutral-300 px-4 py-2">
          Create account
        </Link>
      </div>
    </div>
  );
}
