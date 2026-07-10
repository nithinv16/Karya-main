import React from "react";

export function PageHeader({ overline, title, desc, action }) {
  return (
    <div className="flex items-start justify-between gap-4 mb-6 fade-up">
      <div>
        <p className="overline mb-2">{overline}</p>
        <h1 className="font-display font-black text-3xl sm:text-4xl tracking-tighter leading-none">{title}</h1>
        {desc && <p className="text-[#71717A] text-sm mt-2 max-w-xl">{desc}</p>}
      </div>
      {action}
    </div>
  );
}

export function Stat({ label, value, sub, accent }) {
  return (
    <div className="border-r border-b border-[#E4E4E7] p-5 hover:bg-[#FAFAFA] transition-colors duration-200">
      <p className="overline mb-2">{label}</p>
      <p className={`font-display font-black text-2xl sm:text-3xl tracking-tight ${accent ? "text-[#EA580C]" : "text-[#09090B]"}`}>{value}</p>
      {sub && <p className="text-xs text-[#71717A] mt-1">{sub}</p>}
    </div>
  );
}

export function Badge({ children, tone = "neutral" }) {
  const tones = {
    neutral: "bg-[#F4F4F5] text-[#71717A] border-[#E4E4E7]",
    success: "bg-[#F0FDF4] text-[#16A34A] border-[#16A34A]/30",
    warning: "bg-[#FEFCE8] text-[#A16207] border-[#EAB308]/40",
    critical: "bg-[#FEF2F2] text-[#DC2626] border-[#DC2626]/30",
    accent: "bg-[#FFF7ED] text-[#EA580C] border-[#EA580C]/30",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 text-xs font-semibold border ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function Spinner() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="w-3 h-3 bg-[#EA580C] pulse-dot" />
    </div>
  );
}
