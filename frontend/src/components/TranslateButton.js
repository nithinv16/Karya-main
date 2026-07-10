import React, { useState } from "react";
import api from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Translate as TranslateIcon, ArrowClockwise } from "@phosphor-icons/react";
import { toast } from "sonner";

/**
 * Reusable translate button — feed it any text and it renders a small button
 * that swaps in a translated version below the original when clicked.
 * If the user language is English, it stays a no-op.
 */
export default function TranslateButton({ text, contextLabel = "" }) {
  const { lang, t } = useI18n();
  const [translated, setTranslated] = useState(null);
  const [showing, setShowing] = useState(false);
  const [busy, setBusy] = useState(false);

  if (!text || lang === "en") return null;

  const doTranslate = async () => {
    if (translated) {
      setShowing((s) => !s);
      return;
    }
    setBusy(true);
    try {
      const res = await api.post("/translate", { text, target_lang: lang, context: contextLabel });
      setTranslated(res.data.translated || "");
      setShowing(true);
    } catch (e) {
      toast.error(e?.response?.data?.detail || t("translate.failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div data-testid="translate-container">
      <button
        data-testid="translate-button"
        onClick={doTranslate}
        disabled={busy}
        className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-[#EA580C] hover:text-[#C2410C] transition-colors duration-200 disabled:opacity-50"
      >
        {busy ? <ArrowClockwise size={13} weight="bold" className="animate-spin" /> : <TranslateIcon size={13} weight="bold" />}
        {showing && translated ? t("translate.original") : t("translate.button")}
      </button>
      {showing && translated && (
        <div data-testid="translate-content" className="mt-2 p-3 border-l-2 border-[#EA580C] bg-[#FFF7ED] text-sm text-[#3f3f46] whitespace-pre-line leading-relaxed">
          {translated}
        </div>
      )}
    </div>
  );
}
