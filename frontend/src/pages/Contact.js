import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import api from "@/lib/api";
import { toast } from "sonner";
import { EnvelopeSimple, PaperPlaneTilt, ArrowLeft, CheckCircle } from "@phosphor-icons/react";

const inputCls = "border-2 border-[#E4E4E7] focus:border-[#EA580C] outline-none px-4 py-3 text-sm transition-colors duration-200 bg-white w-full";

export default function Contact() {
  const [form, setForm] = useState({ name: "", email: "", phone: "", company: "", subject: "", message: "" });
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [company, setCompany] = useState(null);

  useEffect(() => {
    api.get("/company-info").then((r) => setCompany(r.data)).catch(() => {});
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.post("/contact", form);
      setDone(true);
      setForm({ name: "", email: "", phone: "", company: "", subject: "", message: "" });
    } catch (err) {
      const msg = err?.response?.data?.detail;
      if (Array.isArray(msg)) toast.error(msg[0]?.msg || "Please check your inputs.");
      else toast.error(msg || "Couldn't send your message. Please try the email link.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-white text-[#09090B]">
      <Helmet>
        <title>Contact Karya AI — Ops enquiries, demos, partnerships</title>
        <meta name="description" content="Get in touch with the Karya AI team. We usually respond within one working day. Support email admin@dukaaon.in, or send us a message via this form." />
        <link rel="canonical" href="https://karyaai.app/contact" />
      </Helmet>

      <header className="border-b border-[#E4E4E7]">
        <div className="max-w-5xl mx-auto px-6 py-6 flex items-center justify-between">
          <Link to="/" className="font-display font-black text-lg tracking-tight" data-testid="contact-home-link">
            Karya<span className="text-[#EA580C]">.</span>
          </Link>
          <nav className="flex items-center gap-5 text-sm">
            <Link to="/blog" className="text-[#71717A] hover:text-[#09090B]">Blog</Link>
            <Link to="/pricing" className="text-[#71717A] hover:text-[#09090B]">Pricing</Link>
            <Link to="/contact" className="font-semibold text-[#09090B]">Contact</Link>
            <Link to="/" className="bg-[#EA580C] text-white px-4 py-2 font-semibold hover:bg-[#C2410C] transition-colors">
              Sign in
            </Link>
          </nav>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-16">
        <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-[#71717A] hover:text-[#EA580C] mb-6" data-testid="contact-back">
          <ArrowLeft size={14} /> Back home
        </Link>
        <p className="overline text-[#EA580C]">Get in touch</p>
        <h1 className="font-display font-black text-4xl sm:text-5xl tracking-tight mt-2">
          Talk to the Karya team.
        </h1>
        <p className="text-lg text-[#3f3f46] mt-4 max-w-2xl leading-relaxed">
          Product demos, partnership enquiries, custom integrations, or just curious about how we can help your ops team — drop us a note. We usually respond within one working day.
        </p>

        <section className="mt-10 grid md:grid-cols-3 gap-6">
          <div className="md:col-span-2">
            {done ? (
              <div className="border-2 border-[#16A34A] bg-[#F0FDF4] p-8 text-center" data-testid="contact-thanks">
                <CheckCircle size={44} weight="duotone" className="mx-auto text-[#16A34A] mb-3" />
                <h2 className="font-display font-bold text-2xl mb-2">Thank you — we've got it.</h2>
                <p className="text-sm text-[#3f3f46] max-w-md mx-auto leading-relaxed">
                  Someone from the {company?.legal_name || "Karya"} team will reply within one working day. If it's urgent, email us at{" "}
                  <a href={`mailto:${company?.support_email || "admin@dukaaon.in"}`} className="text-[#EA580C] underline font-semibold">
                    {company?.support_email || "admin@dukaaon.in"}
                  </a>
                  .
                </p>
                <button
                  onClick={() => setDone(false)}
                  className="mt-6 text-xs text-[#71717A] hover:text-[#09090B] underline"
                  data-testid="contact-send-another"
                >
                  Send another message
                </button>
              </div>
            ) : (
              <form onSubmit={submit} className="border-2 border-[#09090B] bg-white p-6 space-y-4" data-testid="contact-form">
                <div className="grid sm:grid-cols-2 gap-4">
                  <input
                    data-testid="contact-name"
                    required
                    placeholder="Your name"
                    className={inputCls}
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    maxLength={120}
                  />
                  <input
                    data-testid="contact-email"
                    required
                    type="email"
                    placeholder="Email"
                    className={inputCls}
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    maxLength={120}
                  />
                </div>
                <div className="grid sm:grid-cols-2 gap-4">
                  <input
                    data-testid="contact-phone"
                    placeholder="Phone (optional)"
                    className={inputCls}
                    value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                    maxLength={40}
                  />
                  <input
                    data-testid="contact-company"
                    placeholder="Company (optional)"
                    className={inputCls}
                    value={form.company}
                    onChange={(e) => setForm({ ...form, company: e.target.value })}
                    maxLength={120}
                  />
                </div>
                <input
                  data-testid="contact-subject"
                  placeholder="Subject"
                  className={inputCls}
                  value={form.subject}
                  onChange={(e) => setForm({ ...form, subject: e.target.value })}
                  maxLength={200}
                />
                <textarea
                  data-testid="contact-message"
                  required
                  placeholder="Tell us a bit about what you're looking for. (Site count, workforce size, current tooling, etc.)"
                  className={inputCls + " min-h-32 resize-y"}
                  value={form.message}
                  onChange={(e) => setForm({ ...form, message: e.target.value })}
                  minLength={10}
                  maxLength={5000}
                />
                <div className="flex items-center justify-between pt-2">
                  <p className="text-xs text-[#71717A]">We'll never share your details.</p>
                  <button
                    type="submit"
                    disabled={submitting}
                    data-testid="contact-submit"
                    className="inline-flex items-center gap-2 bg-[#EA580C] text-white px-5 py-2.5 text-sm font-semibold hover:bg-[#C2410C] transition-colors disabled:opacity-60"
                  >
                    <PaperPlaneTilt size={15} weight="fill" />
                    {submitting ? "Sending…" : "Send message"}
                  </button>
                </div>
              </form>
            )}
          </div>

          {/* Right column — company info */}
          <aside className="space-y-4" data-testid="contact-company-info">
            <div className="border border-[#E4E4E7] bg-[#FAFAFA] p-5">
              <p className="overline">Company</p>
              <p className="font-display font-bold text-sm mt-1">{company?.legal_name || "SIXN8 Technologies Private Ltd"}</p>
              <p className="text-xs text-[#71717A] mt-1">Product: {company?.product_name || "Karya AI"}</p>
            </div>
            <div className="border border-[#E4E4E7] bg-[#FAFAFA] p-5">
              <p className="overline">Support email</p>
              <a
                href={`mailto:${company?.support_email || "admin@dukaaon.in"}`}
                data-testid="contact-support-email"
                className="text-[#EA580C] font-semibold text-sm mt-1 inline-flex items-center gap-1.5 hover:underline"
              >
                <EnvelopeSimple size={14} weight="bold" />
                {company?.support_email || "admin@dukaaon.in"}
              </a>
              <p className="text-xs text-[#71717A] mt-2">Response within 1 working day.</p>
            </div>
            <div className="border border-[#E4E4E7] bg-[#FAFAFA] p-5">
              <p className="overline">Website</p>
              <a href={company?.website || "https://karyaai.app"} className="text-[#EA580C] font-semibold text-sm mt-1 inline-block hover:underline">
                {(company?.website || "https://karyaai.app").replace(/^https?:\/\//, "")}
              </a>
            </div>
          </aside>
        </section>
      </main>

      <footer className="border-t border-[#E4E4E7] mt-24 py-10 text-center text-xs text-[#71717A]">
        © {new Date().getFullYear()} {company?.legal_name || "SIXN8 Technologies Private Ltd"} · Built on{" "}
        <a href="https://emergent.sh" className="underline" target="_blank" rel="noopener noreferrer">
          Emergent.sh
        </a>
      </footer>
    </div>
  );
}
