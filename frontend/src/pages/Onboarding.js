import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";
import { toast } from "sonner";
import { HardHat, ArrowRight } from "@phosphor-icons/react";

const ROLES = ["Contractor", "Builder / Developer", "MEP", "Civil", "Interiors / Fit-out", "Facility Maintenance", "Other"];

export default function Onboarding() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: user?.name || "",
    phone: user?.phone || "",
    company_name: user?.company_name || "",
    address: user?.address || "",
    role: user?.role || "",
    default_client_phone: user?.default_client_phone || "",
  });
  const [saving, setSaving] = useState(false);

  const inputCls = "w-full border-2 border-[#E4E4E7] focus:border-[#EA580C] outline-none px-3 py-2.5 text-sm transition-colors duration-200 bg-white";

  const save = async (e) => {
    e.preventDefault();
    if (!form.name.trim() || !form.phone.trim()) {
      toast.error("Name and phone are required");
      return;
    }
    setSaving(true);
    try {
      const res = await api.put("/auth/profile", form);
      setUser(res.data);
      toast.success("Profile complete — welcome to Karya");
      navigate("/dashboard", { replace: true });
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Couldn't save profile");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-5 bg-white">
      <div className="lg:col-span-2 hidden lg:flex flex-col justify-between p-14 relative overflow-hidden">
        <div className="absolute inset-0 grid-bg opacity-60" />
        <div className="relative">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-[#EA580C] flex items-center justify-center">
              <HardHat size={22} weight="fill" color="#fff" />
            </div>
            <span className="font-display font-extrabold text-lg tracking-tight">KARYA<span className="text-[#EA580C]">.</span></span>
          </div>
        </div>
        <div className="relative">
          <p className="overline mb-3">One-time setup</p>
          <h1 className="font-display font-black text-4xl tracking-tighter leading-none mb-4">
            Set up your <span className="text-[#EA580C]">command centre.</span>
          </h1>
          <p className="text-[#71717A] text-sm leading-relaxed max-w-sm">
            A few details so we can route wages, WhatsApp updates, compliance alerts and SOPs to the right people on your team.
          </p>
        </div>
        <p className="relative text-xs text-[#71717A]">Everything is editable later from your profile.</p>
      </div>

      <div className="lg:col-span-3 flex items-center justify-center p-6 sm:p-10">
        <form onSubmit={save} data-testid="onboarding-form" className="w-full max-w-lg fade-up">
          <p className="overline mb-2">Complete your profile</p>
          <h2 className="font-display font-black text-3xl tracking-tighter leading-none mb-6">
            Welcome, {user?.name?.split(" ")[0] || "there"}.
          </h2>

          <div className="space-y-3">
            <div>
              <label className="text-xs font-semibold text-[#71717A] uppercase tracking-wide">Full name *</label>
              <input data-testid="ob-name" className={inputCls + " mt-1"} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Your full name" />
            </div>
            <div>
              <label className="text-xs font-semibold text-[#71717A] uppercase tracking-wide">Phone (WhatsApp) *</label>
              <input data-testid="ob-phone" className={inputCls + " mt-1"} value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="+91 98xxxxxxxx" />
              <p className="text-[11px] text-[#71717A] mt-1">Used for alerts and to appear in reports we send on your behalf.</p>
            </div>
            <div>
              <label className="text-xs font-semibold text-[#71717A] uppercase tracking-wide">Company / firm</label>
              <input data-testid="ob-company" className={inputCls + " mt-1"} value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} placeholder="ABC Construction Pvt. Ltd." />
            </div>
            <div className="grid sm:grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-semibold text-[#71717A] uppercase tracking-wide">Role / trade</label>
                <select data-testid="ob-role" className={inputCls + " mt-1"} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                  <option value="">Select…</option>
                  {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-semibold text-[#71717A] uppercase tracking-wide">Default client WhatsApp</label>
                <input data-testid="ob-default-client" className={inputCls + " mt-1"} value={form.default_client_phone} onChange={(e) => setForm({ ...form, default_client_phone: e.target.value })} placeholder="+91 98xxxxxxxx (optional)" />
              </div>
            </div>
            <div>
              <label className="text-xs font-semibold text-[#71717A] uppercase tracking-wide">Office address</label>
              <textarea data-testid="ob-address" className={inputCls + " mt-1 min-h-20"} value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} placeholder="Street, city, state, PIN" />
            </div>
          </div>

          <button
            data-testid="ob-submit"
            type="submit"
            disabled={saving}
            className="mt-6 group flex items-center gap-3 bg-[#09090B] text-white px-6 py-3.5 font-semibold hover:bg-[#EA580C] transition-colors duration-200 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Continue to Karya"} <ArrowRight size={18} weight="bold" />
          </button>
        </form>
      </div>
    </div>
  );
}
