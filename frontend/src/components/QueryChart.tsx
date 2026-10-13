"use client";

import ReactECharts from "echarts-for-react";
import * as echarts from "echarts";
import { useEffect, useState } from "react";
import type { ChartIntent } from "@/lib/types";

type Row = Record<string, unknown>;

// ── Noise filtering ────────────────────────────────────────────────────────
const NOISE = new Set([
  "unknown", "other", "unclear", "n/a", "none", "unspecified",
  "not available", "not specified", "", "null",
]);
function isNoise(v: unknown): boolean {
  if (v === null || v === undefined) return true;
  return NOISE.has(String(v).toLowerCase().trim());
}
function filterRows(rows: Row[], ...cols: (string | null | undefined)[]): Row[] {
  const keyCols = cols.filter(Boolean) as string[];
  if (!keyCols.length) return rows;
  return rows.filter((r) => keyCols.every((c) => !isNoise(r[c])));
}

// ── Value helpers ──────────────────────────────────────────────────────────
function strVal(row: Row, col: string): string {
  const v = row[col];
  return v === null || v === undefined ? "" : String(v);
}
function numVal(row: Row, col: string): number {
  return Number(row[col]) || 0;
}

// ── Color palette ──────────────────────────────────────────────────────────
const PALETTE = [
  "#3b82f6", "#f59e0b", "#ef4444", "#10b981",
  "#8b5cf6", "#06b6d4", "#f97316", "#84cc16",
];
const SINGLE_COLOR = "#3b82f6";

const TOOLTIP_STYLE = {
  backgroundColor: "#1e293b",
  borderColor: "#334155",
  textStyle: { color: "#f8fafc", fontSize: 12 },
};

// ── World map (loaded once) ────────────────────────────────────────────────
let worldMapPromise: Promise<void> | null = null;

function loadWorldMap(): Promise<void> {
  if (worldMapPromise) return worldMapPromise;
  worldMapPromise = fetch("/world.json")
    .then((r) => r.json())
    .then((geoJson) => {
      echarts.registerMap("world", geoJson as Parameters<typeof echarts.registerMap>[1]);
    })
    .catch(() => {
      worldMapPromise = null; // allow retry
    });
  return worldMapPromise;
}

// Normalise DB country names (uppercase) to GeoJSON names (proper case)
// GeoJSON uses English Wikipedia naming; try a few transformations.
function normaliseCountry(raw: string): string {
  const s = raw
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
  // common remaps
  const remap: Record<string, string> = {
    "United States": "United States of America",
    "Usa": "United States of America",
    "Us": "United States of America",
    "Uk": "United Kingdom",
    "Uae": "United Arab Emirates",
    "Congo Brazzaville": "Republic of Congo",
    "Congo Kinshasa": "Democratic Republic of the Congo",
    "Drc": "Democratic Republic of the Congo",
    "North Korea": "North Korea",
    "South Korea": "South Korea",
    "Czech Republic": "Czech Republic",
    "Bosnia": "Bosnia and Herzegovina",
    "Myanmar": "Myanmar",
    "Burma": "Myanmar",
    "Russia": "Russia",
    "Iran": "Iran",
    "Syria": "Syria",
    "Tanzania": "United Republic of Tanzania",
    "Ivory Coast": "Ivory Coast",
    "Cote D Ivoire": "Ivory Coast",
  };
  return remap[s] ?? s;
}

