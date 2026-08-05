import React, { useState, useCallback, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { PageHeader, Badge, Spinner } from "@/components/ui-bits";
import { useAuth } from "@/context/AuthContext";
import { formatMoney, getCountry } from "@/lib/country";
import {
  Calculator, Plus, Trash, ArrowLeft, PencilSimple, Copy,
  Sparkle, PaperPlaneTilt, MagnifyingGlass, CaretDown, CaretUp,
  X, Check, Lightning, Package, Users, Wrench, CurrencyInr,
  Printer, ShareNetwork, ArrowsClockwise, Tag, MapPin, Clock,
  Buildings, Phone, Envelope, Percent, Receipt, Eye,
} from "@phosphor-icons/react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";

/* ---------- Constants ---------- */
const WORK_TYPES = [
  { v: "interior", l: "Interior" },
  { v: "civil", l: "Civil" },
  { v: "electrical", l: "Electrical" },
  { v: "plumbing", l: "Plumbing" },
  { v: "painting", l: "Painting" },
  { v: "flooring", l: "Flooring" },
  { v: "general", l: "General" },
];

const CATEGORIES = [
  { v: "material", l: "Material", icon: Package, tone: "accent" },
  { v: "labor", l: "Labour", icon: Users, tone: "success" },
  { v: "equipment", l: "Equipment", icon: Wrench, tone: "warning" },
  { v: "overhead", l: "Overhead", icon: Buildings, tone: "neutral" },
  { v: "other", l: "Other", icon: Tag, tone: "neutral" },
];

const GST_OPTIONS = [
  { v: 0, l: "No GST" },
  { v: 5, l: "5% GST" },
  { v: 12, l: "12% GST" },
  { v: 18, l: "18% GST" },
];

const STATUS_TONE = {
  draft: "neutral",
  sent: "accent",
  accepted: "success",
  revised: "warning",
};

const AREA_UNITS = [
  { v: "sqft", l: "sq.ft" },
  { v: "sqm", l: "sq.m" },
];

const inputCls = "w-full border-2 border-[#E4E4E7] focus:border-[#EA580C] outline-none px-3 py-2.5 text-sm transition-colors duration-200 bg-white";
const btnPrimary = "flex items-center gap-2 bg-[#09090B] text-white px-4 py-2.5 text-sm font-semibold hover:bg-[#EA580C] transition-colors duration-200";
const btnSecondary = "flex items-center gap-2 border-2 border-[#E4E4E7] px-4 py-2.5 text-sm font-semibold hover:border-[#EA580C] hover:text-[#EA580C] transition-colors duration-200";

/* ================================================================
   MAIN COMPONENT
   ================================================================ */
export default function Estimates() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const fmt = (n) => formatMoney(n, user);
  const country = getCountry(user);
  const [view, setView] = useState("list"); // list | builder | quotation
  const [selectedId, setSelectedId] = useState(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [materialOpen, setMaterialOpen] = useState(false);
  const [seedOpen, setSeedOpen] = useState(false);
  const [search, setSearch] = useState("");

  /* ---- DATA ---- */
  const { data: estimatesData, isLoading } = useQuery({
    queryKey: ["estimates", search],
    queryFn: async () => (await api.get("/estimates", { params: { q: search, limit: 200 } })).data,
  });
  const estimates = estimatesData?.items || [];

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: async () => (await api.get("/projects")).data,
  });

  const pname = (id) => projects?.find((p) => p.id === id)?.name || "";

  const deleteEst = useMutation({
    mutationFn: async (id) => (await api.delete(`/estimates/${id}`)).data,
    onSuccess: () => { toast.success("Estimate deleted"); qc.invalidateQueries({ queryKey: ["estimates"] }); },
  });

  const duplicateEst = useMutation({
    mutationFn: async (id) => (await api.post(`/estimates/${id}/duplicate`)).data,
    onSuccess: (d) => {
      toast.success(`Revision v${d.version} created`);
      qc.invalidateQueries({ queryKey: ["estimates"] });
      setSelectedId(d.id);
      setView("builder");
    },
  });

  /* ---- NAVIGATION ---- */
  const openBuilder = (id) => { setSelectedId(id); setView("builder"); };
  const openQuotation = (id) => { setSelectedId(id); setView("quotation"); };
  const backToList = () => { setSelectedId(null); setView("list"); };

  /* ================================================================
     LIST VIEW
     ================================================================ */
  if (view === "list") {
    if (isLoading) return <Spinner />;
    return (
      <div className="p-5 sm:p-8">
        <PageHeader
          overline="Estimator"
          title="Project Estimates"
          desc="Create detailed cost estimates, optimize with AI, and share professional quotations with clients."
          action={
            <button data-testid="create-estimate-btn" onClick={() => setCreateOpen(true)} className={btnPrimary}>
              <Plus size={16} weight="bold" /> New Estimate
            </button>
          }
        />

        {/* Search & Stats */}
        <div className="flex flex-col sm:flex-row gap-3 mb-6">
          <div className="relative flex-1">
            <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#71717A]" />
            <input
              data-testid="estimate-search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search estimates…"
              className={`${inputCls} pl-9`}
            />
          </div>
          <div className="flex gap-3">
            <button data-testid="material-prices-btn" onClick={() => setMaterialOpen(true)} className={btnSecondary}>
              <Package size={16} weight="duotone" /> Material Prices
            </button>
          </div>
        </div>

        {/* Stats Row */}
        {estimates.length > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-4 border-t border-l border-[#E4E4E7] mb-6">
            <StatBox label="Total Estimates" value={estimates.length} />
            <StatBox label="Draft" value={estimates.filter((e) => e.status === "draft").length} />
            <StatBox label="Sent" value={estimates.filter((e) => e.status === "sent").length} accent />
            <StatBox label="Accepted" value={estimates.filter((e) => e.status === "accepted").length} />
          </div>
        )}

        {/* Estimate Cards */}
        {estimates.length === 0 ? (
          <div className="border-2 border-dashed border-[#E4E4E7] p-12 text-center">
            <Calculator size={48} weight="duotone" className="mx-auto text-[#71717A] mb-4" />
            <p className="text-lg font-semibold text-[#09090B] mb-2">No estimates yet</p>
            <p className="text-sm text-[#71717A] mb-6">Create your first project estimate to get started.</p>
            <button onClick={() => setCreateOpen(true)} className={btnPrimary + " mx-auto"}>
              <Plus size={16} weight="bold" /> Create Estimate
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {estimates.map((est) => (
              <div
                key={est.id}
                data-testid={`estimate-card-${est.id}`}
                className="border-2 border-[#E4E4E7] hover:border-[#EA580C] transition-colors duration-200 p-4 sm:p-5 cursor-pointer"
                onClick={() => openBuilder(est.id)}
              >
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-semibold text-sm truncate">{est.title || "Untitled"}</h3>
                      <Badge tone={STATUS_TONE[est.status] || "neutral"}>{est.status}</Badge>
                      {est.version > 1 && <Badge tone="warning">v{est.version}</Badge>}
                    </div>
                    <p className="text-xs text-[#71717A]">
                      {est.client_name && <span>{est.client_name} · </span>}
                      {pname(est.project_id) && <span>{pname(est.project_id)} · </span>}
                      {est.work_type}
                      {est.area_sqft ? ` · ${est.area_sqft} ${est.area_unit}` : ""}
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="font-display font-black text-xl tracking-tight text-[#09090B]">{fmt(est.grand_total)}</p>
                    <p className="text-xs text-[#71717A]">{est.line_items?.length || 0} items</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 mt-3">
                  <button
                    data-testid={`view-quotation-${est.id}`}
                    onClick={(e) => { e.stopPropagation(); openQuotation(est.id); }}
                    className="text-xs font-semibold text-[#71717A] hover:text-[#EA580C] flex items-center gap-1 transition-colors duration-200"
                  >
                    <Eye size={14} /> Quotation
                  </button>
                  <button
                    data-testid={`duplicate-${est.id}`}
                    onClick={(e) => { e.stopPropagation(); duplicateEst.mutate(est.id); }}
                    className="text-xs font-semibold text-[#71717A] hover:text-[#EA580C] flex items-center gap-1 transition-colors duration-200"
                  >
                    <Copy size={14} /> Revision
                  </button>
                  <button
                    data-testid={`delete-estimate-${est.id}`}
                    onClick={(e) => { e.stopPropagation(); if (window.confirm("Delete this estimate?")) deleteEst.mutate(est.id); }}
                    className="text-xs font-semibold text-[#71717A] hover:text-[#DC2626] flex items-center gap-1 transition-colors duration-200 ml-auto"
                  >
                    <Trash size={14} /> Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Create Dialog */}
        <CreateEstimateDialog
          open={createOpen}
          onClose={() => setCreateOpen(false)}
          projects={projects || []}
          onCreated={(est) => { setCreateOpen(false); openBuilder(est.id); }}
        />

        {/* Material Prices Dialog */}
        <MaterialPricesDialog
          open={materialOpen}
          onClose={() => setMaterialOpen(false)}
          user={user}
        />
      </div>
    );
  }

  /* ================================================================
     BUILDER VIEW
     ================================================================ */
  if (view === "builder" && selectedId) {
    return (
      <EstimateBuilder
        estimateId={selectedId}
        user={user}
        projects={projects || []}
        onBack={backToList}
        onViewQuotation={() => openQuotation(selectedId)}
        fmt={fmt}
        country={country}
      />
    );
  }

  /* ================================================================
     QUOTATION VIEW
     ================================================================ */
  if (view === "quotation" && selectedId) {
    return (
      <QuotationView
        estimateId={selectedId}
        user={user}
        onBack={() => openBuilder(selectedId)}
        onBackToList={backToList}
        fmt={fmt}
      />
    );
  }

  return <Spinner />;
}


/* ================================================================
   STAT BOX
   ================================================================ */
function StatBox({ label, value, accent }) {
  return (
    <div className="border-r border-b border-[#E4E4E7] p-4 hover:bg-[#FAFAFA] transition-colors duration-200">
      <p className="overline mb-1">{label}</p>
      <p className={`font-display font-black text-2xl tracking-tight ${accent ? "text-[#EA580C]" : "text-[#09090B]"}`}>{value}</p>
    </div>
  );
}


/* ================================================================
   CREATE ESTIMATE DIALOG
   ================================================================ */
function CreateEstimateDialog({ open, onClose, projects, onCreated }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    title: "", client_name: "", client_phone: "", work_type: "interior",
    area_sqft: "", area_unit: "sqft", project_id: "",
  });
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const create = useMutation({
    mutationFn: async () => {
      const payload = { ...form, area_sqft: parseFloat(form.area_sqft) || 0, line_items: [] };
      return (await api.post("/estimates", payload)).data;
    },
    onSuccess: (d) => {
      toast.success("Estimate created");
      qc.invalidateQueries({ queryKey: ["estimates"] });
      onCreated(d);
      setForm({ title: "", client_name: "", client_phone: "", work_type: "interior", area_sqft: "", area_unit: "sqft", project_id: "" });
    },
    onError: () => toast.error("Failed to create estimate"),
  });

  if (!open) return null;
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>New Estimate</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <input data-testid="est-title" value={form.title} onChange={(e) => set("title", e.target.value)} placeholder="Estimate title (e.g. 2BHK Interior, Whitefield)" className={inputCls} />
          <div className="grid grid-cols-2 gap-3">
            <input data-testid="est-client-name" value={form.client_name} onChange={(e) => set("client_name", e.target.value)} placeholder="Client name" className={inputCls} />
            <input data-testid="est-client-phone" value={form.client_phone} onChange={(e) => set("client_phone", e.target.value)} placeholder="Client phone" className={inputCls} />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <select data-testid="est-work-type" value={form.work_type} onChange={(e) => set("work_type", e.target.value)} className={inputCls}>
              {WORK_TYPES.map((w) => <option key={w.v} value={w.v}>{w.l}</option>)}
            </select>
            <input data-testid="est-area" value={form.area_sqft} onChange={(e) => set("area_sqft", e.target.value)} placeholder="Area" className={inputCls} type="number" />
            <select data-testid="est-area-unit" value={form.area_unit} onChange={(e) => set("area_unit", e.target.value)} className={inputCls}>
              {AREA_UNITS.map((u) => <option key={u.v} value={u.v}>{u.l}</option>)}
            </select>
          </div>
          {projects.length > 0 && (
            <select data-testid="est-project" value={form.project_id} onChange={(e) => set("project_id", e.target.value)} className={inputCls}>
              <option value="">Link to project (optional)</option>
              {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          )}
        </div>
        <DialogFooter>
          <button data-testid="est-create-submit" onClick={() => create.mutate()} disabled={!form.title.trim()} className={btnPrimary + " disabled:opacity-40"}>
            <Plus size={16} weight="bold" /> Create
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}


/* ================================================================
   ESTIMATE BUILDER (core workspace)
   ================================================================ */
function EstimateBuilder({ estimateId, user, projects, onBack, onViewQuotation, fmt, country }) {
  const qc = useQueryClient();
  const [dirty, setDirty] = useState(false);
  const [addItemOpen, setAddItemOpen] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [newItem, setNewItem] = useState({ category: "material", name: "", unit: "sqft", quantity: "", unit_price: "", notes: "" });

  const { data: est, isLoading } = useQuery({
    queryKey: ["estimate", estimateId],
    queryFn: async () => (await api.get(`/estimates/${estimateId}`)).data,
  });

  const { data: materialPrices } = useQuery({
    queryKey: ["material-prices"],
    queryFn: async () => (await api.get("/material-prices")).data,
  });

  const [localItems, setLocalItems] = useState(null);
  const [localMeta, setLocalMeta] = useState({});

  // Sync from server on first load
  React.useEffect(() => {
    if (est && localItems === null) {
      setLocalItems(est.line_items || []);
      setLocalMeta({
        title: est.title || "",
        client_name: est.client_name || "",
        client_phone: est.client_phone || "",
        client_email: est.client_email || "",
        work_type: est.work_type || "general",
        area_sqft: est.area_sqft || 0,
        area_unit: est.area_unit || "sqft",
        project_id: est.project_id || "",
        gross_margin_percent: est.gross_margin_percent || 0,
        gst_percent: est.gst_percent || 0,
        discount_percent: est.discount_percent || 0,
        estimated_days: est.estimated_days || 0,
        valid_until: est.valid_until || "",
        terms: est.terms || "",
        notes: est.notes || "",
      });
    }
  }, [est]);

  const items = localItems || est?.line_items || [];
  const meta = useMemo(() => ({
    ...(est || {}),
    ...localMeta,
  }), [est, localMeta]);

  // Live calculation
  const calcs = useMemo(() => {
    let material = 0, labor = 0, equipment = 0, overhead = 0, other = 0;
    items.forEach((li) => {
      const t = (li.quantity || 0) * (li.unit_price || 0);
      if (li.category === "material") material += t;
      else if (li.category === "labor") labor += t;
      else if (li.category === "equipment") equipment += t;
      else if (li.category === "overhead") overhead += t;
      else other += t;
    });
    const subtotal = material + labor + equipment + overhead + other;
    const marginAmt = subtotal * ((meta.gross_margin_percent || 0) / 100);
    const afterMargin = subtotal + marginAmt;
    const discountAmt = afterMargin * ((meta.discount_percent || 0) / 100);
    const afterDiscount = afterMargin - discountAmt;
    const gstAmt = afterDiscount * ((meta.gst_percent || 0) / 100);
    const grand = afterDiscount + gstAmt;
    return {
      material: Math.round(material), labor: Math.round(labor),
      equipment: Math.round(equipment), overhead: Math.round(overhead),
      other: Math.round(other), subtotal: Math.round(subtotal),
      marginAmt: Math.round(marginAmt), discountAmt: Math.round(discountAmt),
      gstAmt: Math.round(gstAmt), grand: Math.round(grand),
    };
  }, [items, meta.gross_margin_percent, meta.gst_percent, meta.discount_percent]);

  const setMeta = (k, v) => { setLocalMeta((m) => ({ ...m, [k]: v })); setDirty(true); };

  const addItem = () => {
    const li = {
      id: `li_${Date.now().toString(36)}`,
      category: newItem.category,
      name: newItem.name,
      unit: newItem.unit,
      quantity: parseFloat(newItem.quantity) || 0,
      unit_price: parseFloat(newItem.unit_price) || 0,
      total: (parseFloat(newItem.quantity) || 0) * (parseFloat(newItem.unit_price) || 0),
      notes: newItem.notes,
    };
    setLocalItems([...items, li]);
    setDirty(true);
    setNewItem({ category: "material", name: "", unit: "sqft", quantity: "", unit_price: "", notes: "" });
    setAddItemOpen(false);
    toast.success("Item added");
  };

  const removeItem = (id) => {
    setLocalItems(items.filter((li) => li.id !== id));
    setDirty(true);
  };

  const updateItem = (id, key, val) => {
    setLocalItems(items.map((li) => {
      if (li.id !== id) return li;
      const updated = { ...li, [key]: val };
      updated.total = (updated.quantity || 0) * (updated.unit_price || 0);
      return updated;
    }));
    setDirty(true);
  };

  // Fill price from material DB
  const fillFromMaterial = (matName) => {
    const prices = materialPrices?.items || [];
    const found = prices.find((p) => p.name.toLowerCase() === matName.toLowerCase());
    if (found) {
      setNewItem((n) => ({ ...n, name: found.name, unit: found.unit, unit_price: String(found.price), category: "material" }));
    }
  };

  // Save
  const save = useMutation({
    mutationFn: async () => {
      const payload = {
        ...localMeta,
        line_items: items.map((li) => ({
          category: li.category, name: li.name, unit: li.unit,
          quantity: li.quantity, unit_price: li.unit_price, notes: li.notes || "",
        })),
      };
      return (await api.put(`/estimates/${estimateId}`, payload)).data;
    },
    onSuccess: () => {
      toast.success("Estimate saved");
      setDirty(false);
      qc.invalidateQueries({ queryKey: ["estimate", estimateId] });
      qc.invalidateQueries({ queryKey: ["estimates"] });
    },
    onError: () => toast.error("Failed to save"),
  });

  // AI Optimize
  const optimize = async () => {
    setOptimizing(true);
    try {
      await save.mutateAsync();
      const res = await api.post(`/estimates/${estimateId}/optimize`, { focus: "cost" });
      qc.invalidateQueries({ queryKey: ["estimate", estimateId] });
      setShowSuggestions(true);
      toast.success(`${res.data.suggestions?.length || 0} suggestions generated`);
    } catch {
      toast.error("Optimization failed");
    }
    setOptimizing(false);
  };

  if (isLoading || !est) return <Spinner />;

  const suggestions = est.ai_suggestions || [];

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button data-testid="back-to-estimates" onClick={onBack} className="flex items-center gap-2 text-sm font-semibold text-[#71717A] hover:text-[#09090B] transition-colors duration-200">
          <ArrowLeft size={16} weight="bold" /> All Estimates
        </button>
        <div className="ml-auto flex items-center gap-2">
          {dirty && (
            <button data-testid="save-estimate" onClick={() => save.mutate()} className={btnPrimary}>
              <Check size={16} weight="bold" /> Save
            </button>
          )}
          <button data-testid="ai-optimize" onClick={optimize} disabled={optimizing} className={btnSecondary + " disabled:opacity-50"}>
            <Sparkle size={16} weight="fill" className={optimizing ? "animate-spin" : ""} />
            {optimizing ? "Optimizing…" : "AI Optimize"}
          </button>
          <button data-testid="view-quotation-btn" onClick={onViewQuotation} className={btnSecondary}>
            <Eye size={16} weight="duotone" /> Quotation
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Details + Items */}
        <div className="lg:col-span-2 space-y-6">
          {/* Meta Section */}
          <div className="border-2 border-[#E4E4E7] p-5">
            <p className="overline mb-3">Estimate Details</p>
            <div className="space-y-3">
              <input data-testid="builder-title" value={meta.title} onChange={(e) => setMeta("title", e.target.value)} placeholder="Estimate title" className={inputCls + " font-semibold"} />
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <input data-testid="builder-client-name" value={meta.client_name} onChange={(e) => setMeta("client_name", e.target.value)} placeholder="Client name" className={inputCls} />
                <input data-testid="builder-client-phone" value={meta.client_phone} onChange={(e) => setMeta("client_phone", e.target.value)} placeholder="Client phone" className={inputCls} />
                <input data-testid="builder-client-email" value={meta.client_email} onChange={(e) => setMeta("client_email", e.target.value)} placeholder="Client email" className={inputCls} />
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <select data-testid="builder-work-type" value={meta.work_type} onChange={(e) => setMeta("work_type", e.target.value)} className={inputCls}>
                  {WORK_TYPES.map((w) => <option key={w.v} value={w.v}>{w.l}</option>)}
                </select>
                <input data-testid="builder-area" value={meta.area_sqft} onChange={(e) => setMeta("area_sqft", parseFloat(e.target.value) || 0)} placeholder="Area" className={inputCls} type="number" />
                <select data-testid="builder-area-unit" value={meta.area_unit} onChange={(e) => setMeta("area_unit", e.target.value)} className={inputCls}>
                  {AREA_UNITS.map((u) => <option key={u.v} value={u.v}>{u.l}</option>)}
                </select>
                <input data-testid="builder-days" value={meta.estimated_days || ""} onChange={(e) => setMeta("estimated_days", parseInt(e.target.value) || 0)} placeholder="Est. days" className={inputCls} type="number" />
              </div>
            </div>
          </div>

          {/* Line Items */}
          <div className="border-2 border-[#E4E4E7]">
            <div className="flex items-center justify-between p-4 border-b-2 border-[#E4E4E7]">
              <p className="overline">Line Items ({items.length})</p>
              <button data-testid="add-line-item" onClick={() => setAddItemOpen(true)} className="flex items-center gap-1.5 text-xs font-semibold text-[#EA580C] hover:text-[#C2410C] transition-colors duration-200">
                <Plus size={14} weight="bold" /> Add Item
              </button>
            </div>

            {items.length === 0 ? (
              <div className="p-8 text-center text-sm text-[#71717A]">
                No items yet. Click "Add Item" to start building your estimate.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[#E4E4E7] bg-[#F4F4F5]">
                      <th className="text-left px-3 py-2.5 font-semibold text-xs uppercase tracking-wider text-[#71717A]">Item</th>
                      <th className="text-left px-3 py-2.5 font-semibold text-xs uppercase tracking-wider text-[#71717A] hidden sm:table-cell">Category</th>
                      <th className="text-right px-3 py-2.5 font-semibold text-xs uppercase tracking-wider text-[#71717A]">Qty</th>
                      <th className="text-right px-3 py-2.5 font-semibold text-xs uppercase tracking-wider text-[#71717A]">Rate</th>
                      <th className="text-right px-3 py-2.5 font-semibold text-xs uppercase tracking-wider text-[#71717A]">Total</th>
                      <th className="w-10"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((li) => {
                      const catInfo = CATEGORIES.find((c) => c.v === li.category) || CATEGORIES[4];
                      return (
                        <tr key={li.id} className="border-b border-[#E4E4E7] hover:bg-[#FAFAFA] transition-colors duration-200" data-testid={`line-item-${li.id}`}>
                          <td className="px-3 py-2.5">
                            <input
                              value={li.name}
                              onChange={(e) => updateItem(li.id, "name", e.target.value)}
                              className="bg-transparent border-0 outline-none w-full font-medium text-sm"
                              placeholder="Item name"
                            />
                            <span className="text-xs text-[#71717A] sm:hidden">
                              <Badge tone={catInfo.tone}>{catInfo.l}</Badge>
                            </span>
                          </td>
                          <td className="px-3 py-2.5 hidden sm:table-cell">
                            <Badge tone={catInfo.tone}>{catInfo.l}</Badge>
                          </td>
                          <td className="px-3 py-2.5 text-right">
                            <input
                              value={li.quantity}
                              onChange={(e) => updateItem(li.id, "quantity", parseFloat(e.target.value) || 0)}
                              className="bg-transparent border-0 outline-none w-16 text-right text-sm"
                              type="number"
                            />
                            <span className="text-xs text-[#71717A] ml-1">{li.unit}</span>
                          </td>
                          <td className="px-3 py-2.5 text-right">
                            <span className="text-xs text-[#71717A] mr-0.5">{country.symbol}</span>
                            <input
                              value={li.unit_price}
                              onChange={(e) => updateItem(li.id, "unit_price", parseFloat(e.target.value) || 0)}
                              className="bg-transparent border-0 outline-none w-20 text-right text-sm"
                              type="number"
                            />
                          </td>
                          <td className="px-3 py-2.5 text-right font-semibold">
                            {fmt(Math.round((li.quantity || 0) * (li.unit_price || 0)))}
                          </td>
                          <td className="px-2 py-2.5">
                            <button onClick={() => removeItem(li.id)} className="text-[#71717A] hover:text-[#DC2626] transition-colors duration-200 p-1">
                              <Trash size={14} />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* AI Suggestions */}
          {suggestions.length > 0 && (
            <div className="border-2 border-[#EA580C]/30 bg-[#FFF7ED] p-5">
              <div className="flex items-center justify-between mb-3">
                <p className="overline text-[#EA580C]"><Sparkle size={14} weight="fill" className="inline mr-1" />AI Suggestions</p>
                <button onClick={() => setShowSuggestions(!showSuggestions)} className="text-xs font-semibold text-[#EA580C]">
                  {showSuggestions ? "Hide" : "Show"} ({suggestions.length})
                </button>
              </div>
              {showSuggestions && (
                <div className="space-y-3">
                  {suggestions.map((s, i) => (
                    <div key={i} className="bg-white border border-[#E4E4E7] p-3">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="font-semibold text-sm">{s.title}</p>
                          <p className="text-xs text-[#71717A] mt-1">{s.description}</p>
                        </div>
                        {s.savings_percent > 0 && (
                          <Badge tone="success">-{s.savings_percent}%</Badge>
                        )}
                      </div>
                      {s.affected_items?.length > 0 && (
                        <p className="text-xs text-[#71717A] mt-2">Affects: {s.affected_items.join(", ")}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Terms & Notes */}
          <div className="border-2 border-[#E4E4E7] p-5">
            <p className="overline mb-3">Terms & Notes</p>
            <textarea
              data-testid="builder-terms"
              value={meta.terms}
              onChange={(e) => setMeta("terms", e.target.value)}
              placeholder="Payment terms (e.g. 50% advance, 40% on completion, 10% after handover)"
              className={inputCls + " min-h-[60px] resize-y"}
              rows={2}
            />
            <textarea
              data-testid="builder-notes"
              value={meta.notes}
              onChange={(e) => setMeta("notes", e.target.value)}
              placeholder="Additional notes for the client"
              className={inputCls + " min-h-[60px] resize-y mt-3"}
              rows={2}
            />
          </div>
        </div>

        {/* Right Column: Calculations */}
        <div className="space-y-6">
          {/* Cost Breakdown */}
          <div className="border-2 border-[#E4E4E7] sticky top-20">
            <div className="p-4 border-b-2 border-[#E4E4E7] bg-[#F4F4F5]">
              <p className="overline">Cost Summary</p>
            </div>
            <div className="p-4 space-y-2.5">
              <SummaryRow label="Materials" value={fmt(calcs.material)} icon={<Package size={14} className="text-[#EA580C]" />} />
              <SummaryRow label="Labour" value={fmt(calcs.labor)} icon={<Users size={14} className="text-[#16A34A]" />} />
              {calcs.equipment > 0 && <SummaryRow label="Equipment" value={fmt(calcs.equipment)} icon={<Wrench size={14} className="text-[#EAB308]" />} />}
              {calcs.overhead > 0 && <SummaryRow label="Overhead" value={fmt(calcs.overhead)} />}
              {calcs.other > 0 && <SummaryRow label="Other" value={fmt(calcs.other)} />}
              <div className="border-t border-[#E4E4E7] pt-2.5">
                <SummaryRow label="Subtotal" value={fmt(calcs.subtotal)} bold />
              </div>

              {/* Margin Slider */}
              <div className="pt-2">
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-semibold text-[#71717A]"><Percent size={12} className="inline mr-1" />Profit Margin</span>
                  <span className="font-bold">{meta.gross_margin_percent}%</span>
                </div>
                <input
                  data-testid="margin-slider"
                  type="range" min="0" max="40" step="1"
                  value={meta.gross_margin_percent}
                  onChange={(e) => setMeta("gross_margin_percent", parseInt(e.target.value))}
                  className="w-full accent-[#EA580C] h-1.5"
                />
                {calcs.marginAmt > 0 && <p className="text-xs text-[#71717A] text-right">+{fmt(calcs.marginAmt)}</p>}
              </div>

              {/* GST Selector */}
              <div className="pt-1">
                <p className="text-xs font-semibold text-[#71717A] mb-1">GST Rate</p>
                <div className="flex gap-1.5">
                  {GST_OPTIONS.map((g) => (
                    <button
                      key={g.v}
                      data-testid={`gst-${g.v}`}
                      onClick={() => setMeta("gst_percent", g.v)}
                      className={`flex-1 px-2 py-1.5 text-xs font-semibold border-2 transition-colors duration-200 ${
                        meta.gst_percent === g.v
                          ? "border-[#EA580C] bg-[#FFF7ED] text-[#EA580C]"
                          : "border-[#E4E4E7] text-[#71717A] hover:border-[#EA580C]"
                      }`}
                    >
                      {g.l}
                    </button>
                  ))}
                </div>
                {calcs.gstAmt > 0 && <p className="text-xs text-[#71717A] text-right mt-1">+{fmt(calcs.gstAmt)}</p>}
              </div>

              {/* Discount */}
              <div className="pt-1">
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-semibold text-[#71717A]">Discount</span>
                  <span className="font-bold">{meta.discount_percent}%</span>
                </div>
                <input
                  data-testid="discount-slider"
                  type="range" min="0" max="25" step="1"
                  value={meta.discount_percent}
                  onChange={(e) => setMeta("discount_percent", parseInt(e.target.value))}
                  className="w-full accent-[#EA580C] h-1.5"
                />
                {calcs.discountAmt > 0 && <p className="text-xs text-[#DC2626] text-right">-{fmt(calcs.discountAmt)}</p>}
              </div>

              {/* Grand Total */}
              <div className="border-t-2 border-[#09090B] pt-3 mt-3">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-sm">Grand Total</span>
                  <span className="font-display font-black text-2xl tracking-tight text-[#EA580C]">{fmt(calcs.grand)}</span>
                </div>
                {meta.estimated_days > 0 && (
                  <p className="text-xs text-[#71717A] text-right mt-1">
                    <Clock size={12} className="inline mr-1" />{meta.estimated_days} days estimated
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Add Item Dialog */}
      <Dialog open={addItemOpen} onOpenChange={setAddItemOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader><DialogTitle>Add Line Item</DialogTitle></DialogHeader>
          <div className="space-y-3 py-2">
            <select data-testid="item-category" value={newItem.category} onChange={(e) => setNewItem((n) => ({ ...n, category: e.target.value }))} className={inputCls}>
              {CATEGORIES.map((c) => <option key={c.v} value={c.v}>{c.l}</option>)}
            </select>
            <div className="relative">
              <input
                data-testid="item-name"
                value={newItem.name}
                onChange={(e) => { setNewItem((n) => ({ ...n, name: e.target.value })); fillFromMaterial(e.target.value); }}
                placeholder="Item name (type to search materials)"
                className={inputCls}
                list="mat-suggestions"
              />
              <datalist id="mat-suggestions">
                {(materialPrices?.items || []).map((m) => (
                  <option key={m.id} value={m.name}>{m.name} — {country.symbol}{m.price}/{m.unit}</option>
                ))}
              </datalist>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <input data-testid="item-qty" value={newItem.quantity} onChange={(e) => setNewItem((n) => ({ ...n, quantity: e.target.value }))} placeholder="Quantity" className={inputCls} type="number" />
              <input data-testid="item-unit" value={newItem.unit} onChange={(e) => setNewItem((n) => ({ ...n, unit: e.target.value }))} placeholder="Unit (sqft, kg…)" className={inputCls} />
              <input data-testid="item-price" value={newItem.unit_price} onChange={(e) => setNewItem((n) => ({ ...n, unit_price: e.target.value }))} placeholder="Unit price" className={inputCls} type="number" />
            </div>
            <input data-testid="item-notes" value={newItem.notes} onChange={(e) => setNewItem((n) => ({ ...n, notes: e.target.value }))} placeholder="Notes (optional)" className={inputCls} />
          </div>
          <DialogFooter>
            <button data-testid="item-add-submit" onClick={addItem} disabled={!newItem.name.trim()} className={btnPrimary + " disabled:opacity-40"}>
              <Plus size={16} weight="bold" /> Add
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}


/* ================================================================
   QUOTATION VIEW (Client-facing preview)
   ================================================================ */
function QuotationView({ estimateId, user, onBack, onBackToList, fmt }) {
  const { data: quotation, isLoading } = useQuery({
    queryKey: ["quotation", estimateId],
    queryFn: async () => (await api.get(`/estimates/${estimateId}/quotation`)).data,
  });

  const country = getCountry(user);

  if (isLoading || !quotation) return <Spinner />;

  const q = quotation;
  const categoryOrder = ["material", "labor", "equipment", "overhead", "other"];
  const categoryLabel = { material: "Materials", labor: "Labour Charges", equipment: "Equipment", overhead: "Overhead", other: "Other" };

  const handlePrint = () => window.print();

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-4xl mx-auto">
      {/* Toolbar (hidden in print) */}
      <div className="flex items-center gap-3 mb-6 print:hidden">
        <button data-testid="back-to-builder" onClick={onBack} className="flex items-center gap-2 text-sm font-semibold text-[#71717A] hover:text-[#09090B] transition-colors duration-200">
          <ArrowLeft size={16} weight="bold" /> Back to Builder
        </button>
        <button onClick={onBackToList} className="text-xs font-semibold text-[#71717A] hover:text-[#09090B] transition-colors duration-200">
          All Estimates
        </button>
        <div className="ml-auto flex items-center gap-2">
          <button data-testid="print-quotation" onClick={handlePrint} className={btnPrimary}>
            <Printer size={16} weight="duotone" /> Print / PDF
          </button>
        </div>
      </div>

      {/* Quotation Document */}
      <div className="border-2 border-[#E4E4E7] bg-white" id="quotation-doc">
        {/* Header */}
        <div className="border-b-2 border-[#09090B] p-6 sm:p-8">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="font-display font-black text-2xl sm:text-3xl tracking-tighter text-[#09090B]">QUOTATION</h1>
              <p className="text-xs text-[#71717A] mt-1 font-mono">{q.ref_number} · Version {q.version}</p>
            </div>
            <div className="text-right">
              <p className="font-semibold text-sm">{q.contractor_name}</p>
              {q.contractor_company && <p className="text-xs text-[#71717A]">{q.contractor_company}</p>}
              {q.contractor_phone && <p className="text-xs text-[#71717A]">{q.contractor_phone}</p>}
              {q.contractor_email && <p className="text-xs text-[#71717A]">{q.contractor_email}</p>}
            </div>
          </div>
        </div>

        {/* Client + Project Info */}
        <div className="grid grid-cols-1 sm:grid-cols-2 border-b border-[#E4E4E7]">
          <div className="p-5 sm:p-6 border-b sm:border-b-0 sm:border-r border-[#E4E4E7]">
            <p className="overline mb-2">Client</p>
            <p className="font-semibold text-sm">{q.client_name || "—"}</p>
            {q.client_phone && <p className="text-xs text-[#71717A] mt-0.5"><Phone size={12} className="inline mr-1" />{q.client_phone}</p>}
            {q.client_email && <p className="text-xs text-[#71717A] mt-0.5"><Envelope size={12} className="inline mr-1" />{q.client_email}</p>}
          </div>
          <div className="p-5 sm:p-6">
            <p className="overline mb-2">Project Details</p>
            <p className="text-sm"><span className="text-[#71717A]">Type:</span> <span className="font-semibold capitalize">{q.work_type}</span></p>
            <p className="text-sm"><span className="text-[#71717A]">Area:</span> <span className="font-semibold">{q.area}</span></p>
            {q.estimated_days > 0 && <p className="text-sm"><span className="text-[#71717A]">Duration:</span> <span className="font-semibold">{q.estimated_days} days</span></p>}
            {q.valid_until && <p className="text-sm"><span className="text-[#71717A]">Valid until:</span> <span className="font-semibold">{q.valid_until}</span></p>}
          </div>
        </div>

        {/* Itemized Breakdown */}
        {categoryOrder.map((cat) => {
          const catItems = (q.grouped_items || {})[cat];
          if (!catItems || catItems.length === 0) return null;
          return (
            <div key={cat} className="border-b border-[#E4E4E7]">
              <div className="px-5 sm:px-6 py-3 bg-[#F4F4F5]">
                <p className="text-xs font-bold uppercase tracking-wider text-[#71717A]">{categoryLabel[cat] || cat}</p>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#E4E4E7]">
                    <th className="text-left px-5 sm:px-6 py-2 text-xs font-semibold text-[#71717A] uppercase tracking-wider">Description</th>
                    <th className="text-right px-3 py-2 text-xs font-semibold text-[#71717A] uppercase tracking-wider">Qty</th>
                    <th className="text-right px-3 py-2 text-xs font-semibold text-[#71717A] uppercase tracking-wider">Unit</th>
                    <th className="text-right px-3 py-2 text-xs font-semibold text-[#71717A] uppercase tracking-wider">Rate</th>
                    <th className="text-right px-5 sm:px-6 py-2 text-xs font-semibold text-[#71717A] uppercase tracking-wider">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {catItems.map((li, idx) => (
                    <tr key={idx} className="border-b border-[#E4E4E7]/50">
                      <td className="px-5 sm:px-6 py-2.5 font-medium">{li.name}{li.notes ? <span className="text-xs text-[#71717A] ml-2">({li.notes})</span> : null}</td>
                      <td className="px-3 py-2.5 text-right">{li.quantity}</td>
                      <td className="px-3 py-2.5 text-right text-[#71717A]">{li.unit}</td>
                      <td className="px-3 py-2.5 text-right">{fmt(li.unit_price)}</td>
                      <td className="px-5 sm:px-6 py-2.5 text-right font-semibold">{fmt(li.total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        })}

        {/* Totals */}
        <div className="p-5 sm:p-6">
          <div className="max-w-xs ml-auto space-y-2">
            <TotalRow label="Subtotal" value={fmt(q.subtotal)} />
            {q.gross_margin_percent > 0 && <TotalRow label={`Margin (${q.gross_margin_percent}%)`} value={`+${fmt(q.gross_margin_amount)}`} />}
            {q.discount_percent > 0 && <TotalRow label={`Discount (${q.discount_percent}%)`} value={`-${fmt(q.discount_amount)}`} className="text-[#DC2626]" />}
            {q.gst_percent > 0 && <TotalRow label={`GST (${q.gst_percent}%)`} value={`+${fmt(q.gst_amount)}`} />}
            <div className="border-t-2 border-[#09090B] pt-2 mt-2">
              <div className="flex items-center justify-between">
                <span className="font-bold text-base">Grand Total</span>
                <span className="font-display font-black text-2xl tracking-tight text-[#EA580C]">{fmt(q.grand_total)}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Terms */}
        {(q.terms || q.notes) && (
          <div className="border-t border-[#E4E4E7] p-5 sm:p-6">
            {q.terms && (
              <div className="mb-3">
                <p className="overline mb-1">Payment Terms</p>
                <p className="text-sm text-[#71717A] whitespace-pre-wrap">{q.terms}</p>
              </div>
            )}
            {q.notes && (
              <div>
                <p className="overline mb-1">Notes</p>
                <p className="text-sm text-[#71717A] whitespace-pre-wrap">{q.notes}</p>
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="border-t border-[#E4E4E7] px-5 sm:px-6 py-3 bg-[#F4F4F5]">
          <p className="text-xs text-[#71717A] text-center">
            Generated by KARYA · {new Date(q.created_at).toLocaleDateString()} · {q.ref_number}
          </p>
        </div>
      </div>
    </div>
  );
}


/* ================================================================
   MATERIAL PRICES DIALOG
   ================================================================ */
function MaterialPricesDialog({ open, onClose, user }) {
  const qc = useQueryClient();
  const country = getCountry(user);
  const [search, setSearch] = useState("");
  const [addForm, setAddForm] = useState({ name: "", category: "wood", unit: "sqft", price: "", region: "" });
  const [seeding, setSeeding] = useState(false);
  const [seedRegion, setSeedRegion] = useState("");
  const [seedType, setSeedType] = useState("interior");

  const { data: pricesData, isLoading } = useQuery({
    queryKey: ["material-prices", search],
    queryFn: async () => (await api.get("/material-prices", { params: { q: search } })).data,
    enabled: open,
  });
  const prices = pricesData?.items || [];

  const addPrice = useMutation({
    mutationFn: async () => (await api.post("/material-prices", { ...addForm, price: parseFloat(addForm.price) || 0 })).data,
    onSuccess: () => {
      toast.success("Material price saved");
      qc.invalidateQueries({ queryKey: ["material-prices"] });
      setAddForm({ name: "", category: "wood", unit: "sqft", price: "", region: "" });
    },
  });

  const deletePrice = useMutation({
    mutationFn: async (id) => (await api.delete(`/material-prices/${id}`)).data,
    onSuccess: () => {
      toast.success("Deleted");
      qc.invalidateQueries({ queryKey: ["material-prices"] });
    },
  });

  const seedPrices = async () => {
    if (!seedRegion.trim()) { toast.error("Enter a city/region"); return; }
    setSeeding(true);
    try {
      const res = await api.post("/material-prices/ai-seed", { region: seedRegion, work_type: seedType });
      toast.success(`${res.data.seeded} new materials seeded (${res.data.total} total)`);
      qc.invalidateQueries({ queryKey: ["material-prices"] });
    } catch (e) {
      toast.error("Failed to seed prices. Try again.");
    }
    setSeeding(false);
  };

  if (!open) return null;

  const MATERIAL_CATS = ["wood", "cement", "steel", "tiles", "paint", "electrical", "plumbing", "hardware", "glass", "stone", "adhesive", "waterproofing", "other"];

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>Material Price List</DialogTitle>
        </DialogHeader>

        {/* AI Seed Section */}
        <div className="bg-[#FFF7ED] border border-[#EA580C]/20 p-3 flex flex-col sm:flex-row gap-2 items-end">
          <div className="flex-1">
            <p className="text-xs font-semibold mb-1"><Sparkle size={12} weight="fill" className="inline mr-1 text-[#EA580C]" />AI-Seed Market Prices</p>
            <div className="flex gap-2">
              <input
                data-testid="seed-region"
                value={seedRegion}
                onChange={(e) => setSeedRegion(e.target.value)}
                placeholder="City (e.g. Bangalore)"
                className={inputCls + " text-xs py-1.5"}
              />
              <select data-testid="seed-type" value={seedType} onChange={(e) => setSeedType(e.target.value)} className={inputCls + " text-xs py-1.5 w-32"}>
                {WORK_TYPES.map((w) => <option key={w.v} value={w.v}>{w.l}</option>)}
              </select>
            </div>
          </div>
          <button data-testid="seed-btn" onClick={seedPrices} disabled={seeding} className={btnPrimary + " text-xs py-1.5 shrink-0 disabled:opacity-50"}>
            {seeding ? <ArrowsClockwise size={14} className="animate-spin" /> : <Lightning size={14} weight="fill" />}
            {seeding ? "Seeding…" : "Seed Prices"}
          </button>
        </div>

        {/* Search */}
        <div className="relative">
          <MagnifyingGlass size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#71717A]" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search materials…"
            className={inputCls + " pl-8 text-xs py-2"}
          />
        </div>

        {/* Price List */}
        <div className="flex-1 overflow-y-auto border border-[#E4E4E7]">
          {isLoading ? <div className="p-4 text-center text-sm text-[#71717A]">Loading…</div> :
           prices.length === 0 ? (
            <div className="p-6 text-center text-sm text-[#71717A]">
              No materials yet. Use AI Seed above or add manually below.
            </div>
          ) : (
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-[#F4F4F5] z-10">
                <tr className="border-b border-[#E4E4E7]">
                  <th className="text-left px-3 py-2 font-semibold uppercase tracking-wider text-[#71717A]">Material</th>
                  <th className="text-left px-2 py-2 font-semibold uppercase tracking-wider text-[#71717A]">Cat</th>
                  <th className="text-right px-2 py-2 font-semibold uppercase tracking-wider text-[#71717A]">Price</th>
                  <th className="text-right px-2 py-2 font-semibold uppercase tracking-wider text-[#71717A]">Unit</th>
                  <th className="text-center px-2 py-2 font-semibold uppercase tracking-wider text-[#71717A]">Src</th>
                  <th className="w-8"></th>
                </tr>
              </thead>
              <tbody>
                {prices.map((p) => (
                  <tr key={p.id} className="border-b border-[#E4E4E7]/50 hover:bg-[#FAFAFA]">
                    <td className="px-3 py-2 font-medium">{p.name}</td>
                    <td className="px-2 py-2 text-[#71717A]">{p.category}</td>
                    <td className="px-2 py-2 text-right font-semibold">{country.symbol}{p.price}</td>
                    <td className="px-2 py-2 text-right text-[#71717A]">{p.unit}</td>
                    <td className="px-2 py-2 text-center">
                      <Badge tone={p.source === "ai_seeded" ? "accent" : "neutral"}>
                        {p.source === "ai_seeded" ? "AI" : "Manual"}
                      </Badge>
                    </td>
                    <td className="px-1 py-2">
                      <button onClick={() => deletePrice.mutate(p.id)} className="text-[#71717A] hover:text-[#DC2626] p-1">
                        <Trash size={12} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Add Manual */}
        <div className="border-t border-[#E4E4E7] pt-3">
          <p className="text-xs font-semibold text-[#71717A] mb-2">Add Material</p>
          <div className="flex gap-2">
            <input value={addForm.name} onChange={(e) => setAddForm((f) => ({ ...f, name: e.target.value }))} placeholder="Material name" className={inputCls + " text-xs py-1.5 flex-1"} />
            <select value={addForm.category} onChange={(e) => setAddForm((f) => ({ ...f, category: e.target.value }))} className={inputCls + " text-xs py-1.5 w-24"}>
              {MATERIAL_CATS.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <input value={addForm.price} onChange={(e) => setAddForm((f) => ({ ...f, price: e.target.value }))} placeholder="Price" className={inputCls + " text-xs py-1.5 w-20"} type="number" />
            <input value={addForm.unit} onChange={(e) => setAddForm((f) => ({ ...f, unit: e.target.value }))} placeholder="Unit" className={inputCls + " text-xs py-1.5 w-16"} />
            <button data-testid="add-material-btn" onClick={() => addPrice.mutate()} disabled={!addForm.name.trim()} className={btnPrimary + " text-xs py-1.5 disabled:opacity-40"}>
              <Plus size={12} weight="bold" />
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}


/* ================================================================
   HELPER COMPONENTS
   ================================================================ */
function SummaryRow({ label, value, icon, bold, className = "" }) {
  return (
    <div className={`flex items-center justify-between text-sm ${className}`}>
      <span className={`flex items-center gap-1.5 text-[#71717A] ${bold ? "font-semibold text-[#09090B]" : ""}`}>
        {icon} {label}
      </span>
      <span className={bold ? "font-bold text-[#09090B]" : "font-medium"}>{value}</span>
    </div>
  );
}

function TotalRow({ label, value, className = "" }) {
  return (
    <div className={`flex items-center justify-between text-sm ${className}`}>
      <span className="text-[#71717A]">{label}</span>
      <span className="font-semibold">{value}</span>
    </div>
  );
}
