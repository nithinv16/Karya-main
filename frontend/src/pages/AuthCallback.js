import React, { useEffect, useRef } from "react";
import api from "@/lib/api";

export default function AuthCallback() {
  const processed = useRef(false);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;

    const hash = window.location.hash;
    const sessionId = new URLSearchParams(hash.replace("#", "")).get("session_id");
    if (!sessionId) {
      window.location.replace("/");
      return;
    }
    (async () => {
      try {
        await api.post("/auth/session", { session_id: sessionId });
        // Hard redirect so cookie-based /auth/me runs on a clean URL (no hash),
        // avoiding router timing issues between setUser + navigate.
        window.location.replace("/dashboard");
      } catch (e) {
        window.location.replace("/");
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
