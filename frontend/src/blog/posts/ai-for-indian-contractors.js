import React from "react";

const post = {
  slug: "ai-for-indian-contractors",
  title: "The AI operating system for Indian construction contractors",
  description:
    "How Karya replaces spreadsheets, WhatsApp groups, and paper site diaries with a single AI that runs workers, payroll, compliance and daily reports — in Hindi, Tamil, Malayalam, Telugu, Kannada, Bengali and Marathi.",
  date: "2026-01-08",
  readingTimeMin: 6,
  tags: ["construction", "India", "AI", "payroll", "compliance"],
  body: () => (
    <>
      <p>
        Indian construction is a <strong>$700-billion industry</strong> that
        still runs on paper diaries, WhatsApp forwards, and Excel sheets a
        munshi has been maintaining for two decades. Every contractor
        we&apos;ve spoken to has the same three problems:
      </p>
      <ol>
        <li>They can&apos;t reconcile what they paid a worker last month.</li>
        <li>They miss compliance deadlines and get fined.</li>
        <li>They have no idea if they&apos;re actually profitable on any given site.</li>
      </ol>

      <h2>Why generic construction software fails in India</h2>
      <p>
        Global players like Procore or Buildertrend assume a US general
        contractor with W-2 employees, unions, and OSHA compliance. An Indian
        contractor manages 40 daily-wage workers on 3 sites, deals with GST,
        EPFO, ESIC, labour licenses, and a subcontractor with a WhatsApp
        number. The tooling gap is enormous.
      </p>

      <h2>What Karya does differently</h2>
      <ul>
        <li>
          <strong>Talks in your language.</strong> The AI assistant on Telegram
          replies in Hindi, Tamil, Malayalam, Telugu, Kannada, Bengali, or
          Marathi — whichever the user set. Voice notes get spoken TTS replies.
        </li>
        <li>
          <strong>Runs on messenger apps.</strong> Site supervisors don&apos;t
          install anything. They forward a receipt photo to{" "}
          <a href="https://t.me/karya_ops_bot">@karya_ops_bot</a> and AI files
          it as an expense with vendor, amount, and category extracted.
        </li>
        <li>
          <strong>Handles payroll like a munshi.</strong> Advances, bonuses,
          deductions, and settlements are tracked per worker with a running
          balance. Bulk-pay commands like{" "}
          <code>&ldquo;Pay Ramesh 8000&rdquo;</code> just work.
        </li>
        <li>
          <strong>Never misses a deadline.</strong> Compliance items
          (labour-license renewal, EPFO returns, GST filings) get
          proactively-pinged 3 days, 1 day, and on the due date via Telegram.
        </li>
        <li>
          <strong>Shows you if you&apos;re profitable.</strong> The Cost
          Trends dashboard rolls up expenses, labour wages, and subcontractor
          payments per project with a budget-vs-actual overlay you can read at
          a glance.
        </li>
      </ul>

      <h2>Who is this for</h2>
      <p>
        Small to mid-size contractors doing ₹1 Cr – ₹50 Cr / year of work
        across 1–20 sites. Real-estate developers running &lt;100 workers,
        interior fit-out firms, plumbing & electrical subcontractors, and
        anyone tired of chasing a munshi at month-end for numbers that should
        be one query away.
      </p>

      <p>
        <a
          href="https://karyaai.app/"
          target="_blank"
          rel="noopener"
        >
          Try Karya free →
        </a>{" "}
        Sign in with Google, link Telegram in 30 seconds, forward your first
        receipt.
      </p>
    </>
  ),
};

export default post;
