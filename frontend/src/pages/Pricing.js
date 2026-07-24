import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import { Check, CaretDown, CaretUp, HardHat, Sparkle, ShieldCheck, WhatsappLogo } from "@phosphor-icons/react";

const SITE = "https://karyaai.app";

const TIERS = [
  {
    name: "Site Pilot",
    price: "Free",
    subtext: "For single-site subcontractors",
    description: "Automate workforce records and attendance tracking on a single site without overhead costs.",
    features: [
      "Up to 15 active worker profiles",
      "Daily attendance logs via Telegram bot",
      "1 active project cost ledger",
      "Standard English & Hindi AI support",
      "Community chat & email support",
    ],
    cta: "Get Started Free",
    ctaLink: "/",
    popular: false,
  },
  {
    name: "Contractor Pro",
    price: "₹2,999",
    period: "/month",
    subtext: "For scaling construction firms",
    description: "Run multiple sites seamlessly with multi-lingual AI assistants, automated compliance and deep ledger analytics.",
    features: [
      "Unlimited worker profiles & history logs",
      "WhatsApp & Telegram bot integrations",
      "AI Voice-First command support in Tamil, Telugu, Malayalam, Hindi & English",
      "Automated PF/ESIC & contract renewal alerts",
      "100 receipts/month AI OCR invoice processing",
      "Cost trends & Budget vs. Actual analytics dashboard",
      "Priority 24/7 WhatsApp support hotline",
    ],
    cta: "Start 14-Day Free Trial",
    ctaLink: "/",
    popular: true,
  },
  {
    name: "Enterprise Ops",
    price: "Custom",
    subtext: "For infrastructure enterprises",
    description: "Dedicated infrastructure, white-labeled bots, custom integrations, and strict SLA compliance management.",
    features: [
      "Unlimited active projects & cost ledgers",
      "White-labeled WhatsApp Business API bot with custom brand name",
      "Tally, ERP & payroll database integrations",
      "Unlimited AI receipt processing & PDF export logs",
      "Dedicated account representative & setup assistance",
      "Custom SLA & localized compliance rules module",
    ],
    cta: "Contact Sales",
    ctaLink: "/contact",
    popular: false,
  },
];

const FAQS = [
  {
    q: "What is Karya AI?",
    a: "Karya is the AI-powered operating system for construction. It replaces spreadsheets, manual paperwork, and fragmented WhatsApp groups with a unified, conversational database accessible from Telegram, WhatsApp, and the web in multiple regional languages.",
  },
  {
    q: "Do my supervisors or workers need to install an app?",
    a: "No. Site supervisors and workers can submit daily reports, record attendance, onboard workers with photo IDs, and upload receipts using their existing WhatsApp or Telegram apps. The administrator accesses the consolidated payroll, compliance alerts, and analytics dashboards via the secure web console.",
  },
  {
    q: "Which languages are supported by the AI bot?",
    a: "Karya supports English, Hindi, Tamil, Malayalam, Telugu, Kannada, Bengali, and Marathi. Supervisors can dictate voice notes or send chat messages in their natural dialects, and the AI will extract payroll entries, attendance logs, or expenses automatically.",
  },
  {
    q: "How does the AI receipt scanning work?",
    a: "Supervisors can take a photo of any site voucher, fuel receipt, or invoice and send it to the Karya bot. The AI automatically parses the total amount, vendor name, categories (e.g., Materials, Fuel, Labour Advance), and files it into the correct project ledger instantly.",
  },
  {
    q: "Is there a setup fee or lock-in period?",
    a: "No. Karya plans are flexible. You can sign up on a monthly billing cycle, upgrade/downgrade at any time, or cancel without penalty. The Site Pilot tier is free forever for up to 15 workers.",
  },
];

