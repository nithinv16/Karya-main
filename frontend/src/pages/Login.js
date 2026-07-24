import React, { useState } from "react";
import { Link } from "react-router-dom";
import {
  GoogleLogo,
  HardHat,
  Microphone,
  ShieldCheck,
  Brain,
  CaretDown,
  CaretUp,
  CheckCircle,
  Warning,
  XCircle,
  Play,
  ArrowsClockwise,
  ArrowRight,
  Envelope,
  Globe,
  Coins,
  FileText
} from "@phosphor-icons/react";

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
  const [copiedDiag, setCopiedDiag] = useState(false);

  // Scroll interactive simulation states
  const [activeTab, setActiveTab] = useState("voice"); // 'voice', 'telegram', 'compliance', 'payroll'
  const [selectedLanguage, setSelectedLanguage] = useState("Hindi");
  const [voiceStep, setVoiceStep] = useState(0); // 0 = idle, 1 = loading, 2 = output
  const [complianceStep, setComplianceStep] = useState(0); // 0 = idle, 1 = auditing, 2 = ready
  const [payrollStep, setPayrollStep] = useState(0); // 0 = idle, 1 = settling, 2 = done

  // Telegram simulation states
  const [tgScenario, setTgScenario] = useState("aadhaar"); // 'aadhaar', 'receipt'
  const [tgStep, setTgStep] = useState(0); // 0 = idle, 1 = sending, 2 = loading, 3 = reply_done

  // FAQ accordion state
  const [openFaq, setOpenFaq] = useState(null);

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
      setCopiedDiag(true);
      setTimeout(() => setCopiedDiag(false), 2500);
    } catch (e) {
      window.prompt("Copy diagnostics:", info);
    }
  };

  // Mock voice commands data
  const voiceTranscripts = {
    Hindi: {
      audioText: "रमेश ने आज 4 घंटे ओवरटाइम किया और ₹1500 का सीमेंट खरीदा",
      entities: {
        worker: "Ramesh Kumar (Mason)",
        attendance: "8h Regular + 4h Overtime logged",
        expense: "Cement Procurement (₹1,500)",
        ledgerStatus: "Synced to Project Ledger",
      }
    },
    Tamil: {
      audioText: "ரமேஷ் இன்று 4 மணிநேரம் கூடுதல் நேரம் வேலை செய்தார், ₹1500 மதிப்புள்ள சிமெண்ட் வாங்கினார்",
      entities: {
        worker: "Ramesh Kumar (Mason)",
        attendance: "8h Regular + 4h Overtime logged",
        expense: "Cement Procurement (₹1,500)",
        ledgerStatus: "Synced to Project Ledger",
      }
    },
    Malayalam: {
      audioText: "രമേശ് ഇന്ന് 4 മണിക്കൂർ ഓവർടൈം ജോലി ചെയ്യുകയും 1500 രൂപയുടെ സിമന്റ് വാങ്ങുകയും ചെയ്തു",
      entities: {
        worker: "Ramesh Kumar (Mason)",
        attendance: "8h Regular + 4h Overtime logged",
        expense: "Cement Procurement (₹1,500)",
        ledgerStatus: "Synced to Project Ledger",
      }
    },
    Telugu: {
      audioText: "రమేష్ ఈరోజు 4 గంటల ఓవర్ టైమ్ పని చేసాడు మరియు ₹1500 విలువైన సిమెంట్ కొన్నాడు",
      entities: {
        worker: "Ramesh Kumar (Mason)",
        attendance: "8h Regular + 4h Overtime logged",
        expense: "Cement Procurement (₹1,500)",
        ledgerStatus: "Synced to Project Ledger",
      }
    }
  };

  const handleSimulateVoice = () => {
    setVoiceStep(1);
    setTimeout(() => {
      setVoiceStep(2);
    }, 1200);
  };

  const handleSimulateCompliance = () => {
    setComplianceStep(1);
    setTimeout(() => {
      setComplianceStep(2);
    }, 1500);
  };

  const handleSimulatePayroll = () => {
    setPayrollStep(1);
    setTimeout(() => {
      setPayrollStep(2);
    }, 1200);
  };

  const handleSimulateTelegram = () => {
    setTgStep(1);
    setTimeout(() => {
      setTgStep(2);
      setTimeout(() => {
        setTgStep(3);
      }, 1200);
    }, 800);
  };

  const toggleFaq = (index) => {
    setOpenFaq(openFaq === index ? null : index);
  };

  return (
    <div className="w-full bg-[#FFFFFF] selection:bg-[#EA580C] selection:text-white overflow-x-hidden">
      
      {/* =========================================================================
          FIRST FOLD (Visually identical to the original single-view layout)
          ========================================================================= */}
      <div className="min-h-screen grid lg:grid-cols-2 border-b border-[#E4E4E7]">
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
                  {copiedDiag ? "Copied!" : "Copy diagnostics"}
                </button>
              </div>
            )}
          </div>

          <div className="text-xs text-[#71717A] space-y-1">
            <p>Built for contractors, builders, MEP & civil firms across emerging markets.</p>
            <p className="flex flex-wrap items-center gap-3">
              <Link to="/blog" className="hover:text-[#09090B] hover:underline underline-offset-2" data-testid="footer-blog">Blog</Link>
              <span>·</span>
              <Link to="/pricing" className="hover:text-[#09090B] hover:underline underline-offset-2" data-testid="footer-pricing">Pricing</Link>
              <span>·</span>
              <Link to="/contact" className="hover:text-[#09090B] hover:underline underline-offset-2" data-testid="footer-contact">Contact us</Link>
              <span>·</span>
              <a href="mailto:sixn8.technologies@gmail.com" className="hover:text-[#09090B] hover:underline underline-offset-2">sixn8.technologies@gmail.com</a>
            </p>
            <p className="pt-2">© {new Date().getFullYear()} <span className="font-semibold">SIXN8 Technologies Private Ltd</span></p>
          </div>
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
                <div key={f.t || ('feat-' + i)} className="bg-black/70 backdrop-blur-sm p-6">
                  <f.icon size={26} weight="duotone" color="#EA580C" />
                  <h3 className="font-display font-bold text-white text-base mt-3 mb-1">{f.t}</h3>
                  <p className="text-white/60 text-sm leading-snug">{f.d}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* =========================================================================
          FOLD 2: WHAT IS KARYA (JARGON-FREE EXPLANATION FOR INFORMAL CONSTRUCTION)
          ========================================================================= */}
      <div className="bg-zinc-50 py-24 px-8 lg:px-16 border-b border-[#E4E4E7]">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="grid lg:grid-cols-12 gap-8 mb-16">
            <div className="lg:col-span-5 space-y-3">
              <p className="overline text-[#EA580C]">Made for site conditions</p>
              <h2 className="font-display font-black text-3xl sm:text-4xl tracking-tight leading-none text-[#09090B]">
                Helping you manage daily-wage workers, without making them use complex apps.
              </h2>
            </div>
            <div className="lg:col-span-7 flex items-center">
              <p className="text-zinc-600 text-base sm:text-lg leading-relaxed">
                Most daily-wage laborers and site supervisors don't have the time to learn complicated software. 
                Karya bridges the gap by letting supervisors log work, track advances, and onboard workers using simple 
                <strong> voice notes</strong> or <strong>Telegram messages</strong> in their local language. 
                We turn plain conversation into a clean, digital ledger.
              </p>
            </div>
          </div>

          {/* 3 Simple Steps */}
          <div className="grid md:grid-cols-3 gap-8">
            <div className="bg-white border border-[#E4E4E7] p-8 space-y-4 hover:border-[#EA580C] hover:shadow-md transition-all duration-200">
              <div className="w-10 h-10 bg-orange-100 text-[#EA580C] flex items-center justify-center font-bold text-lg rounded-none">
                1
              </div>
              <h3 className="font-display font-bold text-lg text-[#09090B]">Onboard with a Photo</h3>
              <p className="text-sm text-[#71717A] leading-relaxed">
                No typing names or filling long forms. Simply snap a photo of the worker's Aadhaar or ID card and send it via Telegram. Our assistant automatically reads the details and adds them to your site workforce roster.
              </p>
            </div>

            <div className="bg-white border border-[#E4E4E7] p-8 space-y-4 hover:border-[#EA580C] hover:shadow-md transition-all duration-200">
              <div className="w-10 h-10 bg-orange-100 text-[#EA580C] flex items-center justify-center font-bold text-lg rounded-none">
                2
              </div>
              <h3 className="font-display font-bold text-lg text-[#09090B]">Speak Naturally to Log Work</h3>
              <p className="text-sm text-[#71717A] leading-relaxed">
                Supervisors can record a voice message in Hindi, Tamil, Telugu, or Malayalam saying who worked, what task they did, or if they took a cash advance. The assistant processes it and updates the records instantly.
              </p>
            </div>

            <div className="bg-white border border-[#E4E4E7] p-8 space-y-4 hover:border-[#EA580C] hover:shadow-md transition-all duration-200">
              <div className="w-10 h-10 bg-orange-100 text-[#EA580C] flex items-center justify-center font-bold text-lg rounded-none">
                3
              </div>
              <h3 className="font-display font-bold text-lg text-[#09090B]">Calculate & Pay Dues Instantly</h3>
              <p className="text-sm text-[#71717A] leading-relaxed">
                Wages are calculated automatically based on daily rates and logged attendance days. Deduct advances or food costs without manual bookkeeping errors. When it's time to pay, export a simple UPI list to settle accounts.
              </p>
            </div>
          </div>

          {/* Informal Sector Focus Callout */}
          <div className="mt-16 bg-[#EA580C]/5 border border-[#EA580C]/20 p-8 sm:p-10 flex flex-col sm:flex-row items-start sm:items-center gap-6">
            <div className="w-12 h-12 bg-[#EA580C] text-white flex items-center justify-center flex-shrink-0">
              <HardHat size={24} weight="fill" />
            </div>
            <div className="space-y-1">
              <h4 className="font-display font-bold text-base sm:text-lg text-[#09090B]">Transparent Wages, Honest Records</h4>
              <p className="text-sm text-zinc-600 leading-relaxed">
                Daily-wage construction is heavily reliant on informal, verbal agreements. Karya creates clear digital wage histories for workers, reducing disputes over unpaid overtime, food deductions, or cash advances. It is transparency that works on rugged project sites.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* =========================================================================
          FOLD 3: DETAILED CAPABILITIES (THE WORKSTATION PANELS - UPGRADED TO 6 CARDS)
          ========================================================================= */}
      <div className="py-20 px-8 lg:px-16 max-w-7xl mx-auto">
        <div className="text-center max-w-2xl mx-auto mb-16 space-y-4">
          <p className="overline text-[#EA580C]">Under The Hood</p>
          <h2 className="font-display font-black text-3xl lg:text-4xl tracking-tight">
            An Operating System Built For Indian Project Sites
          </h2>
          <p className="text-[#71717A] text-sm lg:text-base">
            Informal labor projects demand real-time visibility. Karya wraps complex calculations, compliance reporting, and worker logs in simple voice and chat workflows.
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
          {/* Card 1: Workforce Intelligence */}
          <div className="border border-[#E4E4E7] p-8 flex flex-col justify-between hover:border-[#EA580C] hover:shadow-lg transition-all duration-200 bg-white">
            <div className="space-y-4">
              <div className="w-12 h-12 bg-orange-100 flex items-center justify-center text-[#EA580C]">
                <HardHat size={26} weight="duotone" />
              </div>
              <h3 className="font-display font-bold text-xl">Workforce Intelligence</h3>
              <p className="text-sm text-[#71717A] leading-relaxed">
                Manage shifts, track crews, set specialized craft rates (e.g. masons, bar-benders, helpers), and log attendance instantly. Calculate OT payouts dynamically with ZERO spreadsheet errors.
              </p>
            </div>
            <ul className="mt-6 space-y-2 border-t border-[#E4E4E7] pt-4 text-xs text-[#71717A]">
              <li className="flex items-center gap-2">
                <CheckCircle size={16} color="#16A34A" weight="fill" />
                Crew-based grouping and batch attendance
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle size={16} color="#16A34A" weight="fill" />
                Direct UPI/Aadhaar instant payroll export
              </li>
            </ul>
          </div>

          {/* Card 2: Compliance Agent */}
          <div className="border border-[#E4E4E7] p-8 flex flex-col justify-between hover:border-[#EA580C] hover:shadow-lg transition-all duration-200 bg-white">
            <div className="space-y-4">
              <div className="w-12 h-12 bg-orange-100 flex items-center justify-center text-[#EA580C]">
                <ShieldCheck size={26} weight="duotone" />
              </div>
              <h3 className="font-display font-bold text-xl">Proactive Compliance</h3>
              <p className="text-sm text-[#71717A] leading-relaxed">
                Stay audit-ready. The compliance module monitors EPFO filings, ESIC forms, municipal pollution certificates, and labor licenses. Automated warnings alert you before permits expire.
              </p>
            </div>
            <ul className="mt-6 space-y-2 border-t border-[#E4E4E7] pt-4 text-xs text-[#71717A]">
              <li className="flex items-center gap-2">
                <CheckCircle size={16} color="#16A34A" weight="fill" />
                Automated license renewal alerts via WhatsApp
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle size={16} color="#16A34A" weight="fill" />
                PDF compliance checklist export for audits
              </li>
            </ul>
          </div>

          {/* Card 3: Voice-First Operations */}
          <div className="border border-[#E4E4E7] p-8 flex flex-col justify-between hover:border-[#EA580C] hover:shadow-lg transition-all duration-200 bg-white">
            <div className="space-y-4">
              <div className="w-12 h-12 bg-orange-100 flex items-center justify-center text-[#EA580C]">
                <Microphone size={26} weight="duotone" />
              </div>
              <h3 className="font-display font-bold text-xl">Voice-First Operations</h3>
              <p className="text-sm text-[#71717A] leading-relaxed">
                Supervisors don't have time to type on-site. Record a quick voice memo in Hindi, Tamil, Telugu, or Malayalam. Karya extracts workers, task completions, and materials to update your ledger automatically.
              </p>
            </div>
            <ul className="mt-6 space-y-2 border-t border-[#E4E4E7] pt-4 text-xs text-[#71717A]">
              <li className="flex items-center gap-2">
                <CheckCircle size={16} color="#16A34A" weight="fill" />
                High-accuracy local accent recognition engine
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle size={16} color="#16A34A" weight="fill" />
                Direct translation from dialect speech to system ledger
              </li>
            </ul>
          </div>

          {/* Card 4: Telegram Co-Pilot */}
          <div className="border border-[#E4E4E7] p-8 flex flex-col justify-between hover:border-[#EA580C] hover:shadow-lg transition-all duration-200 bg-white">
            <div className="space-y-4">
              <div className="w-12 h-12 bg-orange-100 flex items-center justify-center text-[#EA580C]">
                <Envelope size={26} weight="duotone" />
              </div>
              <h3 className="font-display font-bold text-xl">Telegram AI Co-Pilot</h3>
              <p className="text-sm text-[#71717A] leading-relaxed">
                Connect Karya to Telegram. Send voice memos, upload worker Aadhaar photos, or forward material invoices directly to the bot. Our AI reads documents, maps them, and flags follow-up options.
              </p>
            </div>
            <ul className="mt-6 space-y-2 border-t border-[#E4E4E7] pt-4 text-xs text-[#71717A]">
              <li className="flex items-center gap-2">
                <CheckCircle size={16} color="#16A34A" weight="fill" />
                Snap photo of Aadhaar card to onboard workers
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle size={16} color="#16A34A" weight="fill" />
                Auto-processed media assets stored directly to cloud profiles
              </li>
            </ul>
          </div>

          {/* Card 5: Real-time Expense Tracking */}
          <div className="border border-[#E4E4E7] p-8 flex flex-col justify-between hover:border-[#EA580C] hover:shadow-lg transition-all duration-200 bg-white">
            <div className="space-y-4">
              <div className="w-12 h-12 bg-orange-100 flex items-center justify-center text-[#EA580C]">
                <Coins size={26} weight="duotone" />
              </div>
              <h3 className="font-display font-bold text-xl">Expense Management</h3>
              <p className="text-sm text-[#71717A] leading-relaxed">
                Log manually or forward concrete bills, diesel logs, and hardware receipts via Telegram. Karya automatically categorizes expenditures, links them to active projects, and computes ledger rollups.
              </p>
            </div>
            <ul className="mt-6 space-y-2 border-t border-[#E4E4E7] pt-4 text-xs text-[#71717A]">
              <li className="flex items-center gap-2">
                <CheckCircle size={16} color="#16A34A" weight="fill" />
                Automatic cost categorizations and project attribution
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle size={16} color="#16A34A" weight="fill" />
                Deduplication check and searchable receipts logs
              </li>
            </ul>
          </div>

          {/* Card 6: Org Memory & SOPs */}
          <div className="border border-[#E4E4E7] p-8 flex flex-col justify-between hover:border-[#EA580C] hover:shadow-lg transition-all duration-200 bg-white">
            <div className="space-y-4">
              <div className="w-12 h-12 bg-orange-100 flex items-center justify-center text-[#EA580C]">
                <Brain size={26} weight="duotone" />
              </div>
              <h3 className="font-display font-bold text-xl">Tacit SOP Capture</h3>
              <p className="text-sm text-[#71717A] leading-relaxed">
                Ensure construction standards are met across sites. Document instructions verbally. Karya turns voice walkthroughs into clear, readable Standard Operating Procedures (SOPs) for supervisors.
              </p>
            </div>
            <ul className="mt-6 space-y-2 border-t border-[#E4E4E7] pt-4 text-xs text-[#71717A]">
              <li className="flex items-center gap-2">
                <CheckCircle size={16} color="#16A34A" weight="fill" />
                Auto-structured safety instructions from audio notes
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle size={16} color="#16A34A" weight="fill" />
                Searchable knowledge base for supervisor onboarding
              </li>
            </ul>
          </div>
        </div>
      </div>

      {/* =========================================================================
          FOLD 4: INTERACTIVE PLAYGROUND (SIMULATION ENGINE)
          ========================================================================= */}
      <div className="bg-[#F4F4F5] py-20 px-8 lg:px-16 border-t border-b border-[#E4E4E7]">
        <div className="max-w-7xl mx-auto">
          
          <div className="text-center max-w-2xl mx-auto mb-12 space-y-3">
            <p className="overline text-[#EA580C]">Interactive Simulation</p>
            <h2 className="font-display font-black text-3xl tracking-tight">Test-Drive the AI Core</h2>
            <p className="text-[#71717A] text-sm">
              See how the underlying system logic parses local speech, tracks critical compliance timelines, processes Telegram chat media, and manages UPI payouts.
            </p>
          </div>

          <div className="grid lg:grid-cols-3 gap-8">
            
            {/* Sidebar Controls */}
            <div className="lg:col-span-1 space-y-2">
              <button
                onClick={() => setActiveTab("voice")}
                className={`w-full text-left p-5 border transition-all flex items-start gap-4 ${
                  activeTab === "voice"
                    ? "bg-[#09090B] text-white border-[#09090B]"
                    : "bg-white text-[#09090B] border-[#E4E4E7] hover:border-[#EA580C]"
                }`}
              >
                <Microphone size={24} weight="duotone" className={activeTab === "voice" ? "text-[#EA580C]" : "text-zinc-500"} />
                <div>
                  <h4 className="font-bold text-sm">1. Multi-lingual Voice Input</h4>
                  <p className="text-xs opacity-80 mt-1">Translate supervisor dialect to system transactions.</p>
                </div>
              </button>

              <button
                onClick={() => setActiveTab("telegram")}
                className={`w-full text-left p-5 border transition-all flex items-start gap-4 ${
                  activeTab === "telegram"
                    ? "bg-[#09090B] text-white border-[#09090B]"
                    : "bg-white text-[#09090B] border-[#E4E4E7] hover:border-[#EA580C]"
                }`}
              >
                <Envelope size={24} weight="duotone" className={activeTab === "telegram" ? "text-[#EA580C]" : "text-zinc-500"} />
                <div>
                  <h4 className="font-bold text-sm">2. Telegram AI Chatbot</h4>
                  <p className="text-xs opacity-80 mt-1">Snap Aadhaar IDs or upload cement invoices on-site.</p>
                </div>
              </button>

              <button
                onClick={() => setActiveTab("compliance")}
                className={`w-full text-left p-5 border transition-all flex items-start gap-4 ${
                  activeTab === "compliance"
                    ? "bg-[#09090B] text-white border-[#09090B]"
                    : "bg-white text-[#09090B] border-[#E4E4E7] hover:border-[#EA580C]"
                }`}
              >
                <ShieldCheck size={24} weight="duotone" className={activeTab === "compliance" ? "text-[#EA580C]" : "text-zinc-500"} />
                <div>
                  <h4 className="font-bold text-sm">3. Compliance Scanning</h4>
                  <p className="text-xs opacity-80 mt-1">Run continuous audits on permits and labor rules.</p>
                </div>
              </button>

              <button
                onClick={() => setActiveTab("payroll")}
                className={`w-full text-left p-5 border transition-all flex items-start gap-4 ${
                  activeTab === "payroll"
                    ? "bg-[#09090B] text-white border-[#09090B]"
                    : "bg-white text-[#09090B] border-[#E4E4E7] hover:border-[#EA580C]"
                }`}
              >
                <Coins size={24} weight="duotone" className={activeTab === "payroll" ? "text-[#EA580C]" : "text-zinc-500"} />
                <div>
                  <h4 className="font-bold text-sm">4. Payout Settlements</h4>
                  <p className="text-xs opacity-80 mt-1">Calculate wages and export UPI dispatch files.</p>
                </div>
              </button>
            </div>

            {/* Simulation Canvas */}
            <div className="lg:col-span-2 bg-white border border-[#E4E4E7] p-8 flex flex-col justify-between min-h-[380px]">
              
              {/* TAB 1: VOICE COM */}
              {activeTab === "voice" && (
                <div className="flex-1 flex flex-col justify-between">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between border-b border-[#E4E4E7] pb-3">
                      <span className="font-bold text-xs uppercase tracking-wide text-zinc-500">
                        VOICE INPUT PARSER
                      </span>
                      <div className="flex gap-2">
                        {["Hindi", "Tamil", "Malayalam", "Telugu"].map((lang) => (
                          <button
                            key={lang}
                            onClick={() => {
                              setSelectedLanguage(lang);
                              setVoiceStep(0);
                            }}
                            className={`px-2 py-1 text-xs border ${
                              selectedLanguage === lang
                                ? "bg-[#EA580C] text-white border-[#EA580C]"
                                : "bg-zinc-50 text-zinc-600 border-[#E4E4E7] hover:bg-zinc-100"
                            }`}
                          >
                            {lang}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="bg-zinc-50 p-4 border border-[#E4E4E7] font-mono text-sm relative">
                      <p className="text-xs text-zinc-400 mb-1">// Audio input phrase ({selectedLanguage}):</p>
                      <p className="italic font-bold text-zinc-800">
                        "{voiceTranscripts[selectedLanguage].audioText}"
                      </p>
                    </div>

                    {voiceStep === 1 && (
                      <div className="flex items-center gap-3 text-sm py-2">
                        <ArrowsClockwise size={18} className="animate-spin text-[#EA580C]" />
                        <span className="text-[#71717A]">Processing speech models and mapping variables...</span>
                      </div>
                    )}

                    {voiceStep === 2 && (
                      <div className="grid grid-cols-2 gap-4 fade-in bg-orange-50/50 p-4 border border-orange-200">
                        <div className="space-y-2">
                          <p className="text-xs font-semibold text-[#EA580C]">EXTRACTED ATTENDANCE</p>
                          <p className="text-xs font-bold text-zinc-800">{voiceTranscripts[selectedLanguage].entities.worker}</p>
                          <p className="text-xs text-zinc-600">{voiceTranscripts[selectedLanguage].entities.attendance}</p>
                        </div>
                        <div className="space-y-2">
                          <p className="text-xs font-semibold text-[#EA580C]">EXTRACTED EXPENSE</p>
                          <p className="text-xs font-bold text-zinc-800">{voiceTranscripts[selectedLanguage].entities.expense}</p>
                          <p className="text-xs text-green-700 flex items-center gap-1 font-semibold">
                            <CheckCircle size={14} weight="fill" /> {voiceTranscripts[selectedLanguage].entities.ledgerStatus}
                          </p>
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="pt-6">
                    <button
                      onClick={handleSimulateVoice}
                      className="bg-[#09090B] text-white px-5 py-3 text-sm font-semibold hover:bg-[#EA580C] transition-all flex items-center gap-2"
                    >
                      <Play size={16} weight="fill" />
                      Simulate Voice Processing
                    </button>
                  </div>
                </div>
              )}

              {/* TAB 2: TELEGRAM BOT CO-PILOT */}
              {activeTab === "telegram" && (
                <div className="flex-1 flex flex-col justify-between">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between border-b border-[#E4E4E7] pb-3">
                      <span className="font-bold text-xs uppercase tracking-wide text-zinc-500">
                        TELEGRAM CO-PILOT SIMULATOR
                      </span>
                      <div className="flex gap-2">
                        <button
                          onClick={() => {
                            setTgScenario("aadhaar");
                            setTgStep(0);
                          }}
                          className={`px-2 py-1 text-xs border ${
                            tgScenario === "aadhaar"
                              ? "bg-[#EA580C] text-white border-[#EA580C]"
                              : "bg-zinc-50 text-zinc-600 border-[#E4E4E7]"
                          }`}
                        >
                          Aadhaar Upload
                        </button>
                        <button
                          onClick={() => {
                            setTgScenario("receipt");
                            setTgStep(0);
                          }}
                          className={`px-2 py-1 text-xs border ${
                            tgScenario === "receipt"
                              ? "bg-[#EA580C] text-white border-[#EA580C]"
                              : "bg-zinc-50 text-zinc-600 border-[#E4E4E7]"
                          }`}
                        >
                          Expense Invoice
                        </button>
                      </div>
                    </div>

                    {/* Chat Window Mockup */}
                    <div className="bg-zinc-100 p-4 border border-[#E4E4E7] rounded-sm space-y-3 font-sans text-xs min-h-[160px] flex flex-col justify-end">
                      
                      {tgStep >= 1 && (
                        <div className="self-end bg-green-600 text-white p-2.5 rounded-lg max-w-[80%] fade-in">
                          {tgScenario === "aadhaar" ? (
                            <div className="flex items-center gap-2">
                              <FileText size={16} />
                              <span>[Photo: Aadhaar_Card_Ramesh.jpg]</span>
                            </div>
                          ) : (
                            <div className="flex items-center gap-2">
                              <Coins size={16} />
                              <span>[Photo: cement_bill_50bags.jpg]</span>
                            </div>
                          )}
                        </div>
                      )}

                      {tgStep === 2 && (
                        <div className="self-start bg-white text-zinc-800 p-2.5 border border-[#E4E4E7] rounded-lg max-w-[80%] flex items-center gap-2 shadow-xs">
                          <ArrowsClockwise size={14} className="animate-spin text-[#EA580C]" />
                          <span>Karya AI is reading image payload...</span>
                        </div>
                      )}

                      {tgStep === 3 && (
                        <div className="self-start bg-white text-zinc-800 p-3 border border-[#E4E4E7] rounded-lg max-w-[85%] space-y-2 shadow-xs fade-in">
                          <p className="font-semibold text-orange-600 flex items-center gap-1">
                            <CheckCircle size={14} weight="fill" color="#16A34A" /> KARYA AI PARSED METADATA
                          </p>
                          {tgScenario === "aadhaar" ? (
                            <div className="space-y-1 font-mono text-[10px] bg-zinc-50 p-2 border border-zinc-200">
                              <p><span className="text-zinc-400">Action:</span> Onboard Labourer</p>
                              <p><span className="text-zinc-400">Name:</span> Ramesh Kumar</p>
                              <p><span className="text-zinc-400">ID Number:</span> XXXX-XXXX-4592</p>
                              <p className="text-green-700 font-bold mt-1">✓ Draft Profile Created in Workforce page</p>
                            </div>
                          ) : (
                            <div className="space-y-1 font-mono text-[10px] bg-zinc-50 p-2 border border-zinc-200">
                              <p><span className="text-zinc-400">Action:</span> Log Expense</p>
                              <p><span className="text-zinc-400">Merchant:</span> UltraTech Cement Depot</p>
                              <p><span className="text-zinc-400">Amount:</span> ₹23,500.00 (50 Bags)</p>
                              <p className="text-green-700 font-bold mt-1">✓ Expense logged under Sector 4 Drafts</p>
                            </div>
                          )}
                        </div>
                      )}

                      {tgStep === 0 && (
                        <div className="text-center text-zinc-400 py-6">
                          Select scenario and click Send to simulate Telegram media message.
                        </div>
                      )}
                    </div>

                  </div>

                  <div className="pt-4">
                    <button
                      onClick={handleSimulateTelegram}
                      disabled={tgStep === 2}
                      className="bg-[#09090B] text-white px-5 py-3 text-sm font-semibold hover:bg-[#EA580C] transition-all flex items-center gap-2"
                    >
                      <Play size={16} weight="fill" />
                      Send to Telegram Bot (@karya_ops_bot)
                    </button>
                  </div>
                </div>
              )}

              {/* TAB 3: COMPLIANCE */}
              {activeTab === "compliance" && (
                <div className="flex-1 flex flex-col justify-between">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between border-b border-[#E4E4E7] pb-3">
                      <span className="font-bold text-xs uppercase tracking-wide text-zinc-500">
                        COMPLIANCE HEALTH CHECK
                      </span>
                      <span className="text-xs bg-zinc-100 text-zinc-600 px-2 py-0.5 border border-[#E4E4E7]">V2.4 Active</span>
                    </div>

                    <div className="space-y-2">
                      <div className="flex items-center justify-between p-3 border border-[#E4E4E7]">
                        <div className="flex items-center gap-2">
                          <CheckCircle size={18} color="#16A34A" weight="fill" />
                          <span className="text-xs font-semibold">EPFO Monthly Returns (Form 12A)</span>
                        </div>
                        <span className="text-[10px] text-green-700 font-bold bg-green-50 px-2 py-0.5 border border-green-200">FILED</span>
                      </div>

                      <div className="flex items-center justify-between p-3 border border-[#E4E4E7]">
                        <div className="flex items-center gap-2">
                          {complianceStep === 2 ? (
                            <Warning size={18} color="#EAB308" weight="fill" />
                          ) : (
                            <CheckCircle size={18} color="#16A34A" weight="fill" />
                          )}
                          <span className="text-xs font-semibold">Labour Licence - Site #04</span>
                        </div>
                        {complianceStep === 2 ? (
                          <span className="text-[10px] text-yellow-700 font-bold bg-yellow-50 px-2 py-0.5 border border-yellow-200">RENEWAL DUE (8 DAYS)</span>
                        ) : (
                          <span className="text-[10px] text-green-700 font-bold bg-green-50 px-2 py-0.5 border border-green-200">ACTIVE</span>
                        )}
                      </div>

                      {complianceStep === 2 && (
                        <div className="bg-yellow-50/50 p-3 border border-yellow-100 text-xs text-yellow-800 space-y-1 fade-in">
                          <p className="font-bold">⚠️ Compliance Warning: Renewal Deadline Approaching</p>
                          <p>Karya AI has drafted a renewal packet and queued notifications for Admin.</p>
                        </div>
                      )}
                    </div>

                    {complianceStep === 1 && (
                      <div className="flex items-center gap-3 text-sm py-2">
                        <ArrowsClockwise size={18} className="animate-spin text-[#EA580C]" />
                        <span className="text-[#71717A]">Scanning state labor commission databases...</span>
                      </div>
                    )}
                  </div>

                  <div className="pt-6">
                    <button
                      onClick={handleSimulateCompliance}
                      className="bg-[#09090B] text-white px-5 py-3 text-sm font-semibold hover:bg-[#EA580C] transition-all flex items-center gap-2"
                    >
                      <ArrowsClockwise size={16} weight="bold" />
                      Scan Compliance Registry
                    </button>
                  </div>
                </div>
              )}

              {/* TAB 4: PAYROLL */}
              {activeTab === "payroll" && (
                <div className="flex-1 flex flex-col justify-between">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between border-b border-[#E4E4E7] pb-3">
                      <span className="font-bold text-xs uppercase tracking-wide text-zinc-500">
                        INSTANT SETTLEMENT LEDGER
                      </span>
                      <span className="text-xs font-bold text-[#EA580C]">₹4,850.00 PENDING</span>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full text-left border-collapse text-xs">
                        <thead>
                          <tr className="border-b border-[#E4E4E7] text-zinc-400">
                            <th className="py-2">Worker</th>
                            <th className="py-2">Craft</th>
                            <th className="py-2 text-right">Hours</th>
                            <th className="py-2 text-right">Wage Due</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr className="border-b border-[#E4E4E7]">
                            <td className="py-2 font-bold">Ramesh K.</td>
                            <td className="py-2 text-zinc-500">Mason</td>
                            <td className="py-2 text-right">8h + 4h OT</td>
                            <td className="py-2 text-right font-mono font-bold">₹1,950.00</td>
                          </tr>
                          <tr className="border-b border-[#E4E4E7]">
                            <td className="py-2 font-bold">Amit Lal</td>
                            <td className="py-2 text-zinc-500">Helper</td>
                            <td className="py-2 text-right">8h</td>
                            <td className="py-2 text-right font-mono font-bold">₹1,300.00</td>
                          </tr>
                          <tr className="border-b border-[#E4E4E7]">
                            <td className="py-2 font-bold">Murugan S.</td>
                            <td className="py-2 text-zinc-500">Carpenter</td>
                            <td className="py-2 text-right">8h + 1h OT</td>
                            <td className="py-2 text-right font-mono font-bold">₹1,600.00</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>

                    {payrollStep === 1 && (
                      <div className="flex items-center gap-3 text-sm py-2">
                        <ArrowsClockwise size={18} className="animate-spin text-[#EA580C]" />
                        <span className="text-[#71717A]">Verifying bank links and generating API payload...</span>
                      </div>
                    )}

                    {payrollStep === 2 && (
                      <div className="bg-green-50 p-3 border border-green-200 text-xs text-green-800 space-y-1 fade-in">
                        <p className="font-bold flex items-center gap-1">
                          <CheckCircle size={16} weight="fill" color="#16A34A" /> Settlement Succeeded
                        </p>
                        <p>UPI disbursement files compiled. ₹4,850 distributed to 3 workers. SMS receipts dispatched.</p>
                      </div>
                    )}
                  </div>

                  <div className="pt-6">
                    <button
                      onClick={handleSimulatePayroll}
                      className="bg-[#09090B] text-white px-5 py-3 text-sm font-semibold hover:bg-[#EA580C] transition-all flex items-center gap-2"
                    >
                      <Coins size={16} weight="fill" />
                      Disburse Instant Payouts
                    </button>
                  </div>
                </div>
              )}

            </div>
          </div>

        </div>
      </div>

      {/* =========================================================================
          FOLD 5: FREQUENTLY ASKED QUESTIONS (ACCORDIONS - EXPANDED)
          ========================================================================= */}
      <div className="py-20 px-8 lg:px-16 max-w-4xl mx-auto">
        <div className="text-center mb-12 space-y-3">
          <p className="overline text-[#EA580C]">Support & Documentation</p>
          <h2 className="font-display font-black text-3xl tracking-tight">Frequently Asked Questions</h2>
          <p className="text-[#71717A] text-sm">
            Everything you need to know about setting up and running Karya on your construction projects.
          </p>
        </div>

        <div className="space-y-4">
          {[
            {
              q: "How does the Telegram bot integration work?",
              a: "You link your Telegram account to your Karya profile using a 6-digit link code. Once linked, you can send Aadhaar card photos to register labourers instantly, forward receipt PDFs or snaps to log expenses, and record voice notes. Karya processes them asynchronously using GPT-4o."
            },
            {
              q: "Do supervisors need technical training to use Karya?",
              a: "No. Karya is built with a voice-first interface. Supervisors and crew leads can simply speak in their native tongue (Hindi, Tamil, Telugu, Malayalam, etc.) to log attendance, expenses, and task completions."
            },
            {
              q: "How does the Compliance Agent stay up to date?",
              a: "Karya runs a local legal LLM agent that integrates with municipal guidelines and national standards (like EPFO/ESIC regulations). It proactively checks dates on your licenses and reports, alerting you via WhatsApp before deadlines."
            },
            {
              q: "Can it integrate with existing accounting software?",
              a: "Yes. Karya supports automated CSV/Excel exports and has robust REST APIs to sync ledger data, expense reports, and payroll timesheets directly with Tally, SAP, or custom construction ERPs."
            },
            {
              q: "Is my project data secure?",
              a: "Absolutely. We enforce end-to-end encryption for all audio records, files, and payroll databases. Access controls are granular, ensuring only authorized owners and project managers can approve payments."
            }
          ].map((item, index) => (
            <div key={item.q.slice(0, 20)} className="border border-[#E4E4E7] bg-white">
              <button
                onClick={() => toggleFaq(index)}
                className="w-full flex items-center justify-between p-5 text-left font-bold text-sm md:text-base text-zinc-900 focus:outline-none hover:text-[#EA580C]"
              >
                <span>{item.q}</span>
                {openFaq === index ? (
                  <CaretUp size={18} className="text-[#EA580C]" />
                ) : (
                  <CaretDown size={18} className="text-zinc-400" />
                )}
              </button>
              {openFaq === index && (
                <div className="px-5 pb-5 text-xs md:text-sm text-[#71717A] leading-relaxed border-t border-zinc-100 pt-3 fade-in">
                  {item.a}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* =========================================================================
          FOLD 6: BOTTOM CALL TO ACTION & SYSTEM FOOTER
          ========================================================================= */}
      <div className="bg-[#09090B] text-white border-t border-zinc-800">
        <div className="py-20 px-8 text-center max-w-4xl mx-auto space-y-6">
          <p className="overline text-[#EA580C]">Get Started Instantly</p>
          <h2 className="font-display font-black text-3xl md:text-4xl tracking-tight leading-tight">
            Ready to streamline your construction operations?
          </h2>
          <p className="text-zinc-400 text-sm max-w-lg mx-auto">
            Sign in with your Google account to sync live attendance records, verify compliance states, and dispatch crew payouts.
          </p>
          <div className="pt-4">
            <button
              onClick={handleLogin}
              className="mx-auto group flex items-center gap-3 bg-white text-[#09090B] hover:bg-[#EA580C] hover:text-white px-8 py-4 font-semibold transition-all duration-200"
            >
              <GoogleLogo size={20} weight="bold" />
              Continue with Google
            </button>
            <p className="text-xs text-zinc-500 mt-3">No setup fees. Free diagnostic sandbox included.</p>
          </div>
        </div>

        {/* Global Footer Grid */}
        <div className="max-w-7xl mx-auto px-8 lg:px-16 py-12 border-t border-zinc-900 grid grid-cols-2 md:grid-cols-4 gap-8 text-xs text-zinc-400">
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-white">
              <HardHat size={18} weight="fill" className="text-[#EA580C]" />
              <span className="font-display font-extrabold text-sm tracking-tight">KARYA<span className="text-[#EA580C]">.</span></span>
            </div>
            <p className="text-[11px] text-zinc-500">
              The AI Operating System built for emerging markets' informal construction workforce.
            </p>
          </div>

          <div className="space-y-2">
            <p className="text-white font-bold text-[11px] uppercase tracking-wider">Product</p>
            <ul className="space-y-1.5">
              <li><a href="#features" className="hover:text-white">Features</a></li>
              <li><a href="/blog" className="hover:text-white" data-testid="footer-blog">Blog</a></li>
              <li><a href="#faq" className="hover:text-white">Pricing</a></li>
              <li><a href="/contact" className="hover:text-white" data-testid="footer-contact">Contact</a></li>
            </ul>
          </div>

          <div className="space-y-2">
            <p className="text-white font-bold text-[11px] uppercase tracking-wider">Company</p>
            <ul className="space-y-1.5">
              <li><a href="/contact" className="hover:text-white">About SIXN8</a></li>
              <li><a href="/contact" className="hover:text-white">Support & Docs</a></li>
              <li><a href="mailto:sixn8.technologies@gmail.com" className="hover:text-white flex items-center gap-1">
                <Envelope size={12} /> sixn8.technologies@gmail.com
              </a></li>
            </ul>
          </div>

          <div className="space-y-2">
            <p className="text-white font-bold text-[11px] uppercase tracking-wider">Headquarters</p>
            <p className="text-[11px] text-zinc-500 leading-relaxed">
              SIXN8 Technologies Private Ltd<br />
              Bangalore, Karnataka, India
            </p>
            <p className="pt-2 text-[10px] text-zinc-600">
              © {new Date().getFullYear()} SIXN8 Technologies. All rights reserved.
            </p>
          </div>
        </div>
      </div>

    </div>
  );
}