// ── World-map choropleth component ─────────────────────────────────────────
function WorldMapChart({
  rows,
  nameCol,
  valueCol,
  title,
}: {
  rows: Row[];
  nameCol: string;
  valueCol: string;
  title?: string | null;
}) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    loadWorldMap().then(() => setReady(true));
  }, []);

  if (!ready) {
    return (
      <div className="flex h-[420px] items-center justify-center text-sm text-slate-400">
        Loading world map…
      </div>
    );
  }

  const data = rows
    .filter((r) => !isNoise(r[nameCol]))
    .map((r) => ({
      name: normaliseCountry(strVal(r, nameCol)),
      value: numVal(r, valueCol),
    }));

  const maxVal = Math.max(...data.map((d) => d.value), 1);

  const option = {
    title: title
      ? { text: title, left: "left", textStyle: { fontSize: 13, fontWeight: 600, color: "#1e293b" } }
      : undefined,
    tooltip: {
      ...TOOLTIP_STYLE,
      trigger: "item",
      formatter: (p: { name: string; value: number }) =>
        `${p.name}: ${(p.value ?? 0).toLocaleString()}`,
    },
    visualMap: {
      min: 0,
      max: maxVal,
      left: "left",
      bottom: 20,
      text: ["High", "Low"],
      calculable: true,
      inRange: { color: ["#dbeafe", "#1d4ed8"] },
      textStyle: { color: "#64748b", fontSize: 11 },
    },
    series: [
      {
        type: "map",
        map: "world",
        roam: true,
        emphasis: { label: { show: true }, itemStyle: { areaColor: "#fbbf24" } },
        data,
        itemStyle: { areaColor: "#e2e8f0", borderColor: "#cbd5e1", borderWidth: 0.5 },
        select: { itemStyle: { areaColor: "#fbbf24" } },
      },
    ],
  };

  return (
    <ReactECharts
      option={option}
      style={{ height: 420 }}
      opts={{ renderer: "canvas" }}
    />
  );
}

