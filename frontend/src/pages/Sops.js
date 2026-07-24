import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { PageHeader, Badge, Spinner } from "@/components/ui-bits";
import { ListChecks, Sparkle, ShieldWarning, Wrench, CheckCircle, ArrowBendUpRight } from "@phosphor-icons/react";
import VoiceButton from "@/components/VoiceButton";
import { FileUpload, Attachment } from "@/components/FileUpload";
import TranslateButton from "@/components/TranslateButton";
import { toast } from "sonner";

const CATS = ["general", "concrete", "safety", "electrical", "plumbing", "finishing", "quality"];

export default function Sops() {
  const qc = useQueryClient();
  const [form, setForm] = useState({ title: "", category: "general", raw_input: "", attachments: [] });
  const [active, setActive] = useState(null);

  const { data: sops, isLoading } = useQuery({ queryKey: ["sops"], queryFn: async () => (await api.get("/sops")).data });

  const gen = useMutation({
    mutationFn: async () => (await api.post("/sops/generate", form)).data,
    onSuccess: (d) => { toast.success("SOP generated"); setActive(d); setForm({ title: "", category: "general", raw_input: "", attachments: [] }); qc.invalidateQueries({ queryKey: ["sops"] }); },
    onError: () => toast.error("Generation failed"),
  });

  const inputCls = "w-full border-2 border-[#E4E4E7] focus:border-[#EA580C] outline-none px-3 py-2.5 text-sm transition-colors duration-200 bg-white";

  return (
    <div className="p-5 sm:p-8">
      <PageHeader overline="Dynamic SOP Generation" title="SOP Generator" desc="Turn a supervisor's voice note or rough description into a structured Standard Operating Procedure — steps, safety, inspection points, tools & acceptance criteria." />

      <div className="grid lg:grid-cols-3 gap-px bg-[#E4E4E7] border border-[#E4E4E7]">
        {/* Generator */}
        <div className="lg:col-span-1 bg-white p-6">
          <p className="overline mb-3">New SOP from raw input</p>
          <div className="space-y-3">
            <input data-testid="sop-title-input" className={inputCls} placeholder="Topic (e.g. Concrete receiving)" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            <select data-testid="sop-category-select" className={inputCls} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>{CATS.map((c) => <option key={c}>{c}</option>)}</select>
            <textarea data-testid="sop-input" className={inputCls + " min-h-40"} placeholder="Paste a transcript or describe the process the way a supervisor would explain it… or tap the mic to dictate." value={form.raw_input} onChange={(e) => setForm({ ...form, raw_input: e.target.value })} />
            <div className="flex items-center gap-2">
              <VoiceButton title="Dictate the procedure" onResult={(t) => setForm((p) => ({ ...p, raw_input: (p.raw_input ? p.raw_input + " " : "") + t }))} />
              <span className="text-xs text-[#71717A]">Dictate in any supported language</span>
            </div>
            <FileUpload
              accept=".pdf,.png,.jpg,.jpeg,.webp,.mp3,.wav,.m4a,.mp4,.mov"
              label="Attach source media (photo / PDF / clip)"
              onUploaded={(f) => setForm((p) => ({ ...p, attachments: [...p.attachments, f] }))}
            />
            {form.attachments.length > 0 && <div className="flex flex-wrap gap-2">{form.attachments.map((f) => <Attachment key={f.id} file={f} />)}</div>}
            <button data-testid="generate-sop-button" disabled={!form.raw_input || gen.isPending} onClick={() => gen.mutate()} className="w-full flex items-center justify-center gap-2 bg-[#EA580C] text-white px-4 py-3 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200 disabled:opacity-50">
              <Sparkle size={16} weight="fill" /> {gen.isPending ? "Generating…" : "Generate SOP"}
            </button>
          </div>
        </div>

        {/* Library */}
        <div className="lg:col-span-2 bg-white p-6">
          <p className="overline mb-3">SOP Library</p>
          {isLoading ? <Spinner /> : sops?.length === 0 ? (
            <div className="text-center py-12"><ListChecks size={36} weight="duotone" className="mx-auto text-[#EA580C] mb-3" /><p className="text-[#71717A] text-sm">No SOPs yet. Generate your first one.</p></div>
          ) : (
            <div className="grid sm:grid-cols-2 gap-3" data-testid="sop-library">
              {sops?.map((s) => (
                <button key={s.id} data-testid={`sop-card-${s.id}`} onClick={() => setActive(s)} className="text-left border border-[#E4E4E7] p-4 hover:border-[#EA580C] hover:-translate-y-px transition-all duration-200">
                  <Badge tone="accent">{s.category}</Badge>
                  <h3 className="font-display font-bold mt-2 leading-snug">{s.content?.title || s.title}</h3>
                  <p className="text-xs text-[#71717A] mt-1 line-clamp-2">{s.content?.objective}</p>
                  <p className="text-xs font-semibold text-[#EA580C] mt-2">{s.content?.steps?.length || 0} steps →</p>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {active && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setActive(null)}>
          <div className="absolute inset-0 bg-black/40" />
          <div className="relative bg-white border-2 border-[#09090B] max-w-2xl w-full max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()} data-testid="sop-detail">
            <div className="p-6 border-b border-[#E4E4E7] sticky top-0 bg-white">
              <Badge tone="accent">{active.category}</Badge>
              <h2 className="font-display font-black text-2xl tracking-tight mt-2">{active.content?.title || active.title}</h2>
              {active.content?.objective && <p className="text-sm text-[#71717A] mt-2">{active.content.objective}</p>}
              <div className="mt-3">
                <TranslateButton text={buildSopPlaintext(active)} contextLabel="Construction SOP" />
              </div>
            </div>
            <div className="p-6 space-y-6 text-sm">
              {active.content?.steps?.length > 0 && (
                <Section icon={ListChecks} title="Procedure">
                  <ol className="space-y-2">{active.content.steps.map((s, i) => (
                    <li key={'step-' + i + '-' + s.slice(0, 15)} className="flex gap-3"><span className="font-mono font-bold text-[#EA580C] shrink-0">{String(i + 1).padStart(2, "0")}</span><span className="text-[#3f3f46]">{s}</span></li>
                  ))}</ol>
                </Section>
              )}
              {active.content?.safety_precautions?.length > 0 && <Section icon={ShieldWarning} title="Safety Precautions"><BulletList items={active.content.safety_precautions} /></Section>}
              {active.content?.inspection_points?.length > 0 && <Section icon={CheckCircle} title="Inspection Points"><BulletList items={active.content.inspection_points} /></Section>}
              {active.content?.required_tools?.length > 0 && <Section icon={Wrench} title="Required Tools"><BulletList items={active.content.required_tools} /></Section>}
              {active.content?.acceptance_criteria?.length > 0 && <Section icon={CheckCircle} title="Acceptance Criteria"><BulletList items={active.content.acceptance_criteria} /></Section>}
              {active.content?.escalation && <Section icon={ArrowBendUpRight} title="Escalation"><p className="text-[#3f3f46]">{active.content.escalation}</p></Section>}
              {active.attachments?.length > 0 && <Section icon={ListChecks} title="Source Media"><div className="flex flex-wrap gap-2">{active.attachments.map((f) => <Attachment key={f.id} file={f} />)}</div></Section>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const Section = ({ icon: Icon, title, children }) => (
  <div>
    <div className="flex items-center gap-2 mb-2"><Icon size={16} weight="bold" className="text-[#EA580C]" /><p className="overline">{title}</p></div>
    {children}
  </div>
);
const BulletList = ({ items }) => <ul className="list-disc pl-5 space-y-1 text-[#3f3f46]">{items.map((it, i) => <li key={'item-' + i + '-' + it.slice(0, 15)}>{it}</li>)}</ul>;

function buildSopPlaintext(s) {
  const c = s?.content || {};
  const lines = [];
  if (c.title || s?.title) lines.push(c.title || s.title);
  if (c.objective) lines.push("", c.objective);
  if (c.steps?.length) lines.push("", "Procedure:", ...c.steps.map((t, i) => `${i + 1}. ${t}`));
  if (c.safety_precautions?.length) lines.push("", "Safety Precautions:", ...c.safety_precautions.map((t) => `- ${t}`));
  if (c.inspection_points?.length) lines.push("", "Inspection Points:", ...c.inspection_points.map((t) => `- ${t}`));
  if (c.required_tools?.length) lines.push("", "Required Tools:", ...c.required_tools.map((t) => `- ${t}`));
  if (c.acceptance_criteria?.length) lines.push("", "Acceptance Criteria:", ...c.acceptance_criteria.map((t) => `- ${t}`));
  if (c.escalation) lines.push("", "Escalation:", c.escalation);
  return lines.join("\n").trim();
}
