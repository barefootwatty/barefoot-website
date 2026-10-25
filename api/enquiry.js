// Enquiry handler — runs on Vercel, on Watty's own domain.
//
// WHY THIS EXISTS: the enquiry form used to be a mailto: link, which opens the
// visitor's own email app. On a phone that usually works. On a desktop with no
// mail client set up, the click does nothing at all and the enquiry is lost
// silently — you never even know someone tried. This posts the enquiry to the
// server instead, so it always lands.
//
// SETUP (one environment variable, set in the Vercel dashboard):
//   RESEND_API_KEY   an API key from resend.com
// Optional overrides:
//   ENQUIRY_TO       where enquiries go       (default glenn@barefootfishingsafaris.com.au)
//   ENQUIRY_FROM     the From address         (default onboarding@resend.dev)
//
// The From address only matters for deliverability — Reply-To is always set to
// the person enquiring, so hitting reply in Gmail answers the customer.
//
// Each enquirer also gets an automatic reply listing the open dates. Resend
// only delivers that to outside addresses once ENQUIRY_FROM is on a domain
// verified in Resend — on the default onboarding@resend.dev it is rejected,
// quietly, and the visitor just sees the normal "landed with Watty" message.

const TO = process.env.ENQUIRY_TO || "glenn@barefootfishingsafaris.com.au";
const FROM = process.env.ENQUIRY_FROM || "Barefoot website <onboarding@resend.dev>";

const FIELDS = ["name", "email", "phone", "size", "when", "days", "message"];
const LABELS = {
  name: "Name",
  email: "Email",
  phone: "Phone",
  size: "Group size",
  when: "Time of year",
  days: "Days fishing",
  message: "Notes",
};

const SITE = "https://barefootfishingsafaris.com.au";
const MONTHS = ["January", "February", "March", "April", "May", "June", "July",
  "August", "September", "October", "November", "December"];

function range(w) {
  const [, am, ad] = w.start.split("-").map(Number);
  const [, bm, bd] = w.end.split("-").map(Number);
  return am === bm ? `${ad}–${bd} ${MONTHS[bm - 1]}` : `${ad} ${MONTHS[am - 1]} – ${bd} ${MONTHS[bm - 1]}`;
}

// The open dates come from the same file the pages are built from, fetched
// live, so the auto-reply can never disagree with the website.
async function openDatesText(host) {
  const r = await fetch(`https://${host}/assets/availability.json`);
  if (!r.ok) throw new Error(`availability.json ${r.status}`);
  const av = await r.json();
  const today = new Date().toISOString().slice(0, 10);
  const live = av.windows.filter((w) => w.end >= today);
  const booked = live.filter((w) => w.status === "booked").length;
  const pct = live.length ? Math.round((100 * booked) / live.length) : 0;
  const blocks = Object.entries(av.trips).map(([key, t]) => {
    const open = live.filter((w) => w.trip === key && w.status === "open");
    const rows = open.length ? open.map((w) => `  • ${range(w)} ${w.start.slice(0, 4)}`).join("\n") : "  • All booked — ask about the waitlist";
    return `${t.name} · ${t.place}\n${rows}\n  ${SITE}/${t.page}`;
  });
  return { text: blocks.join("\n\n"), pct, year: av.year };
}

function autoReplyText(data, dates) {
  const first = data.name.split(/\s+/)[0];
  return [
    `G'day ${first},`,
    "",
    "Thanks for getting in touch — your enquiry has landed with me. I'm out on the water most days, so give me a day or two to come back to you properly.",
    data.when ? `\nYou asked about: ${data.when}` : "",
    "",
    "So you're not left waiting on me for the basics, here's exactly what's still open right now:",
    "",
    dates.text,
    "",
    `${dates.year} is already ${dates.pct}% booked, and the best tide windows often book out up to two years ahead. Dates are held first in, best dressed, and a 30% deposit locks yours in.`,
    "",
    "If one of those suits, just hit reply and tell me which one and how many in your crew.",
    /waitlist/i.test(data.when) ? "\nYou picked a booked date, so I've got you down for the waitlist — I'll be in touch if it comes free." : "",
    "",
    "Cheers,",
    "Watty",
    "Barefoot Fishing Safaris · 0417 272 871",
    SITE,
  ].filter((l, i, a) => !(l === "" && a[i - 1] === "")).join("\n");
}

function clean(value, max = 2000) {
  return String(value == null ? "" : value).trim().slice(0, max);
}

function validEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value);
}

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ ok: false, error: "Method not allowed" });
  }

  let body = req.body;
  if (typeof body === "string") {
    try {
      body = JSON.parse(body);
    } catch {
      return res.status(400).json({ ok: false, error: "Could not read that form." });
    }
  }
  body = body || {};

  // Honeypot: a field hidden from people but usually filled in by bots. Answer
  // 200 so the bot thinks it worked and doesn't come back looking for a gap.
  if (clean(body.website)) {
    return res.status(200).json({ ok: true });
  }

  const data = {};
  for (const key of FIELDS) data[key] = clean(body[key], key === "message" ? 4000 : 200);

  if (!data.name) {
    return res.status(400).json({ ok: false, error: "Please add your name." });
  }
  if (!validEmail(data.email)) {
    return res.status(400).json({ ok: false, error: "Please check your email address — that's how Watty gets back to you." });
  }

  const lines = FIELDS
    .filter((k) => data[k])
    .map((k) => `${LABELS[k]}: ${data[k]}`)
    .join("\n");
  const source = clean(body.source, 120) || "website";
  const text = `New enquiry from the Barefoot website (${source})\n\n${lines}\n`;

  const key = process.env.RESEND_API_KEY;
  if (!key) {
    // Not configured yet. Log it so nothing is lost while setup is pending,
    // and tell the browser to fall back to opening the visitor's mail app.
    console.error("ENQUIRY (no RESEND_API_KEY set):\n" + text);
    return res.status(503).json({ ok: false, fallback: true, error: "Email is not connected yet." });
  }

  try {
    const r = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from: FROM,
        to: [TO],
        reply_to: data.email,
        subject: `Trip enquiry — ${data.name}${data.when ? `, ${data.when}` : ""}`,
        text,
      }),
    });

    if (!r.ok) {
      const detail = await r.text();
      // Log the full detail for debugging, but never show it to the visitor.
      console.error("Resend rejected the enquiry:", r.status, detail);
      console.error("ENQUIRY (send failed, preserved here):\n" + text);
      return res.status(502).json({ ok: false, fallback: true, error: "Could not send just now." });
    }

    // Second email: the enquirer gets the open dates straight back. This is a
    // bonus — if it fails for any reason, Watty's copy has already gone, so
    // the enquiry still counts as sent.
    let autoreply = false;
    try {
      const dates = await openDatesText(req.headers["x-forwarded-host"] || req.headers.host);
      const a = await fetch("https://api.resend.com/emails", {
        method: "POST",
        headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          from: FROM,
          to: [data.email],
          reply_to: TO,
          subject: "Got your enquiry — here's what's still open",
          text: autoReplyText(data, dates),
        }),
      });
      autoreply = a.ok;
      if (!a.ok) console.error("Auto-reply rejected:", a.status, await a.text());
    } catch (err) {
      console.error("Auto-reply failed:", err);
    }

    return res.status(200).json({ ok: true, autoreply });
  } catch (err) {
    console.error("Enquiry send threw:", err);
    console.error("ENQUIRY (send failed, preserved here):\n" + text);
    return res.status(502).json({ ok: false, fallback: true, error: "Could not send just now." });
  }
}
