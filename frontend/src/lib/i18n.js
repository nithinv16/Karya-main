// Lightweight i18n for Karya. No external deps — just static dictionaries
// plus a runtime `t(key)` helper wired into a React context (I18nProvider).
//
// Supported languages: English (en), Hindi (hi), Malayalam (ml), Tamil (ta), Telugu (te).
// Only the SHELL is pre-translated (nav labels, buttons, headings, common toasts).
// Dynamic user content (worker names, report bodies, SOP text) is translated on
// demand via POST /api/translate — see components/TranslateButton.js.

import React, { createContext, useContext, useEffect, useMemo, useState, useCallback } from "react";
import en from "./locales/en.json";
import hi from "./locales/hi.json";
import ml from "./locales/ml.json";
import ta from "./locales/ta.json";
import te from "./locales/te.json";

export const LANGUAGES = [
  { code: "en", label: "English", native: "English" },
  { code: "hi", label: "Hindi", native: "हिन्दी" },
  { code: "ml", label: "Malayalam", native: "മലയാളം" },
  { code: "ta", label: "Tamil", native: "தமிழ்" },
  { code: "te", label: "Telugu", native: "తెలుగు" },
];

const DICTS = { en, hi, ml, ta, te };
const STORAGE_KEY = "karya_lang";

export const isSupported = (code) => !!DICTS[code];

const I18nContext = createContext({
  lang: "en",
  setLang: () => {},
  t: (k) => k,
});

export function I18nProvider({ children, userLang }) {
  const initial =
    (userLang && isSupported(userLang) && userLang) ||
    (typeof window !== "undefined" && window.localStorage.getItem(STORAGE_KEY)) ||
    "en";
  const [lang, setLangState] = useState(isSupported(initial) ? initial : "en");

  // Keep in sync with the auth user's saved language when it changes.
  useEffect(() => {
    if (userLang && isSupported(userLang) && userLang !== lang) {
      setLangState(userLang);
      try { localStorage.setItem(STORAGE_KEY, userLang); } catch { /* localStorage may be unavailable in private browsing */ }
    }
  }, [userLang, lang]);

  const setLang = useCallback((code) => {
    if (!isSupported(code)) return;
    setLangState(code);
    try { localStorage.setItem(STORAGE_KEY, code); } catch { /* localStorage may be unavailable in private browsing */ }
  }, []);

  const t = useCallback((key, fallback) => {
    const dict = DICTS[lang] || DICTS.en;
    if (dict[key] != null) return dict[key];
    if (DICTS.en[key] != null) return DICTS.en[key];
    return fallback != null ? fallback : key;
  }, [lang]);

  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  return useContext(I18nContext);
}