// ── Main chart builder ─────────────────────────────────────────────────────
function buildOption(chart: ChartIntent, rows: Row[]): object | null {
  const titleStyle = { fontSize: 13, fontWeight: 600, color: "#1e293b" };
  const titleObj = chart.title
    ? { text: chart.title, left: "left", textStyle: titleStyle }
    : undefined;
  const gridBase = {
    left: 16, right: 24,
    top: titleObj ? 48 : 28,
    bottom: 16,
    containLabel: true,
  };
  const axisLabelStyle = { color: "#64748b", fontSize: 11 };
  const splitLine = { lineStyle: { color: "rgba(148,163,184,0.2)" } };

  switch (chart.chart_kind) {
    case "bar": {
      const x = chart.x_column;
      const y = chart.y_column;
      if (!x || !y) return null;
      const clean = filterRows(rows, x, y);
      if (!clean.length) return null;
      const labels = clean.map((r) => strVal(r, x));
      const values = clean.map((r) => numVal(r, y));
      const isHorizontal = labels.length > 10 || labels.some((l) => l.length > 12);
      return {
        title: titleObj,
        tooltip: { ...TOOLTIP_STYLE, trigger: "axis", axisPointer: { type: "shadow" } },
        grid: { ...gridBase, bottom: isHorizontal ? 10 : 40 },
        ...(isHorizontal
          ? {
              xAxis: { type: "value", axisLabel: axisLabelStyle, splitLine },
              yAxis: { type: "category", data: labels.reverse(), axisLabel: { ...axisLabelStyle, width: 140, overflow: "truncate" }, axisTick: { show: false }, axisLine: { show: false } },
            }
          : {
              xAxis: { type: "category", data: labels, axisLabel: { ...axisLabelStyle, rotate: labels.length > 8 ? 30 : 0, overflow: "truncate", width: 100 } },
              yAxis: { type: "value", axisLabel: axisLabelStyle, splitLine },
            }),
        series: [{
          type: "bar",
          data: isHorizontal ? values.reverse() : values,
          itemStyle: { borderRadius: isHorizontal ? [0, 4, 4, 0] : [4, 4, 0, 0], color: SINGLE_COLOR },
          emphasis: { itemStyle: { color: "#2563eb" } },
          barMaxWidth: 36,
        }],
      };
    }

    case "line":
    case "temporal": {
      const x = chart.x_column;
      const y = chart.y_column;
      if (!x || !y) return null;
      const clean = filterRows(rows, x, y);
      if (!clean.length) return null;
      return {
        title: titleObj,
        tooltip: { ...TOOLTIP_STYLE, trigger: "axis" },
        grid: gridBase,
        xAxis: {
          type: "category",
          data: clean.map((r) => strVal(r, x)),
          boundaryGap: false,
          axisLabel: axisLabelStyle,
          axisLine: { lineStyle: { color: "#cbd5e1" } },
        },
        yAxis: { type: "value", axisLabel: axisLabelStyle, splitLine },
        series: [{
          type: "line",
          data: clean.map((r) => numVal(r, y)),
          smooth: true,
          lineStyle: { color: SINGLE_COLOR, width: 2 },
          itemStyle: { color: SINGLE_COLOR },
          areaStyle: { color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: "rgba(59,130,246,0.2)" }, { offset: 1, color: "rgba(59,130,246,0)" }] } },
          symbol: "circle",
          symbolSize: 5,
        }],
      };
    }

    case "pie": {
      const lbl = chart.label_column ?? chart.x_column;
      const v = chart.value_column ?? chart.y_column;
      if (!lbl || !v) return null;
      const clean = filterRows(rows, lbl, v);
      if (!clean.length) return null;
      const pieData = clean.map((r, i) => ({
        name: strVal(r, lbl),
        value: numVal(r, v),
        itemStyle: { color: PALETTE[i % PALETTE.length] },
      }));
      return {
        title: titleObj,
        tooltip: { ...TOOLTIP_STYLE, trigger: "item", formatter: "{b}: {c} ({d}%)" },
        legend: { orient: "vertical", left: "right", top: "middle", textStyle: { color: "#475569", fontSize: 11 } },
        series: [{
          type: "pie",
          radius: ["38%", "65%"],
          center: ["38%", "55%"],
          data: pieData,
          label: { formatter: "{b}\n{d}%", color: "#334155", fontSize: 11 },
          emphasis: { itemStyle: { shadowBlur: 8, shadowColor: "rgba(0,0,0,0.2)" } },
        }],
      };
    }

    case "scatter": {
      const x = chart.x_column;
      const y = chart.y_column;
      if (!x || !y) return null;
      const clean = filterRows(rows, x, y);
      if (!clean.length) return null;
      return {
        title: titleObj,
        tooltip: {
          ...TOOLTIP_STYLE,
          formatter: (p: { value: [number, number] }) =>
            `${x}: ${p.value[0]}<br/>${y}: ${p.value[1]}`,
        },
        grid: gridBase,
        xAxis: { type: "value", name: x, nameLocation: "end", axisLabel: axisLabelStyle, splitLine },
        yAxis: { type: "value", name: y, nameLocation: "end", axisLabel: axisLabelStyle, splitLine },
        series: [{
          type: "scatter",
          data: clean.map((r) => [numVal(r, x), numVal(r, y)]),
          symbolSize: 7,
          itemStyle: { color: SINGLE_COLOR, opacity: 0.75 },
        }],
      };
    }

    case "heatmap": {
      const x = chart.x_column;
      const y = chart.y_column;
      const v = chart.value_column ?? chart.y_column;
      if (!x || !y || !v) return null;
      const clean = filterRows(rows, x, y);
      if (!clean.length) return null;
      const xVals = [...new Set(clean.map((r) => strVal(r, x)))];
      const yVals = [...new Set(clean.map((r) => strVal(r, y)))];
      const data = clean.map((r) => [xVals.indexOf(strVal(r, x)), yVals.indexOf(strVal(r, y)), numVal(r, v)]);
      const maxV = Math.max(...data.map((d) => d[2] as number), 1);
      return {
        title: titleObj,
        tooltip: { ...TOOLTIP_STYLE, formatter: (p: { value: [number, number, number] }) => `${xVals[p.value[0]]} / ${yVals[p.value[1]]}: ${p.value[2]}` },
        grid: { ...gridBase, bottom: 60 },
        xAxis: { type: "category", data: xVals, splitArea: { show: true }, axisLabel: { ...axisLabelStyle, rotate: xVals.length > 8 ? 30 : 0 } },
        yAxis: { type: "category", data: yVals, splitArea: { show: true }, axisLabel: axisLabelStyle },
        visualMap: { min: 0, max: maxV, calculable: true, orient: "horizontal", left: "center", bottom: 0, inRange: { color: ["#dbeafe", "#1d4ed8"] }, textStyle: { color: "#64748b" } },
        series: [{ type: "heatmap", data, label: { show: data.length <= 60, fontSize: 10 } }],
      };
    }

    case "geo": {
      const lat = chart.lat_column;
      const lon = chart.lon_column;
      if (!lat || !lon) return null;
      const clean = filterRows(rows, lat, lon);
      const points = clean.map((r) => [numVal(r, lon), numVal(r, lat)]).filter(([ln, lt]) => !(ln === 0 && lt === 0));
      if (!points.length) return null;
      return {
        title: titleObj ?? { text: "Incident Locations", left: "left", textStyle: titleStyle },
        tooltip: {
          ...TOOLTIP_STYLE,
          formatter: (p: { value: [number, number] }) =>
            `Lon ${p.value[0].toFixed(2)}, Lat ${p.value[1].toFixed(2)}`,
        },
        grid: gridBase,
        xAxis: { type: "value", name: "Longitude", min: -180, max: 180, axisLabel: axisLabelStyle, splitLine },
        yAxis: { type: "value", name: "Latitude", min: -90, max: 90, axisLabel: axisLabelStyle, splitLine },
        series: [{
          type: "scatter",
          data: points,
          symbolSize: 4,
          itemStyle: { color: "#ef4444", opacity: 0.55 },
        }],
      };
    }

    default:
      return null;
  }
}

