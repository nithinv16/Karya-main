import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { PageHeader, Badge, Spinner } from "@/components/ui-bits";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Broadcast, Sparkle, Warning, Trash, ArrowsClockwise, ShieldCheck } from "@phosphor-icons/react";
import { toast } from "sonner";

const CATS = ["labour", "gst", "safety", "municipal", "tender", "environment"];
const catTone = (c) => ({ labour: "accent", gst: "warning", safety: "critical", municipal: "neutral", tender: "success", environment: "neutral" }[c] || "neutral");
const urgencyTone = (u) => (u === "high" ? "critical" : u === "medium" ? "warning" : "success");

export default function BureaucracyFeed() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ title: "", source: "", category: "labour", region: "", summary: "" });
  const [filterRegion, setFilterRegion] = useState("");
  const [filterCategory, setFilterCategory] = useState("");

  const { data: items, isLoading } = useQuery({
    queryKey: ["feed", filterRegion, filterCategory],
    queryFn: async () => (await api.get("/feed", { params: { region: filterRegion, category: filterCategory } })).data,
  });

  const fetchVerified = useMutation({
    mutationFn: async () => (await api.post("/feed/fetch")).data,
    onSuccess: (d) => { toast.success(`Pulled ${d.added} verified updates from live sources`); qc.invalidateQueries({ queryKey: ["feed"] }); },
    onError: () => toast.error("Fetch failed, try again"),
  });
  const add = useMutation({
    mutationFn: async () => (await api.post("/feed", form)).data,
    onSuccess: () => { toast.success("Update added"); qc.invalidateQueries({ queryKey: ["feed"] }); setOpen(false); setForm({ title: "", source: "", category: "labour", region: "", summary: "" }); },
  });
  const analyze = useMutation({
    mutationFn: async (id) => (await api.post(`/feed/${id}/impact`)).data,
    onSuccess: () => { toast.success("Impact analyzed"); qc.invalidateQueries({ queryKey: ["feed"] }); },
    onError: () => toast.error("Analysis failed"),
  });
  const track = useMutation({
    mutationFn: async (id) => (await api.post(`/feed/${id}/track`)).data,
    onSuccess: () => { toast.success("Added to Compliance tracker"); qc.invalidateQueries({ queryKey: ["compliance"] }); qc.invalidateQueries({ queryKey: ["notifications"] }); },
    onError: () => toast.error("Could not track"),
  });
  const del = useMutation({
    mutationFn: async (id) => (await api.delete(`/feed/${id}`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["feed"] }),
  });

  const inputCls = "w-full border-2 border-[#E4E4E7] focus:border-[#EA580C] outline-none px-3 py-2.5 text-sm transition-colors duration-200 bg-white";

  return (
    <div className="p-5 sm:p-8">
      <PageHeader
        overline="Bureaucracy Intelligence"
        title="Regulation Feed"
        desc="Live, source-linked updates pulled from the internet — labour, GST/CBIC, safety, municipal, environment & CPWD/PWD tenders — with AI impact analysis for your business."
        action={
          <div className="flex gap-2">
            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger asChild>
                <button data-testid="add-feed-button" className="border-2 border-[#09090B] px-4 py-2.5 text-sm font-semibold hover:bg-[#09090B] hover:text-white transition-colors duration-200">Add update</button>
              </DialogTrigger>
              <DialogContent className="rounded-none border-2 border-[#09090B]">
                <DialogHeader><DialogTitle className="font-display">Add regulatory update</DialogTitle><DialogDescription>Paste a circular, notification or tender update to track and analyze.</DialogDescription></DialogHeader>
                <div className="space-y-3">
                  <input data-testid="feed-title-input" className={inputCls} placeholder="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
                  <div className="grid grid-cols-2 gap-3">
                    <input className={inputCls} placeholder="Source / issuing body" value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} />
                    <select className={inputCls} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>{CATS.map((c) => <option key={c}>{c}</option>)}</select>
                  </div>
                  <input className={inputCls} placeholder="Region (state / All India)" value={form.region} onChange={(e) => setForm({ ...form, region: e.target.value })} />
                  <textarea data-testid="feed-summary-input" className={inputCls + " min-h-28"} placeholder="Summary / text of the update…" value={form.summary} onChange={(e) => setForm({ ...form, summary: e.target.value })} />
                </div>
                <DialogFooter><button data-testid="save-feed-button" disabled={!form.title || add.isPending} onClick={() => add.mutate()} className="bg-[#EA580C] text-white px-5 py-2.5 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200 disabled:opacity-50">Add</button></DialogFooter>
              </DialogContent>
            </Dialog>
            <button data-testid="fetch-feed-button" onClick={() => fetchVerified.mutate()} disabled={fetchVerified.isPending} className="flex items-center gap-2 bg-[#EA580C] text-white px-4 py-2.5 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200 disabled:opacity-50">
              <ArrowsClockwise size={16} weight="bold" className={fetchVerified.isPending ? "animate-spin" : ""} /> {fetchVerified.isPending ? "Fetching live data…" : "Fetch live updates"}
            </button>
          </div>
        }
      />

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 mb-5" data-testid="feed-filters">
        <input
          data-testid="feed-region-filter"
          value={filterRegion}
          onChange={(e) => setFilterRegion(e.target.value)}
          placeholder="Filter by region (e.g. Karnataka, Delhi, UAE)"
          className="border-2 border-[#E4E4E7] focus:border-[#EA580C] outline-none px-3 py-1.5 text-sm bg-white w-64"
        />
        <select
          data-testid="feed-category-filter"
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
          className="border-2 border-[#E4E4E7] focus:border-[#EA580C] outline-none px-3 py-1.5 text-sm bg-white"
        >
          <option value="">All categories</option>
          {CATS.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        {(filterRegion || filterCategory) && (
          <button data-testid="feed-clear-filters" onClick={() => { setFilterRegion(""); setFilterCategory(""); }} className="text-xs text-[#EA580C] font-semibold hover:underline">Clear filters</button>
        )}
      </div>

      {isLoading ? <Spinner /> : items?.length === 0 ? (
        <div className="border border-[#E4E4E7] p-12 text-center">
          <Broadcast size={36} weight="duotone" className="mx-auto text-[#EA580C] mb-3" />
          <p className="text-[#71717A] text-sm mb-4">No regulatory updates yet.</p>
          <button data-testid="fetch-feed-empty" onClick={() => fetchVerified.mutate()} disabled={fetchVerified.isPending} className="bg-[#09090B] text-white px-5 py-2.5 text-sm font-semibold hover:bg-[#16A34A] transition-colors duration-200">{fetchVerified.isPending ? "Fetching…" : "Fetch verified updates"}</button>
        </div>
      ) : (
        <div className="grid lg:grid-cols-2 gap-px bg-[#E4E4E7] border border-[#E4E4E7]" data-testid="feed-list">
          {items?.map((it) => (
            <div key={it.id} className="bg-white p-5 flex flex-col" data-testid={`feed-item-${it.id}`}>
              <div className="flex items-start justify-between gap-3 mb-2">
                <h3 className="font-display font-bold leading-snug">{it.title}</h3>
                <button data-testid={`delete-feed-${it.id}`} onClick={() => del.mutate(it.id)} className="text-[#71717A] hover:text-[#DC2626] transition-colors duration-200 shrink-0"><Trash size={15} weight="bold" /></button>
              </div>
              <div className="flex flex-wrap items-center gap-2 mb-3">
                <Badge tone={catTone(it.category)}>{it.category}</Badge>
                <span className="text-xs text-[#71717A] font-medium">{it.source}</span>
                {it.region && <span className="text-xs text-[#71717A]">· {it.region}</span>}
                <span className="text-xs text-[#a1a1aa]">· {it.published_date}</span>
                {it.verified ? <Badge tone="success">Verified source</Badge> : it.url ? <Badge tone="neutral">External</Badge> : null}
              </div>
              <p className="text-sm text-[#3f3f46] mb-4">{it.summary}</p>
              {it.url && (
                <a href={it.url} target="_blank" rel="noreferrer" data-testid={`feed-source-${it.id}`} className="text-xs font-semibold text-[#EA580C] hover:underline mb-4 -mt-2 w-fit">Read original source →</a>
              )}

              {it.impact ? (
                <div className="mt-auto border-2 border-[#09090B] bg-[#FAFAFA] p-4" data-testid={`impact-${it.id}`}>
                  <div className="flex items-center justify-between mb-2">
                    <p className="overline flex items-center gap-1"><Sparkle size={12} weight="fill" className="text-[#EA580C]" /> Impact on your business</p>
                    <Badge tone={urgencyTone(it.impact.urgency)}>{it.impact.urgency} urgency</Badge>
                  </div>
                  <p className="text-sm text-[#3f3f46] mb-3">{it.impact.impact_summary}</p>
                  {it.impact.affected_projects?.length > 0 && (
                    <div className="mb-2 flex flex-wrap gap-1.5">{it.impact.affected_projects.map((p) => <Badge key={p} tone="accent">{p}</Badge>)}</div>
                  )}
                  {it.impact.recommended_actions?.length > 0 && (
                    <div>
                      <p className="overline mb-1 flex items-center gap-1"><Warning size={11} weight="bold" /> Actions</p>
                      <ul className="list-disc pl-5 space-y-1 text-sm text-[#3f3f46]">{it.impact.recommended_actions.slice(0, 5).map((a, i) => <li key={i}>{a}</li>)}</ul>
                    </div>
                  )}
                  <button data-testid={`track-feed-${it.id}`} onClick={() => track.mutate(it.id)} disabled={track.isPending && track.variables === it.id} className="mt-3 flex items-center gap-2 bg-[#09090B] text-white px-3 py-2 text-sm font-semibold hover:bg-[#EA580C] transition-colors duration-200 disabled:opacity-50 w-fit">
                    <ShieldCheck size={14} weight="fill" /> {track.isPending && track.variables === it.id ? "Adding…" : "Track in Compliance"}
                  </button>
                </div>
              ) : (
                <button
                  data-testid={`analyze-feed-${it.id}`}
                  onClick={() => analyze.mutate(it.id)}
                  disabled={analyze.isPending && analyze.variables === it.id}
                  className="mt-auto flex items-center gap-2 border-2 border-[#09090B] px-3 py-2 text-sm font-semibold hover:bg-[#09090B] hover:text-white transition-colors duration-200 disabled:opacity-50 w-fit"
                >
                  <Sparkle size={14} weight="fill" /> {analyze.isPending && analyze.variables === it.id ? "Analyzing…" : "Analyze impact on my business"}
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