export default function Pricing() {
  const [openFaq, setOpenFaq] = useState(null);

  const toggleFaq = (idx) => {
    setOpenFaq(openFaq === idx ? null : idx);
  };

  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Product",
        "@id": `${SITE}/pricing#product`,
        "name": "Karya AI Construction Software Subscription Plans",
        "image": `${SITE}/og-cover.png`,
        "description": "Subscription plans for Karya AI, the operating system for construction contractors. Plans range from Site Pilot (Free) to Contractor Pro (Premium site management) and Enterprise Ops.",
        "brand": { "@type": "Brand", "name": "Karya AI" },
        "offers": {
          "@type": "AggregateOffer",
          "priceCurrency": "INR",
          "lowPrice": "0",
          "highPrice": "2999",
          "offerCount": "3",
          "offers": [
            {
              "@type": "Offer",
              "name": "Site Pilot",
              "price": "0",
              "priceCurrency": "INR",
              "availability": "https://schema.org/InStock",
              "url": `${SITE}/pricing`
            },
            {
              "@type": "Offer",
              "name": "Contractor Pro",
              "price": "2999",
              "priceCurrency": "INR",
              "priceSpecification": {
                "@type": "UnitPriceSpecification",
                "price": "2999",
                "priceCurrency": "INR",
                "referenceQuantity": {
                  "@type": "QuantitativeValue",
                  "value": "1",
                  "unitCode": "MON"
                }
              },
              "availability": "https://schema.org/InStock",
              "url": `${SITE}/pricing`
            }
          ]
        }
      },
      {
        "@type": "FAQPage",
        "@id": `${SITE}/pricing#faq`,
        "mainEntity": FAQS.map((faq) => ({
          "@type": "Question",
          "name": faq.q,
          "acceptedAnswer": {
            "@type": "Answer",
            "text": faq.a
          }
        }))
      }
    ]
  };

  return (
    <div className="min-h-screen bg-white text-[#09090B]">
      <Helmet>
        <title>Pricing Plans & FAQs — Karya AI | Construction Software</title>
        <meta
          name="description"
          content="Choose the perfect plan for your construction sites. Site Pilot is free forever, or select Contractor Pro for complete WhatsApp / Telegram bot integrations, AI receipt scanning, and budget analytics."
        />
        <link rel="canonical" href={`${SITE}/pricing`} />
        <meta property="og:type" content="website" />
        <meta property="og:title" content="Karya AI — Pricing & Plans" />
        <meta property="og:url" content={`${SITE}/pricing`} />
        <meta property="og:image" content={`${SITE}/og-cover.png`} />
        <script type="application/ld+json">{JSON.stringify(jsonLd)}</script>
      </Helmet>

      {/* Global Header */}
      <header className="border-b border-[#E4E4E7]">
        <div className="max-w-5xl mx-auto px-6 py-6 flex items-center justify-between">
          <Link to="/" className="font-display font-black text-lg tracking-tight" data-testid="pricing-home-link">
            Karya<span className="text-[#EA580C]">.</span>
          </Link>
          <nav className="flex items-center gap-5 text-sm">
            <Link to="/blog" className="text-[#71717A] hover:text-[#09090B]">Blog</Link>
            <Link to="/pricing" className="font-semibold text-[#09090B]">Pricing</Link>
            <Link to="/contact" className="text-[#71717A] hover:text-[#09090B]">Contact</Link>
            <Link to="/" className="bg-[#EA580C] text-white px-4 py-2 font-semibold hover:bg-[#C2410C] transition-colors">
              Sign in
            </Link>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-5xl mx-auto px-6 py-16">
        <div className="text-center max-w-2xl mx-auto mb-16">
          <p className="overline text-[#EA580C] font-semibold tracking-wider">PLANS AND PRICING</p>
          <h1 className="font-display font-black text-4xl sm:text-5xl tracking-tight mt-3">
            Transparent pricing for builders of all scales.
          </h1>
          <p className="text-lg text-[#71717A] mt-4 leading-relaxed">
            Get started with a free tier for small crews, or upgrade for automated compliance, OCR, and multi-lingual messaging support.
          </p>
        </div>

        {/* Pricing Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 items-start mb-24">
          {TIERS.map((tier) => (
            <div
              key={tier.name}
              data-testid={`pricing-tier-${tier.name.toLowerCase().replace(" ", "-")}`}
              className={`border-2 p-8 relative flex flex-col min-h-[600px] transition-all duration-300 ${
                tier.popular
                  ? "border-[#EA580C] shadow-lg shadow-orange-50 bg-[#FCFDFD]"
                  : "border-[#09090B]"
              }`}
            >
              {tier.popular && (
                <span className="absolute -top-3.5 left-1/2 -translate-x-1/2 bg-[#EA580C] text-white font-mono text-[10px] font-bold tracking-widest px-3 py-1 uppercase">
                  Most Popular
                </span>
              )}

              <div className="mb-6">
                <h3 className="font-display font-bold text-xl tracking-tight">{tier.name}</h3>
                <p className="text-xs text-[#71717A] mt-1">{tier.subtext}</p>
              </div>

              <div className="flex items-baseline mb-6 border-b border-[#E4E4E7] pb-6">
                <span className="font-display font-black text-4xl sm:text-5xl tracking-tight">{tier.price}</span>
                {tier.period && <span className="text-sm text-[#71717A] ml-1">{tier.period}</span>}
              </div>

              <p className="text-sm text-[#3f3f46] leading-relaxed mb-8 flex-grow">
                {tier.description}
              </p>

              <ul className="space-y-3.5 mb-8 text-sm text-[#09090B] font-medium border-t border-[#E4E4E7] pt-6">
                {tier.features.map((feat, fidx) => (
                  <li key={fidx} className="flex items-start gap-2.5 leading-snug">
                    <Check size={16} weight="bold" className="text-[#EA580C] shrink-0 mt-0.5" />
                    <span>{feat}</span>
                  </li>
                ))}
              </ul>

              <Link
                to={tier.ctaLink}
                className={`w-full py-3 text-center text-sm font-semibold border-2 transition-colors duration-200 mt-auto ${
                  tier.popular
                    ? "bg-[#EA580C] border-[#EA580C] text-white hover:bg-[#C2410C]"
                    : "bg-white border-[#09090B] text-[#09090B] hover:bg-[#F4F4F5]"
                }`}
              >
                {tier.cta}
              </Link>
            </div>
          ))}
        </div>

        {/* FAQ Section */}
        <section className="max-w-3xl mx-auto border-t border-[#E4E4E7] pt-16" data-testid="faq-section">
          <div className="text-center mb-10">
            <h2 className="font-display font-black text-2xl sm:text-3xl tracking-tight">Frequently Asked Questions</h2>
            <p className="text-[#71717A] text-sm mt-2">Everything you need to know about the AI platform.</p>
          </div>

          <div className="space-y-4">
            {FAQS.map((faq, idx) => {
              const active = openFaq === idx;
              return (
                <div key={idx} className="border-2 border-[#09090B]">
                  <button
                    onClick={() => toggleFaq(idx)}
                    className="w-full text-left p-5 flex items-center justify-between font-bold text-sm tracking-tight text-[#09090B] hover:bg-[#F4F4F5] transition-colors"
                    aria-expanded={active}
                  >
                    <span>{faq.q}</span>
                    {active ? <CaretUp size={16} weight="bold" /> : <CaretDown size={16} weight="bold" />}
                  </button>
                  {active && (
                    <div className="p-5 border-t-2 border-[#09090B] bg-[#FAFAFA] text-sm text-[#3f3f46] leading-relaxed transition-all">
                      {faq.a}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      </main>

      {/* Global Footer */}
      <footer className="border-t border-[#E4E4E7] mt-24 py-10 text-center text-xs text-[#71717A]">
        © {new Date().getFullYear()} Karya AI · Built on{" "}
        <a href="https://emergent.sh" className="underline" target="_blank" rel="noopener noreferrer">
          Emergent.sh
        </a>
      </footer>
    </div>
  );
}
