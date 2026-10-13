"use client";

import ReactECharts from "echarts-for-react";

// Labels to strip from dashboard charts
const NOISE = new Set(["unknown", "other", "unclear", "n/a", "none", "unspecified", "not available"]);

function clean(items: { label: string; count: number }[]) {
  return items.filter((x) => x.label && !NOISE.has(x.label.toLowerCase().trim()));
}

const CHART_COLOR = "#3b82f6"; // unified blue for dashboard bars

export function BarChart(props: {
  title: string;
  items: { label: string; count: number }[];
  height?: number;
}) {
  const height = props.height ?? 260;
  const items = clean(props.items);
  if (!items.length) return null;

  const option = {
    title: {
      text: props.title,
      left: "left",
      textStyle: { fontSize: 12, fontWeight: 600, color: "#1e293b" },
    },
    grid: { left: 10, right: 16, top: 36, bottom: 10, containLabel: true },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      backgroundColor: "#1e293b",
      borderColor: "#334155",
      textStyle: { color: "#f8fafc", fontSize: 12 },
    },
    xAxis: {
      type: "value",
      axisLabel: { color: "#94a3b8", fontSize: 11 },
      splitLine: { lineStyle: { color: "rgba(148,163,184,0.15)" } },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    yAxis: {
      type: "category",
      axisLabel: { color: "#475569", width: 140, overflow: "truncate", fontSize: 11 },
      axisLine: { show: false },
      axisTick: { show: false },
      data: items.map((x) => x.label).reverse(),
    },
    series: [
      {
        type: "bar",
        data: items.map((x) => x.count).reverse(),
        itemStyle: { borderRadius: [0, 5, 5, 0], color: CHART_COLOR },
        emphasis: { itemStyle: { color: "#2563eb" } },
        barMaxWidth: 28,
      },
    ],
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <ReactECharts option={option} style={{ height }} />
    </div>
  );
}
