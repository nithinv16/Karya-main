import React from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { PageHeader, Stat, Badge, Spinner } from "@/components/ui-bits";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { Warning, TrendUp, Buildings, Handshake, UsersThree, Broadcast } from "@phosphor-icons/react";
import { useAuth } from "@/context/AuthContext";
import { formatMoney, getCountry } from "@/lib/country";

export default function Dashboard() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const fmt = (n) => formatMoney(n, user);
  const country = getCountry(user);
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard"],
    queryFn: async () => (await api.get("/dashboard/stats")).data,
  });

  if (isLoading) return <Spinner />;
  const t = data?.totals || {};
  const empty = t.workers === 0 && t.projects === 0;

  return (
    <div className="p-5 sm:p-8">
      <PageHeader
        overline="Project Intelligence"
        title="Command Center"
        desc="Real-time picture of labour, cost, settlements and compliance health across all sites."
      />

      {empty ? (
        <div className="border border-[#E4E4E7] p-12 text-center">
          <Buildings size={40} weight="duotone" className="mx-auto text-[#EA580C] mb-4" />
          <h3 className="font-display font-bold text-xl mb-2">Set up your workspace</h3>
          <p className="text-[#71717A] text-sm max-w-md mx-auto mb-6">
            Add your projects and workers to start tracking labour, wages and settlements — or pull live regulatory updates relevant to your business.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <button data-testid="empty-add-workforce" onClick={() => navigate("/workforce")} className="flex items-center gap-2 bg-[#EA580C] text-white px-5 py-3 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200">
              <UsersThree size={16} weight="fill" /> Add projects & workers
            </button>
            <button data-testid="empty-fetch-feed" onClick={() => navigate("/feed")} className="flex items-center gap-2 border-2 border-[#09090B] px-5 py-3 text-sm font-semibold hover:bg-[#09090B] hover:text-white transition-colors duration-200">
              <Broadcast size={16} weight="bold" /> Live regulation feed
            </button>
          </div>
        </div>
      ) : (
        <>
          {/* Stat grid */}
          <div className="grid grid-cols-2 lg:grid-cols-4 border-t border-l border-[#E4E4E7] mb-8" data-testid="dashboard-stats">
            <Stat label="Active Workers" value={t.workers} sub={`${t.present_today} present today`} />
            <Stat label="Active Projects" value={t.projects} />
            <Stat label="Labour Cost Today" value={fmt(t.labour_cost_today)} accent />
            <Stat label="Pending Settlements" value={fmt(t.pending_settlements)} sub="Owed to workers" />
            <Stat label="Total Paid" value={fmt(t.total_paid)} />
            <Stat label="Advances Out" value={fmt(t.total_advances)} />
            <Stat label="Compliance Health" value={`${t.compliance_health}%`} accent={t.compliance_health < 70} />
            <Stat label="Alerts" value={(data?.compliance_alerts || []).length} sub="Next 30 days" />
            <Stat label="Subcontractor Dues" value={fmt(t.subcontractor_pending)} accent sub={`${t.subcontractors || 0} contracts`} />
            <Stat label="Retention Held" value={fmt(t.retention_held)} sub="Across contracts" />
            <Stat label="Docs Pending" value={t.workers_missing_docs || 0} accent={t.workers_missing_docs > 0} sub="Workers onboarding" />
          </div>

          <div className="grid lg:grid-cols-3 gap-px bg-[#E4E4E7] border border-[#E4E4E7]">
            {/* Cost trend */}
            <div className="lg:col-span-2 bg-white p-6">
              <div className="flex items-center gap-2 mb-5">
                <TrendUp size={18} weight="bold" className="text-[#EA580C]" />
                <h3 className="font-display font-bold">Labour Cost & Attendance — Last 7 Days</h3>
              </div>
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={data?.trend || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E4E4E7" />
                  <XAxis dataKey="date" tick={{ fontSize: 12, fill: "#71717A" }} />
                  <YAxis tick={{ fontSize: 12, fill: "#71717A" }} />
                  <Tooltip contentStyle={{ borderRadius: 0, border: "1px solid #09090B", fontSize: 12 }} />
                  <Line type="monotone" dataKey="cost" stroke="#EA580C" strokeWidth={2.5} dot={false} name={`Cost (${country.symbol})`} />
                  <Line type="monotone" dataKey="present" stroke="#09090B" strokeWidth={1.5} dot={false} name="Present" />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Compliance alerts */}
            <div className="bg-white p-6">
              <div className="flex items-center gap-2 mb-5">
                <Warning size={18} weight="bold" className="text-[#DC2626]" />
                <h3 className="font-display font-bold">Compliance Alerts</h3>
              </div>
              <div className="space-y-3">
                {(data?.compliance_alerts || []).length === 0 && (
                  <p className="text-sm text-[#71717A]">No upcoming deadlines.</p>
                )}
                {(data?.compliance_alerts || []).map((c) => (
                  <div key={c.id} className="border border-[#E4E4E7] p-3">
                    <p className="text-sm font-semibold leading-snug">{c.title}</p>
                    <div className="flex items-center justify-between mt-2">
                      <Badge tone="critical">Due {c.due_date}</Badge>
                      <span className="text-xs uppercase text-[#71717A] font-semibold">{c.category}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Project spend + subcontractor dues */}
          <div className="grid lg:grid-cols-3 gap-px bg-[#E4E4E7] border border-[#E4E4E7] border-t-0">
            <div className="lg:col-span-2 bg-white p-6">
              <div className="flex items-center gap-2 mb-5">
                <Buildings size={18} weight="bold" className="text-[#EA580C]" />
                <h3 className="font-display font-bold">Spend by Project</h3>
              </div>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={data?.project_spend || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E4E4E7" />
                  <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#71717A" }} />
                  <YAxis tick={{ fontSize: 12, fill: "#71717A" }} />
                  <Tooltip contentStyle={{ borderRadius: 0, border: "1px solid #09090B", fontSize: 12 }} />
                  <Bar dataKey="spend" fill="#EA580C" name={`Spend (${country.symbol})`} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="bg-white p-6" data-testid="subcontractor-dues">
              <div className="flex items-center gap-2 mb-5">
                <Handshake size={18} weight="bold" className="text-[#EA580C]" />
                <h3 className="font-display font-bold">Subcontractor Dues</h3>
              </div>
              <div className="space-y-3">
                {(data?.subcontractor_dues || []).length === 0 && <p className="text-sm text-[#71717A]">No subcontractor contracts.</p>}
                {(data?.subcontractor_dues || []).map((s) => (
                  <div key={s.name} className="border border-[#E4E4E7] p-3">
                    <p className="text-sm font-semibold leading-snug">{s.name}</p>
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-xs text-[#71717A]">Paid {fmt(s.paid)}</span>
                      <span className="font-mono font-bold text-[#EA580C] text-sm">{fmt(s.pending)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
