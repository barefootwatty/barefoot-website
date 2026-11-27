// Walkabout warranty registration — runs on Vercel, same setup as enquiry.js.
//
// The warranty covers the registered ORIGINAL owner (GW, 7 Nov 2026, modelled
// on Thomas & Thomas). Each registration emails Watty a record (subject starts
// "Walkabout warranty —" so Gmail can filter/label them) and sends the owner a
// confirmation they can keep. Uses the same RESEND_API_KEY as enquiry.js.

const TO = process.env.ENQUIRY_TO || "glenn@barefootfishingsafaris.com.au";
const FROM = process.env.ENQUIRY_FROM || "Watty at Barefoot <glenn@barefootfishingsafaris.com.au>";

const FIELDS = ["name", "email", "phone", "country", "rod", "from", "date", "order"];
const LABELS = {
  name: "Owner",
  email: "Email",
  phone: "Phone",
  country: "Country / postcode",
  rod: "Rod",
  from: "Bought from",
  date: "Date bought",
  order: "Purchase ID",
};
const RODS = ["Walkabout Baitcast", "Walkabout Spin"];

function clean(value, max = 200) {
  return String(value == null ? "" : value).trim().slice(0, max);
}

function validEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value);
}

function ownerText(data) {
  const first = data.name.split(/\s+/)[0];
  return [
    `G'day ${first},`,
    "",
    `Your ${data.rod} is registered to you. Keep this email: it's your warranty record.`,
    "",
    ...FIELDS.filter((k) => data[k] && k !== "email").map((k) => `${LABELS[k]}: ${data[k]}`),
    "",
    "As the registered original owner, you can buy a replacement for any section of your rod, and I can send you the Fuji guide codes if you ever need a guide replaced. Just reply to this email and tell me which rod and which section.",
    "",
    "Tight lines,",
    "Watty",
    "Barefoot Fishing Safaris · 0417 272 871",
    "https://barefootfishingsafaris.com.au/walkabout",
  ].join("\n");
}

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ ok: false, error: "Method not allowed" });
  }

  let body = req.body;
  if (typeof body === "string") {
    try { body = JSON.parse(body); } catch { return res.status(400).json({ ok: false, error: "Could not read that form." }); }
  }
  body = body || {};

  if (clean(body.website)) return res.status(200).json({ ok: true }); // honeypot

  const data = {};
  for (const key of FIELDS) data[key] = clean(body[key]);

  if (!data.name) return res.status(400).json({ ok: false, error: "Please add your name." });
  if (!validEmail(data.email)) return res.status(400).json({ ok: false, error: "Please check your email address. It's where your warranty record goes." });
  if (!RODS.includes(data.rod)) return res.status(400).json({ ok: false, error: "Please pick which rod you have." });
  if (!data.from || !data.date) return res.status(400).json({ ok: false, error: "Please say where and when you bought it." });
  if (!data.order) return res.status(400).json({ ok: false, error: "Please add the Purchase ID from your warranty card." });

  const lines = FIELDS.filter((k) => data[k]).map((k) => `${LABELS[k]}: ${data[k]}`).join("\n");
  const text = `New Walkabout warranty registration\n\n${lines}\n`;

  const key = process.env.RESEND_API_KEY;
  if (!key) {
    console.error("WARRANTY (no RESEND_API_KEY set):\n" + text);
    return res.status(503).json({ ok: false, error: "Registration isn't connected yet. Please email glenn@barefootfishingsafaris.com.au." });
  }

  try {
    const r = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        from: FROM,
        to: [TO],
        reply_to: data.email,
        subject: `Walkabout warranty — ${data.name}, ${data.rod}`,
        text,
      }),
    });
    if (!r.ok) {
      console.error("Resend rejected warranty:", r.status, await r.text());
      console.error("WARRANTY (send failed, preserved here):\n" + text);
      return res.status(502).json({ ok: false, error: "Could not register just now. Please try again in a minute." });
    }

    let confirmed = false;
    try {
      const a = await fetch("https://api.resend.com/emails", {
        method: "POST",
        headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          from: FROM,
          to: [data.email],
          reply_to: TO,
          subject: `Your ${data.rod} is registered`,
          text: ownerText(data),
        }),
      });
      confirmed = a.ok;
      if (!a.ok) console.error("Warranty confirmation rejected:", a.status, await a.text());
    } catch (err) {
      console.error("Warranty confirmation failed:", err);
    }

    return res.status(200).json({ ok: true, confirmed });
  } catch (err) {
    console.error("Warranty send threw:", err);
    console.error("WARRANTY (send failed, preserved here):\n" + text);
    return res.status(502).json({ ok: false, error: "Could not register just now. Please try again in a minute." });
  }
}
