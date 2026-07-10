import React, { useState, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";
import { toast } from "sonner";
import { CheckCircle, WarningCircle, FloppyDisk, PencilSimple } from "@phosphor-icons/react";

const ROLES = ["Contractor", "Builder / Developer", "MEP", "Civil", "Interiors / Fit-out", "Facility Maintenance", "Other"];

const REQUIRED = ["name", "phone"];
const RECOMMENDED = ["company_name", "role", "address", "default_client_phone"];

export default function Profile() {
  const { user, setUser } = useAuth();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    name: "", phone: "", company_name: "", address: "", role: "", default_client_phone: "",
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
      });
    }
  }, [user]);

  const inputCls = "w-full border-2 border-[#E4E4E7] focus:border-[#EA580C] outline-none px-3 py-2.5 text-sm transition-colors duration-200 bg-white disabled:bg-[#FAFAFA] disabled:text-[#3f3f46]";

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
    });
    setEditing(false);
  };

  if (!user) return null;

  const missingReq = REQUIRED.filter((k) => !((user[k] || "").trim && user[k].trim()));
  const missingRec = RECOMMENDED.filter((k) => !((user[k] || "").trim && user[k].trim()));
  const complete = user.profile_complete && missingReq.length === 0;

  const Field = ({ label, k, type = "text", placeholder, disabled = false, wide = false, hint }) => (
    <div className={wide ? "sm:col-span-2" : ""}>
      <label className="text-[11px] font-semibold text-[#71717A] uppercase tracking-wide">{label}</label>
      {type === "textarea" ? (
        <textarea
          data-testid={`profile-${k}`}
          className={inputCls + " mt-1 min-h-20"}
          value={form[k]}
          onChange={(e) => setForm({ ...form, [k]: e.target.value })}
          placeholder={placeholder}
          disabled={disabled || !editing}
        />
      ) : type === "select" ? (
        <select
          data-testid={`profile-${k}`}
          className={inputCls + " mt-1"}
          value={form[k]}
          onChange={(e) => setForm({ ...form, [k]: e.target.value })}
          disabled={disabled || !editing}
        >
          <option value="">Select…</option>
          {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
      ) : (
        <input
          data-testid={`profile-${k}`}
          className={inputCls + " mt-1"}
          value={form[k]}
          onChange={(e) => setForm({ ...form, [k]: e.target.value })}
          placeholder={placeholder}
          disabled={disabled || !editing}
        />
      )}
      {hint && <p className="text-[11px] text-[#71717A] mt-1">{hint}</p>}
    </div>
  );

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

      {/* Status banner */}
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
                {missingRec.length > 0 && `Optional: add ${missingRec.length} more field${missingRec.length === 1 ? "" : "s"} (${missingRec.join(", ")}) to help us route WhatsApp and alerts better.`}
                {missingRec.length === 0 && "All the details are on file."}
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
          <Field label="Full name *" k="name" placeholder="Your full name" />
          <Field label="Phone (WhatsApp) *" k="phone" placeholder="+91 98xxxxxxxx" hint="Used for WhatsApp alerts and to appear as sender in reports." />
          <Field label="Company / firm" k="company_name" placeholder="ABC Construction Pvt. Ltd." />
          <Field label="Role / trade" k="role" type="select" />
          <Field label="Default client WhatsApp" k="default_client_phone" placeholder="+91 98xxxxxxxx" hint="Used by the 'Send now' button on Daily Reports." />
          <div className="sm:col-span-2">
            <label className="text-[11px] font-semibold text-[#71717A] uppercase tracking-wide">Email (from Google)</label>
            <input data-testid="profile-email-field" className={inputCls + " mt-1"} value={user.email || ""} disabled />
          </div>
          <Field label="Office address" k="address" type="textarea" wide placeholder="Street, city, state, PIN" />
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
