import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { Bell, Warning, X, Check } from "@phosphor-icons/react";

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();
  const navigate = useNavigate();

  const { data } = useQuery({
    queryKey: ["notifications"],
    queryFn: async () => (await api.get("/notifications")).data,
    refetchInterval: 60000,
  });

  const dismiss = useMutation({
    mutationFn: async (key) => (await api.post("/notifications/dismiss", { key })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const unread = data?.unread || 0;
  const active = (data?.notifications || []).filter((n) => !n.dismissed);
  const tone = (s) => (s === "critical" ? "text-[#DC2626] border-[#DC2626]" : s === "warning" ? "text-[#A16207] border-[#EAB308]" : "text-[#71717A] border-[#E4E4E7]");

  return (
    <div className="relative shrink-0">
      <button
        data-testid="notification-bell"
        onClick={() => setOpen((v) => !v)}
        className="h-[42px] w-[42px] flex items-center justify-center border-2 border-[#09090B] hover:bg-[#09090B] hover:text-white transition-colors duration-200 relative"
        title="Notifications"
      >
        <Bell size={18} weight="fill" />
        {unread > 0 && (
          <span data-testid="notification-count" className="absolute -top-2 -right-2 bg-[#DC2626] text-white text-[10px] font-bold w-5 h-5 flex items-center justify-center">
            {unread}
          </span>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div data-testid="notification-panel" className="absolute right-0 top-12 w-[340px] bg-white border-2 border-[#09090B] z-50 max-h-[70vh] overflow-y-auto">
            <div className="flex items-center justify-between px-4 py-3 border-b border-[#E4E4E7] sticky top-0 bg-white">
              <p className="overline">Notifications</p>
              <button onClick={() => setOpen(false)} className="text-[#71717A] hover:text-[#09090B]"><X size={16} weight="bold" /></button>
            </div>
            {active.length === 0 ? (
              <div className="p-6 text-center text-sm text-[#71717A] flex flex-col items-center gap-2">
                <Check size={24} weight="bold" className="text-[#16A34A]" /> All clear. Nothing needs your attention.
              </div>
            ) : (
              active.map((n) => (
                <div key={n.key} data-testid="notification-item" className={`border-l-4 ${tone(n.severity)} border-b border-b-[#E4E4E7] p-3 hover:bg-[#FAFAFA] transition-colors duration-200`}>
                  <div className="flex items-start gap-2">
                    {n.severity === "critical" && <Warning size={15} weight="fill" className="text-[#DC2626] mt-0.5 shrink-0" />}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold leading-snug">{n.title}</p>
                      <p className={`text-xs font-bold mt-0.5 ${n.severity === "critical" ? "text-[#DC2626]" : "text-[#71717A]"}`}>{n.message}{n.due_date ? ` · ${n.due_date}` : ""}</p>
                      <div className="flex gap-3 mt-2">
                        <button onClick={() => { setOpen(false); navigate(n.link || "/compliance"); }} className="text-xs font-semibold text-[#EA580C] hover:underline">View →</button>
                        <button data-testid="notification-dismiss" onClick={() => dismiss.mutate(n.key)} className="text-xs font-semibold text-[#71717A] hover:text-[#09090B]">Dismiss</button>
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}
