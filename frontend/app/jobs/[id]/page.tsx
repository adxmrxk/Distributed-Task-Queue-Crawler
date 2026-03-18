"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { getJob, getBrokenLinks, cancelJob, type Job, type BrokenLink } from "@/lib/api";

const STATUS_COLOR: Record<Job["status"], string> = {
  PENDING:     "bg-yellow-500/15 text-yellow-400 border-yellow-500/25",
  IN_PROGRESS: "bg-blue-500/15 text-blue-400 border-blue-500/25",
  COMPLETED:   "bg-emerald-500/15 text-emerald-400 border-emerald-500/25",
  FAILED:      "bg-red-500/15 text-red-400 border-red-500/25",
  CANCELLED:   "bg-zinc-500/15 text-zinc-400 border-zinc-500/25",
};

const ERROR_TYPE_COLOR: Record<string, string> = {
  HTTP_ERROR:       "text-red-400",
  TIMEOUT:          "text-orange-400",
  DNS_ERROR:        "text-yellow-400",
  CONNECTION_ERROR: "text-orange-400",
  SSL_ERROR:        "text-purple-400",
  INVALID_URL:      "text-zinc-400",
};

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
      <p className="text-zinc-500 text-xs uppercase tracking-widest mb-1">{label}</p>
      <p className="text-2xl font-bold text-white">{value}</p>
    </div>
  );
}

function duration(start: string | null, end: string | null): string {
  if (!start) return "—";
  const ms = new Date(end ?? new Date()).getTime() - new Date(start).getTime();
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

export default function JobPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [job, setJob] = useState<Job | null>(null);
  const [brokenLinks, setBrokenLinks] = useState<BrokenLink[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);

  const isActive = (status?: Job["status"]) =>
    status === "PENDING" || status === "IN_PROGRESS";

  const fetchData = useCallback(async () => {
    try {
      const j = await getJob(id);
      setJob(j);
      if (j.status === "COMPLETED" || j.total_broken_links > 0) {
        const bl = await getBrokenLinks(id);
        setBrokenLinks(bl.broken_links);
      }
    } catch {
      setError("Could not load job. It may not exist.");
    }
  }, [id]);

  // Initial fetch + polling while active
  useEffect(() => {
    fetchData();
    const interval = setInterval(() => {
      if (!isActive(job?.status)) return;
      fetchData();
    }, 2000);
    return () => clearInterval(interval);
  }, [fetchData, job?.status]);

  async function handleCancel() {
    if (!job) return;
    setCancelling(true);
    await cancelJob(id);
    await fetchData();
    setCancelling(false);
  }

  if (error) {
    return (
      <div className="text-center py-32">
        <p className="text-red-400 mb-4">{error}</p>
        <button onClick={() => router.push("/")} className="text-zinc-400 hover:text-white underline text-sm">
          Back to home
        </button>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="flex items-center justify-center py-32">
        <div className="flex items-center gap-3 text-zinc-400">
          <span className="w-4 h-4 border-2 border-zinc-600 border-t-emerald-400 rounded-full animate-spin" />
          Loading job…
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex flex-col gap-2 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${STATUS_COLOR[job.status]}`}>
              {isActive(job.status) && (
                <span className="inline-block w-1.5 h-1.5 bg-current rounded-full mr-1.5 animate-pulse" />
              )}
              {job.status}
            </span>
            <span className="text-zinc-500 text-xs font-mono">
              {id.slice(0, 8)}…
            </span>
          </div>
          <h1 className="text-xl font-semibold text-white break-all">{job.url}</h1>
          <p className="text-zinc-500 text-sm">
            Started {job.started_at ? new Date(job.started_at).toLocaleString() : "—"}
            {" · "}Duration: {duration(job.started_at, job.completed_at)}
          </p>
        </div>

        {isActive(job.status) && (
          <button
            onClick={handleCancel}
            disabled={cancelling}
            className="shrink-0 text-sm text-red-400 border border-red-500/30 hover:bg-red-500/10 px-4 py-2 rounded-lg transition-colors disabled:opacity-50"
          >
            {cancelling ? "Cancelling…" : "Cancel Job"}
          </button>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard label="Pages crawled" value={job.total_pages_crawled} />
        <StatCard label="Links found" value={job.total_links_found} />
        <StatCard label="Broken links" value={job.total_broken_links} />
        <StatCard label="Max depth" value={job.max_depth} />
      </div>

      {/* Progress bar (active jobs) */}
      {isActive(job.status) && job.max_pages > 0 && (
        <div className="flex flex-col gap-2">
          <div className="flex justify-between text-xs text-zinc-500">
            <span>Crawling…</span>
            <span>{job.total_pages_crawled} / {job.max_pages} pages</span>
          </div>
          <div className="w-full bg-zinc-800 rounded-full h-1.5">
            <div
              className="bg-emerald-500 h-1.5 rounded-full transition-all duration-500"
              style={{ width: `${Math.min(100, (job.total_pages_crawled / job.max_pages) * 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* Error message */}
      {job.error_message && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-red-400 text-sm">
          <strong className="font-medium">Error:</strong> {job.error_message}
        </div>
      )}

      {/* Broken links table */}
      {brokenLinks.length > 0 && (
        <div className="flex flex-col gap-4">
          <h2 className="text-lg font-semibold text-white">
            Broken Links
            <span className="ml-2 text-sm font-normal text-zinc-500">({job.total_broken_links} total)</span>
          </h2>
          <div className="border border-zinc-800 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 bg-zinc-900/50">
                  <th className="text-left px-4 py-3 text-zinc-400 font-medium">Broken URL</th>
                  <th className="text-left px-4 py-3 text-zinc-400 font-medium hidden sm:table-cell">Found on</th>
                  <th className="text-left px-4 py-3 text-zinc-400 font-medium">Error</th>
                  <th className="text-right px-4 py-3 text-zinc-400 font-medium hidden sm:table-cell">Depth</th>
                </tr>
              </thead>
              <tbody>
                {brokenLinks.map((link, i) => (
                  <tr
                    key={i}
                    className="border-b border-zinc-800/50 last:border-0 hover:bg-zinc-900/40 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-red-400 break-all">{link.broken_url}</span>
                      {link.anchor_text && (
                        <p className="text-zinc-500 text-xs mt-0.5">"{link.anchor_text}"</p>
                      )}
                    </td>
                    <td className="px-4 py-3 hidden sm:table-cell">
                      <span className="font-mono text-xs text-zinc-400 break-all">{link.source_url}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-col gap-0.5">
                        {link.status_code && (
                          <span className="text-xs font-medium text-white">{link.status_code}</span>
                        )}
                        {link.error_type && (
                          <span className={`text-xs ${ERROR_TYPE_COLOR[link.error_type] ?? "text-zinc-400"}`}>
                            {link.error_type}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right text-zinc-500 text-xs hidden sm:table-cell">
                      {link.depth ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty state when completed with no broken links */}
      {job.status === "COMPLETED" && job.total_broken_links === 0 && (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <span className="text-4xl">✓</span>
          <p className="text-white font-semibold text-lg">No broken links found</p>
          <p className="text-zinc-500 text-sm">
            Crawled {job.total_pages_crawled} pages and checked {job.total_links_found} links — all good.
          </p>
        </div>
      )}

      {/* Back */}
      <button
        onClick={() => router.push("/jobs")}
        className="self-start text-sm text-zinc-500 hover:text-white transition-colors"
      >
        ← All jobs
      </button>
    </div>
  );
}
