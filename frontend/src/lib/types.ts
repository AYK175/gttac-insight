export type DashboardTopItem = {
  label: string;
  count: number;
};

export type DashboardSummary = {
  total_incidents: number;
  total_killed: number;
  total_wounded: number;
  total_casualties: number;
  most_affected_region?: string | null;
  top_regions: DashboardTopItem[];
  top_countries: DashboardTopItem[];
  top_ideologies: DashboardTopItem[];
  top_tactics: DashboardTopItem[];
  top_weapon_types: DashboardTopItem[];
  top_groups: DashboardTopItem[];
};

export type ChartIntent = {
  chart_kind: "bar" | "line" | "temporal" | "pie" | "scatter" | "heatmap" | "geo" | "table" | "none";
  x_column?: string | null;
  y_column?: string | null;
  label_column?: string | null;
  value_column?: string | null;
  lat_column?: string | null;
  lon_column?: string | null;
  title?: string | null;
};

export type NLRunResponse = {
  sql: string;
  chart: ChartIntent;
  results: {
    columns: string[];
    rows: Record<string, unknown>[];
    truncated: boolean;
    row_count: number;
  };
};

