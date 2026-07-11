import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { API, getToken } from "@/lib/api";
import { PageHeader, Badge, Spinner } from "@/components/ui-bits";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Plus, Trash, UsersThree, ShieldCheck, Check, Buildings, PencilSimple, MapPin, User, FileArrowDown, ChartLine } from "@phosphor-icons/react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { formatMoney, getCountry } from "@/lib/country";
import CostTrendsPanel from "@/components/CostTrendsPanel";

const ONBOARDING = [
  { key: "id_collected", label: "ID / Aadhaar collected" },
  { key: "contract_signed", label: "Work agreement signed" },
  { key: "induction_done", label: "Safety induction completed" },
  { key: "site_access", label: "Site access approved" },
  { key: "insurance", label: "Insurance / WC cover" },
  { key: "bank_details", label: "Bank / UPI details" },
];

const EMPTY_PROJECT = { name: "", location: "", client: "", client_phone: "", budget: "" };

export default function Workforce() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const country = getCountry(user);
  const RATE_TYPES = country.rateTypes;
  const fmt = (n) => formatMoney(n, user);
  const [open, setOpen] = useState(false);
  const [projOpen, setProjOpen] = useState(false);
  const [editingProject, setEditingProject] = useState(null); // holds project object when editing, null when creating
  const [form, setForm] = useState({ name: "", role: "Labour", phone: "", rate: "", rate_type: "daily", project_id: "", subcontractor: "" });
  const [proj, setProj] = useState(EMPTY_PROJECT);

  const { data: workers, isLoading } = useQuery({ queryKey: ["workers"], queryFn: async () => (await api.get("/workers")).data });
  const { data: projects } = useQuery({ queryKey: ["projects"], queryFn: async () => (await api.get("/projects")).data });

  const pname = (id) => projects?.find((p) => p.id === id)?.name || "—";
  const workersInProject = (pid) => (workers || []).filter((w) => w.project_id === pid).length;

  const addWorker = useMutation({
    mutationFn: async () => (await api.post("/workers", { ...form, rate: parseFloat(form.rate) || 0, project_id: form.project_id || null })).data,
    onSuccess: () => { toast.success("Worker added"); qc.invalidateQueries({ queryKey: ["workers"] }); setOpen(false); setForm({ name: "", role: "Labour", phone: "", rate: "", rate_type: "daily", project_id: "", subcontractor: "" }); },
  });
  const saveProject = useMutation({
    mutationFn: async () => {
      const payload = { ...proj, budget: parseFloat(proj.budget) || 0 };
      if (editingProject) return (await api.put(`/projects/${editingProject.id}`, payload)).data;
      return (await api.post("/projects", payload)).data;
    },
    onSuccess: () => {
      toast.success(editingProject ? "Project updated" : "Project added");
      qc.invalidateQueries({ queryKey: ["projects"] });
      qc.invalidateQueries({ queryKey: ["workers"] });
      setProjOpen(false); setEditingProject(null); setProj(EMPTY_PROJECT);
    },
    onError: () => toast.error("Save failed"),
  });
  const delProject = useMutation({
    mutationFn: async (id) => (await api.delete(`/projects/${id}`)).data,
    onSuccess: () => { toast.success("Project deleted"); qc.invalidateQueries({ queryKey: ["projects"] }); qc.invalidateQueries({ queryKey: ["workers"] }); },
    onError: () => toast.error("Delete failed"),
  });
  const openNewProject = () => { setEditingProject(null); setProj(EMPTY_PROJECT); setProjOpen(true); };
  const openEditProject = (p) => {
    setEditingProject(p);
    setProj({ name: p.name || "", location: p.location || "", client: p.client || "", client_phone: p.client_phone || "", budget: p.budget || "" });
    setProjOpen(true);
  };
  const del = useMutation({
    mutationFn: async (id) => (await api.delete(`/workers/${id}`)).data,
    onSuccess: () => { toast.success("Removed"); qc.invalidateQueries({ queryKey: ["workers"] }); },
  });

  const [obWorker, setObWorker] = useState(null);
  const [obState, setObState] = useState({});
  const [costsProject, setCostsProject] = useState(null);
  const openOnboarding = (w) => {
    setObWorker(w);
    setObState({ ...ONBOARDING.reduce((a, i) => ({ ...a, [i.key]: false }), {}), ...(w.onboarding || {}) });
  };
  const saveOnboarding = useMutation({
    mutationFn: async () => (await api.post(`/workers/${obWorker.id}/onboarding`, { onboarding: obState })).data,
    onSuccess: () => { toast.success("Onboarding updated"); qc.invalidateQueries({ queryKey: ["workers"] }); qc.invalidateQueries({ queryKey: ["dashboard"] }); setObWorker(null); },
  });
  const obCount = (w) => ONBOARDING.filter((i) => w.onboarding?.[i.key]).length;

  if (isLoading) return <Spinner />;

  const inputCls = "w-full border-2 border-[#E4E4E7] focus:border-[#EA580C] outline-none px-3 py-2.5 text-sm transition-colors duration-200 bg-white";

  return (
    <div className="p-5 sm:p-8">
      <PageHeader
        overline="Workforce Intelligence"
        title="Workforce"
        desc="Workers, crews, subcontractors and labour suppliers — assignable across projects with any pay structure."
        action={
          <div className="flex gap-2">
            <Dialog open={projOpen} onOpenChange={(v) => { setProjOpen(v); if (!v) { setEditingProject(null); setProj(EMPTY_PROJECT); } }}>
              <DialogTrigger asChild>
                <button data-testid="add-project-button" onClick={openNewProject} className="border-2 border-[#09090B] px-4 py-2.5 text-sm font-semibold hover:bg-[#09090B] hover:text-white transition-colors duration-200">New Project</button>
              </DialogTrigger>
              <DialogContent className="rounded-none border-2 border-[#09090B]">
                <DialogHeader><DialogTitle className="font-display">{editingProject ? "Edit Project" : "New Project"}</DialogTitle><DialogDescription>{editingProject ? "Update project details." : "Create a project to assign workers and track spend."}</DialogDescription></DialogHeader>
                <div className="space-y-3">
                  <input data-testid="project-name-input" className={inputCls} placeholder="Project name" value={proj.name} onChange={(e) => setProj({ ...proj, name: e.target.value })} />
                  <input className={inputCls} placeholder="Location" value={proj.location} onChange={(e) => setProj({ ...proj, location: e.target.value })} />
                  <input className={inputCls} placeholder="Client name" value={proj.client} onChange={(e) => setProj({ ...proj, client: e.target.value })} />
                  <input data-testid="project-client-phone-input" className={inputCls} placeholder="Client WhatsApp (+91…)" value={proj.client_phone} onChange={(e) => setProj({ ...proj, client_phone: e.target.value })} />
                  <input className={inputCls} placeholder={`Budget (${country.symbol})`} type="number" value={proj.budget} onChange={(e) => setProj({ ...proj, budget: e.target.value })} />
                </div>
                <DialogFooter>
                  <button data-testid="save-project-button" disabled={!proj.name || saveProject.isPending} onClick={() => saveProject.mutate()} className="bg-[#EA580C] text-white px-5 py-2.5 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200 disabled:opacity-50">
                    {saveProject.isPending ? "Saving…" : (editingProject ? "Save" : "Create")}
                  </button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger asChild>
                <button data-testid="add-worker-button" className="flex items-center gap-2 bg-[#EA580C] text-white px-4 py-2.5 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200"><Plus size={16} weight="bold" /> Add Worker</button>
              </DialogTrigger>
              <DialogContent className="rounded-none border-2 border-[#09090B]">
                <DialogHeader><DialogTitle className="font-display">Add Worker</DialogTitle><DialogDescription>Add a worker with any pay structure and assign to a project.</DialogDescription></DialogHeader>
                <div className="space-y-3">
                  <input data-testid="worker-name-input" className={inputCls} placeholder="Full name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
                  <div className="grid grid-cols-2 gap-3">
                    <input className={inputCls} placeholder="Role / trade" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} />
                    <input className={inputCls} placeholder="Phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <input data-testid="worker-rate-input" className={inputCls} type="number" placeholder={`Rate (${country.symbol})`} value={form.rate} onChange={(e) => setForm({ ...form, rate: e.target.value })} />
                    <select data-testid="worker-ratetype-select" className={inputCls} value={form.rate_type} onChange={(e) => setForm({ ...form, rate_type: e.target.value })}>
                      {RATE_TYPES.map((r) => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </div>
                  <select data-testid="worker-project-select" className={inputCls} value={form.project_id} onChange={(e) => setForm({ ...form, project_id: e.target.value })}>
                    <option value="">— Assign project —</option>
                    {projects?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                  <input className={inputCls} placeholder="Subcontractor / labour supplier (optional)" value={form.subcontractor} onChange={(e) => setForm({ ...form, subcontractor: e.target.value })} />
                </div>
                <DialogFooter>
                  <button data-testid="save-worker-button" disabled={!form.name || addWorker.isPending} onClick={() => addWorker.mutate()} className="bg-[#EA580C] text-white px-5 py-2.5 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200 disabled:opacity-50">{addWorker.isPending ? "Saving…" : "Add Worker"}</button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        }
      />

      {/* Projects section */}
      {projects && projects.length > 0 && (
        <div className="mb-8" data-testid="projects-section">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Buildings size={18} weight="duotone" className="text-[#EA580C]" />
              <h2 className="font-display font-bold text-lg">Projects</h2>
              <span className="text-xs text-[#71717A]">({projects.length})</span>
            </div>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-px bg-[#E4E4E7] border border-[#E4E4E7]">
            {projects.map((p) => (
              <div key={p.id} data-testid={`project-card-${p.id}`} className="bg-white p-5 flex flex-col gap-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <h3 className="font-display font-bold text-base leading-tight truncate" title={p.name}>{p.name}</h3>
                    {p.location && <p className="text-xs text-[#71717A] flex items-center gap-1 mt-0.5"><MapPin size={12} weight="bold" />{p.location}</p>}
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <button data-testid={`edit-project-${p.id}`} onClick={() => openEditProject(p)} className="p-1.5 text-[#71717A] hover:text-[#EA580C] transition-colors duration-200" title="Edit project"><PencilSimple size={15} weight="bold" /></button>
                    <button
                      data-testid={`delete-project-${p.id}`}
                      onClick={() => {
                        const wc = workersInProject(p.id);
                        const msg = wc > 0
                          ? `Delete "${p.name}"? ${wc} worker(s) will be unassigned but not deleted.`
                          : `Delete "${p.name}"?`;
                        if (window.confirm(msg)) delProject.mutate(p.id);
                      }}
                      className="p-1.5 text-[#71717A] hover:text-[#DC2626] transition-colors duration-200"
                      title="Delete project"
                    >
                      <Trash size={15} weight="bold" />
                    </button>
                  </div>
                </div>
                {p.client && <p className="text-xs text-[#3f3f46] flex items-center gap-1"><User size={12} weight="bold" />{p.client}</p>}
                <div className="flex items-center justify-between mt-1 pt-2 border-t border-[#F4F4F5]">
                  <Badge tone="accent">{workersInProject(p.id)} worker{workersInProject(p.id) === 1 ? "" : "s"}</Badge>
                  {p.budget > 0 && <span className="text-xs font-mono text-[#71717A]">Budget: {fmt(p.budget)}</span>}
                </div>
                <button
                  data-testid={`view-costs-${p.id}`}
                  onClick={() => setCostsProject(p)}
                  className="mt-2 flex items-center justify-center gap-1.5 border-2 border-[#E4E4E7] hover:border-[#EA580C] hover:text-[#EA580C] px-3 py-1.5 text-xs font-semibold text-[#3f3f46] transition-colors duration-200"
                >
                  <ChartLine size={13} weight="bold" /> View cost trends
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Per-project cost trends dialog */}
      <Dialog open={!!costsProject} onOpenChange={(v) => !v && setCostsProject(null)}>
        <DialogContent className="rounded-none border-2 border-[#09090B] max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-display flex items-center gap-2">
              <ChartLine size={18} weight="duotone" className="text-[#EA580C]" />
              {costsProject?.name} — Cost trends
            </DialogTitle>
            <DialogDescription>
              Month-over-month cost breakdown for this project, with budget overlay when a budget is set.
            </DialogDescription>
          </DialogHeader>
          {costsProject && <CostTrendsPanel projectId={costsProject.id} dense />}
        </DialogContent>
      </Dialog>

      {workers?.length === 0 ? (
        <div className="border border-[#E4E4E7] p-12 text-center">
          <UsersThree size={36} weight="duotone" className="mx-auto text-[#EA580C] mb-3" />
          <p className="text-[#71717A] text-sm">No workers yet. Add your first worker to start tracking attendance and wages.</p>
        </div>
      ) : (
        <div className="border border-[#E4E4E7] overflow-x-auto" data-testid="workers-table">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#E4E4E7] text-left">
                {["Name", "Trade", "Rate", "Project", "Onboarding", ""].map((h) => (
                  <th key={h} className="overline px-4 py-3 font-bold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {workers?.map((w) => (
                <tr key={w.id} data-testid={`worker-row-${w.id}`} className="border-b border-[#E4E4E7] hover:bg-[#FFF7ED] transition-colors duration-200">
                  <td className="px-4 py-3 font-semibold">{w.name}</td>
                  <td className="px-4 py-3 text-[#71717A]">{w.role}</td>
                  <td className="px-4 py-3 font-mono">{fmt(w.rate)} <span className="text-[#71717A]">/{w.rate_type}</span></td>
                  <td className="px-4 py-3"><Badge tone="accent">{pname(w.project_id)}</Badge></td>
                  <td className="px-4 py-3">
                    <button
                      data-testid={`onboarding-btn-${w.id}`}
                      onClick={() => openOnboarding(w)}
                      className={`inline-flex items-center gap-1.5 px-2 py-1 text-xs font-bold border transition-colors duration-200 ${
                        obCount(w) === ONBOARDING.length
                          ? "bg-[#F0FDF4] text-[#16A34A] border-[#16A34A]/30"
                          : "bg-[#FEF2F2] text-[#DC2626] border-[#DC2626]/30 hover:bg-[#DC2626] hover:text-white"
                      }`}
                    >
                      <ShieldCheck size={13} weight="bold" /> {obCount(w)}/{ONBOARDING.length}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button data-testid={`delete-worker-${w.id}`} onClick={() => del.mutate(w.id)} className="text-[#71717A] hover:text-[#DC2626] transition-colors duration-200"><Trash size={16} weight="bold" /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Dialog open={!!obWorker} onOpenChange={(v) => !v && setObWorker(null)}>
        <DialogContent className="rounded-none border-2 border-[#09090B]">
          <DialogHeader>
            <DialogTitle className="font-display flex items-center gap-2"><ShieldCheck size={18} weight="fill" className="text-[#EA580C]" /> Onboarding — {obWorker?.name}</DialogTitle>
            <DialogDescription>Track documents & site readiness for this worker.</DialogDescription>
          </DialogHeader>
          <div className="space-y-2" data-testid="onboarding-checklist">
            {ONBOARDING.map((item) => {
              const on = !!obState[item.key];
              return (
                <button
                  key={item.key}
                  data-testid={`onboarding-item-${item.key}`}
                  onClick={() => setObState((s) => ({ ...s, [item.key]: !s[item.key] }))}
                  className={`w-full flex items-center gap-3 border-2 px-3 py-2.5 text-sm font-semibold text-left transition-colors duration-200 ${
                    on ? "border-[#16A34A] bg-[#F0FDF4] text-[#16A34A]" : "border-[#E4E4E7] hover:border-[#EA580C]"
                  }`}
                >
                  <span className={`w-5 h-5 flex items-center justify-center border-2 ${on ? "bg-[#16A34A] border-[#16A34A] text-white" : "border-[#a1a1aa]"}`}>
                    {on && <Check size={13} weight="bold" />}
                  </span>
                  {item.label}
                </button>
              );
            })}
          </div>
          {(obWorker?.documents?.length > 0) && (
            <div className="pt-3 border-t border-[#E4E4E7]" data-testid="worker-documents">
              <p className="overline mb-2">Files (via Telegram)</p>
              <div className="space-y-1.5 max-h-40 overflow-y-auto">
                {obWorker.documents.map((d) => (
                  <a
                    key={d.id}
                    data-testid={`worker-doc-${d.id}`}
                    href={`${API}/files/${d.path}?auth=${getToken()}`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-2 border border-[#E4E4E7] px-3 py-2 text-xs font-semibold hover:border-[#EA580C] hover:bg-[#FFF7ED] transition-colors duration-200"
                  >
                    <FileArrowDown size={14} weight="bold" className="text-[#EA580C] shrink-0" />
                    <span className="truncate flex-1">{d.filename}</span>
                    <span className="text-[#71717A] font-normal shrink-0">{(d.uploaded_at || "").slice(0, 10)}</span>
                  </a>
                ))}
              </div>
            </div>
          )}
          <DialogFooter>
            <button data-testid="save-onboarding-button" disabled={saveOnboarding.isPending} onClick={() => saveOnboarding.mutate()} className="bg-[#EA580C] text-white px-5 py-2.5 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200 disabled:opacity-50">{saveOnboarding.isPending ? "Saving…" : "Save"}</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
