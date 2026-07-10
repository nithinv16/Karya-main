import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { PageHeader, Badge, Spinner } from "@/components/ui-bits";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Brain, Plus, MagnifyingGlass, Sparkle } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function Knowledge() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ title: "", content: "", project_id: "", tags: "" });
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);
  const [asking, setAsking] = useState(false);

  const { data: items, isLoading } = useQuery({ queryKey: ["knowledge"], queryFn: async () => (await api.get("/knowledge")).data });
  const { data: projects } = useQuery({ queryKey: ["projects"], queryFn: async () => (await api.get("/projects")).data });
  const pname = (id) => projects?.find((p) => p.id === id)?.name;

  const add = useMutation({
    mutationFn: async () => (await api.post("/knowledge", { ...form, project_id: form.project_id || null, tags: form.tags.split(",").map((t) => t.trim()).filter(Boolean) })).data,
    onSuccess: () => { toast.success("Saved to memory"); qc.invalidateQueries({ queryKey: ["knowledge"] }); setOpen(false); setForm({ title: "", content: "", project_id: "", tags: "" }); },
  });

  const ask = async () => {
    if (!question.trim()) return;
    setAsking(true); setAnswer(null);
    try {
      const res = await api.post("/knowledge/ask", { question });
      setAnswer(res.data.answer);
    } catch { toast.error("Could not answer"); } finally { setAsking(false); }
  };

  const inputCls = "w-full border-2 border-[#E4E4E7] focus:border-[#EA580C] outline-none px-3 py-2.5 text-sm transition-colors duration-200 bg-white";

  return (
    <div className="p-5 sm:p-8">
      <PageHeader
        overline="Organizational Knowledge"
        title="Org Memory"
        desc="Capture decisions, supplier intel, pricing, delays & lessons learned. Then ask questions and get answers from your company's history — even after people leave."
        action={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild><button data-testid="add-knowledge-button" className="flex items-center gap-2 bg-[#EA580C] text-white px-4 py-2.5 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200"><Plus size={16} weight="bold" /> Add Memory</button></DialogTrigger>
            <DialogContent className="rounded-none border-2 border-[#09090B]">
              <DialogHeader><DialogTitle className="font-display">Capture Knowledge</DialogTitle><DialogDescription>Save a decision, supplier detail, price or lesson learned to org memory.</DialogDescription></DialogHeader>
              <div className="space-y-3">
                <input data-testid="knowledge-title-input" className={inputCls} placeholder="Title (e.g. Steel price negotiation)" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
                <textarea data-testid="knowledge-content-input" className={inputCls + " min-h-28"} placeholder="The decision, context, supplier, price, lesson learned…" value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} />
                <select className={inputCls} value={form.project_id} onChange={(e) => setForm({ ...form, project_id: e.target.value })}><option value="">— Link project (optional) —</option>{projects?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select>
                <input className={inputCls} placeholder="Tags (comma separated)" value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} />
              </div>
              <DialogFooter><button data-testid="save-knowledge-button" disabled={!form.title || !form.content || add.isPending} onClick={() => add.mutate()} className="bg-[#EA580C] text-white px-5 py-2.5 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200 disabled:opacity-50">Save</button></DialogFooter>
            </DialogContent>
          </Dialog>
        }
      />

      {/* Ask memory */}
      <div className="border-2 border-[#09090B] bg-[#FAFAFA] p-5 mb-8" data-testid="ask-memory-box">
        <p className="overline mb-3 flex items-center gap-1"><Sparkle size={12} weight="fill" className="text-[#EA580C]" /> Ask your company memory</p>
        <div className="flex gap-2">
          <div className="flex items-center flex-1 border-2 border-[#09090B] bg-white">
            <MagnifyingGlass size={18} className="ml-3 text-[#EA580C]" />
            <input data-testid="memory-question-input" value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={(e) => e.key === "Enter" && ask()} placeholder='e.g. "Why was Skyline Towers delayed?" or "Which supplier had lowest defects?"' className="flex-1 px-3 py-2.5 text-sm outline-none bg-transparent" />
          </div>
          <button data-testid="ask-memory-button" onClick={ask} disabled={asking} className="bg-[#09090B] text-white px-5 text-sm font-semibold hover:bg-[#EA580C] transition-colors duration-200 disabled:opacity-50">{asking ? "…" : "Ask"}</button>
        </div>
        {(asking || answer) && (
          <div className="mt-4 bg-white border border-[#E4E4E7] p-4 text-sm whitespace-pre-wrap" data-testid="memory-answer">
            {asking ? <span className="text-[#71717A]">Searching company memory…</span> : answer}
          </div>
        )}
      </div>

      {isLoading ? <Spinner /> : items?.length === 0 ? (
        <div className="border border-[#E4E4E7] p-12 text-center"><Brain size={36} weight="duotone" className="mx-auto text-[#EA580C] mb-3" /><p className="text-[#71717A] text-sm">No memories captured yet.</p></div>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-px bg-[#E4E4E7] border border-[#E4E4E7]" data-testid="knowledge-list">
          {items?.map((k) => (
            <div key={k.id} className="bg-white p-5">
              <h3 className="font-display font-bold leading-snug mb-2">{k.title}</h3>
              <p className="text-sm text-[#3f3f46] mb-3 line-clamp-4">{k.content}</p>
              <div className="flex flex-wrap gap-1.5">
                {pname(k.project_id) && <Badge tone="accent">{pname(k.project_id)}</Badge>}
                {k.tags?.map((t) => <Badge key={t}>{t}</Badge>)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
