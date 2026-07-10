import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { API } from "@/lib/api";
import { PageHeader, Badge, Spinner } from "@/components/ui-bits";
import { FileUpload } from "@/components/FileUpload";
import VoiceButton from "@/components/VoiceButton";
import { ClipboardText, Sparkle, MapPin, Trash, Camera, ListChecks, ShieldWarning, Wrench, CheckCircle, ArrowBendUpRight, UsersThree } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function DailyReports() {
  const qc = useQueryClient();
  const [form, setForm] = useState({ project_id: "", location: "", notes_text: "", photos: [], report_date: new Date().toISOString().slice(0, 10) });
  const [active, setActive] = useState(null);
  const [locating, setLocating] = useState(false);

  const { data: reports, isLoading } = useQuery({ queryKey: ["reports"], queryFn: async () => (await api.get("/reports")).data });
  const { data: projects } = useQuery({ queryKey: ["projects"], queryFn: async () => (await api.get("/projects")).data });

  const gen = useMutation({
    mutationFn: async () => (await api.post("/reports/generate", {
      project_id: form.project_id || null,
      location: form.location,
      notes_text: form.notes_text,
      photo_ids: form.photos.map((p) => p.id),
      report_date: form.report_date,
    })).data,
    onSuccess: (d) => {
      toast.success("Daily report generated");
      setActive(d);
      setForm({ project_id: "", location: "", notes_text: "", photos: [], report_date: new Date().toISOString().slice(0, 10) });
      qc.invalidateQueries({ queryKey: ["reports"] });
    },
    onError: () => toast.error("Report generation failed"),
  });

  const del = useMutation({
    mutationFn: async (id) => (await api.delete(`/reports/${id}`)).data,
    onSuccess: () => { toast.success("Report deleted"); qc.invalidateQueries({ queryKey: ["reports"] }); },
  });

  const geolocate = () => {
    if (!navigator.geolocation) return toast.error("Geolocation not supported");
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => { setForm((p) => ({ ...p, location: `${pos.coords.latitude.toFixed(5)}, ${pos.coords.longitude.toFixed(5)}` })); setLocating(false); },
      () => { toast.error("Couldn't get location"); setLocating(false); }
    );
  };

  const inputCls = "w-full border-2 border-[#E4E4E7] focus:border-[#EA580C] outline-none px-3 py-2.5 text-sm transition-colors duration-200 bg-white";

  return (
    <div className="p-5 sm:p-8">
      <PageHeader
        overline="Field Intelligence"
        title="Daily Reports"
        desc="Field team sends photos, a voice note and location — AI turns them into a professional daily site report for clients and management."
      />

      <div className="grid lg:grid-cols-3 gap-px bg-[#E4E4E7] border border-[#E4E4E7]">
        {/* Generator */}
        <div className="lg:col-span-1 bg-white p-6">
          <p className="overline mb-3">New report from the field</p>
          <div className="space-y-3">
            <select data-testid="report-project-select" className={inputCls} value={form.project_id} onChange={(e) => setForm({ ...form, project_id: e.target.value })}>
              <option value="">— Select project (optional) —</option>
              {projects?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            <input data-testid="report-date-input" type="date" className={inputCls} value={form.report_date} onChange={(e) => setForm({ ...form, report_date: e.target.value })} />
            <div className="flex gap-2">
              <input data-testid="report-location-input" className={inputCls} placeholder="Site location" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
              <button type="button" data-testid="report-geolocate-button" onClick={geolocate} disabled={locating} title="Use my location"
                className="h-[42px] w-[46px] shrink-0 flex items-center justify-center border-2 border-[#09090B] hover:bg-[#EA580C] hover:border-[#EA580C] hover:text-white transition-colors duration-200 disabled:opacity-50">
                <MapPin size={18} weight="fill" />
              </button>
            </div>
            <textarea data-testid="report-notes-input" className={inputCls + " min-h-32"} placeholder="What happened on site today? Type or tap the mic to send a voice note…" value={form.notes_text} onChange={(e) => setForm({ ...form, notes_text: e.target.value })} />
            <div className="flex items-center gap-2">
              <VoiceButton title="Record a voice note" onResult={(t) => setForm((p) => ({ ...p, notes_text: (p.notes_text ? p.notes_text + " " : "") + t }))} />
              <span className="text-xs text-[#71717A]">Voice note in any supported language</span>
            </div>
            <FileUpload
              accept=".png,.jpg,.jpeg,.webp"
              label={`Add site photo (${form.photos.length} added)`}
              onUploaded={(f) => setForm((p) => ({ ...p, photos: [...p.photos, f] }))}
            />
            {form.photos.length > 0 && (
              <div className="grid grid-cols-3 gap-2" data-testid="report-photo-grid">
                {form.photos.map((f) => (
                  <img key={f.id} src={`${API}/files/${f.path}`} alt={f.filename} className="w-full h-16 object-cover border border-[#E4E4E7]" />
                ))}
              </div>
            )}
            <button data-testid="generate-report-button" disabled={(!form.notes_text.trim() && form.photos.length === 0) || gen.isPending} onClick={() => gen.mutate()}
              className="w-full flex items-center justify-center gap-2 bg-[#EA580C] text-white px-4 py-3 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200 disabled:opacity-50">
              <Sparkle size={16} weight="fill" /> {gen.isPending ? "Writing report…" : "Generate Daily Report"}
            </button>
          </div>
        </div>

        {/* Library */}
        <div className="lg:col-span-2 bg-white p-6">
          <p className="overline mb-3">Report Archive</p>
          {isLoading ? <Spinner /> : reports?.length === 0 ? (
            <div className="text-center py-12"><ClipboardText size={36} weight="duotone" className="mx-auto text-[#EA580C] mb-3" /><p className="text-[#71717A] text-sm">No reports yet. Send photos + a voice note to generate the first one.</p></div>
          ) : (
            <div className="grid sm:grid-cols-2 gap-3" data-testid="report-library">
              {reports?.map((r) => (
                <div key={r.id} data-testid={`report-card-${r.id}`} className="border border-[#E4E4E7] p-4 hover:border-[#EA580C] transition-colors duration-200 flex flex-col">
                  <div className="flex items-start justify-between gap-2">
                    <Badge tone="accent">{r.report_date}</Badge>
                    <button data-testid={`delete-report-${r.id}`} onClick={() => del.mutate(r.id)} className="text-[#71717A] hover:text-[#DC2626] transition-colors duration-200"><Trash size={15} weight="bold" /></button>
                  </div>
                  <button onClick={() => setActive(r)} className="text-left mt-2">
                    <h3 className="font-display font-bold leading-snug">{r.content?.title || "Daily Report"}</h3>
                    <p className="text-xs text-[#71717A] mt-1 line-clamp-2">{r.content?.summary}</p>
                    <div className="flex items-center gap-2 mt-2 text-xs text-[#71717A]">
                      {r.project_name && <Badge>{r.project_name}</Badge>}
                      {r.photos?.length > 0 && <span className="flex items-center gap-1"><Camera size={13} weight="bold" /> {r.photos.length}</span>}
                      {r.location && <span className="flex items-center gap-1 truncate"><MapPin size={13} weight="bold" /> {r.location}</span>}
                    </div>
                    <p className="text-xs font-semibold text-[#EA580C] mt-2">Open report →</p>
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {active && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setActive(null)}>
          <div className="absolute inset-0 bg-black/40" />
          <div className="relative bg-white border-2 border-[#09090B] max-w-2xl w-full max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()} data-testid="report-detail">
            <div className="p-6 border-b border-[#E4E4E7] sticky top-0 bg-white">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="accent">{active.report_date}</Badge>
                {active.project_name && <Badge>{active.project_name}</Badge>}
                {active.location && <Badge tone="neutral">{active.location}</Badge>}
                {active.content?.weather && <Badge tone="neutral">{active.content.weather}</Badge>}
              </div>
              <h2 className="font-display font-black text-2xl tracking-tight mt-2">{active.content?.title || "Daily Report"}</h2>
              {active.content?.summary && <p className="text-sm text-[#71717A] mt-2">{active.content.summary}</p>}
            </div>
            <div className="p-6 space-y-6 text-sm">
              {active.photos?.length > 0 && (
                <Section icon={Camera} title="Site Photos">
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {active.photos.map((f) => (
                      <a key={f.id} href={`${API}/files/${f.path}`} target="_blank" rel="noreferrer">
                        <img src={`${API}/files/${f.path}`} alt={f.filename} className="w-full h-28 object-cover border border-[#E4E4E7] hover:border-[#EA580C]" />
                      </a>
                    ))}
                  </div>
                </Section>
              )}
              {active.content?.work_completed?.length > 0 && (
                <Section icon={ListChecks} title="Work Completed">
                  <ol className="space-y-2">{active.content.work_completed.map((s, i) => (
                    <li key={i} className="flex gap-3"><span className="font-mono font-bold text-[#EA580C] shrink-0">{String(i + 1).padStart(2, "0")}</span><span className="text-[#3f3f46]">{s}</span></li>
                  ))}</ol>
                </Section>
              )}
              {active.content?.manpower && <Section icon={UsersThree} title="Manpower"><p className="text-[#3f3f46]">{active.content.manpower}</p></Section>}
              {active.content?.materials_used?.length > 0 && <Section icon={Wrench} title="Materials & Equipment"><BulletList items={active.content.materials_used} /></Section>}
              {active.content?.issues_delays?.length > 0 && <Section icon={ShieldWarning} title="Issues & Delays"><BulletList items={active.content.issues_delays} /></Section>}
              {active.content?.safety_observations?.length > 0 && <Section icon={CheckCircle} title="Safety Observations"><BulletList items={active.content.safety_observations} /></Section>}
              {active.content?.next_steps?.length > 0 && <Section icon={ArrowBendUpRight} title="Next Steps"><BulletList items={active.content.next_steps} /></Section>}
              {active.notes_text && <Section icon={ClipboardText} title="Original Field Notes"><p className="text-[#71717A] italic">"{active.notes_text}"</p></Section>}
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
const BulletList = ({ items }) => <ul className="list-disc pl-5 space-y-1 text-[#3f3f46]">{items.map((it, i) => <li key={i}>{it}</li>)}</ul>;
