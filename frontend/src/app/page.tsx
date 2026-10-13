"use client";

import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";

import { BarChart } from "@/components/BarChart";
import { KpiCard } from "@/components/KpiCard";
import { QueryChart } from "@/components/QueryChart";
import { explainResults, getDashboardSummary, nlRunQuery } from "@/lib/api";
import type { DashboardSummary, NLRunResponse } from "@/lib/types";

function formatInt(n: number) {
  return new Intl.NumberFormat("en-US").format(n);
}

export default function Home() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const [question, setQuestion] = useState("");
  const [submittedQuestion, setSubmittedQuestion] = useState("");
  const [incidentType, setIncidentType] = useState<"Both" | "Terrorist Incident" | "VITA">("Both");
  const [region, setRegion] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const [runOut, setRunOut] = useState<NLRunResponse | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [runBusy, setRunBusy] = useState(false);

  const [explainBusy, setExplainBusy] = useState(false);
  const [explainError, setExplainError] = useState<string | null>(null);
  const [explanation, setExplanation] = useState<string | null>(null);

  useEffect(() => {
    getDashboardSummary(8)
      .then((d) => { setSummary(d); setSummaryError(null); })
      .catch((e: unknown) => { setSummary(null); setSummaryError(e instanceof Error ? e.message : String(e)); });
  }, []);

  const incidentTypes = useMemo(() => {
    if (incidentType === "Both") return ["Terrorist Incident", "VITA"] as const;
    return [incidentType] as const;
  }, [incidentType]);

  async function onRun() {
    setRunBusy(true);
    setRunError(null);
    setExplainError(null);
    setExplanation(null);
    const q = question.trim();
    setSubmittedQuestion(q);
    try {
      const out = await nlRunQuery({
        question: q,
        incident_types: [...incidentTypes],
        region: region || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      });
      setRunOut(out);
    } catch (e: unknown) {
      setRunOut(null);
      setRunError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunBusy(false);
    }
  }

  async function onExplain() {
    if (!runOut) return;
    setExplainBusy(true);
    setExplainError(null);
    try {
      const out = await explainResults({
        question: submittedQuestion,
        sql: runOut.sql,
        result_rows: runOut.results.rows.slice(0, 50),
      });
      setExplanation(out.explanation_markdown);
    } catch (e: unknown) {
      setExplainError(e instanceof Error ? e.message : String(e));
      setExplanation(null);
    } finally {
      setExplainBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* ── Header ── */}
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-slate-900 shadow-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500 text-white font-bold text-sm select-none">
              G
            </div>
            <div>
              <div className="text-sm font-semibold tracking-tight text-white">GTTAC Insight</div>
              <div className="text-xs text-slate-400">GRID Terrorism Database · NL→SQL Analytics</div>
            </div>
          </div>
          <div className="hidden text-xs text-slate-500 sm:block">
            API:{" "}
            <span className="font-mono text-slate-400">
              {process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8001"}
            </span>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl grid-cols-12 gap-5 px-5 py-5">
        {/* ── Left: Query Builder ── */}
        <aside className="col-span-12 lg:col-span-4">
          <div className="sticky top-[57px] rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-sm font-bold text-slate-900">Query Builder</div>
            <div className="mt-0.5 text-xs text-slate-500">
              Ask a question in plain English — converted to safe SQL.
            </div>

            <label className="mt-4 block text-xs font-semibold text-slate-700">Question</label>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) onRun(); }}
              placeholder="e.g. What were the most common tactics used in 2023?"
              className="mt-1 h-28 w-full resize-none rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-blue-400 focus:bg-white"
            />

            <div className="mt-3 grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700">Incident type</label>
                <select
                  value={incidentType}
                  onChange={(e) => setIncidentType(e.target.value as typeof incidentType)}
                  className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 p-2 text-sm text-slate-900 outline-none focus:border-blue-400"
                >
                  <option value="Both">Both</option>
                  <option value="Terrorist Incident">Terrorist Incident</option>
                  <option value="VITA">VITA</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700">Region</label>
                <input
                  value={region}
                  onChange={(e) => setRegion(e.target.value)}
                  placeholder="e.g. South Asia"
                  className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 p-2 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-blue-400"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700">From (YYYY-MM-DD)</label>
                <input
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  placeholder="optional"
                  className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 p-2 text-sm text-slate-900 outline-none focus:border-blue-400"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700">To (YYYY-MM-DD)</label>
                <input
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  placeholder="optional"
                  className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 p-2 text-sm text-slate-900 outline-none focus:border-blue-400"
                />
              </div>
            </div>

            <button
              onClick={onRun}
              disabled={runBusy || !question.trim()}
              className="mt-4 inline-flex w-full items-center justify-center rounded-lg bg-blue-600 px-3 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {runBusy ? (
                <span className="flex items-center gap-2">
                  <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 00-8 8h4l-3 3-3-3h4z" />
                  </svg>
                  Running…
                </span>
              ) : "Run Query  ⌘↵"}
            </button>

            {runError ? (
              <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">
                <span className="font-semibold">Error: </span>{runError}
              </div>
            ) : null}

            {runOut?.sql ? (
              <div className="mt-4">
                <div className="text-xs font-semibold text-slate-600">Generated SQL</div>
                <pre className="mt-1 max-h-44 overflow-auto rounded-lg border border-slate-200 bg-slate-900 p-3 text-xs text-green-400">
                  {runOut.sql}
                </pre>
              </div>
            ) : null}

            {runOut ? (
              <button
                onClick={onExplain}
                disabled={explainBusy}
                className="mt-3 inline-flex w-full items-center justify-center rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                {explainBusy ? "Explaining…" : "✦ Explain with RAG"}
              </button>
            ) : null}

            {explainError ? (
              <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">
                {explainError}
              </div>
            ) : null}

            {explanation ? (
              <div className="mt-3 rounded-lg border border-blue-100 bg-blue-50 p-3 text-sm text-slate-800">
                <div className="mb-2 text-xs font-bold uppercase tracking-wide text-blue-600">
                  Analysis
                </div>
                <div className="prose prose-sm max-w-none text-slate-700 [&_p]:mb-2 [&_ul]:pl-4 [&_li]:mb-1">
                  <ReactMarkdown>{explanation}</ReactMarkdown>
                </div>
              </div>
            ) : null}
          </div>
        </aside>

        {/* ── Right: Dashboard + Results ── */}
        <main className="col-span-12 lg:col-span-8">
          <div className="grid grid-cols-1 gap-5">

            {/* KPI row */}
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <div className="text-sm font-bold text-slate-900">Dashboard Overview</div>
                {summary?.most_affected_region ? (
                  <div className="rounded-full border border-purple-200 bg-purple-50 px-3 py-1 text-xs font-medium text-purple-700">
                    Most affected: {summary.most_affected_region}
                  </div>
                ) : null}
              </div>
              {summaryError ? (
                <div className="mt-2 text-sm text-red-600">{summaryError}</div>
              ) : !summary ? (
                <div className="mt-3 flex gap-3">
                  {[...Array(4)].map((_, i) => (
                    <div key={i} className="h-20 flex-1 animate-pulse rounded-xl bg-slate-100" />
                  ))}
                </div>
              ) : (
                <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <KpiCard accent="blue"   label="Total incidents"  value={formatInt(summary.total_incidents)} />
                  <KpiCard accent="amber"  label="Total casualties" value={formatInt(summary.total_casualties)} />
                  <KpiCard accent="red"    label="Total killed"     value={formatInt(summary.total_killed)} />
                  <KpiCard accent="orange" label="Total wounded"    value={formatInt(summary.total_wounded)} />
                </div>
              )}
            </div>

            {/* Dashboard charts */}
            {summary ? (
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <BarChart title="Most affected regions"  items={summary.top_regions} />
                <BarChart title="Top countries"          items={summary.top_countries} />
                <BarChart title="Prevalent ideologies"   items={summary.top_ideologies} />
                <BarChart title="Prevalent tactics"      items={summary.top_tactics} />
                <BarChart title="Weapon types"           items={summary.top_weapon_types} />
                <BarChart title="Top groups"             items={summary.top_groups} />
              </div>
            ) : null}

            {/* Query results */}
            {runOut ? (
              <div className="space-y-4">
                {/* Chart */}
                <QueryChart
                  chart={runOut.chart}
                  rows={runOut.results.rows}
                  question={submittedQuestion}
                />

                {/* Table */}
                <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
                  <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
                    <div className="max-w-[70%]">
                      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Results</div>
                      <div className="mt-0.5 truncate text-sm font-medium text-slate-800">
                        {submittedQuestion}
                      </div>
                    </div>
                    <div className="shrink-0 text-xs text-slate-500">
                      {formatInt(runOut.results.row_count)} row{runOut.results.row_count !== 1 ? "s" : ""}
                      {runOut.results.truncated ? " (truncated)" : ""}
                    </div>
                  </div>

                  <div className="overflow-auto">
                    <table className="min-w-full text-left text-sm">
                      <thead>
                        <tr className="bg-slate-50">
                          {runOut.results.columns.map((c) => (
                            <th key={c} className="px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
                              {c}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {runOut.results.rows.slice(0, 200).map((row, idx) => (
                          <tr key={idx} className="hover:bg-slate-50">
                            {runOut.results.columns.map((c) => (
                              <td key={c} className="px-4 py-2 text-slate-800">
                                {String(row[c] ?? "")}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {runOut.results.row_count > 200 ? (
                    <div className="border-t border-slate-100 px-4 py-2 text-xs text-slate-400">
                      Showing first 200 of {formatInt(runOut.results.row_count)} rows
                    </div>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>
        </main>
      </div>
    </div>
  );
}
