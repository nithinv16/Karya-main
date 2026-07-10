import React, { useState, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";
import { toast } from "sonner";
import { CheckCircle, WarningCircle, FloppyDisk, PencilSimple } from "@phosphor-icons/react";
import { COUNTRIES } from "@/lib/country";

const ROLES = ["Contractor", "Builder / Developer", "MEP", "Civil", "Interiors / Fit-out", "Facility Maintenance", "Other"];
const REQUIRED = ["name", "phone"];
const RECOMMENDED = ["company_name", "role", "address", "default_client_phone"];

const inputCls = "w-full border-2 border-[#E4E4E7] focus:border-[#EA580C] outline-none px-3 py-2.5 text-sm transition-colors duration-200 bg-white disabled:bg-[#FAFAFA] disabled:text-[#3f3f46] mt-1";
const labelCls = "text-[11px] font-semibold text-[#71717A] uppercase tracking-wide";
const hintCls = "text-[11px] text-[#71717A] mt-1";

export default function Profile() {
  const { user, setUser } = useAuth();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    name: "", phone: "", company_name: "", address: "", role: "", default_client_phone: "",
    country: "IN", language: "en", ramadan_mode: false,
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (user) {
      setForm({
        name: user.name || "",
        phone: user.phone || "",
        company_name: user.company_name || "",
        address: user.address || "",
        role: user.role || "",
        default_client_phone: user.default_client_phone || "",
        country: user.country || "IN",
        language: user.language || "en",
        ramadan_mode: !!user.ramadan_mode,
      });
    }
  }, [user]);

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
      toast.success("Profile updated");
      setEditing(false);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Couldn't save profile");
    } finally {
      setSaving(false);
    }
  };

  const cancel = () => {
    setForm({
      name: user?.name || "", phone: user?.phone || "", company_name: user?.company_name || "",
      address: user?.address || "", role: user?.role || "", default_client_phone: user?.default_client_phone || "",
      country: user?.country || "IN", language: user?.language || "en", ramadan_mode: !!user?.ramadan_mode,
    });
    setEditing(false);
  };

  if (!user) return null;

  const missingReq = REQUIRED.filter((k) => !((user[k] || "").toString().trim()));
  const missingRec = RECOMMENDED.filter((k) => !((user[k] || "").toString().trim()));
  const complete = user.profile_complete && missingReq.length === 0;
  const disabled = !editing;
  const onChange = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <div className="max-w-3xl mx-auto p-6 sm:p-10 fade-up">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <p className="overline mb-2">Your profile</p>
          <h1 className="font-display font-black text-4xl tracking-tighter leading-none">
            {user.name || "Set up your profile"}
          </h1>
          <p className="text-sm text-[#71717A] mt-2">{user.email}</p>
        </div>
        {user.picture && <img src={user.picture} alt="" className="w-16 h-16 object-cover border border-[#E4E4E7]" />}
      </div>

      <div
        data-testid="profile-status-banner"
        className={`border-l-4 p-4 mb-6 flex items-start gap-3 ${
          complete ? "border-green-600 bg-green-50" : "border-[#EA580C] bg-[#FFF7ED]"
        }`}
      >
        {complete ? (
          <CheckCircle size={22} weight="fill" className="text-green-600 shrink-0" />
        ) : (
          <WarningCircle size={22} weight="fill" className="text-[#EA580C] shrink-0" />
        )}
        <div className="text-sm">
          {complete ? (
            <>
              <p className="font-semibold">Your profile is complete.</p>
              <p className="text-[#71717A] mt-0.5">
                {missingRec.length > 0
                  ? `Optional: add ${missingRec.length} more field${missingRec.length === 1 ? "" : "s"} (${missingRec.join(", ")}) to help us route WhatsApp and alerts better.`
                  : "All the details are on file."}
              </p>
            </>
          ) : (
            <>
              <p className="font-semibold">Your profile is incomplete.</p>
              <p className="text-[#71717A] mt-0.5">
                Missing: <span className="font-semibold text-[#09090B]">{missingReq.join(", ")}</span>. Fill these in to unlock WhatsApp auto-send and alerts.
              </p>
            </>
          )}
        </div>
      </div>

      <form onSubmit={save} className="space-y-4">
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>Full name *</label>
            <input data-testid="profile-name" className={inputCls} value={form.name} onChange={onChange("name")} placeholder="Your full name" disabled={disabled} />
          </div>
          <div>
            <label className={labelCls}>Phone (WhatsApp) *</label>
            <input data-testid="profile-phone" className={inputCls} value={form.phone} onChange={onChange("phone")} placeholder="+91 98xxxxxxxx" disabled={disabled} />
            <p className={hintCls}>Used for WhatsApp alerts and to appear as sender in reports.</p>
          </div>
          <div>
            <label className={labelCls}>Company / firm</label>
            <input data-testid="profile-company_name" className={inputCls} value={form.company_name} onChange={onChange("company_name")} placeholder="ABC Construction Pvt. Ltd." disabled={disabled} />
          </div>
          <div>
            <label className={labelCls}>Role / trade</label>
            <select data-testid="profile-role" className={inputCls} value={form.role} onChange={onChange("role")} disabled={disabled}>
              <option value="">Select…</option>
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <div>
            <label className={labelCls}>Default client WhatsApp</label>
            <input data-testid="profile-default_client_phone" className={inputCls} value={form.default_client_phone} onChange={onChange("default_client_phone")} placeholder="+91 98xxxxxxxx" disabled={disabled} />
            <p className={hintCls}>Used by the &quot;Send now&quot; button on Daily Reports.</p>
          </div>
          <div className="sm:col-span-2">
            <label className={labelCls}>Email (from Google)</label>
            <input data-testid="profile-email-field" className={inputCls} value={user.email || ""} disabled />
          </div>
          <div className="sm:col-span-2">
            <label className={labelCls}>Office address</label>
            <textarea data-testid="profile-address" className={inputCls + " min-h-20"} value={form.address} onChange={onChange("address")} placeholder="Street, city, state, PIN" disabled={disabled} />
          </div>

          <div className="sm:col-span-2 pt-2">
            <label className={labelCls}>Country / region</label>
            <div className="grid grid-cols-2 gap-2 mt-1" data-testid="profile-country-selector">
              {Object.values(COUNTRIES).map((c) => (
                <button
                  key={c.code}
                  type="button"
                  data-testid={`profile-country-${c.code}`}
                  disabled={disabled}
                  onClick={() => setForm((f) => ({ ...f, country: c.code }))}
                  className={`flex items-center gap-3 px-4 py-2.5 border-2 transition-colors duration-200 text-left disabled:opacity-60 ${
                    form.country === c.code ? "border-[#EA580C] bg-[#FFF7ED]" : "border-[#E4E4E7] bg-white hover:border-[#09090B]"
                  }`}
                >
                  <span className="text-xl leading-none">{c.flag}</span>
                  <div className="min-w-0">
                    <p className="font-display font-bold text-sm">{c.name}</p>
                    <p className="text-[11px] text-[#71717A]">{c.currency} · {c.dial}</p>
                  </div>
                </button>
              ))}
            </div>
            <p className={hintCls}>Switching country changes your currency, compliance categories and regulation feed sources.</p>
          </div>

          {form.country === "AE" && (
            <div className="sm:col-span-2">
              <label className={`flex items-center gap-3 border-2 p-3 transition-colors duration-200 ${disabled ? "border-[#E4E4E7] bg-[#FAFAFA]" : "border-[#E4E4E7] hover:border-[#EA580C] cursor-pointer"}`} data-testid="profile-ramadan-toggle">
                <input type="checkbox" disabled={disabled} checked={form.ramadan_mode} onChange={(e) => setForm({ ...form, ramadan_mode: e.target.checked })} className="w-4 h-4 accent-[#EA580C]" />
                <div>
                  <p className="text-sm font-semibold">Ramadan-adjusted work hours</p>
                  <p className={hintCls}>Reduces default shift to 6 hours and factors prayer breaks into attendance during Ramadan.</p>
                </div>
              </label>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3 pt-2">
          {!editing ? (
            <button
              data-testid="profile-edit-button"
              type="button"
              onClick={() => setEditing(true)}
              className="flex items-center gap-2 bg-[#09090B] text-white px-5 py-2.5 text-sm font-semibold hover:bg-[#EA580C] transition-colors duration-200"
            >
              <PencilSimple size={16} weight="bold" /> Edit profile
            </button>
          ) : (
            <>
              <button
                data-testid="profile-save-button"
                type="submit"
                disabled={saving}
                className="flex items-center gap-2 bg-[#EA580C] text-white px-5 py-2.5 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200 disabled:opacity-50"
              >
                <FloppyDisk size={16} weight="fill" /> {saving ? "Saving…" : "Save changes"}
              </button>
              <button
                data-testid="profile-cancel-button"
                type="button"
                onClick={cancel}
                className="text-sm text-[#71717A] hover:text-[#09090B] transition-colors duration-200"
              >
                Cancel
              </button>
            </>
          )}
        </div>
      </form>
    </div>
  );
}
