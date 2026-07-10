import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { PageHeader, Badge, Spinner } from "@/components/ui-bits";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Money, Plus, ArrowLeft } from "@phosphor-icons/react";
import { toast } from "sonner";

const fmt = (n) => "₹" + Math.round(n || 0).toLocaleString("en-IN");
const TXN_TYPES = ["payment", "advance", "bonus", "deduction", "food", "accommodation", "transport", "penalty", "wage"];
const toneFor = (t) => (["payment", "wage", "bonus"].includes(t) ? "success" : t === "advance" ? "warning" : "critical");

export default function Payroll() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState(null);
  const [open, setOpen] = useState(false);
  const [txn, setTxn] = useState({ type: "payment", amount: "", note: "" });

  const { data: workers, isLoading } = useQuery({ queryKey: ["workers"], queryFn: async () => (await api.get("/workers")).data });
  const { data: txns } = useQuery({ queryKey: ["transactions"], queryFn: async () => (await api.get("/transactions")).data });

  const ledger = useQuery({
    queryKey: ["ledger", selected?.id],
    queryFn: async () => (await api.get(`/workers/${selected.id}/ledger`)).data,
    enabled: !!selected,
  });

  const balanceFor = (wid) => {
    const ts = (txns || []).filter((t) => t.worker_id === wid);
    const earned = ts.filter((t) => ["wage", "payment", "bonus"].includes(t.type)).reduce((s, t) => s + t.amount, 0);
    const adv = ts.filter((t) => t.type === "advance").reduce((s, t) => s + t.amount, 0);
    const ded = ts.filter((t) => ["deduction", "food", "accommodation", "transport", "penalty"].includes(t.type)).reduce((s, t) => s + t.amount, 0);
    return earned - adv - ded;
  };

  const addTxn = useMutation({
    mutationFn: async () => (await api.post("/transactions", { worker_id: selected.id, type: txn.type, amount: parseFloat(txn.amount) || 0, note: txn.note })).data,
    onSuccess: () => { toast.success("Recorded"); qc.invalidateQueries(); setOpen(false); setTxn({ type: "payment", amount: "", note: "" }); },
  });

  if (isLoading) return <Spinner />;
  const inputCls = "w-full border-2 border-[#E4E4E7] focus:border-[#EA580C] outline-none px-3 py-2.5 text-sm transition-colors duration-200 bg-white";

  if (selected) {
    const L = ledger.data;
    return (
      <div className="p-5 sm:p-8">
        <button data-testid="back-to-payroll" onClick={() => setSelected(null)} className="flex items-center gap-2 text-sm font-semibold text-[#71717A] hover:text-[#09090B] mb-5 transition-colors duration-200"><ArrowLeft size={16} weight="bold" /> All settlements</button>
        <PageHeader
          overline="Settlement Ledger"
          title={selected.name}
          desc={`${selected.role} · ₹${selected.rate?.toLocaleString("en-IN")}/${selected.rate_type}`}
          action={<button data-testid="add-txn-button" onClick={() => setOpen(true)} className="flex items-center gap-2 bg-[#EA580C] text-white px-4 py-2.5 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200"><Plus size={16} weight="bold" /> Add entry</button>}
        />
        {ledger.isLoading ? <Spinner /> : (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 border-t border-l border-[#E4E4E7] mb-6">
              {[["Earned", L?.earned, false], ["Advances", L?.advances, false], ["Deductions", L?.deductions, false], ["Net Payable", L?.balance, true]].map(([lab, val, acc]) => (
                <div key={lab} className="border-r border-b border-[#E4E4E7] p-5">
                  <p className="overline mb-2">{lab}</p>
                  <p className={`font-display font-black text-2xl tracking-tight ${acc ? "text-[#EA580C]" : ""}`}>{fmt(val)}</p>
                </div>
              ))}
            </div>
            <div className="border border-[#E4E4E7]" data-testid="ledger-table">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-[#E4E4E7] text-left">{["Date", "Type", "Note", "Amount"].map((h) => <th key={h} className="overline px-4 py-3">{h}</th>)}</tr></thead>
                <tbody>
                  {L?.transactions?.length === 0 && <tr><td colSpan={4} className="px-4 py-8 text-center text-[#71717A] text-sm">No entries yet.</td></tr>}
                  {L?.transactions?.map((tr) => (
                    <tr key={tr.id} className="border-b border-[#E4E4E7] hover:bg-[#FAFAFA] transition-colors duration-200">
                      <td className="px-4 py-3 font-mono text-[#71717A]">{tr.date}</td>
                      <td className="px-4 py-3"><Badge tone={toneFor(tr.type)}>{tr.type}</Badge></td>
                      <td className="px-4 py-3 text-[#71717A]">{tr.note || "—"}</td>
                      <td className="px-4 py-3 font-mono font-semibold">{fmt(tr.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogContent className="rounded-none border-2 border-[#09090B]">
            <DialogHeader><DialogTitle className="font-display">Add ledger entry — {selected.name}</DialogTitle><DialogDescription>Record a wage, payment, advance, bonus or deduction.</DialogDescription></DialogHeader>
            <div className="space-y-3">
              <select data-testid="txn-type-select" className={inputCls} value={txn.type} onChange={(e) => setTxn({ ...txn, type: e.target.value })}>
                {TXN_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
              <input data-testid="txn-amount-input" className={inputCls} type="number" placeholder="Amount (₹)" value={txn.amount} onChange={(e) => setTxn({ ...txn, amount: e.target.value })} />
              <input className={inputCls} placeholder="Note (optional)" value={txn.note} onChange={(e) => setTxn({ ...txn, note: e.target.value })} />
            </div>
            <DialogFooter>
              <button data-testid="save-txn-button" disabled={!txn.amount || addTxn.isPending} onClick={() => addTxn.mutate()} className="bg-[#EA580C] text-white px-5 py-2.5 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200 disabled:opacity-50">Record</button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    );
  }

  return (
    <div className="p-5 sm:p-8">
      <PageHeader overline="Payroll & Settlements" title="Settlements" desc="Multi-rate wages, advances, deductions and live net payable for every worker. Click a worker to open their ledger." />
      {workers?.length === 0 ? (
        <div className="border border-[#E4E4E7] p-12 text-center"><Money size={36} weight="duotone" className="mx-auto text-[#EA580C] mb-3" /><p className="text-[#71717A] text-sm">No workers yet.</p></div>
      ) : (
        <div className="border border-[#E4E4E7] overflow-x-auto" data-testid="settlements-table">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-[#E4E4E7] text-left">{["Worker", "Trade", "Rate", "Net Payable", ""].map((h) => <th key={h} className="overline px-4 py-3">{h}</th>)}</tr></thead>
            <tbody>
              {workers?.map((w) => {
                const bal = balanceFor(w.id);
                return (
                  <tr key={w.id} data-testid={`settlement-row-${w.id}`} onClick={() => setSelected(w)} className="border-b border-[#E4E4E7] hover:bg-[#FFF7ED] cursor-pointer transition-colors duration-200">
                    <td className="px-4 py-3 font-semibold">{w.name}</td>
                    <td className="px-4 py-3 text-[#71717A]">{w.role}</td>
                    <td className="px-4 py-3 font-mono">₹{w.rate?.toLocaleString("en-IN")}/{w.rate_type}</td>
                    <td className="px-4 py-3 font-mono font-bold text-[#EA580C]">{fmt(bal)}</td>
                    <td className="px-4 py-3 text-right text-xs font-semibold text-[#71717A]">Open ledger →</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
