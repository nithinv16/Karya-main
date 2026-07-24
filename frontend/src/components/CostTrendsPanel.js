import React, { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { Spinner, Badge } from "@/components/ui-bits";
import { formatMoney, getCountry } from "@/lib/country";
import { useAuth } from "@/context/AuthContext";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ReferenceLine, ComposedChart, Line, Cell,
} from "recharts";
import { TrendUp, ChartBar, Buildings, Target, WarningCircle, CurrencyCircleDollar, ArrowUpRight } from "@phosphor-icons/react";

const PERIODS = [
  { key: "week", label: "Weekly" },
  { key: "month", label: "Monthly" },
  { key: "quarter", label: "Quarterly" },
  { key: "year", label: "Yearly" },
];

const RANGES = [
  { key: "all", label: "All time", n: null },
  { key: "3", label: "Last 3", n: 3 },
  { key: "6", label: "Last 6", n: 6 },
  { key: "12", label: "Last 12", n: 12 },
];

const COLORS = { expenses: "#EA580C", labour: "#09090B", subs: "#F59E0B", budget: "#16A34A" };

function StatusChip({ status, percent }) {
  if (status === "no_budget") return <span className="text-[10px] uppercase tracking-wider text-[#71717A] font-bold">No budget</span>;
  const tone = status === "over" ? "critical" : status === "warn" ? "warning" : "success";
  return <Badge tone={tone}>{percent}%</Badge>;
}

