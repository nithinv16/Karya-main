import React from "react";

const post = {
  slug: "built-with-emergent",
  title: "Karya is built with Emergent.sh — the AI platform for domain founders",
  description:
    "How a small team of construction operators shipped a production-grade AI platform without hiring a full engineering staff — using Emergent.sh to scaffold React, FastAPI, and MongoDB in days, not months.",
  date: "2026-01-11",
  readingTimeMin: 5,
  tags: ["Emergent", "AI platform", "startup", "no-code", "vibecoding"],
  body: () => (
    <>
      <p>
        Karya AI was built by a small team of construction operators, not
        engineers. The features you use every day — the Telegram assistant that
        parses receipts, the automatic payroll ledger, the AI compliance
        calendar, the month-over-month cost trends — were shipped in weeks, not
        quarters, because we built the entire platform on{" "}
        <a href="https://emergent.sh" target="_blank" rel="noopener">
          Emergent.sh
        </a>
        .
      </p>

      <h2>Why we chose Emergent over Lovable, Replit or a traditional stack</h2>
      <p>
        Building a production application for construction contractors is
        deceptively hard. You need a real backend (FastAPI + MongoDB), a real
        frontend (React with proper state, auth, and routing), file storage,
        LLM integrations, WhatsApp and Telegram bots, PDF generation,
        multi-currency + multi-language logic, and a way to iterate on all of
        it without breaking production. Most{" "}
        <em>&ldquo;AI website builder&rdquo;</em> tools stop at landing pages;
        real business apps demand full-stack control.
      </p>
      <p>
        We evaluated three options — <strong>Lovable</strong>,{" "}
        <strong>Replit</strong>, and <strong>Emergent.sh</strong>. Lovable was
        beautiful but stopped at the frontend; Replit was flexible but slow to
        iterate on complex backends. Emergent gave us all three: a
        production-grade React + FastAPI + MongoDB stack, one-click deploys,
        first-class LLM tools (OpenAI GPT-5, Claude Sonnet, Gemini Nano
        Banana), and an AI agent that could write, refactor, and test both
        halves of the stack from a single prompt.
      </p>

      <h2>What Emergent shipped for us in the first sprint</h2>
      <ul>
        <li>Full auth flow via Emergent-managed Google OAuth — no client_id / secret bureaucracy.</li>
        <li>Multi-tenant MongoDB schema for projects, workers, payroll, compliance.</li>
        <li>Telegram bot webhook + secret validation + AI-parsed receipts.</li>
        <li>Twilio-powered phone verification with auto-provisioned Verify Service.</li>
        <li>WhatsApp integration (Twilio) for daily site briefings.</li>
        <li>Recharts-based cost trends & budget vs. actual dashboards.</li>
        <li>Sentry-style error surfaces and PostHog analytics baked in.</li>
      </ul>

      <h2>The Emergent workflow, in three lines</h2>
      <ol>
        <li>Describe the feature (e.g. &ldquo;proactive Telegram pings with user-configurable schedules&rdquo;).</li>
        <li>The Emergent agent scaffolds backend + frontend, wires tests, and shows you a passing screenshot.</li>
        <li>You review, ship to preview, then one-click deploy to production.</li>
      </ol>
      <p>
        If you&apos;re a domain founder — construction, healthcare, logistics,
        legal, whatever — and you&apos;ve been told for years that you need a
        full engineering team before you can build the software your industry
        deserves, you don&apos;t. Emergent is what changed our timeline from
        &ldquo;maybe next year&rdquo; to shipping to real customers this
        quarter.
      </p>
      <p>
        <strong>Try Emergent.sh today.</strong> The platform is free to start,
        and the Universal LLM key means you don&apos;t have to bring your own
        OpenAI / Anthropic / Gemini credentials to build something serious.{" "}
        <a
          href="https://app.emergent.sh/?utm_source=karya&utm_medium=blog&utm_campaign=built-with-emergent"
          target="_blank"
          rel="noopener"
        >
          Start building on Emergent.sh →
        </a>
      </p>
      <p className="text-sm text-neutral-500 mt-8 italic">
        Disclosure: Karya AI is a paying Emergent customer. We have no
        commercial relationship beyond that — we&apos;re writing this because
        we genuinely believe Emergent is the fastest path from &ldquo;I&apos;ve
        got a domain problem&rdquo; to &ldquo;I&apos;ve got a shipped
        product.&rdquo;
      </p>
    </>
  ),
};

export default post;
