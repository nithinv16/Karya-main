import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { PageHeader, Badge, Spinner } from "@/components/ui-bits";
import { useAuth } from "@/context/AuthContext";
import { formatMoney } from "@/lib/country";
import { Receipt, MagnifyingGlass, Plus, Trash, Calendar, Storefront, Tag, Sparkle, PaperPlaneTilt } from "@phosphor-icons/react";
import { toast } from "sonner";

const CATS = ["cement", "steel", "aggregate", "tools", "fuel", "transport", "labour_petty", "food", "office", "other"];

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
    amount: "", category: "other", summary: "",
  });

  const { data, isLoading } = useQuery({
    queryKey: ["expenses", q, category],
    queryFn: async () => (await api.get("/expenses", { params: { q, category } })).data,
  });

  const create = useMutation({
    mutationFn: async () => (await api.post("/expenses", { ...form, amount: parseFloat(form.amount || "0") })).data,
    onSuccess: () => {
      toast.success("Expense added");
      setForm({ vendor: "", date: new Date().toISOString().slice(0, 10), amount: "", category: "other", summary: "" });
      setShowForm(false);
      qc.invalidateQueries({ queryKey: ["expenses"] });
    },
    onError: () => toast.error("Couldn't add expense"),
  });

  const del = useMutation({
    mutationFn: async (id) => (await api.delete(`/expenses/${id}`)).data,
    onSuccess: () => { toast.success("Deleted"); qc.invalidateQueries({ queryKey: ["expenses"] }); },
  });

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
          <button
            data-testid="add-expense-button"
            onClick={() => setShowForm((s) => !s)}
            className="flex items-center gap-2 bg-[#EA580C] text-white px-4 py-2.5 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200"
          >
            <Plus size={16} weight="bold" /> Add expense
          </button>
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
              {CATS.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
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
          {items.map((it) => (
            <div key={it.id} className="flex items-start gap-3 sm:gap-5 px-4 sm:px-5 py-4 border-b border-[#E4E4E7] last:border-b-0 hover:bg-[#FAFAFA] transition-colors duration-200" data-testid={`expense-${it.id}`}>
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
                  {(it.items || []).length > 0 && <span className="flex items-center gap-1"><Tag size={12} /> {it.items.length} item{it.items.length === 1 ? "" : "s"}</span>}
                </div>
              </div>
              <div className="text-right shrink-0">
                <p className="font-mono font-black text-lg text-[#09090B]">{fmt(it.amount)}</p>
                <button
                  data-testid={`delete-expense-${it.id}`}
                  onClick={() => del.mutate(it.id)}
                  className="mt-1 text-[#71717A] hover:text-[#DC2626] transition-colors duration-200 press"
                  aria-label="Delete expense"
                >
                  <Trash size={15} weight="bold" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="mt-8 border border-[#E4E4E7] p-4 flex items-center gap-3 bg-white text-sm text-[#71717A]">
        <Sparkle size={18} weight="duotone" className="text-[#EA580C] shrink-0" />
        <p>Every receipt you forward to Telegram is parsed by AI (vendor, date, amount, line items, category) and stored here — no manual data entry.</p>
      </div>
    </div>
  );
}
