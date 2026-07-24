import React, { useCallback, useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { PaperPlaneTilt, LinkSimple, LinkBreak, CopySimple, CheckCircle } from "@phosphor-icons/react";

export default function TelegramConnect() {
  const [status, setStatus] = useState(null);
  const [code, setCode] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await api.get("/telegram/status");
      setStatus(res.data);
      if (res.data.linked) setCode(null);
    } catch (err) {
      if (process.env.NODE_ENV !== "production") console.warn("Telegram status check failed:", err);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!code || status?.linked) return;
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [code, status?.linked, load]);

  const generate = async () => {
    setBusy(true);
    try {
      const res = await api.post("/telegram/link/code");
      setCode(res.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Couldn't generate code");
    } finally {
      setBusy(false);
    }
  };

  const unlink = async () => {
    setBusy(true);
    try {
      await api.post("/telegram/link/unlink");
      toast.success("Telegram disconnected");
      setCode(null);
      await load();
    } catch {
      toast.error("Couldn't unlink");
    } finally {
      setBusy(false);
    }
  };

  const copy = () => {
    navigator.clipboard?.writeText(`/start ${code.code}`);
    toast.success("Copied — paste it in the Telegram chat");
  };

  if (!status) return null;

  return (
    <div data-testid="telegram-connect-card" className="border-2 border-[#09090B] mt-8">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-[#E4E4E7] bg-[#F4F4F5]">
        <div className="w-9 h-9 bg-[#229ED9] flex items-center justify-center shrink-0">
          <PaperPlaneTilt size={20} weight="fill" color="#fff" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-display font-bold text-base leading-tight">Telegram Assistant</p>
          <p className="text-xs text-[#71717A]">Send voice notes, photos, receipts & documents — the AI files them for you.</p>
        </div>
        {status.linked && (
          <span data-testid="telegram-linked-badge" className="flex items-center gap-1.5 text-xs font-bold text-[#16A34A] bg-[#F0FDF4] border border-[#16A34A]/30 px-2 py-1 shrink-0">
            <CheckCircle size={14} weight="fill" /> Linked
          </span>
        )}
      </div>

      <div className="p-5">
        {!status.configured ? (
          <p className="text-sm text-[#71717A]">Telegram bot is not configured on the server yet.</p>
        ) : status.linked ? (
          <div className="space-y-3">
            <p className="text-sm">
              Connected{status.telegram_username ? <> as <span className="font-semibold">@{status.telegram_username}</span></> : ""}. Message the bot anytime — try <span className="font-mono text-xs bg-[#F4F4F5] px-1.5 py-0.5">"Ramesh took an advance of ₹500"</span> or send a receipt photo.
            </p>
            <button
              data-testid="telegram-unlink-button"
              onClick={unlink}
              disabled={busy}
              className="flex items-center gap-2 text-xs font-semibold text-[#71717A] hover:text-[#DC2626] transition-colors duration-200 disabled:opacity-50"
            >
              <LinkBreak size={14} weight="bold" /> Disconnect Telegram
            </button>
          </div>
        ) : code ? (
          <div className="space-y-4">
            <div className="flex items-center gap-3 flex-wrap">
              <div data-testid="telegram-link-code" className="font-mono text-2xl font-bold tracking-[0.3em] border-2 border-dashed border-[#EA580C] bg-[#FFF7ED] px-4 py-2">
                {code.code}
              </div>
              <button data-testid="telegram-copy-code" onClick={copy} className="flex items-center gap-1.5 text-xs font-semibold text-[#71717A] hover:text-[#09090B] transition-colors duration-200">
                <CopySimple size={14} weight="bold" /> Copy /start command
              </button>
            </div>
            <ol className="text-sm text-[#71717A] space-y-1 list-decimal pl-4">
              <li>Open the bot in Telegram{code.bot_username ? <> (<span className="font-semibold">@{code.bot_username}</span>)</> : ""}</li>
              <li>Send <span className="font-mono text-xs bg-[#F4F4F5] px-1.5 py-0.5">/start {code.code}</span></li>
              <li>That's it — this page updates automatically once linked.</li>
            </ol>
            {code.deep_link && (
              <a
                data-testid="telegram-open-button"
                href={code.deep_link}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 bg-[#229ED9] text-white px-5 py-2.5 text-sm font-semibold hover:opacity-90 transition-opacity duration-200"
              >
                <PaperPlaneTilt size={16} weight="fill" /> Open Telegram & Link
              </a>
            )}
            <p className="text-[11px] text-[#71717A]">Code valid for 15 minutes. <span className="pulse-dot inline-block w-1.5 h-1.5 bg-[#EA580C] mx-1" /> Waiting for you to link…</p>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-[#71717A]">
              Link your Telegram to run Karya from your pocket: log advances by voice, forward receipts, upload worker IDs — the AI asks what to do and files everything in the right place.
            </p>
            <button
              data-testid="telegram-generate-code"
              onClick={generate}
              disabled={busy}
              className="flex items-center gap-2 bg-[#09090B] text-white px-5 py-2.5 text-sm font-semibold hover:bg-[#229ED9] transition-colors duration-200 disabled:opacity-50"
            >
              <LinkSimple size={16} weight="bold" /> {busy ? "Generating…" : "Connect Telegram"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
