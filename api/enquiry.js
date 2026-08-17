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

    return res.status(200).json({ ok: true });
  } catch (err) {
    console.error("Enquiry send threw:", err);
    console.error("ENQUIRY (send failed, preserved here):\n" + text);
    return res.status(502).json({ ok: false, fallback: true, error: "Could not send just now." });
  }
}
