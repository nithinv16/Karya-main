import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { toast } from "sonner";
import { Bell, Clock, ShieldCheck, CurrencyCircleDollar, Sun } from "@phosphor-icons/react";

const WEEKDAYS = [
  { d: 1, label: "Mon" },
  { d: 2, label: "Tue" },
  { d: 3, label: "Wed" },
  { d: 4, label: "Thu" },
  { d: 5, label: "Fri" },
  { d: 6, label: "Sat" },
  { d: 7, label: "Sun" },
];

// Small curated timezone list — covers Karya's main markets. Fallback: freeform input.
const TZ_OPTIONS = [
  "Asia/Kolkata",
  "Asia/Dubai",
  "Asia/Karachi",
  "Asia/Colombo",
  "Asia/Kathmandu",
  "Asia/Dhaka",
  "Asia/Singapore",
  "Europe/London",
  "UTC",
];

const inputCls = "border-2 border-[#E4E4E7] focus:border-[#EA580C] outline-none px-3 py-2 text-sm transition-colors duration-200 bg-white";

function Row({ icon: Icon, title, subtitle, enabled, onToggle, children, testId }) {
  return (
    <div className="border border-[#E4E4E7] bg-white p-4" data-testid={testId}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 min-w-0 flex-1">
          <div className="w-9 h-9 shrink-0 bg-[#FFF7ED] flex items-center justify-center">
            <Icon size={18} weight="duotone" className="text-[#EA580C]" />
          </div>
          <div className="min-w-0">
            <p className="font-display font-bold text-sm">{title}</p>
            <p className="text-xs text-[#71717A] mt-0.5 leading-snug">{subtitle}</p>
          </div>
        </div>
        <label className="inline-flex items-center cursor-pointer shrink-0" data-testid={`${testId}-switch`}>
          <input
            type="checkbox"
            checked={!!enabled}
            onChange={(e) => onToggle(e.target.checked)}
            className="sr-only peer"
          />
          <span className="relative w-10 h-6 bg-[#E4E4E7] transition-colors duration-200 peer-checked:bg-[#EA580C]">
            <span
              className={`absolute top-0.5 w-5 h-5 bg-white transition-transform duration-200 ${enabled ? "translate-x-4" : "translate-x-0.5"}`}
            />
          </span>
        </label>
      </div>
      {enabled && children && (
        <div className="mt-3 pl-12" data-testid={`${testId}-detail`}>
          {children}
        </div>
      )}
    </div>
  );
}

