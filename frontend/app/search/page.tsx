"use client";

import { useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { searchPages, type SearchResultItem } from "@/lib/api";
import Link from "next/link";

function HighlightSnippet({ highlights }: { highlights: Record<string, string[]> | null }) {
  if (!highlights) return null;
  const snippets = Object.values(highlights).flat().slice(0, 2);
  if (snippets.length === 0) return null;
  return (
    <div className="flex flex-col gap-1 mt-2">
      {snippets.map((s, i) => (
        <p
          key={i}
          className="text-xs text-zinc-400 leading-relaxed"
          dangerouslySetInnerHTML={{ __html: s.replace(/<em>/g, '<mark class="bg-yellow-400/20 text-yellow-300 rounded px-0.5">').replace(/<\/em>/g, '</mark>') }}
        />
      ))}
    </div>
  );
}

export default function SearchPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("q") ?? "");
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await searchPages(query.trim());
      setResults(res.results);
      setTotal(res.total);
      setSearched(true);
      router.replace(`/search?q=${encodeURIComponent(query.trim())}`, { scroll: false });
    } catch {
      setError("Search failed. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-bold text-white">Search Crawled Content</h1>
        <p className="text-zinc-400 text-sm">
          Full-text search across every page indexed by the crawler — titles and body content.
        </p>
      </div>

      <form onSubmit={handleSearch} className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder='Search e.g. "login", "pricing", "API documentation"'
          className="flex-1 bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-3 text-white placeholder:text-zinc-500 focus:outline-none focus:border-emerald-500 transition-colors text-sm"
        />
        <button
          type="submit"
          disabled={loading}
          className="bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-black font-semibold px-5 py-3 rounded-lg transition-colors whitespace-nowrap"
        >
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      {error && (
        <p className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3">
          {error}
        </p>
      )}

      {searched && total !== null && (
        <p className="text-zinc-500 text-sm">
          {total === 0 ? "No results found." : `${total} result${total !== 1 ? "s" : ""} for "${query}"`}
        </p>
      )}

      {results.length > 0 && (
        <div className="flex flex-col gap-3">
          {results.map((item) => (
            <div
              key={item.id}
              className="border border-zinc-800 rounded-xl p-5 hover:border-zinc-600 transition-colors"
            >
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div className="flex flex-col gap-1 min-w-0">
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-white font-medium hover:text-emerald-400 transition-colors truncate"
                  >
                    {item.title || item.url}
                  </a>
                  <span className="font-mono text-xs text-zinc-500 truncate">{item.url}</span>
                  <HighlightSnippet highlights={item.highlights} />
                </div>
                <div className="flex items-center gap-3 shrink-0 text-xs text-zinc-500">
                  {item.depth !== null && <span>depth {item.depth}</span>}
                  {item.status_code && <span>{item.status_code}</span>}
                  {item.score && <span className="text-emerald-500/70">score {item.score.toFixed(2)}</span>}
                </div>
              </div>
              <div className="mt-3 pt-3 border-t border-zinc-800/60">
                <Link
                  href={`/jobs/${item.job_id}`}
                  className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
                >
                  From job {item.job_id.slice(0, 8)}… →
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
