import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { PageHeader, Badge, Spinner } from "@/components/ui-bits";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { ShieldCheck, Plus, Sparkle, Warning } from "@phosphor-icons/react";
import { FileUpload, Attachment } from "@/components/FileUpload";
import { toast } from "sonner";
import ExportMenu from "@/components/ExportMenu";

const CATS = ["permit", "license", "insurance", "registration", "safety", "tender"];

export default function Compliance() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ title: "", category: "permit", due_date: "", document_text: "", attachments: [] });
  const [active, setActive] = useState(null);

  const { data: items, isLoading } = useQuery({ queryKey: ["compliance"], queryFn: async () => (await api.get("/compliance")).data });

  const add = useMutation({
    mutationFn: async () => (await api.post("/compliance", form)).data,
    onSuccess: () => { toast.success("Added"); qc.invalidateQueries({ queryKey: ["compliance"] }); qc.invalidateQueries({ queryKey: ["notifications"] }); setOpen(false); setForm({ title: "", category: "permit", due_date: "", document_text: "", attachments: [] }); },
  });
  const analyze = useMutation({
    mutationFn: async (id) => (await api.post(`/compliance/${id}/analyze`)).data,
    onSuccess: (d) => { toast.success("Analyzed by AI"); setActive(d); qc.invalidateQueries({ queryKey: ["compliance"] }); },
    onError: () => toast.error("Analysis failed"),
  });

  if (isLoading) return <Spinner />;
  const inputCls = "w-full border-2 border-[#E4E4E7] focus:border-[#EA580C] outline-none px-3 py-2.5 text-sm transition-colors duration-200 bg-white";
  const dueTone = (d) => { if (!d) return "neutral"; const days = (new Date(d) - new Date()) / 86400000; return days < 7 ? "critical" : days < 30 ? "warning" : "success"; };

  return (
    <div className="p-5 sm:p-8">
      <PageHeader
        overline="Compliance Intelligence"
        title="Bureaucracy Agent"
        desc="Track permits, licenses, insurance & registrations. Upload a document and the AI explains what changed, who's affected, the deadline and penalties."
        action={
          <div className="flex flex-wrap gap-2">
            {items?.length > 0 && (
              <ExportMenu
                endpoint="/compliance/export"
                filename="Compliance Register"
                label="Export"
                testId="compliance-export-menu"
              />
            )}
            <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild><button data-testid="add-compliance-button" className="flex items-center gap-2 bg-[#EA580C] text-white px-4 py-2.5 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200"><Plus size={16} weight="bold" /> Add Item</button></DialogTrigger>
            <DialogContent className="rounded-none border-2 border-[#09090B]">
              <DialogHeader><DialogTitle className="font-display">Add Compliance Item</DialogTitle><DialogDescription>Track a permit, license, insurance or registration and analyze it with AI.</DialogDescription></DialogHeader>
              <div className="space-y-3">
                <input data-testid="compliance-title-input" className={inputCls} placeholder="Title (e.g. Labour License Renewal)" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
                <div className="grid grid-cols-2 gap-3">
                  <select data-testid="compliance-category-select" className={inputCls} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>{CATS.map((c) => <option key={c}>{c}</option>)}</select>
                  <input data-testid="compliance-due-input" type="date" className={inputCls} value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
                </div>
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
                {form.attachments.length > 0 && (
                  <div className="flex flex-wrap gap-2">{form.attachments.map((f) => <Attachment key={f.id} file={f} />)}</div>
                )}
              </div>
              <DialogFooter><button data-testid="save-compliance-button" disabled={!form.title || add.isPending} onClick={() => add.mutate()} className="bg-[#EA580C] text-white px-5 py-2.5 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200 disabled:opacity-50">Add</button></DialogFooter>
            </DialogContent>
          </Dialog>
          </div>
        }
      />

      {items?.length === 0 ? (
        <div className="border border-[#E4E4E7] p-12 text-center"><ShieldCheck size={36} weight="duotone" className="mx-auto text-[#EA580C] mb-3" /><p className="text-[#71717A] text-sm">No compliance items yet. Add your permits/licenses, or open the Regulation Feed to track a live update.</p></div>
      ) : (
        <div className="grid md:grid-cols-2 gap-px bg-[#E4E4E7] border border-[#E4E4E7]" data-testid="compliance-list">
          {items?.map((c) => (
            <div key={c.id} className="bg-white p-5 flex flex-col">
              <div className="flex items-start justify-between gap-3 mb-3">
                <h3 className="font-display font-bold leading-snug">{c.title}</h3>
                <Badge tone="accent">{c.category}</Badge>
              </div>
              <div className="flex items-center gap-2 mb-4">
                {c.due_date && <Badge tone={dueTone(c.due_date)}>Due {c.due_date}</Badge>}
                {c.analysis?.risk_level && <Badge tone={c.analysis.risk_level === "high" ? "critical" : c.analysis.risk_level === "medium" ? "warning" : "success"}>{c.analysis.risk_level} risk</Badge>}
              </div>
              {c.attachments?.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-4">{c.attachments.map((f) => <Attachment key={f.id} file={f} />)}</div>
              )}
              {c.analysis ? (
                <button data-testid={`view-analysis-${c.id}`} onClick={() => setActive(c)} className="mt-auto text-sm font-semibold text-[#EA580C] hover:underline text-left">View AI analysis →</button>
              ) : (
                <button data-testid={`analyze-${c.id}`} onClick={() => analyze.mutate(c.id)} disabled={analyze.isPending} className="mt-auto flex items-center gap-2 border-2 border-[#09090B] px-3 py-2 text-sm font-semibold hover:bg-[#09090B] hover:text-white transition-colors duration-200 disabled:opacity-50 w-fit">
                  <Sparkle size={14} weight="fill" /> {analyze.isPending ? "Analyzing…" : "Analyze with AI"}
                </button>
              )}
            </div>
          ))}
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
                  <ul className="list-disc pl-5 space-y-1 text-[#3f3f46]">{active.analysis.actions_required.map((a, i) => <li key={i}>{a}</li>)}</ul>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
