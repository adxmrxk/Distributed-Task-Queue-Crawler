"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listJobs, type Job } from "@/lib/api";

const STATUS_COLOR: Record<Job["status"], string> = {
  PENDING:     "bg-yellow-500/15 text-yellow-400 border-yellow-500/25",
  IN_PROGRESS: "bg-blue-500/15 text-blue-400 border-blue-500/25",
  COMPLETED:   "bg-emerald-500/15 text-emerald-400 border-emerald-500/25",
  FAILED:      "bg-red-500/15 text-red-400 border-red-500/25",
  CANCELLED:   "bg-zinc-500/15 text-zinc-400 border-zinc-500/25",
};

function timeAgo(dateStr: string): string {
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listJobs(50)
      .then((r) => setJobs(r.jobs))
      .catch(() => setError("Could not connect to the API. Is the backend running?"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">All Jobs</h1>
        <Link
          href="/"
          className="text-sm bg-emerald-500 hover:bg-emerald-400 text-black font-semibold px-4 py-2 rounded-lg transition-colors"
        >
          + New Job
        </Link>
      </div>

      {loading && (
        <div className="flex items-center gap-3 text-zinc-400 py-16 justify-center">
          <span className="w-4 h-4 border-2 border-zinc-600 border-t-emerald-400 rounded-full animate-spin" />
          Loading…
        </div>
      )}

      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-5 text-red-400 text-sm">
          {error}
        </div>
      )}

      {!loading && !error && jobs.length === 0 && (
        <div className="text-center py-24 flex flex-col items-center gap-4">
          <p className="text-zinc-500 text-lg">No jobs yet.</p>
          <Link href="/" className="text-emerald-400 hover:text-emerald-300 text-sm underline">
            Submit your first crawl →
          </Link>
        </div>
      )}

      {jobs.length > 0 && (
        <div className="border border-zinc-800 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-900/50">
                <th className="text-left px-4 py-3 text-zinc-400 font-medium">URL</th>
                <th className="text-left px-4 py-3 text-zinc-400 font-medium">Status</th>
                <th className="text-right px-4 py-3 text-zinc-400 font-medium hidden sm:table-cell">Pages</th>
                <th className="text-right px-4 py-3 text-zinc-400 font-medium hidden sm:table-cell">Broken</th>
                <th className="text-right px-4 py-3 text-zinc-400 font-medium">Started</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr
                  key={job.id}
                  className="border-b border-zinc-800/50 last:border-0 hover:bg-zinc-900/40 transition-colors cursor-pointer"
                  onClick={() => window.location.href = `/jobs/${job.id}`}
                >
                  <td className="px-4 py-3 max-w-xs">
                    <span className="font-mono text-xs text-zinc-200 truncate block">{job.url}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${STATUS_COLOR[job.status]}`}>
                      {job.status === "IN_PROGRESS" && (
                        <span className="inline-block w-1.5 h-1.5 bg-current rounded-full mr-1 animate-pulse" />
                      )}
                      {job.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right text-zinc-400 hidden sm:table-cell">
                    {job.total_pages_crawled}
                  </td>
                  <td className="px-4 py-3 text-right hidden sm:table-cell">
                    <span className={job.total_broken_links > 0 ? "text-red-400 font-medium" : "text-zinc-400"}>
                      {job.total_broken_links}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right text-zinc-500 text-xs">
                    {job.created_at ? timeAgo(job.created_at) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
