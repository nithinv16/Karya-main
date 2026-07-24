import React, { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { PageHeader, Badge, Spinner } from "@/components/ui-bits";
import { useAuth } from "@/context/AuthContext";
import { formatMoney } from "@/lib/country";
import { Receipt, MagnifyingGlass, Plus, Trash, Calendar, Storefront, Tag, Sparkle, PaperPlaneTilt, Buildings, PencilSimple, X, CaretDown, CaretUp } from "@phosphor-icons/react";
import { toast } from "sonner";
import CostTrendsPanel from "@/components/CostTrendsPanel";
function Swipeable({ children, onSwipeLeft, threshold = 80 }) {
  const [translationX, setTranslationX] = useState(0);
  const [isSwiping, setIsSwiping] = useState(false);
  const touchStart = React.useRef({ x: 0, y: 0 });
  const isHorizontal = React.useRef(null);

  const handleTouchStart = (e) => {
    touchStart.current = {
      x: e.touches[0].clientX,
      y: e.touches[0].clientY,
    };
    setIsSwiping(true);
    isHorizontal.current = null;
  };

  const handleTouchMove = (e) => {
    if (!isSwiping) return;

    const currentX = e.touches[0].clientX;
    const currentY = e.touches[0].clientY;

    const diffX = currentX - touchStart.current.x;
    const diffY = currentY - touchStart.current.y;

    if (isHorizontal.current === null) {
      isHorizontal.current = Math.abs(diffX) > Math.abs(diffY);
    }

    if (!isHorizontal.current) {
      setIsSwiping(false);
      setTranslationX(0);
      return;
    }

    if (e.cancelable) {
      e.preventDefault();
    }

    if (diffX < 0) {
      setTranslationX(diffX);
    } else {
      setTranslationX(0);
    }
  };

  const handleTouchEnd = () => {
    setIsSwiping(false);
    if (translationX < -threshold) {
      setTranslationX(-window.innerWidth);
      setTimeout(() => {
        onSwipeLeft();
        setTranslationX(0);
      }, 200);
    } else {
      setTranslationX(0);
    }
    isHorizontal.current = null;
  };

  return (
    <div className="relative overflow-hidden w-full">
      <div 
        className="absolute inset-0 flex items-center justify-end bg-[#DC2626] text-white px-6 select-none"
        style={{
          opacity: translationX < 0 ? 1 : 0,
          transition: "opacity 0.15s ease",
        }}
      >
        <div className="flex items-center gap-2 font-bold text-xs uppercase tracking-wider">
          <Trash size={18} weight="bold" />
          <span>Delete</span>
        </div>
      </div>

      <div
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        style={{
          transform: `translateX(${translationX}px)`,
          transition: isSwiping ? "none" : "transform 0.25s cubic-bezier(0.16, 1, 0.3, 1)",
        }}
        className="relative w-full bg-white touch-pan-y"
      >
        {children}
      </div>
    </div>
  );
}


const CATS = [
  "cement", "steel", "aggregate", "bricks", "sand", "hardware", "electrical", "plumbing", "paint",
  "tools", "safety", "scaffolding", "formwork", "fuel", "transport", "machinery_rent",
  "labour_petty", "subcontractor", "food", "water", "utilities", "office", "permits", "insurance", "other",
];

const inputCls = "w-full border-2 border-[#E4E4E7] focus:border-[#EA580C] outline-none px-3 py-2.5 text-sm transition-colors duration-200 bg-white";

export default function Expenses() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const fmt = (n) => formatMoney(n, user);
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    vendor: "", date: new Date().toISOString().slice(0, 10),
    amount: "", category: "other", customCategory: "", summary: "", project_id: "",
  });
  const [receiptBusy, setReceiptBusy] = useState(false);
  const receiptInputRef = React.useRef(null);
  // Review/edit modal state: { mode: "review"|"edit", expense: {...} }
  const [editModal, setEditModal] = useState(null);
  // Expanded line-item detail for a specific expense
  const [expandedId, setExpandedId] = useState(null);

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: async () => (await api.get("/projects")).data,
  });

  const { data, isLoading } = useQuery({
    queryKey: ["expenses", q, category],
    queryFn: async () => (await api.get("/expenses", { params: { q, category } })).data,
  });

  const create = useMutation({
    mutationFn: async () => {
      // If user picked "other" and typed a custom label, send that as the category.
      const rawCat = form.category === "other" && form.customCategory.trim()
        ? form.customCategory.trim().toLowerCase().replace(/\s+/g, "_").slice(0, 40)
        : form.category;
      const payload = { ...form, category: rawCat, amount: parseFloat(form.amount || "0"), project_id: form.project_id || null };
      delete payload.customCategory;
      return (await api.post("/expenses", payload)).data;
    },
    onSuccess: () => {
      toast.success("Expense added");
      setForm({ vendor: "", date: new Date().toISOString().slice(0, 10), amount: "", category: "other", customCategory: "", summary: "", project_id: "" });
      setShowForm(false);
      qc.invalidateQueries({ queryKey: ["expenses"] });
      qc.invalidateQueries({ queryKey: ["cost-trends"] });
    },
    onError: () => toast.error("Couldn't add expense"),
  });

  const update = useMutation({
    mutationFn: async ({ id, body }) => (await api.patch(`/expenses/${id}`, body)).data,
    onSuccess: () => {
      toast.success("Expense updated");
      setEditModal(null);
      qc.invalidateQueries({ queryKey: ["expenses"] });
      qc.invalidateQueries({ queryKey: ["cost-trends"] });
    },
    onError: () => toast.error("Couldn't update expense"),
  });

  const del = useMutation({
    mutationFn: async (id) => (await api.delete(`/expenses/${id}`)).data,
    onSuccess: () => {
      toast.success("Deleted");
      qc.invalidateQueries({ queryKey: ["expenses"] });
      qc.invalidateQueries({ queryKey: ["cost-trends"] });
    },
  });

  const openEditModal = useCallback((expense, mode = "edit") => {
    setEditModal({ mode, expense: { ...expense } });
  }, []);

  const items = data?.items || [];
  const byCat = data?.by_category || [];
  const total = data?.total || 0;

  return (
    <div className="p-5 sm:p-8">
      <PageHeader
        overline="Cost Tracking"
        title="Expenses & Receipts"
        desc="Every receipt captured via Telegram or added manually — searchable, categorized, and rolled up so you know where the money went."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <input
              ref={receiptInputRef}
              type="file"
              accept="image/*,application/pdf"
              className="hidden"
              data-testid="expense-receipt-input"
              onChange={async (e) => {
                const f = e.target.files?.[0];
                if (!f) return;
                setReceiptBusy(true);
                try {
                  const fd = new FormData();
                  fd.append("file", f);
                  const res = await api.post("/expenses/upload-receipt", fd, {
                    headers: { "Content-Type": "multipart/form-data" },
                    timeout: 60000,
                  });
                  const parsedOk = res.data.parsed;
                  const exp = res.data.expense || {};
                  qc.invalidateQueries({ queryKey: ["expenses"] });
                  qc.invalidateQueries({ queryKey: ["cost-trends"] });
                  // Open review modal so user can inspect and edit parsed data
                  if (parsedOk && exp.id) {
                    toast.success("Receipt parsed — review the details below");
                    openEditModal(exp, "review");
                  } else {
                    toast.warning("Receipt saved but couldn't auto-detect details — tap edit to fill in.");
                  }
                } catch (err) {
                  const detail = err?.response?.data?.detail;
                  toast.error(detail || "Couldn't process that receipt");
                } finally {
                  setReceiptBusy(false);
                  if (receiptInputRef.current) receiptInputRef.current.value = "";
                }
              }}
            />
            <button
              data-testid="upload-receipt-button"
              onClick={() => receiptInputRef.current?.click()}
              disabled={receiptBusy}
              className="flex items-center gap-2 border-2 border-[#09090B] px-4 py-2 text-sm font-semibold hover:bg-[#09090B] hover:text-white transition-colors duration-200 disabled:opacity-60"
            >
              <Sparkle size={16} weight="fill" />
              {receiptBusy ? "Parsing…" : "Upload receipt (AI)"}
            </button>
            <button
              data-testid="add-expense-button"
              onClick={() => setShowForm((s) => !s)}
              className="flex items-center gap-2 bg-[#EA580C] text-white px-4 py-2.5 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200"
            >
              <Plus size={16} weight="bold" /> Add expense
            </button>
          </div>
        }
      />

      {/* Add form */}
      {showForm && (
        <div data-testid="expense-form" className="border-2 border-[#09090B] p-5 mb-6 bg-white">
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
            <input data-testid="expense-vendor" className={inputCls} placeholder="Vendor / supplier" value={form.vendor} onChange={(e) => setForm({ ...form, vendor: e.target.value })} />
            <input data-testid="expense-date" type="date" className={inputCls} value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
            <input data-testid="expense-amount" type="number" step="0.01" className={inputCls} placeholder="Amount" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
            <select data-testid="expense-category" className={inputCls} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
              {CATS.map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
            </select>
          </div>
          {form.category === "other" && (
            <input
              data-testid="expense-custom-category"
              className={inputCls + " mb-3"}
              placeholder='Custom category (e.g. "site accommodation" — used to group receipts)'
              value={form.customCategory}
              onChange={(e) => setForm({ ...form, customCategory: e.target.value })}
              maxLength={40}
            />
          )}
          {projects && projects.length > 0 && (
            <select
              data-testid="expense-project"
              className={inputCls + " mb-3"}
              value={form.project_id}
              onChange={(e) => setForm({ ...form, project_id: e.target.value })}
            >
              <option value="">— Attach to project (optional) —</option>
              {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          )}
          <textarea data-testid="expense-summary" className={inputCls + " min-h-16"} placeholder="What was this for? (optional)" value={form.summary} onChange={(e) => setForm({ ...form, summary: e.target.value })} />
          <div className="mt-3 flex items-center gap-3">
            <button
              data-testid="expense-save-button"
              onClick={() => create.mutate()}
              disabled={create.isPending || !form.amount}
              className="flex items-center gap-2 bg-[#09090B] text-white px-4 py-2 text-sm font-semibold hover:bg-[#EA580C] transition-colors duration-200 disabled:opacity-50"
            >
              {create.isPending ? "Saving…" : "Save expense"}
            </button>
            <button data-testid="expense-cancel-button" onClick={() => setShowForm(false)} className="text-xs text-[#71717A] hover:text-[#09090B]">Cancel</button>
          </div>
        </div>
      )}

      {/* Cost trends & budget vs actual */}
      <div className="mb-6">
        <CostTrendsPanel />
      </div>

      {/* Rollup */}
      <div className="grid sm:grid-cols-3 gap-px bg-[#E4E4E7] border border-[#E4E4E7] mb-6" data-testid="expense-rollup">
        <div className="bg-white p-5">
          <p className="overline">Total spend</p>
          <p className="font-display font-black text-3xl tracking-tight mt-1">{fmt(total)}</p>
          <p className="text-xs text-[#71717A] mt-1">{items.length} receipt{items.length === 1 ? "" : "s"}</p>
        </div>
        <div className="bg-white p-5 sm:col-span-2">
          <p className="overline mb-3">By category</p>
          {byCat.length === 0 ? (
            <p className="text-sm text-[#71717A]">No expenses yet.</p>
          ) : (
            <div className="space-y-2">
              {byCat.slice(0, 5).map((c) => {
                const pct = total > 0 ? Math.round((c.amount / total) * 100) : 0;
                return (
                  <div key={c.category} className="flex items-center gap-3 text-sm">
                    <Badge>{c.category}</Badge>
                    <div className="flex-1 h-2 bg-[#F4F4F5] overflow-hidden">
                      <div className="h-full bg-[#EA580C]" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="font-mono font-semibold text-[#09090B] w-24 text-right">{fmt(c.amount)}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <div className="flex-1 min-w-[200px] flex items-center gap-2 border-2 border-[#E4E4E7] px-3 py-2 bg-white focus-within:border-[#EA580C] transition-colors duration-200">
          <MagnifyingGlass size={16} className="text-[#71717A]" />
          <input data-testid="expense-search" className="flex-1 outline-none text-sm bg-transparent" placeholder="Search vendor or notes" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <select data-testid="expense-filter-category" className="border-2 border-[#E4E4E7] px-3 py-2 text-sm bg-white" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">All categories</option>
          {CATS.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      {/* List */}
      {isLoading ? (
        <Spinner />
      ) : items.length === 0 ? (
        <div className="border border-[#E4E4E7] p-12 text-center" data-testid="expenses-empty">
          <Receipt size={40} weight="duotone" className="mx-auto text-[#EA580C] mb-4" />
          <h3 className="font-display font-bold text-xl mb-2">No expenses yet</h3>
          <p className="text-[#71717A] text-sm max-w-md mx-auto mb-6">
            Forward any receipt photo to the Karya Telegram bot and tap <span className="font-mono text-xs bg-[#F4F4F5] px-1.5 py-0.5">Receipt</span> — AI extracts vendor, amount and category into this list. Or add one manually with the button above.
          </p>
          <div className="flex items-center justify-center gap-2 text-xs text-[#71717A]">
            <PaperPlaneTilt size={14} weight="fill" />
            <span>Tip: link Telegram from Profile → Connect Telegram</span>
          </div>
        </div>
      ) : (
        <div className="border border-[#E4E4E7]" data-testid="expenses-list">
          {items.map((it) => {
            const hasItems = (it.items || []).length > 0;
            const isExpanded = expandedId === it.id;
            return (
              <Swipeable key={it.id} onSwipeLeft={() => del.mutate(it.id)}>
                <div data-testid={`expense-${it.id}`}>
                  <div
                    className={`flex items-start gap-3 sm:gap-5 px-4 sm:px-5 py-4 border-b border-[#E4E4E7] last:border-b-0 hover:bg-[#FAFAFA] transition-colors duration-200 ${hasItems ? 'cursor-pointer' : ''}`}
                    onClick={() => hasItems && setExpandedId(isExpanded ? null : it.id)}
                  >
                    <div className="w-10 h-10 shrink-0 bg-[#FFF7ED] flex items-center justify-center">
                      <Receipt size={20} weight="duotone" className="text-[#EA580C]" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2 mb-1">
                        <p className="font-display font-bold leading-tight truncate flex items-center gap-1.5">
                          <Storefront size={14} className="text-[#71717A]" /> {it.vendor || "Unknown vendor"}
                        </p>
                        <Badge tone="accent">{it.category || "other"}</Badge>
                        {it.source === "telegram" && (
                          <span className="text-[10px] font-semibold text-[#229ED9] flex items-center gap-1">
                            <PaperPlaneTilt size={10} weight="fill" /> Telegram
                          </span>
                        )}
                      </div>
                      {it.summary && <p className="text-sm text-[#3f3f46] leading-snug line-clamp-2">{it.summary}</p>}
                      <div className="flex items-center gap-3 mt-1.5 text-xs text-[#71717A]">
                        <span className="flex items-center gap-1"><Calendar size={12} /> {it.date || "—"}</span>
                        {hasItems && (
                          <button
                            className="flex items-center gap-1 text-[#EA580C] font-semibold hover:underline"
                            onClick={(e) => { e.stopPropagation(); setExpandedId(isExpanded ? null : it.id); }}
                          >
                            <Tag size={12} /> {it.items.length} item{it.items.length === 1 ? "" : "s"}
                            {isExpanded ? <CaretUp size={10} /> : <CaretDown size={10} />}
                          </button>
                        )}
                        {it.project_id && (
                          <span className="flex items-center gap-1"><Buildings size={12} /> {projects?.find((p) => p.id === it.project_id)?.name || "Project"}</span>
                        )}
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="font-mono font-black text-lg text-[#09090B]">{fmt(it.amount)}</p>
                      <div className="flex items-center gap-1 mt-1 justify-end">
                        <button
                          data-testid={`edit-expense-${it.id}`}
                          onClick={(e) => { e.stopPropagation(); openEditModal(it, "edit"); }}
                          className="text-[#71717A] hover:text-[#EA580C] transition-colors duration-200 press p-0.5"
                          aria-label="Edit expense"
                        >
                          <PencilSimple size={14} weight="bold" />
                        </button>
                        <button
                          data-testid={`delete-expense-${it.id}`}
                          onClick={(e) => { e.stopPropagation(); del.mutate(it.id); }}
                          className="text-[#71717A] hover:text-[#DC2626] transition-colors duration-200 press p-0.5"
                          aria-label="Delete expense"
                        >
                          <Trash size={14} weight="bold" />
                        </button>
                      </div>
                    </div>
                  </div>
                  {/* Expandable line items */}
                  {isExpanded && hasItems && (
                    <div className="bg-[#FAFAFA] border-b border-[#E4E4E7] px-5 sm:px-14 py-3">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-[#71717A] text-xs uppercase tracking-wider">
                            <th className="text-left py-1 font-semibold">Material</th>
                            <th className="text-right py-1 font-semibold w-20">Qty</th>
                            <th className="text-right py-1 font-semibold w-28">Amount</th>
                          </tr>
                        </thead>
                        <tbody>
                          {it.items.map((li, idx) => (
                            <tr key={'li-' + idx + '-' + (li.name || '').slice(0, 10)} className="border-t border-[#E4E4E7]">
                              <td className="py-1.5 text-[#09090B] font-medium">{li.name || '—'}</td>
                              <td className="py-1.5 text-right text-[#71717A] font-mono">{li.qty || '—'}</td>
                              <td className="py-1.5 text-right font-mono font-semibold text-[#09090B]">{fmt(li.amount || 0)}</td>
                            </tr>
                          ))}
                          <tr className="border-t-2 border-[#09090B]">
                            <td className="py-1.5 font-bold text-[#09090B]" colSpan={2}>Total</td>
                            <td className="py-1.5 text-right font-mono font-black text-[#EA580C]">{fmt(it.amount)}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </Swipeable>
            );
          })}
        </div>
      )}

      <div className="mt-8 border border-[#E4E4E7] p-4 flex items-center gap-3 bg-white text-sm text-[#71717A]">
        <Sparkle size={18} weight="duotone" className="text-[#EA580C] shrink-0" />
        <p>Every receipt you forward to Telegram is parsed by AI (vendor, date, amount, line items, category) and stored here — no manual data entry.</p>
      </div>

      {/* Review / Edit Modal */}
      {editModal && (
        <ExpenseEditModal
          mode={editModal.mode}
          expense={editModal.expense}
          projects={projects}
          fmt={fmt}
          onSave={(id, body) => update.mutate({ id, body })}
          onClose={() => setEditModal(null)}
          saving={update.isPending}
        />
      )}
    </div>
  );
}


/* ----------------------------------------------------------------
   Inline edit/review modal — shown after receipt upload or on edit
   ---------------------------------------------------------------- */
function ExpenseEditModal({ mode, expense, projects, fmt, onSave, onClose, saving }) {
  const [form, setForm] = useState({
    vendor: expense.vendor || "",
    date: expense.date || new Date().toISOString().slice(0, 10),
    category: expense.category || "other",
    summary: expense.summary || "",
    project_id: expense.project_id || "",
    items: (expense.items || []).map((li) => ({ ...li })),
  });

  const itemsTotal = form.items.reduce((s, li) => s + (parseFloat(li.amount) || 0), 0);
  const displayTotal = form.items.length > 0 ? itemsTotal : (expense.amount || 0);

  const updateItem = (idx, field, value) => {
    setForm((f) => {
      const items = [...f.items];
      items[idx] = { ...items[idx], [field]: field === "amount" ? value : value };
      return { ...f, items };
    });
  };

  const addItem = () => {
    setForm((f) => ({ ...f, items: [...f.items, { name: "", qty: "", amount: 0 }] }));
  };

  const removeItem = (idx) => {
    setForm((f) => ({ ...f, items: f.items.filter((_, i) => i !== idx) }));
  };

  const handleSave = () => {
    const amount = form.items.length > 0
      ? form.items.reduce((s, li) => s + (parseFloat(li.amount) || 0), 0)
      : expense.amount;
    onSave(expense.id, {
      vendor: form.vendor,
      date: form.date,
      category: form.category,
      summary: form.summary,
      project_id: form.project_id || null,
      items: form.items.map((li) => ({ name: li.name, qty: String(li.qty || ""), amount: parseFloat(li.amount) || 0 })),
      amount: Math.round(amount * 100) / 100,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4" onClick={onClose}>
      <div
        className="bg-white border-2 border-[#09090B] w-full max-w-lg max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-[#E4E4E7]">
          <div className="flex items-center gap-2">
            <Receipt size={20} weight="duotone" className="text-[#EA580C]" />
            <h3 className="font-display font-bold text-lg">
              {mode === "review" ? "Parsed Receipt — Review & Edit" : "Edit Expense"}
            </h3>
          </div>
          <button onClick={onClose} className="text-[#71717A] hover:text-[#09090B] transition-colors">
            <X size={20} weight="bold" />
          </button>
        </div>

        {/* Form fields */}
        <div className="p-5 space-y-4">
          {/* Top fields */}
          <div className="grid sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-[#71717A] uppercase tracking-wider mb-1 block">Vendor</label>
              <input
                data-testid="edit-vendor"
                className={inputCls}
                value={form.vendor}
                onChange={(e) => setForm({ ...form, vendor: e.target.value })}
                placeholder="Vendor name"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-[#71717A] uppercase tracking-wider mb-1 block">Date</label>
              <input
                data-testid="edit-date"
                type="date"
                className={inputCls}
                value={form.date}
                onChange={(e) => setForm({ ...form, date: e.target.value })}
              />
            </div>
          </div>

          <div className="grid sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-[#71717A] uppercase tracking-wider mb-1 block">Category</label>
              <select
                data-testid="edit-category"
                className={inputCls}
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
              >
                {CATS.map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
              </select>
            </div>
            {projects && projects.length > 0 && (
              <div>
                <label className="text-xs font-semibold text-[#71717A] uppercase tracking-wider mb-1 block">Project</label>
                <select
                  data-testid="edit-project"
                  className={inputCls}
                  value={form.project_id}
                  onChange={(e) => setForm({ ...form, project_id: e.target.value })}
                >
                  <option value="">— None —</option>
                  {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </div>
            )}
          </div>

          {/* Line items */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold text-[#71717A] uppercase tracking-wider">Line Items</label>
              <button
                onClick={addItem}
                className="text-xs font-semibold text-[#EA580C] hover:text-[#09090B] flex items-center gap-1 transition-colors"
              >
                <Plus size={12} weight="bold" /> Add item
              </button>
            </div>
            {form.items.length === 0 ? (
              <p className="text-sm text-[#71717A] italic border border-dashed border-[#E4E4E7] p-3 text-center">
                No line items parsed. Click "Add item" to add materials manually.
              </p>
            ) : (
              <div className="border border-[#E4E4E7] divide-y divide-[#E4E4E7]">
                {/* Table header */}
                <div className="grid grid-cols-[1fr_70px_90px_32px] gap-2 px-3 py-2 bg-[#F4F4F5] text-xs font-semibold text-[#71717A] uppercase tracking-wider">
                  <span>Material</span>
                  <span className="text-right">Qty</span>
                  <span className="text-right">Amount</span>
                  <span></span>
                </div>
                {form.items.map((li, idx) => (
                  <div key={'edit-item-' + idx} className="grid grid-cols-[1fr_70px_90px_32px] gap-2 px-3 py-1.5 items-center">
                    <input
                      className="border border-[#E4E4E7] px-2 py-1.5 text-sm outline-none focus:border-[#EA580C] transition-colors bg-white"
                      value={li.name || ""}
                      onChange={(e) => updateItem(idx, "name", e.target.value)}
                      placeholder="Material"
                    />
                    <input
                      className="border border-[#E4E4E7] px-2 py-1.5 text-sm text-right outline-none focus:border-[#EA580C] transition-colors bg-white font-mono"
                      value={li.qty || ""}
                      onChange={(e) => updateItem(idx, "qty", e.target.value)}
                      placeholder="Qty"
                    />
                    <input
                      type="number"
                      step="0.01"
                      className="border border-[#E4E4E7] px-2 py-1.5 text-sm text-right outline-none focus:border-[#EA580C] transition-colors bg-white font-mono"
                      value={li.amount || ""}
                      onChange={(e) => updateItem(idx, "amount", e.target.value)}
                      placeholder="0"
                    />
                    <button
                      onClick={() => removeItem(idx)}
                      className="text-[#71717A] hover:text-[#DC2626] transition-colors flex items-center justify-center"
                    >
                      <X size={14} weight="bold" />
                    </button>
                  </div>
                ))}
                {/* Auto-total row */}
                <div className="grid grid-cols-[1fr_70px_90px_32px] gap-2 px-3 py-2 bg-[#F4F4F5]">
                  <span className="font-bold text-sm text-[#09090B]" style={{ gridColumn: 'span 2' }}>Total</span>
                  <span className="text-right font-mono font-black text-[#EA580C] text-sm">{fmt(itemsTotal)}</span>
                  <span></span>
                </div>
              </div>
            )}
          </div>

          {/* Summary */}
          <div>
            <label className="text-xs font-semibold text-[#71717A] uppercase tracking-wider mb-1 block">Summary / Notes</label>
            <textarea
              data-testid="edit-summary"
              className={inputCls + " min-h-16"}
              value={form.summary}
              onChange={(e) => setForm({ ...form, summary: e.target.value })}
              placeholder="What was this for?"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-5 border-t border-[#E4E4E7] bg-[#FAFAFA]">
          <p className="text-sm text-[#71717A]">
            Total: <span className="font-mono font-black text-[#09090B] text-base">{fmt(displayTotal)}</span>
          </p>
          <div className="flex items-center gap-3">
            <button onClick={onClose} className="text-xs text-[#71717A] hover:text-[#09090B] font-semibold">Cancel</button>
            <button
              data-testid="edit-save-button"
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-2 bg-[#09090B] text-white px-4 py-2 text-sm font-semibold hover:bg-[#EA580C] transition-colors duration-200 disabled:opacity-50"
            >
              {saving ? "Saving…" : mode === "review" ? "Confirm & Save" : "Save Changes"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
