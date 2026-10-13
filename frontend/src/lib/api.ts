import type { DashboardSummary, NLRunResponse } from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/[\s\/]+$/, "").trim() || "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "ngrok-skip-browser-warning": "true",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const data = (await res.json()) as { detail?: unknown };
      if (typeof data?.detail === "string") detail = data.detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export function getDashboardSummary(topN = 8) {
  return apiFetch<DashboardSummary>(`/dashboard/summary?top_n=${topN}`);
}

export function nlRunQuery(input: {
  question: string;
  incident_types: ("Terrorist Incident" | "VITA")[];
  region?: string;
  date_from?: string;
  date_to?: string;
}) {
  return apiFetch<NLRunResponse>("/query/nl_run", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function explainResults(input: {
  question: string;
  sql: string;
  result_rows: Record<string, unknown>[];
}) {
  return apiFetch<{ explanation_markdown: string }>("/explain", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

