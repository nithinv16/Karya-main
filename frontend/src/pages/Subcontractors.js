import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { PageHeader, Badge, Spinner } from "@/components/ui-bits";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Handshake, Plus, Trash, ArrowLeft } from "@phosphor-icons/react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { formatMoney, getCountry } from "@/lib/country";

const TXN_TYPES = [
  { v: "payment", l: "Payment made" },
  { v: "advance", l: "Advance paid" },
  { v: "extra_work", l: "Extra / additional work" },
  { v: "material", l: "Owner-supplied material (recover)" },
  { v: "deduction", l: "Deduction / penalty" },
  { v: "retention_release", l: "Retention release" },
];
const toneFor = (t) => (["payment", "advance"].includes(t) ? "success" : t === "extra_work" ? "accent" : t === "retention_release" ? "warning" : "critical");
const labelFor = (t) => TXN_TYPES.find((x) => x.v === t)?.l || t;

export default function Subcontractors() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const fmt = (n) => formatMoney(n, user);
  const country = getCountry(user);
  const [selected, setSelected] = useState(null);
  const [open, setOpen] = useState(false);
  const [txnOpen, setTxnOpen] = useState(false);
  const [form, setForm] = useState({ name: "", firm: "", trade: "", project_id: "", contact: "", contract_value: "", retention_percent: "5" });
  const [txn, setTxn] = useState({ type: "payment", amount: "", note: "" });

  const { data: subs, isLoading } = useQuery({ queryKey: ["subcontractors"], queryFn: async () => (await api.get("/subcontractors")).data });
  const { data: projects } = useQuery({ queryKey: ["projects"], queryFn: async () => (await api.get("/projects")).data });
  const pname = (id) => projects?.find((p) => p.id === id)?.name || "—";

  const detail = useQuery({
    queryKey: ["subcontractor", selected?.id],
    queryFn: async () => (await api.get(`/subcontractors/${selected.id}`)).data,
    enabled: !!selected,
  });

  const addSub = useMutation({
    mutationFn: async () => (await api.post("/subcontractors", { ...form, contract_value: parseFloat(form.contract_value) || 0, retention_percent: parseFloat(form.retention_percent) || 0, project_id: form.project_id || null })).data,
    onSuccess: () => { toast.success("Subcontractor added"); qc.invalidateQueries({ queryKey: ["subcontractors"] }); setOpen(false); setForm({ name: "", firm: "", trade: "", project_id: "", contact: "", contract_value: "", retention_percent: "5" }); },
  });
  const addTxn = useMutation({
    mutationFn: async () => (await api.post(`/subcontractors/${selected.id}/transactions`, { type: txn.type, amount: parseFloat(txn.amount) || 0, note: txn.note })).data,
    onSuccess: () => { toast.success("Entry recorded"); qc.invalidateQueries(); setTxnOpen(false); setTxn({ type: "payment", amount: "", note: "" }); },
  });
  const del = useMutation({
    mutationFn: async (id) => (await api.delete(`/subcontractors/${id}`)).data,
    onSuccess: () => { toast.success("Removed"); qc.invalidateQueries({ queryKey: ["subcontractors"] }); },
  });

  const inputCls = "w-full border-2 border-[#E4E4E7] focus:border-[#EA580C] outline-none px-3 py-2.5 text-sm transition-colors duration-200 bg-white";

  if (isLoading) return <Spinner />;

  // DETAIL VIEW
  if (selected) {
    const d = detail.data;
    const s = d?.summary || {};
    return (
      <div className="p-5 sm:p-8">
        <button data-testid="back-to-subs" onClick={() => setSelected(null)} className="flex items-center gap-2 text-sm font-semibold text-[#71717A] hover:text-[#09090B] mb-5 transition-colors duration-200"><ArrowLeft size={16} weight="bold" /> All subcontractors</button>
        <PageHeader
          overline="Contract Ledger"
          title={selected.name}
          desc={`${selected.firm || ""}${selected.firm ? " · " : ""}${selected.trade} · ${pname(selected.project_id)}${selected.contact ? " · " + selected.contact : ""}`}
          action={<button data-testid="add-subtxn-button" onClick={() => setTxnOpen(true)} className="flex items-center gap-2 bg-[#EA580C] text-white px-4 py-2.5 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200"><Plus size={16} weight="bold" /> Add entry</button>}
        />
        {detail.isLoading ? <Spinner /> : (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 border-t border-l border-[#E4E4E7] mb-6" data-testid="sub-summary">
              {[
                ["Contract Value", s.contract_value, false],
                ["Extra Work", s.extra_work, false],
                ["Gross Contract", s.gross, false],
                ["Material Recovered", s.material_recovered, false],
                ["Deductions", s.deductions, false],
                ["Retention Held", s.retention_held, false],
                ["Paid", s.paid, false],
                ["Pending", s.pending, true],
              ].map(([lab, val, acc]) => (
                <div key={lab} className="border-r border-b border-[#E4E4E7] p-5">
                  <p className="overline mb-2">{lab}</p>
                  <p className={`font-display font-black text-xl sm:text-2xl tracking-tight ${acc ? "text-[#EA580C]" : ""}`}>{fmt(val)}</p>
                </div>
              ))}
            </div>

            <div className="border border-[#E4E4E7]" data-testid="sub-ledger-table">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-[#E4E4E7] text-left">{["Date", "Type", "Note", "Amount"].map((h) => <th key={h} className="overline px-4 py-3">{h}</th>)}</tr></thead>
                <tbody>
                  {d?.transactions?.length === 0 && <tr><td colSpan={4} className="px-4 py-8 text-center text-[#71717A] text-sm">No entries yet.</td></tr>}
                  {d?.transactions?.map((tr) => (
                    <tr key={tr.id} className="border-b border-[#E4E4E7] hover:bg-[#FAFAFA] transition-colors duration-200">
                      <td className="px-4 py-3 font-mono text-[#71717A]">{tr.date}</td>
                      <td className="px-4 py-3"><Badge tone={toneFor(tr.type)}>{labelFor(tr.type)}</Badge></td>
                      <td className="px-4 py-3 text-[#71717A]">{tr.note || "—"}</td>
                      <td className="px-4 py-3 font-mono font-semibold">{fmt(tr.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        <Dialog open={txnOpen} onOpenChange={setTxnOpen}>
          <DialogContent className="rounded-none border-2 border-[#09090B]">
            <DialogHeader><DialogTitle className="font-display">Add ledger entry — {selected.name}</DialogTitle><DialogDescription>Record payment, extra work, material recovery, deduction or retention release.</DialogDescription></DialogHeader>
            <div className="space-y-3">
              <select data-testid="subtxn-type-select" className={inputCls} value={txn.type} onChange={(e) => setTxn({ ...txn, type: e.target.value })}>
                {TXN_TYPES.map((t) => <option key={t.v} value={t.v}>{t.l}</option>)}
              </select>
              <input data-testid="subtxn-amount-input" className={inputCls} type="number" placeholder={`Amount (${country.symbol})`} value={txn.amount} onChange={(e) => setTxn({ ...txn, amount: e.target.value })} />
              <input className={inputCls} placeholder="Note (e.g. 2nd running bill)" value={txn.note} onChange={(e) => setTxn({ ...txn, note: e.target.value })} />
            </div>
            <DialogFooter><button data-testid="save-subtxn-button" disabled={!(parseFloat(txn.amount) > 0) || addTxn.isPending} onClick={() => addTxn.mutate()} className="bg-[#EA580C] text-white px-5 py-2.5 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200 disabled:opacity-50">Record</button></DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    );
  }

  // LIST VIEW
  return (
    <div className="p-5 sm:p-8">
      <PageHeader
        overline="Subcontractor Accounting"
        title="Subcontractors"
        desc="Track contract value, extra work, owner-supplied material, retention and running payments — with live pending dues per subcontractor."
        action={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <button data-testid="add-sub-button" className="flex items-center gap-2 bg-[#EA580C] text-white px-4 py-2.5 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200"><Plus size={16} weight="bold" /> Add Subcontractor</button>
            </DialogTrigger>
            <DialogContent className="rounded-none border-2 border-[#09090B]">
              <DialogHeader><DialogTitle className="font-display">Add Subcontractor</DialogTitle><DialogDescription>Create a contract to track payments, retention and pending dues.</DialogDescription></DialogHeader>
              <div className="space-y-3">
                <input data-testid="sub-name-input" className={inputCls} placeholder="Contact person / crew name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
                <div className="grid grid-cols-2 gap-3">
                  <input className={inputCls} placeholder="Firm name" value={form.firm} onChange={(e) => setForm({ ...form, firm: e.target.value })} />
                  <input className={inputCls} placeholder="Trade (e.g. Masonry)" value={form.trade} onChange={(e) => setForm({ ...form, trade: e.target.value })} />
                </div>
                <select className={inputCls} value={form.project_id} onChange={(e) => setForm({ ...form, project_id: e.target.value })}>
                  <option value="">— Assign project —</option>
                  {projects?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
                <input className={inputCls} placeholder="Contact number" value={form.contact} onChange={(e) => setForm({ ...form, contact: e.target.value })} />
                <div className="grid grid-cols-2 gap-3">
                  <input data-testid="sub-contract-input" className={inputCls} type="number" placeholder={`Contract value (${country.symbol})`} value={form.contract_value} onChange={(e) => setForm({ ...form, contract_value: e.target.value })} />
                  <input data-testid="sub-retention-input" className={inputCls} type="number" placeholder="Retention %" value={form.retention_percent} onChange={(e) => setForm({ ...form, retention_percent: e.target.value })} />
                </div>
              </div>
              <DialogFooter><button data-testid="save-sub-button" disabled={!form.name || addSub.isPending} onClick={() => addSub.mutate()} className="bg-[#EA580C] text-white px-5 py-2.5 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200 disabled:opacity-50">{addSub.isPending ? "Saving…" : "Add"}</button></DialogFooter>
            </DialogContent>
          </Dialog>
        }
      />

      {subs?.length === 0 ? (
        <div className="border border-[#E4E4E7] p-12 text-center">
          <Handshake size={36} weight="duotone" className="mx-auto text-[#EA580C] mb-3" />
          <p className="text-[#71717A] text-sm">No subcontractors yet. Add your first contract to start tracking dues and retention.</p>
        </div>
      ) : (
        <div className="border border-[#E4E4E7] overflow-x-auto" data-testid="subs-table">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#E4E4E7] text-left">
                {["Subcontractor", "Trade", "Project", "Contract", "Retention", "Paid", "Pending", ""].map((h) => <th key={h} className="overline px-4 py-3">{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {subs?.map((s) => (
                <tr key={s.id} data-testid={`sub-row-${s.id}`} onClick={() => setSelected(s)} className="border-b border-[#E4E4E7] hover:bg-[#FFF7ED] cursor-pointer transition-colors duration-200">
                  <td className="px-4 py-3">
                    <p className="font-semibold">{s.name}</p>
                    <p className="text-xs text-[#71717A]">{s.firm}</p>
                  </td>
                  <td className="px-4 py-3 text-[#71717A]">{s.trade}</td>
                  <td className="px-4 py-3"><Badge tone="accent">{pname(s.project_id)}</Badge></td>
                  <td className="px-4 py-3 font-mono">{fmt(s.summary?.gross)}</td>
                  <td className="px-4 py-3 font-mono text-[#71717A]">{fmt(s.summary?.retention_held)}</td>
                  <td className="px-4 py-3 font-mono">{fmt(s.summary?.paid)}</td>
                  <td className="px-4 py-3 font-mono font-bold text-[#EA580C]">{fmt(s.summary?.pending)}</td>
                  <td className="px-4 py-3 text-right">
                    <button data-testid={`delete-sub-${s.id}`} onClick={(e) => { e.stopPropagation(); del.mutate(s.id); }} className="text-[#71717A] hover:text-[#DC2626] transition-colors duration-200"><Trash size={16} weight="bold" /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
