import React from "react";

const post = {
  slug: "cost-trends-budget-vs-actual",
  title: "How Karya's cost trends & budget-vs-actual overlay works",
  description:
    "A deep dive into how Karya rolls up expenses, labour wages, and subcontractor payments into a single month-over-month view — and how the budget overlay flags projects heading over-budget before they blow up.",
  date: "2026-01-03",
  readingTimeMin: 4,
  tags: ["cost tracking", "budget", "reporting"],
  body: () => (
    <>
      <p>
        The single most-requested feature in Karya&apos;s first year was
        &ldquo;show me if I&apos;m over budget on Site X before I write the
        next cheque.&rdquo; That&apos;s a harder problem than it looks. A real
        project&apos;s cost lives in three separate places:
      </p>
      <ul>
        <li>Material and petty expenses (your receipts).</li>
        <li>Labour wages & bonuses (your worker ledger).</li>
        <li>Subcontractor payments and extras (your sub ledger).</li>
      </ul>
      <p>
        Most tools ask you to keep those three separate and reconcile them in
        Excel at month-end. Karya rolls them up in real time and shows you the
        picture on a single chart — updated the moment a receipt is
        forwarded via Telegram or a wage entry is posted.
      </p>

      <h2>The three streams, unified</h2>
      <p>
        Under the hood, the{" "}
        <code>GET /api/cost-trends</code> endpoint pulls three collections —
        expenses, worker transactions (wage + bonus), sub-transactions
        (payments + advances + extra work) — filters by owner, optionally by
        project, and buckets them by <em>week</em>, <em>month</em>,{" "}
        <em>quarter</em>, or <em>year</em>. The frontend renders it as a
        stacked bar chart (Expenses in orange, Labour in black, Subs in amber)
        with a dashed green reference line for the budget threshold when a
        single project is picked.
      </p>

      <h2>Budget vs actual — the signal, not the noise</h2>
      <p>
        Every project gets a budget field. The Cost Intelligence panel
        classifies each project into <strong>ok</strong> (&lt;80% used),{" "}
        <strong>warn</strong> (80–100%), <strong>over</strong> (&gt;100%), or{" "}
        <strong>no_budget</strong>. The colours match: green, amber, red,
        gray. A horizontal bar chart shows all projects at once so you can
        spot the two that need immediate attention.
      </p>
      <p>
        A separate call-out row appears if any expenses aren&apos;t attached
        to a project — the fastest way to keep budgets accurate is to attach
        every receipt as it comes in, which the Web upload flow now does
        automatically.
      </p>

      <h2>Time windows worth caring about</h2>
      <p>
        We ship four period toggles (Weekly, Monthly, Quarterly, Yearly) and
        four range toggles (All time, Last 3, Last 6, Last 12). Quarterly is
        the sweet spot for owners; monthly is for on-the-ground supervisors;
        weekly is for the tight-cash-flow moments. Yearly is for board decks.
      </p>

      <p>
        <a
          href="https://karyaai.app/"
          target="_blank"
          rel="noopener"
        >
          Open the Cost Trends dashboard →
        </a>{" "}
        (sign in first — the demo user starts at zero, forward a receipt or
        two to see the chart light up).
      </p>
    </>
  ),
};

export default post;
