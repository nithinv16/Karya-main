import React, { useMemo, useState } from "react";
import api from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { PageHeader } from "@/components/ui-bits";
import {
  MagnifyingGlass, Sparkle, Rocket, UsersThree, Money, ClipboardText,
  ListChecks, ShieldCheck, PaperPlaneTilt, WhatsappLogo, Question,
  Buildings, ChartLineUp, CaretDown, Brain, Handshake,
} from "@phosphor-icons/react";
import { toast } from "sonner";
import TranslateButton from "@/components/TranslateButton";

/**
 * Karya Help Center — self-contained, offline-capable docs.
 *
 * Content stays in English deliberately. Every article has a Translate button
 * that calls POST /api/translate with the user's current UI language, so we
 * only pay for LLM translation when the user actually wants it.
 */
const SECTIONS = [
  {
    id: "getting-started",
    icon: Rocket,
    title: "Getting Started",
    intro: "You can be up and running in about 5 minutes. Sign in with Google, complete your profile, and add your first project.",
    articles: [
      {
        q: "How do I sign in?",
        a: "Karya uses your Google account — no separate password to remember. On the login screen tap “Continue with Google”, pick the account you want to use for your business, and you're in. You can switch accounts anytime from Profile → Sign out.",
      },
      {
        q: "What information do I need to enter first?",
        a: "Open Profile and fill in: your name, WhatsApp number, company name, role, and your country (India or UAE). Your country decides your currency, your compliance categories, and which regulator news feed shows up. Save — that unlocks the rest of the app.",
      },
      {
        q: "How do I add my first project?",
        a: "Open Workforce → tap “Add project”. Give it a name (e.g. “Skyline Tower – Bandra”), location, client, budget and start date. You can add more projects later.",
      },
      {
        q: "What's the fastest way to try Karya?",
        a: "Add one project, add 3 workers under it, mark today's attendance, then generate a Daily Report — that walks you through everything the platform can do in under 3 minutes.",
      },
    ],
  },
  {
    id: "workforce",
    icon: UsersThree,
    title: "Workforce & Attendance",
    intro: "Track every worker on every site with wage rates, advances, documents and daily attendance.",
    articles: [
      {
        q: "How do I add a worker?",
        a: "Workforce → Add worker. Enter name, phone (optional), trade (mason, carpenter…), the project they're on, and their wage rate (per day, per hour, per sq ft or piece-rate). Onboarding fields like Aadhaar / Emirates ID and insurance can be added later.",
      },
      {
        q: "How does attendance work?",
        a: "On the Workforce page open a worker → “Mark attendance”. Or send Telegram / voice: “10 workers arrived at Skyline Tower today”, and Karya's AI parses it into attendance rows automatically. Attendance drives daily labour cost + payroll.",
      },
      {
        q: "How do worker documents get uploaded?",
        a: "Two ways: (1) In the web app, open a worker → Documents tab → drag files in. (2) On Telegram, send a photo/PDF, and the bot asks “what should I do with this?”. Pick “Worker file” → tell it whose file it is. It's attached to the worker profile automatically.",
      },
      {
        q: "What are advances?",
        a: "An advance is money paid to a worker before payroll is due. Karya keeps a running ledger — advances get deducted from their next settlement. Log an advance from the worker's card or via Telegram: “Ramesh took ₹5,000 advance”.",
      },
    ],
  },
  {
    id: "payroll",
    icon: Money,
    title: "Payroll & Settlements",
    intro: "Weekly, monthly or on-demand payroll. Karya computes net payable from attendance, wage rate, advances and deductions.",
    articles: [
      {
        q: "How is a worker's balance calculated?",
        a: "Attendance × wage rate = gross wages earned. Minus advances taken. Minus any deductions. Equals current balance owed. You see this live on each worker's card and on the Payroll page.",
      },
      {
        q: "How do I pay a worker?",
        a: "Payroll → find the worker → “Settle”. Enter the amount you're paying and the mode (cash, bank, UPI, WPS). It's logged as a payment transaction and the balance drops. You can also record via Telegram: “Pay Manoj ₹12,000”.",
      },
      {
        q: "What is retention money?",
        a: "For subcontractors — a % of each bill you hold back until project completion. Karya tracks retention balance per subcontractor and reminds you at handover.",
      },
    ],
  },
  {
    id: "reports",
    icon: ClipboardText,
    title: "Daily Reports",
    intro: "Turn a voice note + 2 photos into a polished daily site report you can send to clients via WhatsApp.",
    articles: [
      {
        q: "How do I create a daily report?",
        a: "Daily Reports → pick project → type or dictate what happened on site → attach 1–3 photos → tap Generate. AI writes a structured report (work done, materials, workforce, issues, next steps) in about 20 seconds.",
      },
      {
        q: "How do I send it on WhatsApp?",
        a: "Tick “Auto-send on WhatsApp when generated” before generating, or open a generated report and tap “Send on WhatsApp”. Recipients are pulled from the project's client / subcontractor phone numbers plus any extra numbers you paste in.",
      },
      {
        q: "Why did WhatsApp fail to send?",
        a: "During the Twilio Sandbox phase, each recipient must first WhatsApp `join <sandbox-code>` to +1 (415) 523-8886. Once they do, they're opted in. In production you'll use your own approved WhatsApp Business number and this step goes away.",
      },
      {
        q: "Can I send via Telegram instead?",
        a: "Yes. Once Telegram is linked, send `/report` in the bot — it generates today's report from your notes/photos and posts it back in-chat.",
      },
    ],
  },
  {
    id: "sops",
    icon: ListChecks,
    title: "SOP Generator",
    intro: "Standard Operating Procedures for any site activity — shuttering, curing, safety, handover — generated in your voice.",
    articles: [
      {
        q: "How does SOP generation work?",
        a: "SOP Generator → describe the activity (e.g. “concrete curing for slab in monsoon”) → tap Generate. Karya writes a step-by-step SOP with materials, safety checks, roles and QC checkpoints. Edit and save to your Org Memory.",
      },
      {
        q: "Where are saved SOPs?",
        a: "Under the SOP Generator page, on the right. Every SOP is searchable and can be shared as a PDF or via WhatsApp.",
      },
    ],
  },
  {
    id: "compliance",
    icon: ShieldCheck,
    title: "Compliance Agent",
    intro: "Never miss a permit, license or filing deadline. Karya tracks every compliance item with automatic reminders.",
    articles: [
      {
        q: "What is auto-seeded on first sign-in?",
        a: "When you pick your country, Karya seeds a starter checklist: for India — BOCW Cess, GST returns, CLRA, Factories/Shops registration, ESIC/EPFO. For UAE — DED Trade License, MOHRE labour cards, Emirates ID, WPS, Civil Defense NOC and more. You edit due dates from there.",
      },
      {
        q: "How do I get penalty estimates?",
        a: "Open any compliance item → “Analyze”. AI reads the notes, cross-references your country's typical fine ranges, and gives you a plain-language penalty estimate + recommended remediation.",
      },
      {
        q: "How do I upload a permit document?",
        a: "Open the item → drag the PDF in. Or forward it to Telegram, tap “Compliance” when the bot asks. AI extracts key dates and files it here.",
      },
    ],
  },
  {
    id: "telegram",
    icon: PaperPlaneTilt,
    title: "Telegram Assistant",
    intro: "Karya as a Telegram chat. Voice notes, receipts, worker photos, quick queries — everything on your phone.",
    articles: [
      {
        q: "How do I link Telegram?",
        a: "Profile → Connect Telegram → tap Generate. Copy the 6-character code and open the bot in Telegram (it's @karya_ops_bot). Send `/start XXXXXX`. The web app updates automatically once linked.",
      },
      {
        q: "What can I say to the bot?",
        a: "Try: “Ramesh took ₹5,000 advance”, “Pay Manoj ₹12,000”, “10 workers at Skyline today”, “How much do I owe Ramesh?”. Send a voice note in any language — it's transcribed and acted on. Send a photo/receipt — it asks where to file it.",
      },
      {
        q: "What if the code says invalid?",
        a: "Codes expire in 15 minutes and are single-use. Regenerate a fresh one and paste it into Telegram as `/start XXXXXX`. Make sure you're generating from the same Karya URL you signed in on.",
      },
      {
        q: "Can I unlink?",
        a: "Yes — Profile → Disconnect Telegram, or send /unlink in the bot. To relink, generate a new code.",
      },
    ],
  },
  {
    id: "whatsapp",
    icon: WhatsappLogo,
    title: "WhatsApp Delivery",
    intro: "Daily reports, alerts and PDFs delivered directly to your client's WhatsApp — no app install required.",
    articles: [
      {
        q: "How do I set my phone up for WhatsApp?",
        a: "Profile → Verify your phone. We send a one-time SMS code via Twilio Verify. Once verified you can send reports from your account.",
      },
      {
        q: "What's the Twilio Sandbox?",
        a: "A free Twilio channel that lets you send WhatsApp messages while you evaluate the platform. The catch: each recipient must first send `join <sandbox-code>` to +1 (415) 523-8886 from their WhatsApp. Once done, they can receive messages from your app.",
      },
      {
        q: "How do I move to production WhatsApp?",
        a: "Apply for a Twilio WhatsApp Business number (or bring your own approved number). Update TWILIO_WHATSAPP_FROM in your env with `whatsapp:+<yournumber>`. No more sandbox opt-ins.",
      },
    ],
  },
  {
    id: "insights",
    icon: ChartLineUp,
    title: "Predictive Insights",
    intro: "Early-warning signals across labour, cost and schedule. Plus AI-scored subcontractor performance.",
    articles: [
      {
        q: "How is labour shortage predicted?",
        a: "Karya looks at your last 7 days of attendance vs expected worker-days. Above 60% absenteeism = high risk, 30–60% = medium.",
      },
      {
        q: "How is cost overrun measured?",
        a: "For each project: labour spend as % of budget. Above 20% (with the project not near completion) is high risk.",
      },
      {
        q: "How are subcontractor scorecards computed?",
        a: "Based on penalty/deduction ratio (lower = better), payment progress vs contracted value, and delivery timeliness. A = 80+, B = 60–79, C = below 60.",
      },
    ],
  },
  {
    id: "knowledge",
    icon: Brain,
    title: "Org Memory",
    intro: "Everything your team learns, permanently searchable. Notes, receipts, decisions, incidents.",
    articles: [
      {
        q: "What goes into Org Memory?",
        a: "Anything you save via the Note action — snippets from meetings, key decisions, incident reports, supplier feedback. Photos/PDFs forwarded to Telegram with “Note” tag also end up here.",
      },
      {
        q: "How do I query it?",
        a: "Org Memory → ask a natural-language question, e.g. “Why was Skyline Towers delayed?” or “Which supplier had lowest defects?”. AI answers using only your saved memory.",
      },
    ],
  },
  {
    id: "subs",
    icon: Handshake,
    title: "Subcontractors",
    intro: "Track every subcontractor's contract value, deductions, retention and pending payments in one place.",
    articles: [
      {
        q: "How do I add a subcontractor?",
        a: "Subcontractors → Add. Enter name, trade, contract value, retention %, phone. Log each bill/payment as a subcontractor transaction. Karya keeps a running net-payable balance.",
      },
      {
        q: "What are deductions?",
        a: "Retention (held back until handover), penalties (for delays / quality issues), TDS/withholding, or advance recoveries. Each is a line item on the subcontractor ledger.",
      },
    ],
  },
];

