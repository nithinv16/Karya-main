import React from "react";
import { GoogleLogo, HardHat, Microphone, ShieldCheck, Brain } from "@phosphor-icons/react";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
const handleLogin = () => {
  const redirectUrl = window.location.origin + "/dashboard";
  window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
};

const features = [
  { icon: HardHat, t: "Workforce Intelligence", d: "Workers, crews, multi-rate payroll & instant settlements." },
  { icon: ShieldCheck, t: "Compliance Agent", d: "AI tracks permits, licenses & deadlines before they expire." },
  { icon: Brain, t: "Org Memory + SOPs", d: "Capture tacit knowledge. Generate SOPs from a voice note." },
  { icon: Microphone, t: "Voice-First Ops", d: "Command your site in plain Hindi, Tamil, Malayalam & more." },
];

export default function Login() {
  const authError = new URLSearchParams(window.location.search).get("auth_error");
  const copyDiagnostics = async () => {
    const info = [
      `time: ${new Date().toISOString()}`,
      `origin: ${window.location.origin}`,
      `backend: ${process.env.REACT_APP_BACKEND_URL || "(unset)"}`,
      `user_agent: ${navigator.userAgent}`,
      `auth_error: ${authError || "(none)"}`,
    ].join("\n");
    try {
      await navigator.clipboard.writeText(info);
    } catch (e) {
      // fallback if clipboard blocked
      window.prompt("Copy diagnostics:", info);
    }
  };
  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      {/* Left: brand + form */}
      <div className="flex flex-col justify-between p-8 lg:p-14 grid-bg">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-[#EA580C] flex items-center justify-center">
            <HardHat size={22} weight="fill" color="#fff" />
          </div>
          <span className="font-display font-extrabold text-lg tracking-tight">KARYA<span className="text-[#EA580C]">.</span></span>
        </div>

        <div className="max-w-md fade-up">
          <p className="overline mb-4">AI Operating System · Construction</p>
          <h1 className="font-display font-black text-4xl sm:text-5xl tracking-tighter leading-none mb-5">
            <span className="text-[#EA580C]">Karya</span> — where work actually gets done.
          </h1>
          <p className="text-[#71717A] text-base leading-relaxed mb-8">
            Labour, wages, compliance, SOPs and institutional memory — unified into one AI-native platform built for India's informal construction workforce.
          </p>
          <button
            data-testid="google-login-button"
            onClick={handleLogin}
            className="group flex items-center gap-3 bg-[#09090B] text-white px-6 py-4 font-semibold hover:bg-[#EA580C] transition-colors duration-200"
          >
            <GoogleLogo size={20} weight="bold" />
            Continue with Google
          </button>
          <p className="text-xs text-[#71717A] mt-4">No setup. Sign in and start running your operations on live data.</p>
          {authError && (
            <div data-testid="auth-error-banner" className="mt-4 border border-red-500 bg-red-50 p-3 text-xs text-red-800 max-w-md break-all">
              <strong className="block mb-1">Sign-in failed:</strong>
              {authError}
              <button
                data-testid="copy-diagnostics-btn"
                type="button"
                onClick={copyDiagnostics}
                className="mt-2 inline-block underline underline-offset-2 text-red-900 hover:text-red-700"
              >
                Copy diagnostics
              </button>
            </div>
          )}
        </div>

        <p className="text-xs text-[#71717A]">Built for contractors, builders, MEP & civil firms across emerging markets.</p>
      </div>

      {/* Right: image + features */}
      <div className="relative hidden lg:block">
        <img
          src="https://images.pexels.com/photos/4170184/pexels-photo-4170184.jpeg"
          alt="Construction site"
          className="absolute inset-0 w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-black/65" />
        <div className="relative h-full flex flex-col justify-end p-14">
          <div className="grid grid-cols-2 gap-px bg-white/15 border border-white/15">
            {features.map((f, i) => (
              <div key={i} className="bg-black/70 backdrop-blur-sm p-6">
                <f.icon size={26} weight="duotone" color="#EA580C" />
                <h3 className="font-display font-bold text-white text-base mt-3 mb-1">{f.t}</h3>
                <p className="text-white/60 text-sm leading-snug">{f.d}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