export default function CostTrendsPanel({ projectId: lockedProjectId = null, dense = false }) {
  const { user } = useAuth();
  const country = getCountry(user);
  const fmt = (n) => formatMoney(n, user);
  const compact = (n) => {
    const abs = Math.abs(n || 0);
    if (abs >= 1e7) return `${country.symbol}${(n / 1e7).toFixed(1)}Cr`;
    if (abs >= 1e5) return `${country.symbol}${(n / 1e5).toFixed(1)}L`;
    if (abs >= 1e3) return `${country.symbol}${(n / 1e3).toFixed(1)}k`;
    return `${country.symbol}${Math.round(n || 0)}`;
  };

  const [period, setPeriod] = useState("month");
  const [range, setRange] = useState("12");
  const [projectId, setProjectId] = useState(lockedProjectId || "");

  const activeProjectId = lockedProjectId || projectId;

  const { data, isLoading } = useQuery({
    queryKey: ["cost-trends", period, activeProjectId],
    queryFn: async () =>
      (await api.get("/cost-trends", { params: { period, project_id: activeProjectId || undefined } })).data,
  });

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: async () => (await api.get("/projects")).data,
    enabled: !lockedProjectId,
  });

  const buckets = useMemo(() => {
    const allBuckets = data?.buckets || [];
    const r = RANGES.find((x) => x.key === range);
    if (!r || !r.n) return allBuckets;
    return allBuckets.slice(-r.n);
  }, [data?.buckets, range]);

  const totalWindow = buckets.reduce((s, b) => s + (b.total || 0), 0);
  const avgPerPeriod = buckets.length ? totalWindow / buckets.length : 0;

  // If a specific project is selected we compute a per-period budget line
  // (project.budget spread evenly across observed periods for a rough overlay).
  const selectedProject = (data?.projects || []).find((p) => p.id === activeProjectId);
  const budgetPerPeriod = selectedProject && selectedProject.budget > 0 && buckets.length
    ? selectedProject.budget / Math.max(buckets.length, 1)
    : 0;

  const chartData = useMemo(
    () => buckets.map((b) => ({ ...b, budget: budgetPerPeriod || null })),
    [buckets, budgetPerPeriod]
  );

  const budgetChartData = useMemo(() => {
    const projectRows = data?.projects || [];
    return projectRows.map((p) => ({
      name: p.name.length > 18 ? p.name.slice(0, 17) + "…" : p.name,
      fullName: p.name,
      budget: p.budget,
      actual: p.actual,
      status: p.status,
      percent: p.percent,
    }));
  }, [data?.projects]);

  const projectRows = data?.projects || [];
  const overall = data?.overall || { budget: 0, actual: 0, percent: 0, unassigned: 0 };
  const overBudget = projectRows.filter((p) => p.status === "over");
  const nearBudget = projectRows.filter((p) => p.status === "warn");

  // eslint-disable-next-line react/no-unstable-nested-components
  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload || !payload.length) return null;
    const row = payload[0].payload;
    return (
      <div className="bg-white border-2 border-[#09090B] px-3 py-2 text-xs shadow-lg" data-testid="cost-trends-tooltip">
        <p className="font-display font-bold text-[#09090B] mb-1.5">{label}</p>
        <div className="space-y-0.5 font-mono">
          <p><span className="inline-block w-2 h-2 mr-1.5" style={{ background: COLORS.expenses }} />Expenses: <b>{fmt(row.expenses)}</b></p>
          <p><span className="inline-block w-2 h-2 mr-1.5" style={{ background: COLORS.labour }} />Labour: <b>{fmt(row.labour)}</b></p>
          <p><span className="inline-block w-2 h-2 mr-1.5" style={{ background: COLORS.subs }} />Subs: <b>{fmt(row.subs)}</b></p>
          <p className="pt-1 border-t border-[#E4E4E7] mt-1">Total: <b className="text-[#EA580C]">{fmt(row.total)}</b></p>
          {row.budget ? <p className="text-[#16A34A]">Budget line: <b>{fmt(row.budget)}</b></p> : null}
        </div>
      </div>
    );
  };

  // eslint-disable-next-line react/no-unstable-nested-components
  const BudgetTooltip = ({ active, payload }) => {
    if (!active || !payload || !payload.length) return null;
    const row = payload[0].payload;
    return (
      <div className="bg-white border-2 border-[#09090B] px-3 py-2 text-xs shadow-lg">
        <p className="font-display font-bold text-[#09090B] mb-1.5">{row.fullName}</p>
        <p className="font-mono">Budget: <b>{fmt(row.budget)}</b></p>
        <p className="font-mono">Actual: <b className="text-[#EA580C]">{fmt(row.actual)}</b></p>
        <p className="font-mono pt-1 border-t border-[#E4E4E7] mt-1">Used: <b>{row.percent}%</b></p>
      </div>
    );
  };


  if (isLoading) {
    return (
      <div className={dense ? "" : "border border-[#E4E4E7] bg-white p-6"} data-testid="cost-trends-loading">
        <Spinner />
      </div>
    );
  }

  const hasData = data?.has_data && buckets.length > 0;

  return (
    <section
      className={dense ? "" : "border border-[#E4E4E7] bg-white"}
      data-testid={lockedProjectId ? `cost-trends-project-${lockedProjectId}` : "cost-trends"}
    >
      {dense ? (
        <div className="flex flex-wrap gap-2 px-1 pt-1 pb-4">
          <div className="inline-flex border-2 border-[#E4E4E7]" data-testid="cost-trends-period">
            {PERIODS.map((p) => (
              <button
                key={p.key}
                data-testid={`period-${p.key}`}
                onClick={() => setPeriod(p.key)}
                className={`px-3 py-2 text-xs font-semibold transition-colors duration-150 ${period === p.key ? "bg-[#09090B] text-white" : "bg-white text-[#71717A] hover:text-[#09090B]"}`}
              >
                {p.label}
              </button>
            ))}
          </div>
          <div className="inline-flex border-2 border-[#E4E4E7]" data-testid="cost-trends-range">
            {RANGES.map((r) => (
              <button
                key={r.key}
                data-testid={`range-${r.key}`}
                onClick={() => setRange(r.key)}
                className={`px-3 py-2 text-xs font-semibold transition-colors duration-150 ${range === r.key ? "bg-[#EA580C] text-white" : "bg-white text-[#71717A] hover:text-[#09090B]"}`}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-start justify-between gap-3 p-5 border-b border-[#E4E4E7]">
          <div>
            <p className="overline">Cost Intelligence</p>
            <h2 className="font-display font-black text-xl tracking-tight flex items-center gap-2 mt-0.5">
              <TrendUp size={20} weight="duotone" className="text-[#EA580C]" />
              Cost Trends & Budget
            </h2>
            <p className="text-xs text-[#71717A] mt-1 max-w-lg">
              Expenses, labour wages and subcontractor payouts rolled up per {period === "month" ? "month" : period}. Toggle the window to spot spikes early.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {!lockedProjectId && projects && projects.length > 0 && (
              <select
                data-testid="cost-trends-project-filter"
                value={projectId}
                onChange={(e) => setProjectId(e.target.value)}
                className="border-2 border-[#E4E4E7] px-3 py-2 text-xs font-semibold bg-white focus:border-[#EA580C] outline-none"
              >
                <option value="">All projects</option>
                {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            )}
            <div className="inline-flex border-2 border-[#E4E4E7]" data-testid="cost-trends-period">
              {PERIODS.map((p) => (
                <button
                  key={p.key}
                  data-testid={`period-${p.key}`}
                  onClick={() => setPeriod(p.key)}
                  className={`px-3 py-2 text-xs font-semibold transition-colors duration-150 ${period === p.key ? "bg-[#09090B] text-white" : "bg-white text-[#71717A] hover:text-[#09090B]"}`}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <div className="inline-flex border-2 border-[#E4E4E7]" data-testid="cost-trends-range">
              {RANGES.map((r) => (
                <button
                  key={r.key}
                  data-testid={`range-${r.key}`}
                  onClick={() => setRange(r.key)}
                  className={`px-3 py-2 text-xs font-semibold transition-colors duration-150 ${range === r.key ? "bg-[#EA580C] text-white" : "bg-white text-[#71717A] hover:text-[#09090B]"}`}
                >
                  {r.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {!hasData ? (
        <div className="p-10 text-center" data-testid="cost-trends-empty">
          <ChartBar size={36} weight="duotone" className="mx-auto text-[#EA580C] mb-3" />
          <h3 className="font-display font-bold text-lg mb-1">No cost history yet</h3>
          <p className="text-sm text-[#71717A] max-w-md mx-auto">
            Add expenses, log wages, or record subcontractor payments — every entry shows up here as a month-over-month bar so you can compare periods and catch budget drift early.
          </p>
        </div>
      ) : (
        <div className="p-5 sm:p-6 space-y-6">
          {/* Rollup stats */}
          <div className="grid sm:grid-cols-4 gap-px bg-[#E4E4E7] border border-[#E4E4E7]" data-testid="cost-rollup">
            <div className="bg-white p-4">
              <p className="overline">Total cost ({range === "all" ? "all time" : buckets.length + " periods"})</p>
              <p className="font-display font-black text-2xl tracking-tight mt-1 text-[#09090B]">{fmt(totalWindow)}</p>
            </div>
            <div className="bg-white p-4">
              <p className="overline">Average / {period}</p>
              <p className="font-display font-black text-2xl tracking-tight mt-1 text-[#09090B]">{fmt(avgPerPeriod)}</p>
            </div>
            <div className="bg-white p-4">
              <p className="overline">Overall budget</p>
              <p className="font-display font-black text-2xl tracking-tight mt-1 text-[#09090B]">
                {overall.budget > 0 ? fmt(overall.budget) : <span className="text-[#71717A] text-sm font-semibold">— not set —</span>}
              </p>
              {overall.budget > 0 && <p className="text-xs text-[#71717A] mt-0.5">{overall.percent}% used ({fmt(overall.actual)})</p>}
            </div>
            <div className="bg-white p-4">
              <p className="overline">Attention</p>
              <p className="font-display font-black text-2xl tracking-tight mt-1 text-[#EA580C]">
                {overBudget.length + nearBudget.length}
              </p>
              <p className="text-xs text-[#71717A] mt-0.5">
                {overBudget.length} over · {nearBudget.length} near limit
              </p>
            </div>
          </div>

          {/* Trend chart */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <ChartBar size={16} weight="bold" className="text-[#EA580C]" />
                <h3 className="font-display font-bold text-sm uppercase tracking-wider">Month-over-Month Cost{selectedProject ? ` — ${selectedProject.name}` : ""}</h3>
              </div>
              <div className="flex items-center gap-3 text-xs text-[#71717A]">
                <span className="inline-flex items-center gap-1"><span className="w-2.5 h-2.5" style={{ background: COLORS.expenses }} />Expenses</span>
                <span className="inline-flex items-center gap-1"><span className="w-2.5 h-2.5" style={{ background: COLORS.labour }} />Labour</span>
                <span className="inline-flex items-center gap-1"><span className="w-2.5 h-2.5" style={{ background: COLORS.subs }} />Subs</span>
                {budgetPerPeriod > 0 && (
                  <span className="inline-flex items-center gap-1"><span className="w-4 h-0.5" style={{ background: COLORS.budget }} />Budget/{period}</span>
                )}
              </div>
            </div>
            <div className="border border-[#E4E4E7] p-3 bg-[#FAFAFA]">
              <ResponsiveContainer width="100%" height={280}>
                <ComposedChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E4E4E7" vertical={false} />
                  <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#71717A" }} axisLine={{ stroke: "#E4E4E7" }} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "#71717A" }} axisLine={{ stroke: "#E4E4E7" }} tickLine={false} tickFormatter={compact} width={60} />
                  <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(234, 88, 12, 0.06)" }} />
                  <Bar dataKey="expenses" stackId="cost" fill={COLORS.expenses} radius={[0, 0, 0, 0]} />
                  <Bar dataKey="labour" stackId="cost" fill={COLORS.labour} radius={[0, 0, 0, 0]} />
                  <Bar dataKey="subs" stackId="cost" fill={COLORS.subs} radius={[2, 2, 0, 0]} />
                  {budgetPerPeriod > 0 && (
                    <ReferenceLine y={budgetPerPeriod} stroke={COLORS.budget} strokeWidth={2} strokeDasharray="6 3" label={{ value: `Budget/${period}`, position: "insideTopRight", fill: COLORS.budget, fontSize: 11, fontWeight: 600 }} />
                  )}
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Budget vs Actual per project — only show on "All projects" view */}
          {!activeProjectId && projectRows.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Target size={16} weight="bold" className="text-[#EA580C]" />
                <h3 className="font-display font-bold text-sm uppercase tracking-wider">Budget vs Actual — per project</h3>
              </div>
              <div className="border border-[#E4E4E7] p-3 bg-[#FAFAFA]">
                <ResponsiveContainer width="100%" height={Math.max(180, projectRows.length * 46 + 40)}>
                  <BarChart data={budgetChartData} layout="vertical" margin={{ top: 8, right: 24, bottom: 0, left: 8 }} barGap={4}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E4E4E7" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 11, fill: "#71717A" }} axisLine={{ stroke: "#E4E4E7" }} tickLine={false} tickFormatter={compact} />
                    <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fill: "#09090B" }} axisLine={false} tickLine={false} width={110} />
                    <Tooltip content={<BudgetTooltip />} cursor={{ fill: "rgba(234, 88, 12, 0.06)" }} />
                    <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} iconType="square" />
                    <Bar dataKey="budget" fill="#E4E4E7" name="Budget" radius={[0, 2, 2, 0]} />
                    <Bar dataKey="actual" name="Actual" radius={[0, 2, 2, 0]}>
                      {budgetChartData.map((row, i) => (
                        <Cell key={row.name || ('cell-' + i)} fill={row.status === "over" ? "#DC2626" : row.status === "warn" ? "#F59E0B" : "#EA580C"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Per-project detail rows */}
              <div className="mt-4 border border-[#E4E4E7] divide-y divide-[#E4E4E7] bg-white" data-testid="budget-vs-actual-list">
                {projectRows.map((p) => {
                  const barPct = p.budget > 0 ? Math.min(100, p.percent) : 0;
                  const barColor = p.status === "over" ? "bg-[#DC2626]" : p.status === "warn" ? "bg-[#F59E0B]" : "bg-[#EA580C]";
                  return (
                    <div key={p.id} className="p-4" data-testid={`budget-row-${p.id}`}>
                      <div className="flex items-center justify-between gap-3 mb-2">
                        <div className="min-w-0 flex-1">
                          <p className="font-display font-bold text-sm truncate flex items-center gap-1.5">
                            <Buildings size={13} weight="duotone" className="text-[#71717A] shrink-0" />
                            {p.name}
                          </p>
                          <p className="text-xs text-[#71717A] mt-0.5 font-mono">
                            {fmt(p.actual)} spent{p.budget > 0 ? ` of ${fmt(p.budget)}` : " (no budget set)"}
                          </p>
                        </div>
                        <div className="text-right shrink-0">
                          <StatusChip status={p.status} percent={p.percent} />
                          {p.status === "over" && (
                            <p className="text-[10px] text-[#DC2626] font-semibold mt-1 flex items-center gap-1 justify-end">
                              <WarningCircle size={10} weight="fill" /> Over by {fmt(p.actual - p.budget)}
                            </p>
                          )}
                          {p.status === "ok" && p.budget > 0 && (
                            <p className="text-[10px] text-[#71717A] mt-1">{fmt(p.remaining)} left</p>
                          )}
                        </div>
                      </div>
                      {p.budget > 0 && (
                        <div className="h-2 bg-[#F4F4F5] relative overflow-hidden">
                          <div className={`h-full ${barColor} transition-all duration-300`} style={{ width: `${barPct}%` }} />
                          {p.status === "over" && (
                            <div className="absolute inset-y-0 right-0 w-1 bg-[#09090B]" />
                          )}
                        </div>
                      )}
                      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-[11px] text-[#71717A] font-mono">
                        <span>Expenses <b className="text-[#09090B]">{fmt(p.expenses)}</b></span>
                        <span>Labour <b className="text-[#09090B]">{fmt(p.labour)}</b></span>
                        <span>Subs <b className="text-[#09090B]">{fmt(p.subs)}</b></span>
                      </div>
                    </div>
                  );
                })}
                {overall.unassigned > 0 && (
                  <div className="p-4 bg-[#FFF7ED]" data-testid="budget-row-unassigned">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm text-[#3f3f46] flex items-center gap-1.5">
                        <CurrencyCircleDollar size={14} weight="duotone" className="text-[#EA580C]" />
                        Unassigned to any project
                      </p>
                      <p className="font-mono font-black text-[#EA580C]">{fmt(overall.unassigned)}</p>
                    </div>
                    <p className="text-[11px] text-[#71717A] mt-1">Tip: attach a project when adding expenses to keep budgets accurate.</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Single-project deep view: show KPI + composition */}
          {activeProjectId && selectedProject && (
            <div className="grid sm:grid-cols-3 gap-px bg-[#E4E4E7] border border-[#E4E4E7]" data-testid="single-project-breakdown">
              <div className="bg-white p-4">
                <p className="overline">Actual spend</p>
                <p className="font-display font-black text-2xl mt-1 text-[#EA580C]">{fmt(selectedProject.actual)}</p>
                <p className="text-[11px] text-[#71717A] mt-1 font-mono">
                  E {fmt(selectedProject.expenses)} · L {fmt(selectedProject.labour)} · S {fmt(selectedProject.subs)}
                </p>
              </div>
              <div className="bg-white p-4">
                <p className="overline">Budget</p>
                <p className="font-display font-black text-2xl mt-1 text-[#09090B]">
                  {selectedProject.budget > 0 ? fmt(selectedProject.budget) : "—"}
                </p>
                {selectedProject.budget > 0 && (
                  <p className="text-[11px] text-[#71717A] mt-1">{fmt(selectedProject.remaining)} remaining</p>
                )}
              </div>
              <div className="bg-white p-4">
                <p className="overline">Budget used</p>
                {selectedProject.budget > 0 ? (
                  <>
                    <p className="font-display font-black text-2xl mt-1">
                      <span className={selectedProject.status === "over" ? "text-[#DC2626]" : selectedProject.status === "warn" ? "text-[#F59E0B]" : "text-[#16A34A]"}>
                        {selectedProject.percent}%
                      </span>
                    </p>
                    <div className="h-2 bg-[#F4F4F5] mt-2 overflow-hidden">
                      <div
                        className={`h-full ${selectedProject.status === "over" ? "bg-[#DC2626]" : selectedProject.status === "warn" ? "bg-[#F59E0B]" : "bg-[#16A34A]"}`}
                        style={{ width: `${Math.min(100, selectedProject.percent)}%` }}
                      />
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-[#71717A] mt-2">Set a budget on this project (Workforce → Edit project) to enable overlay.</p>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