function ArticleCard({ item, sectionTitle }) {
  const [open, setOpen] = useState(false);
  const compositeBody = `${item.q}\n\n${item.a}`;
  return (
    <div data-testid={`help-article-${item.q.slice(0, 24).replace(/\s+/g, "-").toLowerCase()}`} className="border border-[#E4E4E7] bg-white">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between gap-3 px-5 py-4 text-left hover:bg-[#FAFAFA] transition-colors duration-200"
        aria-expanded={open}
      >
        <span className="font-display font-bold text-sm sm:text-base leading-snug">{item.q}</span>
        <CaretDown size={16} weight="bold" className={`shrink-0 text-[#71717A] transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="px-5 pb-5 -mt-1 text-sm text-[#3f3f46] leading-relaxed border-t border-[#E4E4E7] pt-4">
          <p className="whitespace-pre-line">{item.a}</p>
          <div className="mt-3">
            <TranslateButton text={compositeBody} contextLabel={sectionTitle} />
          </div>
        </div>
      )}
    </div>
  );
}

export default function Help() {
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const [asking, setAsking] = useState(false);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return SECTIONS;
    return SECTIONS
      .map((s) => ({
        ...s,
        articles: s.articles.filter(
          (a) => a.q.toLowerCase().includes(needle) || a.a.toLowerCase().includes(needle) || s.title.toLowerCase().includes(needle)
        ),
      }))
      .filter((s) => s.articles.length > 0);
  }, [q]);

  const ask = async () => {
    if (!question.trim()) return;
    setAsking(true);
    setAnswer(null);
    try {
      const res = await api.post("/help/ask", { question: question.trim() });
      setAnswer(res.data.answer || "");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Couldn't get an answer");
    } finally {
      setAsking(false);
    }
  };

  return (
    <div className="p-5 sm:p-8 max-w-5xl">
      <PageHeader
        overline={t("help.overline")}
        title={t("help.title")}
        desc={t("help.desc")}
      />

      {/* Search */}
      <div className="mb-8 border-2 border-[#09090B] flex items-center gap-3 px-4 py-3 bg-white">
        <MagnifyingGlass size={18} weight="bold" className="text-[#71717A] shrink-0" />
        <input
          data-testid="help-search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t("help.searchPlaceholder")}
          className="flex-1 outline-none bg-transparent text-sm"
        />
      </div>

      {/* Ask AI */}
      <div className="mb-8 border-2 border-dashed border-[#EA580C] bg-[#FFF7ED] p-5">
        <div className="flex items-center gap-2 mb-3">
          <Sparkle size={18} weight="fill" className="text-[#EA580C]" />
          <h3 className="font-display font-bold">{t("help.askAI")}</h3>
        </div>
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            data-testid="help-ask-input"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !asking && ask()}
            placeholder={t("help.askPlaceholder")}
            className="flex-1 border-2 border-[#E4E4E7] focus:border-[#EA580C] outline-none px-3 py-2.5 text-sm bg-white"
          />
          <button
            data-testid="help-ask-button"
            onClick={ask}
            disabled={asking || !question.trim()}
            className="flex items-center justify-center gap-2 bg-[#09090B] text-white px-5 py-2.5 text-sm font-semibold hover:bg-[#EA580C] transition-colors duration-200 disabled:opacity-50"
          >
            <Question size={16} weight="bold" /> {asking ? t("help.askingLabel") : t("help.askButton")}
          </button>
        </div>
        {answer && (
          <div data-testid="help-ask-answer" className="mt-4 p-4 bg-white border border-[#E4E4E7] text-sm text-[#3f3f46] whitespace-pre-line leading-relaxed">
            {answer}
            <div className="mt-3"><TranslateButton text={answer} contextLabel="Help answer" /></div>
          </div>
        )}
      </div>

      {/* Sections */}
      {filtered.length === 0 ? (
        <div className="border border-[#E4E4E7] p-10 text-center text-sm text-[#71717A]">
          {t("help.noResults")}
        </div>
      ) : (
        <div className="space-y-8">
          {filtered.map((s) => (
            <section key={s.id} data-testid={`help-section-${s.id}`}>
              <div className="flex items-center gap-2 mb-2">
                <s.icon size={20} weight="duotone" className="text-[#EA580C]" />
                <h2 className="font-display font-black text-xl tracking-tight">{s.title}</h2>
              </div>
              <p className="text-sm text-[#71717A] mb-4">{s.intro}</p>
              <div className="space-y-2">
                {s.articles.map((a) => (
                  <ArticleCard key={a.q} item={a} sectionTitle={s.title} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      {/* Bottom CTAs */}
      <div className="mt-10 grid sm:grid-cols-2 gap-3">
        <div className="border border-[#E4E4E7] p-4 flex items-center gap-3 bg-white">
          <Buildings size={22} weight="duotone" className="text-[#EA580C] shrink-0" />
          <div>
            <p className="font-display font-bold text-sm">Still stuck?</p>
            <p className="text-xs text-[#71717A]">Use the Ask AI box above with your specific situation — it can reference your live data.</p>
          </div>
        </div>
        <div className="border border-[#E4E4E7] p-4 flex items-center gap-3 bg-white">
          <PaperPlaneTilt size={22} weight="duotone" className="text-[#EA580C] shrink-0" />
          <div>
            <p className="font-display font-bold text-sm">Prefer chat?</p>
            <p className="text-xs text-[#71717A]">Link Telegram from Profile → Connect Telegram, and use the bot as your assistant.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
