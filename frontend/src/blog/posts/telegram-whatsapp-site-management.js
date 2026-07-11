import React from "react";

const post = {
  slug: "telegram-whatsapp-site-management",
  title: "Running a construction site from WhatsApp and Telegram",
  description:
    "Why Karya put the primary interface on messengers your workers already use — not on a mobile app they'll never install. A field guide to Telegram-first site operations.",
  date: "2026-01-05",
  readingTimeMin: 4,
  tags: ["Telegram", "WhatsApp", "field ops", "mobile"],
  body: () => (
    <>
      <p>
        The dirty secret of construction software is that <em>nobody on-site
        installs the app</em>. Site supervisors download it once, forget the
        password, and go back to shouting attendance updates on the site
        WhatsApp group. The last-mile of any construction workflow lives on
        the messenger app the crew already uses.
      </p>

      <p>
        Karya was built around that reality. The primary interface is the
        Telegram bot{" "}
        <a href="https://t.me/karya_ops_bot" target="_blank" rel="noopener">
          @karya_ops_bot
        </a>{" "}
        (with WhatsApp on the roadmap via Twilio). Everything a supervisor
        needs to do — mark attendance, forward a receipt, log an advance,
        record a task-completion, send a daily site report — happens in a
        chat.
      </p>

      <h2>What the Telegram bot actually does</h2>
      <ul>
        <li>
          <strong>Natural-language commands.</strong> &ldquo;Ramesh took an
          advance of 5000&rdquo; posts an advance to Ramesh&apos;s ledger.
          &ldquo;10 workers came to Site A today&rdquo; logs attendance.
        </li>
        <li>
          <strong>Forward-and-file media.</strong> Send a receipt photo, tap
          &ldquo;Receipt&rdquo;, and AI parses vendor + amount + category into
          your expense ledger. Send a photo of a completed slab, tap
          &ldquo;Daily report&rdquo;, and it gets attached to today&apos;s log.
        </li>
        <li>
          <strong>Voice-first for supervisors who don&apos;t type.</strong>{" "}
          Record a Hindi/Tamil/Malayalam voice note; Whisper transcribes it;
          the AI executes the command; the bot replies with a Hindi/Tamil TTS
          confirmation.
        </li>
        <li>
          <strong>Proactive morning briefings.</strong> Opt-in daily digest at
          your chosen time — active workers, upcoming compliance deadlines,
          pending settlements.
        </li>
        <li>
          <strong>Compliance alerts.</strong> Automatic 3-day / 1-day / on-the-day
          reminders for every deadline you record.
        </li>
        <li>
          <strong>Multi-language replies.</strong> The bot detects your saved
          app language and responds in it (long messages only — short acks
          stay in English so numbers and names don&apos;t get transliterated).
        </li>
      </ul>

      <h2>Why not just a mobile app?</h2>
      <p>
        We tried. Two rounds of user testing killed the idea. Site staff
        won&apos;t install one more app; the Play Store rating tanks the
        moment mobile data gets patchy on-site; and updating a native app
        every time we ship a feature is a losing race. Telegram gives us
        near-native UX, push notifications, media handling, and multi-device
        sync — for zero install friction.
      </p>

      <p>
        <a
          href="https://karyaai.app/"
          target="_blank"
          rel="noopener"
        >
          Try Karya free →
        </a>{" "}
        Link your Telegram from the Profile page, forward a receipt, and watch
        the AI file it for you in under 10 seconds.
      </p>
    </>
  ),
};

export default post;
