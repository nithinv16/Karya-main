import React from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { PageHeader, Badge, Spinner } from "@/components/ui-bits";
import { TrendUp, Warning, Handshake, Sparkle, UsersThree, CurrencyInr, ClockCountdown, Buildings } from "@phosphor-icons/react";
import ExportMenu from "@/components/ExportMenu";
import { useAuth } from "@/context/AuthContext";
import { formatMoney } from "@/lib/country";

const levelTone = (l) => (l === "high" ? "critical" : l === "medium" ? "warning" : "success");
const ratingTone = (r) => (r === "A" ? "success" : r === "B" ? "warning" : "critical");

const PRED_META = {
  labour_shortage: { icon: UsersThree, title: "Labour Shortage" },
  cost_overrun: { icon: CurrencyInr, title: "Cost Overrun" },
  delay_risk: { icon: ClockCountdown, title: "Delay Risk" },
};

export default function Insights() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const fmt = (n) => formatMoney(n, user);
  const { data, isLoading } = useQuery({ queryKey: ["insights"], queryFn: async () => (await api.get("/insights")).data });
  const hasData = !!data?.has_data;
  const briefing = useQuery({
    queryKey: ["insights-briefing"],
    queryFn: async () => (await api.get("/insights/briefing")).data,
    enabled: hasData,
  });

  if (isLoading) return <Spinner />;
  const preds = data?.predictions || {};
  const summary = briefing.data?.ai_summary;
  const cards = summary ? summary.split("\n").map((l) => l.replace(/^[-•]\s*/, "").trim()).filter(Boolean) : [];

  return (
    <div className="p-5 sm:p-8">
      <PageHeader
        overline="Project Intelligence"
        title="Predictive Insights"
        desc="Early-warning signals across labour, cost and schedule — plus AI-scored subcontractor performance, so you act before problems compound."
        action={
          hasData ? (
            <ExportMenu
              endpoint="/insights/export"
              filename="Predictive Insights"
              label="Export insights"
              testId="insights-export-menu"
            />
          ) : null
        }
      />

      {!hasData ? (
        <div data-testid="insights-empty" className="border border-[#E4E4E7] p-12 text-center">
          <Sparkle size={40} weight="duotone" className="mx-auto text-[#EA580C] mb-4" />
          <h3 className="font-display font-bold text-xl mb-2">Nothing to predict yet</h3>
          <p className="text-[#71717A] text-sm max-w-md mx-auto mb-6">
            Add projects, workers, attendance and transactions to unlock live risk signals across labour, cost and schedule.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <button data-testid="insights-cta-workforce" onClick={() => navigate("/workforce")} className="flex items-center gap-2 bg-[#EA580C] text-white px-5 py-3 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200">
              <UsersThree size={16} weight="fill" /> Add projects &amp; workers
            </button>
            <button data-testid="insights-cta-subs" onClick={() => navigate("/subcontractors")} className="flex items-center gap-2 border-2 border-[#09090B] px-5 py-3 text-sm font-semibold hover:bg-[#09090B] hover:text-white transition-colors duration-200">
              <Handshake size={16} weight="bold" /> Add subcontractors
            </button>
          </div>
        </div>
      ) : (
      <>
      {/* Risk predictions */}
      <div className="grid md:grid-cols-3 gap-px bg-[#E4E4E7] border border-[#E4E4E7] mb-8" data-testid="predictions">
        {["labour_shortage", "cost_overrun", "delay_risk"].map((k) => {
          const p = preds[k] || {};
          const M = PRED_META[k];
          return (
            <div key={k} className="bg-white p-6" data-testid={`prediction-${k}`}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <M.icon size={20} weight="duotone" className="text-[#EA580C]" />
                  <h3 className="font-display font-bold">{M.title}</h3>
                </div>
                <Badge tone={levelTone(p.level)}>{p.level} risk</Badge>
              </div>
              <p className="font-display font-black text-2xl tracking-tight mb-2">{p.metric}</p>
              <p className="text-sm text-[#71717A] leading-snug">{p.detail}</p>
            </div>
          );
        })}
      </div>

      <div className="grid lg:grid-cols-3 gap-px bg-[#E4E4E7] border border-[#E4E4E7]">
        {/* AI narrative */}
        <div className="lg:col-span-1 bg-white p-6">
          <div className="flex items-center gap-2 mb-4">
            <Sparkle size={18} weight="fill" className="text-[#EA580C]" />
            <h3 className="font-display font-bold">AI Risk Briefing</h3>
          </div>
          {briefing.isLoading ? (
            <div className="flex items-center gap-2 text-sm text-[#71717A]" data-testid="briefing-loading">
              <span className="w-1.5 h-1.5 bg-[#EA580C] pulse-dot" />
              <span className="w-1.5 h-1.5 bg-[#EA580C] pulse-dot" style={{ animationDelay: "0.2s" }} />
              <span className="w-1.5 h-1.5 bg-[#EA580C] pulse-dot" style={{ animationDelay: "0.4s" }} />
              <span className="ml-1">Analyzing your operations…</span>
            </div>
          ) : cards.length > 0 ? (
            <ul className="space-y-3" data-testid="ai-briefing">
              {cards.map((c, i) => (
                <li key={'briefing-' + i + '-' + c.slice(0, 15)} className="flex gap-2 text-sm text-[#3f3f46]">
                  <Warning size={15} weight="bold" className="text-[#EA580C] mt-0.5 shrink-0" />
                  <span>{c}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-[#71717A]">No briefing yet — add projects, workers and activity to generate live insights.</p>
          )}
        </div>

        {/* Subcontractor scorecards */}
        <div className="lg:col-span-2 bg-white p-6">
          <div className="flex items-center gap-2 mb-4">
            <Handshake size={18} weight="bold" className="text-[#EA580C]" />
            <h3 className="font-display font-bold">Subcontractor Scorecards</h3>
          </div>
          {(data?.subcontractor_scorecards || []).length === 0 ? (
            <p className="text-sm text-[#71717A]">No subcontractors to score yet.</p>
          ) : (
            <div className="space-y-3" data-testid="scorecards">
              {data.subcontractor_scorecards.map((s) => (
                <div key={s.id} className="border border-[#E4E4E7] p-4" data-testid={`scorecard-${s.id}`}>
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <p className="font-semibold leading-snug">{s.name}</p>
                      <p className="text-xs text-[#71717A]">{s.trade}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="font-display font-black text-2xl tracking-tight">{s.score}</span>
                      <Badge tone={ratingTone(s.rating)}>Grade {s.rating}</Badge>
                    </div>
                  </div>
                  <div className="h-2 bg-[#F4F4F5] mb-2">
                    <div className={`h-full ${s.rating === "A" ? "bg-[#16A34A]" : s.rating === "B" ? "bg-[#EAB308]" : "bg-[#DC2626]"}`} style={{ width: `${s.score}%` }} />
                  </div>
                  <div className="flex items-center justify-between text-xs text-[#71717A]">
                    <span>Penalties/deductions: <span className="font-mono font-semibold text-[#09090B]">{fmt(s.deductions)}</span></span>
                    <span>Pending: <span className="font-mono font-semibold text-[#EA580C]">{fmt(s.pending)}</span></span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Project labour burn */}
      {(data?.project_overrun || []).length > 0 && (
        <div className="border border-[#E4E4E7] border-t-0 bg-white p-6">
          <div className="flex items-center gap-2 mb-5">
            <TrendUp size={18} weight="bold" className="text-[#EA580C]" />
            <h3 className="font-display font-bold">Labour Spend vs Budget</h3>
          </div>
          <div className="overflow-x-auto" data-testid="project-overrun">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-[#E4E4E7] text-left">{["Project", "Labour Spend", "Budget", "% of Budget"].map((h) => <th key={h} className="overline px-4 py-3">{h}</th>)}</tr></thead>
              <tbody>
                {data.project_overrun.map((p) => (
                  <tr key={p.name} className="border-b border-[#E4E4E7] hover:bg-[#FAFAFA] transition-colors duration-200">
                    <td className="px-4 py-3 font-semibold">{p.name}</td>
                    <td className="px-4 py-3 font-mono">{fmt(p.spend)}</td>
                    <td className="px-4 py-3 font-mono text-[#71717A]">{fmt(p.budget)}</td>
                    <td className="px-4 py-3"><Badge tone={p.labour_pct_of_budget > 20 ? "critical" : p.labour_pct_of_budget > 12 ? "warning" : "success"}>{p.labour_pct_of_budget}%</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      </>
      )}
    </div>
  );
}
