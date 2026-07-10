import React, { useEffect } from "react";
import api, { setToken } from "@/lib/api";

// Module-scoped guard: survives React StrictMode double-mount so we
// never POST the one-time session_id to the backend more than once.
let inFlight = false;

export default function AuthCallback() {
  useEffect(() => {
    if (inFlight) return;
    inFlight = true;

    const hash = window.location.hash;
    const sessionId = new URLSearchParams(hash.replace("#", "")).get("session_id");
    if (!sessionId) {
      window.location.replace("/");
      return;
    }
    (async () => {
      try {
        const res = await api.post("/auth/session", { session_id: sessionId });
        if (res.data?.session_token) setToken(res.data.session_token);
        // Hard redirect so /auth/me runs on a clean URL (no hash), with the new
        // Bearer token already in localStorage.
        window.location.replace("/dashboard");
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error("[AuthCallback] session exchange failed:", e?.response?.status, e?.response?.data);
        window.location.replace("/?auth_error=" + encodeURIComponent(e?.response?.data?.detail || e?.message || "unknown"));
      }
    })();
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-white">
      <div className="text-center">
        <div className="w-3 h-3 bg-[#EA580C] mx-auto mb-4 pulse-dot" />
        <p className="overline">Signing you in…</p>
      </div>
    </div>
  );
}
