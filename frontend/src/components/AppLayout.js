import React, { useState, useEffect } from "react";
import { Outlet, NavLink, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import CommandBar from "@/components/CommandBar";
import AIAssistant from "@/components/AIAssistant";
import NotificationBell from "@/components/NotificationBell";
import {
  HardHat, SquaresFour, UsersThree, Money, ShieldCheck,
  ListChecks, Brain, SignOut, Sparkle, Handshake, Broadcast, ChartLineUp, ClipboardText,
  DotsThreeCircle, X, UserCircle,
} from "@phosphor-icons/react";

const nav = [
  { to: "/dashboard", label: "Command Center", icon: SquaresFour },
  { to: "/workforce", label: "Workforce", icon: UsersThree },
  { to: "/payroll", label: "Payroll & Settlements", icon: Money },
  { to: "/subcontractors", label: "Subcontractors", icon: Handshake },
  { to: "/reports", label: "Daily Reports", icon: ClipboardText },
  { to: "/insights", label: "Predictive Insights", icon: ChartLineUp },
  { to: "/compliance", label: "Compliance Agent", icon: ShieldCheck },
  { to: "/feed", label: "Regulation Feed", icon: Broadcast },
  { to: "/sops", label: "SOP Generator", icon: ListChecks },
  { to: "/knowledge", label: "Org Memory", icon: Brain },
];

const mobileTabs = [
  { to: "/dashboard", label: "Home", icon: SquaresFour },
  { to: "/workforce", label: "Workforce", icon: UsersThree },
  { to: "/reports", label: "Reports", icon: ClipboardText },
  { to: "/payroll", label: "Payroll", icon: Money },
];

function MoreSheet({ open, onClose, onLogout, user }) {
  const navigate = useNavigate();
  const location = useLocation();
  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [open]);
  if (!open) return null;
  const rest = nav.filter((n) => !mobileTabs.some((t) => t.to === n.to));
  const go = (to) => { onClose(); navigate(to); };
  return (
    <div className="fixed inset-0 z-50 md:hidden" data-testid="mobile-more-sheet">
      <div className="absolute inset-0 bg-black/40 fade-in" onClick={onClose} />
      <div className="absolute bottom-0 inset-x-0 bg-white border-t-2 border-[#09090B] sheet-up safe-bottom max-h-[85vh] overflow-y-auto">
        <div className="flex items-center justify-between px-5 pt-4 pb-2">
          <p className="overline">All modules</p>
          <button data-testid="close-more-sheet" onClick={onClose} className="p-2 -m-2 text-[#71717A] press"><X size={20} weight="bold" /></button>
        </div>
        <div className="grid grid-cols-3 gap-2 px-4 pb-3">
          {rest.map((n) => {
            const active = location.pathname === n.to;
            return (
              <button
                key={n.to}
                data-testid={`more-nav-${n.to.replace("/", "")}`}
                onClick={() => go(n.to)}
                className={`press flex flex-col items-center gap-1.5 border-2 px-2 py-4 text-[11px] font-semibold text-center leading-tight ${
                  active ? "border-[#EA580C] bg-[#FFF7ED] text-[#09090B]" : "border-[#E4E4E7] text-[#3f3f46]"
                }`}
              >
                <n.icon size={22} weight="duotone" className={active ? "text-[#EA580C]" : "text-[#71717A]"} />
                {n.label}
              </button>
            );
          })}
        </div>
        <div className="border-t border-[#E4E4E7] px-4 py-3 flex items-center gap-3">
          <button data-testid="mobile-profile-link" onClick={() => go("/profile")} className="press flex-1 flex items-center gap-3 text-left p-2 -m-2">
            {user?.picture ? (
              <img src={user.picture} alt="" className="w-9 h-9 object-cover shrink-0" />
            ) : (
              <div className="w-9 h-9 bg-[#09090B] text-white flex items-center justify-center text-xs font-bold shrink-0">{user?.name?.[0] || "U"}</div>
            )}
            <div className="min-w-0">
              <p className="text-sm font-semibold truncate flex items-center gap-1.5">
                {user?.name || "Profile"}
                <UserCircle size={14} className="text-[#71717A]" />
              </p>
              <p className="text-xs text-[#71717A] truncate">{user?.email}</p>
            </div>
          </button>
          <button data-testid="mobile-logout" onClick={onLogout} className="press flex items-center gap-1.5 text-xs font-semibold text-[#71717A] border border-[#E4E4E7] px-3 py-2">
            <SignOut size={15} weight="bold" /> Sign out
          </button>
        </div>
      </div>
    </div>
  );
}

