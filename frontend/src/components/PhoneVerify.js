import React, { useCallback, useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { CheckCircle, ShieldCheck, PaperPlaneTilt, ArrowClockwise } from "@phosphor-icons/react";

export default function PhoneVerify() {
  const { user, setUser } = useAuth();
  const [status, setStatus] = useState(null);
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState("idle"); // idle | sent | done
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await api.get("/profile/phone/verify/status");
      setStatus(res.data);
      setPhone(res.data.phone || user?.phone || "");
    } catch (e) {
      // Status stays null, section renders nothing.
      if (process.env.NODE_ENV !== "production") console.warn("Phone verify status failed:", e);
    }
  }, [user?.phone]);

  useEffect(() => { load(); }, [load]);

  const startVerify = async () => {
    if (!phone.trim()) { toast.error("Enter your phone number"); return; }
    setBusy(true);
    try {
      const res = await api.post("/profile/phone/verify/start", { phone: phone.trim() });
      toast.success("Code sent — check your SMS");
      setPhone(res.data.phone);
      setStep("sent");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Couldn't send code");
    } finally { setBusy(false); }
  };

  const checkVerify = async () => {
    if (!code.trim()) { toast.error("Enter the 6-digit code"); return; }
    setBusy(true);
    try {
      const res = await api.post("/profile/phone/verify/check", { phone: phone.trim(), code: code.trim() });
      if (res.data.verified) {
        toast.success("Phone verified");
        if (res.data.user) setUser(res.data.user);
        setStep("done");
        await load();
      } else {
        toast.error("That code was wrong. Try again or resend.");
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Verification failed");
    } finally { setBusy(false); }
  };

  if (!status) return null;

  const verified = status.phone_verified;

  return (
    <div data-testid="phone-verify-card" className="border-2 border-[#09090B] mt-8">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-[#E4E4E7] bg-[#F4F4F5]">
        <div className="w-9 h-9 bg-[#16A34A] flex items-center justify-center shrink-0">
          <ShieldCheck size={20} weight="fill" color="#fff" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-display font-bold text-base leading-tight">Verify your phone</p>
          <p className="text-xs text-[#71717A]">Required to send WhatsApp reports from your account via Twilio.</p>
        </div>
        {verified && (
          <span data-testid="phone-verified-badge" className="flex items-center gap-1.5 text-xs font-bold text-[#16A34A] bg-[#F0FDF4] border border-[#16A34A]/30 px-2 py-1 shrink-0">
            <CheckCircle size={14} weight="fill" /> Verified
          </span>
        )}
      </div>

      <div className="p-5">
        {!status.verify_available ? (
          <p className="text-sm text-[#71717A]">
            Phone verification isn&apos;t configured on the server yet. Ask the admin to set <span className="font-mono text-xs bg-[#F4F4F5] px-1.5 py-0.5">TWILIO_VERIFY_SERVICE_SID</span> in the backend environment.
          </p>
        ) : verified ? (
          <div className="space-y-3">
            <p className="text-sm">Verified as <span className="font-mono text-xs bg-[#F4F4F5] px-1.5 py-0.5">{status.phone}</span>. You can now send WhatsApp reports from your Karya account.</p>
            <button
              data-testid="phone-verify-restart"
              onClick={() => { setStep("idle"); setCode(""); }}
              className="flex items-center gap-2 text-xs font-semibold text-[#71717A] hover:text-[#09090B] transition-colors duration-200"
            >
              <ArrowClockwise size={14} weight="bold" /> Verify a different number
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <label className="text-[11px] font-semibold text-[#71717A] uppercase tracking-wide">Phone (international format)</label>
              <input
                data-testid="phone-verify-input"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+919876543210"
                disabled={step === "sent" || busy}
                className="w-full border-2 border-[#E4E4E7] focus:border-[#EA580C] outline-none px-3 py-2.5 text-sm mt-1 bg-white disabled:bg-[#FAFAFA]"
              />
              <p className="text-[11px] text-[#71717A] mt-1">Start with your country code, e.g. +91 (India), +971 (UAE).</p>
            </div>
            {step === "sent" && (
              <div>
                <label className="text-[11px] font-semibold text-[#71717A] uppercase tracking-wide">6-digit code from SMS</label>
                <input
                  data-testid="phone-verify-code-input"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 8))}
                  placeholder="123456"
                  inputMode="numeric"
                  className="w-full border-2 border-[#E4E4E7] focus:border-[#EA580C] outline-none px-3 py-2.5 text-lg font-mono tracking-widest mt-1"
                />
              </div>
            )}
            <div className="flex flex-wrap items-center gap-3">
              {step !== "sent" ? (
                <button
                  data-testid="phone-verify-send"
                  onClick={startVerify}
                  disabled={busy}
                  className="flex items-center gap-2 bg-[#09090B] text-white px-5 py-2.5 text-sm font-semibold hover:bg-[#EA580C] transition-colors duration-200 disabled:opacity-50"
                >
                  <PaperPlaneTilt size={16} weight="fill" /> {busy ? "Sending…" : "Send code"}
                </button>
              ) : (
                <>
                  <button
                    data-testid="phone-verify-check"
                    onClick={checkVerify}
                    disabled={busy || code.length < 4}
                    className="flex items-center gap-2 bg-[#EA580C] text-white px-5 py-2.5 text-sm font-semibold hover:bg-[#C2410C] transition-colors duration-200 disabled:opacity-50"
                  >
                    <CheckCircle size={16} weight="fill" /> {busy ? "Verifying…" : "Verify"}
                  </button>
                  <button
                    data-testid="phone-verify-resend"
                    onClick={startVerify}
                    disabled={busy}
                    className="text-xs font-semibold text-[#71717A] hover:text-[#09090B] transition-colors duration-200"
                  >
                    Resend
                  </button>
                  <button
                    data-testid="phone-verify-change"
                    onClick={() => { setStep("idle"); setCode(""); }}
                    className="text-xs font-semibold text-[#71717A] hover:text-[#09090B] transition-colors duration-200"
                  >
                    Change number
                  </button>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
