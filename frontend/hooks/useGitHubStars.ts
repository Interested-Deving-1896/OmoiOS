"use client";

import { useEffect, useState } from "react";

/**
 * @module useGitHubStars
 * @description React hook to fetch and cache GitHub repository star counts
 *
 * Fetches stargazer count from GitHub API with sessionStorage caching
 * to reduce API calls. Cache TTL is 5 minutes.
 *
 * @example
 * ```tsx
 * function RepoCard({ repo }: { repo: string }) {
 *   const stars = useGitHubStars(repo);
 *
 *   return (
 *     <div>
 *       <h3>{repo}</h3>
 *       {stars !== null ? <span>⭐ {stars}</span> : <span>Loading...</span>}
 *     </div>
 *   );
 * }
 * ```
 */

const CACHE_KEY = "github-stars-cache";
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

interface CacheEntry {
  count: number;
  timestamp: number;
}

/**
 * Get cached star count from sessionStorage
 * @returns Cached count or null if expired/missing
 */
function getCached(): number | null {
  try {
    const raw = sessionStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const entry: CacheEntry = JSON.parse(raw);
    if (Date.now() - entry.timestamp > CACHE_TTL) return null;
    return entry.count;
  } catch {
    return null;
  }
}

/**
 * Set star count in sessionStorage cache
 * @param count - The star count to cache
 */
function setCache(count: number) {
  try {
    const entry: CacheEntry = { count, timestamp: Date.now() };
    sessionStorage.setItem(CACHE_KEY, JSON.stringify(entry));
  } catch {
    // sessionStorage unavailable (SSR, private browsing) — ignore
  }
}

/**
 * Hook to fetch GitHub star count for a repository
 * @param repo - Repository identifier in "owner/repo" format
 * @returns Star count or null if loading/error
 */
export function useGitHubStars(repo: string): number | null {
  const [stars, setStars] = useState<number | null>(() => getCached());

  useEffect(() => {
    const cached = getCached();
    if (cached !== null) {
      setStars(cached);
      return;
    }

    let cancelled = false;

    fetch(`https://api.github.com/repos/${repo}`, {
      headers: { Accept: "application/vnd.github.v3+json" },
    })
      .then((res) => {
        if (!res.ok) throw new Error(`GitHub API ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (cancelled) return;
        const count = data.stargazers_count as number;
        setStars(count);
        setCache(count);
      })
      .catch(() => {
        // Silently fail — the UI will just not show a count
      });

    return () => {
      cancelled = true;
    };
  }, [repo]);

  return stars;
}
