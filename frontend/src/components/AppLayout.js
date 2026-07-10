import React, { useState } from "react";
import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import CommandBar from "@/components/CommandBar";
import AIAssistant from "@/components/AIAssistant";
import NotificationBell from "@/components/NotificationBell";
import {
  HardHat, SquaresFour, UsersThree, Money, ShieldCheck,
  ListChecks, Brain, SignOut, Sparkle, Handshake, Broadcast, ChartLineUp,
} from "@phosphor-icons/react";

const nav = [
  { to: "/dashboard", label: "Command Center", icon: SquaresFour },
  { to: "/workforce", label: "Workforce", icon: UsersThree },
  { to: "/payroll", label: "Payroll & Settlements", icon: Money },
  { to: "/subcontractors", label: "Subcontractors", icon: Handshake },
  { to: "/insights", label: "Predictive Insights", icon: ChartLineUp },
  { to: "/compliance", label: "Compliance Agent", icon: ShieldCheck },
  { to: "/feed", label: "Regulation Feed", icon: Broadcast },
  { to: "/sops", label: "SOP Generator", icon: ListChecks },
  { to: "/knowledge", label: "Org Memory", icon: Brain },
];

export default function AppLayout() {
  const { user, logout } = useAuth();
  const [assistantOpen, setAssistantOpen] = useState(false);
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex bg-white">
      {/* Sidebar */}
      <aside className="w-64 shrink-0 border-r border-[#E4E4E7] flex-col hidden md:flex sticky top-0 h-screen">
        <div className="h-16 flex items-center gap-3 px-5 border-b border-[#E4E4E7]">
          <div className="w-8 h-8 bg-[#EA580C] flex items-center justify-center">
            <HardHat size={20} weight="fill" color="#fff" />
          </div>
          <span className="font-display font-extrabold tracking-tight">KARYA<span className="text-[#EA580C]">.</span></span>
        </div>
        <nav className="flex-1 py-4">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              data-testid={`nav-${n.to.replace("/", "")}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-5 py-3 text-sm font-medium border-l-2 transition-colors duration-200 ${
                  isActive
                    ? "border-[#EA580C] bg-[#FFF7ED] text-[#09090B]"
                    : "border-transparent text-[#71717A] hover:text-[#09090B] hover:bg-[#F4F4F5]"
                }`
              }
            >
              <n.icon size={18} weight="duotone" />
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-[#E4E4E7] p-4">
          <div className="flex items-center gap-3 mb-3">
            {user?.picture ? (
              <img src={user.picture} alt="" className="w-8 h-8 object-cover" />
            ) : (
              <div className="w-8 h-8 bg-[#09090B] text-white flex items-center justify-center text-xs font-bold">
                {user?.name?.[0] || "U"}
              </div>
            )}
            <div className="min-w-0">
              <p className="text-sm font-semibold truncate">{user?.name}</p>
              <p className="text-xs text-[#71717A] truncate">{user?.company_name}</p>
            </div>
          </div>
          <button
            data-testid="logout-button"
            onClick={logout}
            className="flex items-center gap-2 text-xs font-semibold text-[#71717A] hover:text-[#DC2626] transition-colors duration-200"
          >
            <SignOut size={16} weight="bold" /> Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 min-w-0 flex flex-col">
        {/* Top bar with command bar */}
        <header className="h-16 border-b border-[#E4E4E7] flex items-center gap-3 px-4 sm:px-6 sticky top-0 bg-white z-40">
          <CommandBar />
          <NotificationBell />
          <button
            data-testid="open-assistant-button"
            onClick={() => setAssistantOpen(true)}
            className="hidden sm:flex items-center gap-2 bg-[#09090B] text-white px-4 py-2.5 text-sm font-semibold hover:bg-[#EA580C] transition-colors duration-200 shrink-0"
          >
            <Sparkle size={16} weight="fill" /> Ask AI
          </button>
        </header>

        <main className="flex-1 overflow-x-hidden">
          <Outlet />
        </main>
      </div>

      <AIAssistant open={assistantOpen} onClose={() => setAssistantOpen(false)} />

      {/* mobile bottom nav */}
      <div className="md:hidden fixed bottom-0 inset-x-0 bg-white border-t border-[#E4E4E7] flex z-40">
        {nav.slice(0, 5).map((n) => (
          <button
            key={n.to}
            onClick={() => navigate(n.to)}
            className="flex-1 flex flex-col items-center py-2 text-[#71717A]"
          >
            <n.icon size={20} weight="duotone" />
          </button>
        ))}
      </div>
    </div>
  );
}
