import React, { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { PageHeader, Badge, Spinner } from "@/components/ui-bits";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { UsersThree, Check, X, MoonStars, Buildings, Plus, Trash, Calendar, Sparkle } from "@phosphor-icons/react";

const inputCls = "border-2 border-[#E4E4E7] focus:border-[#EA580C] outline-none px-3 py-2 text-sm transition-colors duration-200 bg-white";

const STATUS_META = {
  present: { label: "Present", color: "bg-[#16A34A] text-white border-[#16A34A]", icon: Check },
  absent: { label: "Absent", color: "bg-[#DC2626] text-white border-[#DC2626]", icon: X },
  half_day: { label: "Half day", color: "bg-[#F59E0B] text-white border-[#F59E0B]", icon: MoonStars },
};

export default function Attendance() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const today = new Date().toISOString().slice(0, 10);
  const [date, setDate] = useState(today);
  const [projectId, setProjectId] = useState("");
  const [showHead, setShowHead] = useState(false);
  const [head, setHead] = useState({ count: "", project_id: "", note: "" });

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: async () => (await api.get("/projects")).data,
  });

  const { data: roster, isLoading } = useQuery({
    queryKey: ["attendance-roster", date, projectId],
    queryFn: async () =>
      (await api.get("/attendance/roster", { params: { date, project_id: projectId || undefined } })).data,
  });

  const mark = useMutation({
    mutationFn: async ({ worker_id, status }) =>
      (await api.post("/attendance/mark", { worker_id, status, date })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["attendance-roster"] }),
    onError: () => toast.error("Couldn't mark attendance"),
  });

  const headcount = useMutation({
    mutationFn: async () =>
      (await api.post("/attendance/headcount", {
        count: parseInt(head.count || "0", 10),
        project_id: head.project_id || null,
        date,
        note: head.note || null,
      })).data,
    onSuccess: () => {
      toast.success("Headcount logged");
      setShowHead(false);
      setHead({ count: "", project_id: "", note: "" });
      qc.invalidateQueries({ queryKey: ["attendance-roster"] });
    },
    onError: () => toast.error("Couldn't log headcount"),
  });

  const deleteHead = useMutation({
    mutationFn: async (id) => (await api.delete(`/attendance/${id}`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["attendance-roster"] }),
  });

  const bulkMark = useMutation({
    mutationFn: async (status) => {
      const entries = (roster?.roster || []).filter((r) => r.status !== status).map((r) => ({
        worker_id: r.worker_id, status, date,
      }));
      if (!entries.length) return { skipped: true };
      return (await api.post("/attendance/bulk", { date, entries })).data;
    },
    onSuccess: (res) => {
      if (!res?.skipped) toast.success("Bulk update applied");
      qc.invalidateQueries({ queryKey: ["attendance-roster"] });
    },
  });

  const stats = useMemo(() => {
    const r = roster?.roster || [];
    return {
      total: r.length,
      present: r.filter((w) => w.status === "present").length,
      absent: r.filter((w) => w.status === "absent").length,
      half: r.filter((w) => w.status === "half_day").length,
      unmarked: r.filter((w) => w.status === "unmarked").length,
      head: (roster?.headcounts || []).reduce((s, h) => s + (h.count || 0), 0),
    };
  }, [roster]);

  return (
    <div>
      <PageHeader
        overline="Workforce"
        title="Attendance Register"
        desc="Mark daily attendance per worker or log a quick headcount from the site. Supervisors can also send /attendance from Telegram."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <button
              data-testid="attendance-headcount-open"
              onClick={() => setShowHead((s) => !s)}
              className="flex items-center gap-2 border-2 border-[#09090B] px-4 py-2 text-sm font-semibold hover:bg-[#09090B] hover:text-white transition-colors duration-200"
            >
              <Sparkle size={15} weight="fill" /> Quick headcount
            </button>
            <button
              data-testid="attendance-mark-all-present"
              onClick={() => bulkMark.mutate("present")}
              className="flex items-center gap-2 bg-[#EA580C] text-white px-4 py-2.5 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200"
            >
              <Check size={16} weight="bold" /> Mark all present
            </button>
          </div>
        }
      />

      {/* Filters */}
      <div className="border-2 border-[#E4E4E7] bg-white p-4 mb-6 grid sm:grid-cols-3 gap-3">
        <div>
          <label className="text-[11px] font-semibold text-[#71717A] uppercase tracking-wide">Date</label>
          <input
            data-testid="attendance-date"
            type="date"
            value={date}
            max={today}
            onChange={(e) => setDate(e.target.value)}
            className={inputCls + " w-full mt-1"}
          />
        </div>
        <div>
          <label className="text-[11px] font-semibold text-[#71717A] uppercase tracking-wide">Project filter</label>
          <select
            data-testid="attendance-project-filter"
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            className={inputCls + " w-full mt-1"}
          >
            <option value="">All projects</option>
            {(projects || []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </div>
        <div className="flex items-end">
          <button
            onClick={() => setDate(today)}
            className="text-xs font-semibold text-[#EA580C] hover:underline"
            data-testid="attendance-today"
          >
            Jump to today
          </button>
        </div>
      </div>

      {/* Quick headcount */}
      {showHead && (
        <div className="border-2 border-[#09090B] bg-white p-5 mb-6" data-testid="headcount-form">
          <p className="font-display font-bold text-sm mb-3">Log a quick headcount for {date}</p>
          <div className="grid sm:grid-cols-3 gap-3">
            <input
              data-testid="headcount-count"
              type="number"
              placeholder="Number of workers"
              className={inputCls}
              value={head.count}
              onChange={(e) => setHead({ ...head, count: e.target.value })}
            />
            <select
              data-testid="headcount-project"
              className={inputCls}
              value={head.project_id}
              onChange={(e) => setHead({ ...head, project_id: e.target.value })}
            >
              <option value="">— No project —</option>
              {(projects || []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            <input
              data-testid="headcount-note"
              type="text"
              placeholder="Note (optional)"
              className={inputCls}
              value={head.note}
              onChange={(e) => setHead({ ...head, note: e.target.value })}
            />
          </div>
          <div className="flex gap-2 mt-3">
            <button
              data-testid="headcount-submit"
              onClick={() => headcount.mutate()}
              disabled={!head.count || headcount.isPending}
              className="bg-[#EA580C] text-white px-4 py-2 text-sm font-semibold hover:bg-[#C2410C] disabled:opacity-60"
            >
              Log headcount
            </button>
            <button onClick={() => setShowHead(false)} className="text-sm text-[#71717A] hover:text-[#09090B]">Cancel</button>
          </div>
        </div>
      )}

      {/* Rollup */}
      <div className="grid sm:grid-cols-5 gap-px bg-[#E4E4E7] border border-[#E4E4E7] mb-6" data-testid="attendance-stats">
        <div className="bg-white p-4">
          <p className="overline">Roster</p>
          <p className="font-display font-black text-2xl mt-1">{stats.total}</p>
        </div>
        <div className="bg-white p-4">
          <p className="overline">Present</p>
          <p className="font-display font-black text-2xl mt-1 text-[#16A34A]">{stats.present}</p>
        </div>
        <div className="bg-white p-4">
          <p className="overline">Absent</p>
          <p className="font-display font-black text-2xl mt-1 text-[#DC2626]">{stats.absent}</p>
        </div>
        <div className="bg-white p-4">
          <p className="overline">Half day</p>
          <p className="font-display font-black text-2xl mt-1 text-[#F59E0B]">{stats.half}</p>
        </div>
        <div className="bg-white p-4">
          <p className="overline">Headcount tally</p>
          <p className="font-display font-black text-2xl mt-1 text-[#EA580C]">{stats.head}</p>
        </div>
      </div>

      {isLoading ? <Spinner /> : (
        <>
          {/* Roster grid */}
          {(roster?.roster || []).length === 0 ? (
            <div className="border-2 border-dashed border-[#E4E4E7] p-10 text-center bg-white" data-testid="attendance-empty">
              <UsersThree size={36} weight="duotone" className="mx-auto text-[#EA580C] mb-3" />
              <h3 className="font-display font-bold text-lg mb-1">No workers to mark</h3>
              <p className="text-sm text-[#71717A]">
                {projectId ? "This project has no workers assigned. " : "Add workers from the Workforce page. "}
                Supervisors can also send <code className="text-[#EA580C]">/attendance</code> from Telegram.
              </p>
            </div>
          ) : (
            <div className="border-2 border-[#E4E4E7] bg-white divide-y divide-[#E4E4E7]" data-testid="attendance-roster-list">
              {(roster?.roster || []).map((w) => {
                const proj = (projects || []).find((p) => p.id === w.project_id);
                return (
                  <div key={w.worker_id} className="p-4 flex flex-wrap items-center justify-between gap-3" data-testid={`attendance-row-${w.worker_id}`}>
                    <div className="min-w-0 flex-1">
                      <p className="font-display font-bold text-sm truncate">{w.name}</p>
                      <div className="flex items-center gap-3 mt-1 text-xs text-[#71717A]">
                        <span>{w.role || "—"}</span>
                        {proj && <span className="flex items-center gap-1"><Buildings size={11} />{proj.name}</span>}
                        <span className="font-mono">{w.rate_type}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {["present", "half_day", "absent"].map((s) => {
                        const meta = STATUS_META[s];
                        const Icon = meta.icon;
                        const active = w.status === s;
                        return (
                          <button
                            key={s}
                            data-testid={`attendance-set-${w.worker_id}-${s}`}
                            onClick={() => mark.mutate({ worker_id: w.worker_id, status: s })}
                            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold border-2 transition-colors duration-150 ${
                              active
                                ? meta.color
                                : "border-[#E4E4E7] bg-white text-[#71717A] hover:border-[#09090B] hover:text-[#09090B]"
                            }`}
                          >
                            <Icon size={12} weight="bold" />
                            {meta.label}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Headcount entries for the day */}
          {(roster?.headcounts || []).length > 0 && (
            <div className="mt-6" data-testid="attendance-headcount-list">
              <p className="overline mb-2">Headcount entries today (from supervisors)</p>
              <div className="border border-[#E4E4E7] bg-white divide-y divide-[#E4E4E7]">
                {roster.headcounts.map((h) => {
                  const proj = (projects || []).find((p) => p.id === h.project_id);
                  return (
                    <div key={h.id} className="p-3 flex items-center justify-between gap-3 text-sm">
                      <div className="flex items-center gap-3">
                        <Badge tone="accent">{h.count}</Badge>
                        <span className="text-[#3f3f46]">
                          workers{proj ? ` at ${proj.name}` : ""}
                        </span>
                        {h.note && <span className="text-xs text-[#71717A] italic">{h.note}</span>}
                      </div>
                      <button
                        onClick={() => deleteHead.mutate(h.id)}
                        className="text-[#71717A] hover:text-[#DC2626]"
                        data-testid={`headcount-delete-${h.id}`}
                        title="Delete"
                      >
                        <Trash size={14} />
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