export default function AppLayout() {
  const { user, logout } = useAuth();
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const [chipVisible, setChipVisible] = useState(false);
  useEffect(() => {
    if (location.pathname === "/dashboard") {
      setChipVisible(false);
      const t = setTimeout(() => setChipVisible(true), 220);
      const h = setTimeout(() => setChipVisible(false), 6000);
      return () => { clearTimeout(t); clearTimeout(h); };
    }
    setChipVisible(false);
  }, [location.pathname]);
  useEffect(() => { setMoreOpen(false); }, [location.pathname]);

  return (
    <div className="min-h-screen flex bg-white">
      {/* Sidebar (desktop) */}
      <aside className="w-64 shrink-0 border-r border-[#E4E4E7] flex-col hidden md:flex sticky top-0 h-screen">
        <div className="h-16 flex items-center gap-3 px-5 border-b border-[#E4E4E7]">
          <div className="w-8 h-8 bg-[#EA580C] flex items-center justify-center">
            <HardHat size={20} weight="fill" color="#fff" />
          </div>
          <span className="font-display font-extrabold tracking-tight">KARYA<span className="text-[#EA580C]">.</span></span>
        </div>
        <nav className="flex-1 py-4 overflow-y-auto">
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
          <button
            data-testid="profile-link"
            onClick={() => navigate("/profile")}
            className={`w-full flex items-center gap-3 mb-3 p-2 -m-2 text-left hover:bg-[#F4F4F5] transition-colors duration-200 ${location.pathname === "/profile" ? "bg-[#FFF7ED]" : ""}`}
            title="Open your profile"
          >
            {user?.picture ? (
              <img src={user.picture} alt="" className="w-8 h-8 object-cover shrink-0" />
            ) : (
              <div className="w-8 h-8 bg-[#09090B] text-white flex items-center justify-center text-xs font-bold shrink-0">
                {user?.name?.[0] || "U"}
              </div>
            )}
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold truncate flex items-center gap-1.5">
                {user?.name || "Set up profile"}
                {user?.profile_complete === false && (
                  <span data-testid="profile-incomplete-dot" className="w-1.5 h-1.5 bg-[#EA580C] shrink-0" title="Profile incomplete" />
                )}
              </p>
              <p data-testid="profile-email" className="text-xs text-[#71717A] truncate underline underline-offset-2 decoration-transparent hover:decoration-[#EA580C] transition-colors duration-200">
                {user?.email}
              </p>
            </div>
          </button>
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
        <header className="h-14 md:h-16 border-b border-[#E4E4E7] flex items-center gap-2 md:gap-3 px-3 sm:px-6 sticky top-0 bg-white z-40 safe-top">
          {/* mobile logo */}
          <button onClick={() => navigate("/dashboard")} className="md:hidden flex items-center gap-2 shrink-0 press" data-testid="mobile-logo">
            <div className="w-7 h-7 bg-[#EA580C] flex items-center justify-center">
              <HardHat size={16} weight="fill" color="#fff" />
            </div>
          </button>
          <CommandBar />
          {chipVisible && (
            <div
              data-testid="signed-in-chip"
              className="hidden md:flex items-center gap-2 border border-[#09090B] px-3 py-1.5 text-xs font-mono shrink-0 fade-up-fast"
            >
              <span className="w-1.5 h-1.5 bg-[#EA580C] pulse-dot" />
              Signed in as <span className="font-semibold text-[#09090B]">{user?.name?.split(" ")[0] || user?.email}</span>
            </div>
          )}
          <NotificationBell />
          <button
            data-testid="open-assistant-button"
            onClick={() => setAssistantOpen(true)}
            className="hidden sm:flex items-center gap-2 bg-[#09090B] text-white px-4 py-2.5 text-sm font-semibold hover:bg-[#EA580C] transition-colors duration-200 shrink-0"
          >
            <Sparkle size={16} weight="fill" /> Ask AI
          </button>
        </header>

        <main className="flex-1 overflow-x-hidden pb-24 md:pb-0">
          <Outlet />
        </main>
      </div>

      <AIAssistant open={assistantOpen} onClose={() => setAssistantOpen(false)} />

      {/* mobile AI FAB */}
      <button
        data-testid="mobile-ai-fab"
        onClick={() => setAssistantOpen(true)}
        className="sm:hidden fixed right-4 bottom-[84px] z-40 p-3.5 bg-[#09090B] text-white shadow-lg press"
        style={{ boxShadow: "4px 4px 0 #EA580C" }}
        aria-label="Ask AI"
      >
        <Sparkle size={22} weight="fill" />
      </button>

      {/* mobile bottom tab bar */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 bg-white border-t-2 border-[#09090B] flex z-40 safe-bottom" data-testid="mobile-bottom-nav">
        {mobileTabs.map((n) => {
          const active = location.pathname === n.to;
          return (
            <button
              key={n.to}
              data-testid={`mobile-tab-${n.to.replace("/", "")}`}
              onClick={() => navigate(n.to)}
              className={`press flex-1 flex flex-col items-center gap-0.5 pt-2 pb-1.5 text-[10px] font-semibold ${
                active ? "text-[#EA580C]" : "text-[#71717A]"
              }`}
            >
              <n.icon size={22} weight={active ? "fill" : "duotone"} />
              {n.label}
              <span className={`h-0.5 w-8 mt-0.5 ${active ? "bg-[#EA580C]" : "bg-transparent"}`} />
            </button>
          );
        })}
        <button
          data-testid="mobile-tab-more"
          onClick={() => setMoreOpen(true)}
          className={`press flex-1 flex flex-col items-center gap-0.5 pt-2 pb-1.5 text-[10px] font-semibold ${moreOpen ? "text-[#EA580C]" : "text-[#71717A]"}`}
        >
          <DotsThreeCircle size={22} weight="duotone" />
          More
          <span className="h-0.5 w-8 mt-0.5 bg-transparent" />
        </button>
      </nav>

      <MoreSheet open={moreOpen} onClose={() => setMoreOpen(false)} onLogout={logout} user={user} />
    </div>
  );
}