const GEO_KEYS = ["country", "nation", "countries", "state"];
const REGION_KEYS = ["region"];

// Detect if a column name refers to a country/geo field
function isGeoCol(col: string): boolean {
  const c = col.toLowerCase();
  return GEO_KEYS.some((k) => c.includes(k));
}
function isRegionCol(col: string): boolean {
  const c = col.toLowerCase();
  return REGION_KEYS.some((k) => c === k || c.startsWith(k + "_"));
}

// From the chart intent, determine if this should render as a world map
function resolveWorldMap(
  chart: ChartIntent,
  rows: Row[]
): { nameCol: string; valueCol: string } | null {
  if (!rows.length) return null;
  const keys = Object.keys(rows[0]);

  // Helper: find first numeric column (excluding nameCol)
  function firstNumCol(exclude: string): string | null {
    return keys.find((k) => k !== exclude && typeof rows[0][k] === "number") ?? null;
  }

  // 1. Chart intent already has a country x_column
  const intentX = chart.x_column ?? chart.label_column ?? "";
  if (
    (chart.chart_kind === "bar" || chart.chart_kind === "pie" || chart.chart_kind === "table") &&
    isGeoCol(intentX)
  ) {
    const valueCol = chart.y_column ?? chart.value_column ?? firstNumCol(intentX);
    if (valueCol) return { nameCol: intentX, valueCol };
  }

  // 2. Auto-detect from actual result columns (handles chart_kind:"table" case)
  const geoCol = keys.find(isGeoCol);
  if (geoCol) {
    const valueCol = firstNumCol(geoCol);
    if (valueCol) return { nameCol: geoCol, valueCol };
  }

  return null;
}

// ── Public component ───────────────────────────────────────────────────────
export function QueryChart({
  chart,
  rows,
  question,
}: {
  chart: ChartIntent;
  rows: Row[];
  question?: string;
}) {
  if (!rows.length) return null;

  const displayTitle = question?.trim() || chart.title || null;

  // World-map choropleth — takes priority for any country-column result
  const worldMap = resolveWorldMap(chart, rows);
  if (worldMap) {
    const clean = filterRows(rows, worldMap.nameCol, worldMap.valueCol);
    if (clean.length) {
      return (
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          {displayTitle && (
            <div className="mb-3 text-sm font-semibold text-slate-800">{displayTitle}</div>
          )}
          <WorldMapChart
            rows={clean}
            nameCol={worldMap.nameCol}
            valueCol={worldMap.valueCol}
            title={chart.title}
          />
        </div>
      );
    }
  }

  // Non-map charts
  if (chart.chart_kind === "table" || chart.chart_kind === "none") return null;

  const option = buildOption(chart, rows);
  if (!option) return null;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      {displayTitle && (
        <div className="mb-3 text-sm font-semibold text-slate-800">{displayTitle}</div>
      )}
      <ReactECharts
        option={option}
        style={{ height: 360 }}
        opts={{ renderer: "canvas" }}
      />
    </div>
  );
}