export default function TelegramNotifications() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["tg-notifications"],
    queryFn: async () => (await api.get("/telegram/notifications")).data,
  });

  const [prefs, setPrefs] = useState(null);

  useEffect(() => {
    if (data?.notifications) setPrefs(data.notifications);
  }, [data]);

  const save = useMutation({
    mutationFn: async (patch) => (await api.put("/telegram/notifications", patch)).data,
    onSuccess: (res) => {
      setPrefs(res.notifications);
      qc.invalidateQueries({ queryKey: ["tg-notifications"] });
      toast.success("Notification preferences saved");
    },
    onError: (e) => toast.error(e?.response?.data?.detail || "Couldn't save"),
  });

  if (isLoading || !prefs) return null;
  const linked = !!data?.telegram_linked;

  const patchAndSave = (patch) => {
    // Optimistic local update + debounce would be nicer, but instant PUT keeps
    // things simple and avoids stale-state pitfalls with the toggle switches.
    setPrefs((p) => ({
      ...p,
      ...Object.keys(patch).reduce((acc, k) => {
        acc[k] = typeof patch[k] === "object" && !Array.isArray(patch[k]) && p?.[k]
          ? { ...p[k], ...patch[k] }
          : patch[k];
        return acc;
      }, {}),
    }));
    save.mutate(patch);
  };

  const toggleDay = (d) => {
    const cur = prefs.payroll_reminder?.days || [];
    const next = cur.includes(d) ? cur.filter((x) => x !== d) : [...cur, d].sort();
    patchAndSave({ payroll_reminder: { days: next } });
  };

  return (
    <section className="mt-8 border-2 border-[#E4E4E7]" data-testid="telegram-notifications">
      <div className="bg-[#09090B] text-white px-5 py-4 flex items-center gap-2">
        <Bell size={18} weight="fill" className="text-[#EA580C]" />
        <h2 className="font-display font-bold">Proactive Telegram pings</h2>
      </div>
      <div className="p-5 space-y-4">
        {!linked && (
          <div className="border-l-4 border-[#EA580C] bg-[#FFF7ED] p-3 text-xs text-[#3f3f46]" data-testid="tg-not-linked-hint">
            Link Telegram above to start receiving these pings — you can pre-configure them anyway.
          </div>
        )}

        <div className="grid sm:grid-cols-2 gap-3" data-testid="tg-tz-row">
          <div>
            <label className="text-[11px] font-semibold text-[#71717A] uppercase tracking-wide">Timezone</label>
            <select
              data-testid="tg-timezone"
              className={inputCls + " w-full mt-1"}
              value={prefs.timezone}
              onChange={(e) => patchAndSave({ timezone: e.target.value })}
            >
              {TZ_OPTIONS.map((tz) => <option key={tz} value={tz}>{tz}</option>)}
              {!TZ_OPTIONS.includes(prefs.timezone) && <option value={prefs.timezone}>{prefs.timezone}</option>}
            </select>
            <p className="text-[11px] text-[#71717A] mt-1">All ping times use this timezone.</p>
          </div>
        </div>

        <Row
          icon={Sun}
          title="Morning briefing"
          subtitle="A quick daily summary at your chosen time — active workers, upcoming compliance deadlines, pending payroll."
          enabled={prefs.morning_briefing?.enabled}
          onToggle={(v) => patchAndSave({ morning_briefing: { enabled: v } })}
          testId="pref-morning"
        >
          <div className="flex items-center gap-2 text-xs">
            <Clock size={13} weight="bold" className="text-[#71717A]" />
            <span className="text-[#71717A]">Send at</span>
            <input
              data-testid="pref-morning-time"
              type="time"
              value={prefs.morning_briefing?.time || "08:00"}
              onChange={(e) => patchAndSave({ morning_briefing: { time: e.target.value } })}
              className={inputCls + " w-28"}
            />
          </div>
        </Row>

        <Row
          icon={ShieldCheck}
          title="Compliance deadline alerts"
          subtitle="Nudges when a compliance item is due in 3 days, 1 day, or today — sent around 09:00 in your timezone."
          enabled={prefs.compliance_alerts?.enabled}
          onToggle={(v) => patchAndSave({ compliance_alerts: { enabled: v } })}
          testId="pref-compliance"
        />

        <Row
          icon={CurrencyCircleDollar}
          title="Payroll dues reminder"
          subtitle="Digest of pending settlements to workers, sent on selected weekdays."
          enabled={prefs.payroll_reminder?.enabled}
          onToggle={(v) => patchAndSave({ payroll_reminder: { enabled: v } })}
          testId="pref-payroll"
        >
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs">
              <Clock size={13} weight="bold" className="text-[#71717A]" />
              <span className="text-[#71717A]">Send at</span>
              <input
                data-testid="pref-payroll-time"
                type="time"
                value={prefs.payroll_reminder?.time || "09:00"}
                onChange={(e) => patchAndSave({ payroll_reminder: { time: e.target.value } })}
                className={inputCls + " w-28"}
              />
            </div>
            <div className="flex flex-wrap gap-1.5" data-testid="pref-payroll-days">
              {WEEKDAYS.map((w) => {
                const active = (prefs.payroll_reminder?.days || []).includes(w.d);
                return (
                  <button
                    key={w.d}
                    type="button"
                    data-testid={`pref-payroll-day-${w.d}`}
                    onClick={() => toggleDay(w.d)}
                    className={`px-2.5 py-1 text-[11px] font-semibold border-2 transition-colors duration-150 ${active ? "border-[#EA580C] bg-[#EA580C] text-white" : "border-[#E4E4E7] bg-white text-[#71717A] hover:border-[#09090B]"}`}
                  >
                    {w.label}
                  </button>
                );
              })}
            </div>
          </div>
        </Row>

        <p className="text-[11px] text-[#71717A]">
          All pings are localized to your saved app language and can be turned off individually. You'll never get duplicate reminders on the same day.
        </p>
      </div>
    </section>
  );
}
