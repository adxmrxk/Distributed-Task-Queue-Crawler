"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { submitJob } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [maxDepth, setMaxDepth] = useState(3);
  const [maxPages, setMaxPages] = useState(100);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const job = await submitJob(url, { max_depth: maxDepth, max_pages: maxPages });
      router.push(`/jobs/${job.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col items-center gap-16 py-16">
      {/* Hero */}
      <div className="text-center flex flex-col gap-4">
        <div className="inline-flex items-center gap-2 bg-emerald-500/10 text-emerald-400 text-sm font-medium px-3 py-1 rounded-full border border-emerald-500/20 mx-auto">
          <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
          Distributed crawler — workers running in parallel
        </div>
        <h1 className="text-5xl font-bold tracking-tight text-white">
          Find every broken link
          <br />
          <span className="text-emerald-400">on any website.</span>
        </h1>
        <p className="text-zinc-400 text-lg max-w-lg mx-auto">
          Submit a URL and the crawler fans out across the entire site using
          background workers — your browser doesn&apos;t wait, the API doesn&apos;t block.
        </p>
      </div>

      {/* Submit form */}
      <form onSubmit={handleSubmit} className="w-full max-w-2xl flex flex-col gap-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com"
            required
            className="flex-1 bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-3 text-white placeholder:text-zinc-500 focus:outline-none focus:border-emerald-500 transition-colors font-mono text-sm"
          />
          <button
            type="submit"
            disabled={loading}
            className="bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 disabled:cursor-not-allowed text-black font-semibold px-6 py-3 rounded-lg transition-colors whitespace-nowrap"
          >
            {loading ? "Submitting…" : "Start Crawl"}
          </button>
        </div>

        {/* Options */}
        <div className="flex gap-6 text-sm text-zinc-400">
          <label className="flex items-center gap-2">
            <span>Max depth</span>
            <select
              value={maxDepth}
              onChange={(e) => setMaxDepth(Number(e.target.value))}
              className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-white focus:outline-none focus:border-emerald-500"
            >
              {[1, 2, 3, 4, 5].map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2">
            <span>Max pages</span>
            <select
              value={maxPages}
              onChange={(e) => setMaxPages(Number(e.target.value))}
              className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-white focus:outline-none focus:border-emerald-500"
            >
              {[50, 100, 250, 500, 1000].map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </label>
        </div>

        {error && (
          <p className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3">
            {error}
          </p>
        )}
      </form>

      {/* How it works */}
      <div className="w-full max-w-2xl grid grid-cols-3 gap-4">
        {[
          { step: "01", title: "Submit URL", desc: "API accepts your job instantly and returns a job ID" },
          { step: "02", title: "Workers crawl", desc: "3 Celery workers fan out in parallel using BFS — Playwright renders JS" },
          { step: "03", title: "View results", desc: "Every broken link with its source page, status code, and error type" },
        ].map(({ step, title, desc }) => (
          <div key={step} className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 flex flex-col gap-2">
            <span className="text-emerald-400 font-mono text-xs">{step}</span>
            <h3 className="font-semibold text-white">{title}</h3>
            <p className="text-zinc-400 text-sm leading-relaxed">{desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
