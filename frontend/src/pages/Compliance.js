import React, { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { PageHeader, Badge, Spinner } from "@/components/ui-bits";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { ShieldCheck, Plus, Sparkle, Warning, ClockCountdown, CurrencyInr, ListChecks, ArrowClockwise, CheckCircle, Trash, MapPin } from "@phosphor-icons/react";
import { FileUpload, Attachment } from "@/components/FileUpload";
import { toast } from "sonner";
import ExportMenu from "@/components/ExportMenu";

const CATS = ["permit", "license", "insurance", "registration", "safety", "tender", "labour", "gst", "municipal", "environment"];
const STATUS_COLORS = { pending: "warning", in_progress: "accent", completed: "success" };
const EMPTY_FORM = { title: "", category: "permit", due_date: "", expiry_date: "", document_text: "", attachments: [], project_ids: [], status: "pending" };

function urgencyMeta(days) {
  if (days === null || days === undefined) return { tone: "neutral", label: "no date" };
  if (days < 0) return { tone: "critical", label: `${Math.abs(days)}d overdue` };
  if (days <= 7) return { tone: "critical", label: `${days}d left` };
  if (days <= 15) return { tone: "warning", label: `${days}d left` };
  if (days <= 30) return { tone: "warning", label: `${days}d left` };
  return { tone: "success", label: `${days}d left` };
}
function daysUntil(dueStr) {
  if (!dueStr) return null;
  const d = new Date(dueStr);
  if (isNaN(d)) return null;
  return Math.floor((d - new Date()) / 86400000);
}

function ScoreCard({ dashboard }) {
  if (!dashboard) return null;
  const { score, counts, totals, penalty_exposure } = dashboard;
  const scoreColor = score >= 80 ? "#16A34A" : score >= 60 ? "#EA580C" : "#DC2626";
  return (
    <div className="border-2 border-[#09090B] bg-white p-5 sm:p-6 mb-6" data-testid="compliance-score-card">
      <div className="flex flex-col lg:flex-row lg:items-center gap-6">
        <div className="flex items-center gap-4 lg:border-r lg:pr-8 lg:border-[#E4E4E7]">
          <div className="relative w-24 h-24 shrink-0" data-testid="compliance-score">
            <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
              <circle cx="18" cy="18" r="15.9" fill="none" stroke="#F4F4F5" strokeWidth="3" />
              <circle cx="18" cy="18" r="15.9" fill="none" stroke={scoreColor} strokeWidth="3"
                strokeDasharray={`${score}, 100`} strokeLinecap="round" />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="font-display font-black text-2xl leading-none" style={{ color: scoreColor }}>{score}</span>
              <span className="text-[10px] text-[#71717A] mt-0.5 uppercase tracking-wider">score</span>
            </div>
          </div>
          <div>
            <p className="overline mb-1">Compliance Score</p>
            <p className="text-xs text-[#3f3f46] max-w-[240px] leading-snug">
              {score >= 80 ? "You're on top of your paperwork." : score >= 60 ? "A few items need attention this week." : "Immediate action needed — overdue exposure is high."}
            </p>
          </div>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-5 flex-1 gap-3 lg:gap-6">
          {[
            { key: "overdue", label: "Overdue", val: counts.overdue, color: "text-[#DC2626]", testid: "count-overdue" },
            { key: "critical", label: "≤7 days", val: counts.critical, color: "text-[#EA580C]", testid: "count-critical" },
            { key: "warning", label: "8-30 days", val: counts.warning + counts.watch, color: "text-[#CA8A04]", testid: "count-warning" },
            { key: "ok", label: "Healthy", val: counts.ok, color: "text-[#16A34A]", testid: "count-ok" },
            { key: "exposure", label: "Penalty exposure", val: `₹${Math.round(penalty_exposure).toLocaleString("en-IN")}`, color: "text-[#09090B]", testid: "penalty-exposure" },
          ].map((s) => (
            <div key={s.key} data-testid={s.testid}>
              <p className="overline mb-1">{s.label}</p>
              <p className={`font-display font-bold text-xl tracking-tight ${s.color}`}>{s.val}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function Compliance() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [active, setActive] = useState(null);
  const [renewalActive, setRenewalActive] = useState(null);
  const [penaltyActive, setPenaltyActive] = useState(null);

  const { data: items, isLoading } = useQuery({ queryKey: ["compliance"], queryFn: async () => (await api.get("/compliance")).data });
  const { data: dashboard } = useQuery({ queryKey: ["compliance-dashboard"], queryFn: async () => (await api.get("/compliance/dashboard")).data });
  const { data: projects } = useQuery({ queryKey: ["projects"], queryFn: async () => (await api.get("/projects")).data });

  const projectName = (id) => projects?.find((p) => p.id === id)?.name || id;

  const closeForm = () => { setOpen(false); setEditingId(null); setForm(EMPTY_FORM); };
  const invalidateAll = () => { qc.invalidateQueries({ queryKey: ["compliance"] }); qc.invalidateQueries({ queryKey: ["compliance-dashboard"] }); qc.invalidateQueries({ queryKey: ["notifications"] }); };

  const save = useMutation({
    mutationFn: async () => {
      if (editingId) return (await api.patch(`/compliance/${editingId}`, form)).data;
      return (await api.post("/compliance", form)).data;
    },
    onSuccess: () => { toast.success(editingId ? "Updated" : "Added"); invalidateAll(); closeForm(); },
    onError: () => toast.error("Save failed"),
  });
  const analyze = useMutation({
    mutationFn: async (id) => (await api.post(`/compliance/${id}/analyze`)).data,
    onSuccess: (d) => { toast.success("Analyzed by AI"); setActive(d); invalidateAll(); },
    onError: () => toast.error("Analysis failed"),
  });
  const renew = useMutation({
    mutationFn: async (id) => (await api.post(`/compliance/${id}/renew`)).data,
    onSuccess: (d) => { toast.success("Renewal plan generated"); setRenewalActive(d); invalidateAll(); },
    onError: () => toast.error("Renewal plan failed"),
  });
  const penalty = useMutation({
    mutationFn: async (id) => (await api.post(`/compliance/${id}/penalty`)).data,
    onSuccess: (d) => { toast.success("Penalty estimated"); setPenaltyActive(d); invalidateAll(); },
    onError: () => toast.error("Penalty estimate failed"),
  });
  const patch = useMutation({
    mutationFn: async ({ id, body }) => (await api.patch(`/compliance/${id}`, body)).data,
    onSuccess: () => invalidateAll(),
  });
  const del = useMutation({
    mutationFn: async (id) => (await api.delete(`/compliance/${id}`)).data,
    onSuccess: () => { toast.success("Removed"); invalidateAll(); },
  });

  const openEdit = (c) => {
    setEditingId(c.id);
    setForm({
      title: c.title || "",
      category: c.category || "permit",
      due_date: c.due_date || "",
      expiry_date: c.expiry_date || "",
      document_text: c.document_text || "",
      attachments: c.attachments || [],
      project_ids: c.project_ids || [],
      status: c.status || "pending",
    });
    setOpen(true);
  };

  const toggleStep = (item, idx) => {
    const plan = item.renewal_plan || {};
    const steps = [...(plan.steps || [])];
    steps[idx] = { ...steps[idx], done: !steps[idx].done };
    const newPlan = { ...plan, steps };
    const allDone = steps.length > 0 && steps.every((s) => s.done);
    patch.mutate({ id: item.id, body: { renewal_plan: newPlan, ...(allDone ? { status: "completed" } : {}) } });
    setRenewalActive({ ...item, renewal_plan: newPlan });
  };

  const sortedItems = useMemo(() => {
    const arr = [...(items || [])];
    return arr.sort((a, b) => {
      const da = daysUntil(a.due_date);
      const db = daysUntil(b.due_date);
      if (da === null && db === null) return 0;
      if (da === null) return 1;
      if (db === null) return -1;
      return da - db;
    });
  }, [items]);

  if (isLoading) return <Spinner />;
  const inputCls = "w-full border-2 border-[#E4E4E7] focus:border-[#EA580C] outline-none px-3 py-2.5 text-sm transition-colors duration-200 bg-white";

  return (
    <div className="p-5 sm:p-8">
      <PageHeader
        overline="Compliance Intelligence"
        title="Bureaucracy Agent"
        desc="Track permits, licenses, insurance & registrations. Upload a document and the AI explains what changed, deadlines, penalties — and one click generates the renewal checklist."
        action={
          <div className="flex flex-wrap gap-2">
            {items?.length > 0 && (
              <ExportMenu endpoint="/compliance/export" filename="Compliance Register" label="Export" testId="compliance-export-menu" />
            )}
            <Dialog open={open} onOpenChange={(v) => { if (!v) closeForm(); else setOpen(true); }}>
              <DialogTrigger asChild>
                <button data-testid="add-compliance-button" onClick={() => { setEditingId(null); setForm(EMPTY_FORM); setOpen(true); }} className="flex items-center gap-2 bg-[#EA580C] text-white px-4 py-2.5 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200"><Plus size={16} weight="bold" /> Add Item</button>
              </DialogTrigger>
              <DialogContent className="rounded-none border-2 border-[#09090B] max-w-lg max-h-[85vh] overflow-y-auto">
                <DialogHeader><DialogTitle className="font-display">{editingId ? "Edit compliance item" : "Add compliance item"}</DialogTitle><DialogDescription>Track a permit, license, insurance or registration and analyze with AI.</DialogDescription></DialogHeader>
                <div className="space-y-3">
                  <input data-testid="compliance-title-input" className={inputCls} placeholder="Title (e.g. Labour License Renewal)" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
                  <div className="grid grid-cols-2 gap-3">
                    <select data-testid="compliance-category-select" className={inputCls} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>{CATS.map((c) => <option key={c}>{c}</option>)}</select>
                    <select data-testid="compliance-status-select" className={inputCls} value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                      <option value="pending">pending</option>
                      <option value="in_progress">in progress</option>
                      <option value="completed">completed</option>
                    </select>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="overline mb-1 block">Due date</label>
                      <input data-testid="compliance-due-input" type="date" className={inputCls} value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
                    </div>
                    <div>
                      <label className="overline mb-1 block">Expiry / validity</label>
                      <input data-testid="compliance-expiry-input" type="date" className={inputCls} value={form.expiry_date} onChange={(e) => setForm({ ...form, expiry_date: e.target.value })} />
                    </div>
                  </div>
                  {projects?.length > 0 && (
                    <div>
                      <label className="overline mb-1 block">Applies to projects</label>
                      <div className="flex flex-wrap gap-1.5">
                        {projects.map((p) => {
                          const on = form.project_ids.includes(p.id);
                          return (
                            <button
                              key={p.id}
                              type="button"
                              data-testid={`project-toggle-${p.id}`}
                              onClick={() => setForm((f) => ({ ...f, project_ids: on ? f.project_ids.filter((x) => x !== p.id) : [...f.project_ids, p.id] }))}
                              className={`px-2.5 py-1 text-xs border-2 transition-colors duration-150 ${on ? "border-[#EA580C] bg-[#EA580C] text-white" : "border-[#E4E4E7] hover:border-[#09090B]"}`}
                            >{p.name}</button>
                          );
                        })}
                      </div>
                    </div>
                  )}
                  <textarea data-testid="compliance-doc-input" className={inputCls + " min-h-28"} placeholder="Paste circular / notification / document text here for AI analysis…" value={form.document_text} onChange={(e) => setForm({ ...form, document_text: e.target.value })} />
                  <FileUpload
                    accept=".pdf,.txt,.png,.jpg,.jpeg,.webp"
                    label="Upload document (PDF / image / txt)"
                    onUploaded={(f) => setForm((prev) => ({
                      ...prev,
                      attachments: [...prev.attachments, f],
                      document_text: f.extracted_text && !prev.document_text ? f.extracted_text : prev.document_text,
                    }))}
                  />
                  {form.attachments.length > 0 && (<div className="flex flex-wrap gap-2">{form.attachments.map((f) => <Attachment key={f.id} file={f} />)}</div>)}
                </div>
                <DialogFooter>
                  <button data-testid="save-compliance-button" disabled={!form.title || save.isPending} onClick={() => save.mutate()} className="bg-[#EA580C] text-white px-5 py-2.5 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200 disabled:opacity-50">
                    {save.isPending ? "Saving…" : (editingId ? "Save" : "Add")}
                  </button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        }
      />

      <ScoreCard dashboard={dashboard} />

      {items?.length === 0 ? (
        <div className="border border-[#E4E4E7] p-12 text-center"><ShieldCheck size={36} weight="duotone" className="mx-auto text-[#EA580C] mb-3" /><p className="text-[#71717A] text-sm">No compliance items yet. Add your permits/licenses, or open the Regulation Feed to track a live update.</p></div>
      ) : (
        <div className="grid md:grid-cols-2 gap-px bg-[#E4E4E7] border border-[#E4E4E7]" data-testid="compliance-list">
          {sortedItems.map((c) => {
            const days = daysUntil(c.due_date || c.expiry_date);
            const meta = urgencyMeta(days);
            return (
              <div key={c.id} data-testid={`compliance-card-${c.id}`} className="bg-white p-5 flex flex-col">
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div className="min-w-0">
                    <h3 className="font-display font-bold leading-snug break-words">{c.title}</h3>
                    <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
                      <Badge tone="accent">{c.category}</Badge>
                      <Badge tone={STATUS_COLORS[c.status] || "neutral"}>{(c.status || "pending").replace("_", " ")}</Badge>
                      {(c.due_date || c.expiry_date) && <Badge tone={meta.tone}><ClockCountdown size={11} weight="bold" className="mr-1 inline" />{meta.label}</Badge>}
                      {c.analysis?.risk_level && <Badge tone={c.analysis.risk_level === "high" ? "critical" : c.analysis.risk_level === "medium" ? "warning" : "success"}>{c.analysis.risk_level} risk</Badge>}
                    </div>
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <button data-testid={`edit-compliance-${c.id}`} onClick={() => openEdit(c)} className="p-1.5 text-[#71717A] hover:text-[#EA580C] transition-colors duration-200" title="Edit"><Sparkle size={14} weight="bold" /></button>
                    <button data-testid={`delete-compliance-${c.id}`} onClick={() => { if (window.confirm(`Delete "${c.title}"?`)) del.mutate(c.id); }} className="p-1.5 text-[#71717A] hover:text-[#DC2626] transition-colors duration-200" title="Delete"><Trash size={14} weight="bold" /></button>
                  </div>
                </div>
                {c.project_ids?.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-2">
                    {c.project_ids.map((pid) => <span key={pid} className="text-[11px] px-1.5 py-0.5 bg-[#F4F4F5] text-[#3f3f46] flex items-center gap-1"><MapPin size={10} weight="bold" />{projectName(pid)}</span>)}
                  </div>
                )}
                {c.attachments?.length > 0 && (<div className="flex flex-wrap gap-2 mb-3">{c.attachments.map((f) => <Attachment key={f.id} file={f} />)}</div>)}
                <div className="mt-auto pt-3 border-t border-[#F4F4F5] flex flex-wrap gap-1.5">
                  {c.analysis ? (
                    <button data-testid={`view-analysis-${c.id}`} onClick={() => setActive(c)} className="text-xs font-semibold text-[#EA580C] hover:underline">AI analysis →</button>
                  ) : (
                    <button data-testid={`analyze-${c.id}`} onClick={() => analyze.mutate(c.id)} disabled={analyze.isPending && analyze.variables === c.id} className="flex items-center gap-1 text-xs font-semibold border border-[#09090B] px-2 py-1 hover:bg-[#09090B] hover:text-white transition-colors duration-200 disabled:opacity-50">
                      <Sparkle size={11} weight="fill" /> Analyze
                    </button>
                  )}
                  {c.renewal_plan ? (
                    <button data-testid={`view-renewal-${c.id}`} onClick={() => setRenewalActive(c)} className="flex items-center gap-1 text-xs font-semibold text-[#EA580C] hover:underline">
                      <ListChecks size={11} weight="bold" /> Renewal plan
                    </button>
                  ) : (
                    <button data-testid={`renew-${c.id}`} onClick={() => renew.mutate(c.id)} disabled={renew.isPending && renew.variables === c.id} className="flex items-center gap-1 text-xs font-semibold border border-[#09090B] px-2 py-1 hover:bg-[#09090B] hover:text-white transition-colors duration-200 disabled:opacity-50">
                      <ArrowClockwise size={11} weight="bold" /> Start renewal
                    </button>
                  )}
                  {(days !== null && days < 0) && (
                    c.penalty_estimate ? (
                      <button data-testid={`view-penalty-${c.id}`} onClick={() => setPenaltyActive(c)} className="flex items-center gap-1 text-xs font-semibold text-[#DC2626] hover:underline">
                        <CurrencyInr size={11} weight="bold" /> Penalty ₹{Math.round(c.penalty_estimate.amount_max || c.penalty_estimate.amount_min || 0).toLocaleString("en-IN")}
                      </button>
                    ) : (
                      <button data-testid={`penalty-${c.id}`} onClick={() => penalty.mutate(c.id)} disabled={penalty.isPending && penalty.variables === c.id} className="flex items-center gap-1 text-xs font-semibold border border-[#DC2626] text-[#DC2626] px-2 py-1 hover:bg-[#DC2626] hover:text-white transition-colors duration-200 disabled:opacity-50">
                        <CurrencyInr size={11} weight="bold" /> Estimate penalty
                      </button>
                    )
                  )}
                  {c.status !== "completed" && (
                    <button data-testid={`complete-${c.id}`} onClick={() => patch.mutate({ id: c.id, body: { status: "completed" } })} className="ml-auto flex items-center gap-1 text-xs font-semibold text-[#16A34A] hover:underline">
                      <CheckCircle size={12} weight="bold" /> Mark done
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <Dialog open={!!active} onOpenChange={(v) => !v && setActive(null)}>
        <DialogContent className="rounded-none border-2 border-[#09090B] max-w-lg">
          <DialogHeader><DialogTitle className="font-display flex items-center gap-2"><Sparkle size={18} weight="fill" className="text-[#EA580C]" /> AI Analysis</DialogTitle><DialogDescription>AI-generated breakdown of this compliance document.</DialogDescription></DialogHeader>
          {active?.analysis && (
            <div className="space-y-4 text-sm max-h-[60vh] overflow-y-auto">
              <h4 className="font-display font-bold">{active.title}</h4>
              {active.analysis.summary && <p className="text-[#3f3f46]">{active.analysis.summary}</p>}
              {[["What changed", active.analysis.what_changed], ["Who is affected", active.analysis.who_is_affected], ["Deadline", active.analysis.deadline], ["Penalties", active.analysis.penalties]].map(([k, v]) => v && (
                <div key={k}><p className="overline mb-1">{k}</p><p className="text-[#3f3f46]">{v}</p></div>
              ))}
              {active.analysis.actions_required?.length > 0 && (
                <div><p className="overline mb-1 flex items-center gap-1"><Warning size={12} weight="bold" /> Actions required</p>
                  <ul className="list-disc pl-5 space-y-1 text-[#3f3f46]">{active.analysis.actions_required.map((a, i) => <li key={`ar-${i}`}>{a}</li>)}</ul>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={!!renewalActive} onOpenChange={(v) => !v && setRenewalActive(null)}>
        <DialogContent className="rounded-none border-2 border-[#09090B] max-w-xl" data-testid="renewal-plan-dialog">
          <DialogHeader><DialogTitle className="font-display flex items-center gap-2"><ListChecks size={18} weight="bold" className="text-[#EA580C]" /> Renewal Plan</DialogTitle><DialogDescription>AI-generated step-by-step renewal checklist.</DialogDescription></DialogHeader>
          {renewalActive?.renewal_plan && (
            <div className="space-y-4 text-sm max-h-[65vh] overflow-y-auto">
              <h4 className="font-display font-bold">{renewalActive.title}</h4>
              <div className="grid grid-cols-2 gap-3 text-xs">
                {renewalActive.renewal_plan.submission_office && <div><p className="overline mb-1">Where</p><p className="text-[#3f3f46]">{renewalActive.renewal_plan.submission_office}</p></div>}
                {renewalActive.renewal_plan.fee_estimate && <div><p className="overline mb-1">Fee</p><p className="text-[#3f3f46]">{renewalActive.renewal_plan.fee_estimate}</p></div>}
                {renewalActive.renewal_plan.processing_time && <div><p className="overline mb-1">Processing time</p><p className="text-[#3f3f46]">{renewalActive.renewal_plan.processing_time}</p></div>}
                {renewalActive.renewal_plan.portal_url && <div><p className="overline mb-1">Portal</p><a href={renewalActive.renewal_plan.portal_url} target="_blank" rel="noreferrer" className="text-[#EA580C] hover:underline break-all">{renewalActive.renewal_plan.portal_url}</a></div>}
              </div>
              {renewalActive.renewal_plan.docs_needed?.length > 0 && (
                <div><p className="overline mb-1">Documents to prepare</p>
                  <ul className="list-disc pl-5 space-y-1 text-[#3f3f46]">{renewalActive.renewal_plan.docs_needed.map((d, i) => <li key={`d-${i}`}>{d}</li>)}</ul>
                </div>
              )}
              {renewalActive.renewal_plan.steps?.length > 0 && (
                <div>
                  <p className="overline mb-2">Step-by-step</p>
                  <ol className="space-y-2">
                    {renewalActive.renewal_plan.steps.map((s, i) => (
                      <li key={`s-${i}`} className="flex items-start gap-3 border border-[#E4E4E7] p-3">
                        <input
                          type="checkbox"
                          data-testid={`step-toggle-${renewalActive.id}-${i}`}
                          checked={!!s.done}
                          onChange={() => toggleStep(renewalActive, i)}
                          className="mt-1 w-4 h-4 accent-[#EA580C]"
                        />
                        <div className="flex-1">
                          <p className={`font-semibold text-sm ${s.done ? "line-through text-[#71717A]" : ""}`}>{s.title}</p>
                          {s.detail && <p className="text-xs text-[#71717A] mt-0.5">{s.detail}</p>}
                        </div>
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={!!penaltyActive} onOpenChange={(v) => !v && setPenaltyActive(null)}>
        <DialogContent className="rounded-none border-2 border-[#09090B] max-w-lg" data-testid="penalty-dialog">
          <DialogHeader><DialogTitle className="font-display flex items-center gap-2"><CurrencyInr size={18} weight="bold" className="text-[#DC2626]" /> Penalty Estimate</DialogTitle><DialogDescription>Cost of delay per typical Indian statutes.</DialogDescription></DialogHeader>
          {penaltyActive?.penalty_estimate && (
            <div className="space-y-3 text-sm">
              <h4 className="font-display font-bold">{penaltyActive.title}</h4>
              <div className="grid grid-cols-2 gap-3 border border-[#E4E4E7] p-3">
                <div><p className="overline mb-1">Days overdue</p><p className="font-display font-bold text-lg">{penaltyActive.penalty_estimate.days_overdue}</p></div>
                <div><p className="overline mb-1">Estimated fine</p>
                  <p className="font-display font-bold text-lg text-[#DC2626]">
                    ₹{Math.round(penaltyActive.penalty_estimate.amount_min || 0).toLocaleString("en-IN")}
                    {penaltyActive.penalty_estimate.amount_max && penaltyActive.penalty_estimate.amount_max !== penaltyActive.penalty_estimate.amount_min && ` – ₹${Math.round(penaltyActive.penalty_estimate.amount_max).toLocaleString("en-IN")}`}
                  </p>
                </div>
              </div>
              {penaltyActive.penalty_estimate.basis && <div><p className="overline mb-1">Basis</p><p className="text-[#3f3f46]">{penaltyActive.penalty_estimate.basis}</p></div>}
              {penaltyActive.penalty_estimate.worst_case && <div><p className="overline mb-1 text-[#DC2626]">Worst case</p><p className="text-[#3f3f46]">{penaltyActive.penalty_estimate.worst_case}</p></div>}
              {penaltyActive.penalty_estimate.escalation?.length > 0 && (
                <div><p className="overline mb-1">Escalation</p>
                  <ul className="text-xs space-y-1">{penaltyActive.penalty_estimate.escalation.map((e, i) => <li key={`e-${i}`} className="flex justify-between border-b border-[#F4F4F5] py-1"><span>after {e.days_after_due}d</span><span className="text-[#3f3f46]">{e.penalty}</span></li>)}</ul>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
