// Walkabout shop checkout — runs on Vercel, on Watty's own domain.
//
// WHAT IT DOES: the Walkabout page sends a list of items and where they are
// being posted. This works out the prices and postage from
// assets/walkabout-shop.json (never from what the browser says), checks
// nothing is sold out, and opens a Stripe checkout page for the buyer.
//
// SETUP (one environment variable, set in the Vercel dashboard):
//   STRIPE_SECRET_KEY   a Stripe secret key (test key on Preview, live on Production)
// Until that is set, or while "open" is false in walkabout-shop.json, the page
// shows the "opens Sunday" message and nobody can be charged.
//
// DEPOSIT WAITLIST: once a rod has sold out, and only while "waitlist.enabled"
// is true in walkabout-shop.json, a buyer can pay a deposit (a share of the
// next-batch price in "waitlist.prices") to hold a rod from the next batch. Deposits are marked
// "walkabout-waitlist" so they are never counted as stock sold.
//
// STOCK AND THE FOUNDING 100: there is no database. Every completed order
// carries a short list of what was bought (in Stripe "metadata"). This adds
// those up to know how many rods and shirts are left.

const STRIPE = "https://api.stripe.com/v1";
const ROW = ["US","CA","GB","IE","FR","DE","ES","IT","PT","NL","BE","CH","AT","DK","SE","NO","FI","IS",
  "PL","CZ","GR","JP","SG","HK","MY","ID","TH","VN","PH","KR","TW","IN","AE","ZA","BR","AR","CL","MX",
  "FJ","NC","VU","SB","WS","TO","CK","PF"];
const REGIONS = { AU: ["AU"], NZ: ["NZ"], PG: ["PG"], ROW };

function form(obj, prefix, out) {
  out = out || [];
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}[${k}]` : k;
    if (v === undefined || v === null) continue;
    if (typeof v === "object") form(v, key, out);
    else out.push(`${encodeURIComponent(key)}=${encodeURIComponent(v)}`);
  }
  return out;
}

async function stripe(method, path, params) {
  const qs = params ? form(params).join("&") : "";
  const r = await fetch(`${STRIPE}${path}${method === "GET" && qs ? "?" + qs : ""}`, {
    method,
    headers: {
      Authorization: `Bearer ${process.env.STRIPE_SECRET_KEY}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: method === "POST" ? qs : undefined,
  });
  const j = await r.json();
  if (!r.ok) throw new Error(j.error && j.error.message ? j.error.message : `Stripe ${r.status}`);
  return j;
}

async function loadShop(host) {
  const r = await fetch(`https://${host}/assets/walkabout-shop.json`, { cache: "no-store" });
  if (!r.ok) throw new Error(`walkabout-shop.json ${r.status}`);
  return r.json();
}

// "rod-spin:1,shirt-collared|L:2" -> { "rod-spin": 1, "shirt-collared|L": 2 }
function parseItems(s) {
  const out = {};
  String(s || "").split(",").forEach((p) => {
    const i = p.lastIndexOf(":");
    if (i < 1) return;
    const n = parseInt(p.slice(i + 1), 10);
    if (n > 0) out[p.slice(0, i)] = (out[p.slice(0, i)] || 0) + n;
  });
  return out;
}

// Adds up everything sold so far from completed Stripe checkouts.
async function sold(shop) {
  const totals = {};
  let after;
  for (let page = 0; page < 20; page++) {
    const res = await stripe("GET", "/checkout/sessions", {
      limit: 100, status: "complete", created: { gte: shop.launch_ts }, starting_after: after,
    });
    for (const s of res.data) {
      if (!s.metadata || s.metadata.shop !== "walkabout" || s.payment_status !== "paid") continue;
      for (const [k, n] of Object.entries(parseItems(s.metadata.items))) totals[k] = (totals[k] || 0) + n;
    }
    if (!res.has_more) break;
    after = res.data[res.data.length - 1].id;
  }
  return totals;
}

function status(shop, totals) {
  const rodsSold = { spin: 0, baitcast: 0 };
  for (const [sku, rod] of Object.entries(shop.rods)) {
    const n = totals[sku] || 0;
    for (const [kind, each] of Object.entries(rod.rods)) rodsSold[kind] += n * each;
  }
  // Expedition Kits: "kit|shirt-collared|L|XL" = one Pair, that shirt, those shorts.
  let kitsSold = 0;
  const kitUse = {};
  for (const [key, n] of Object.entries(totals)) {
    if (!key.startsWith("kit|")) continue;
    const [, shirt, shirtSize, shortsSize] = key.split("|");
    kitsSold += n;
    rodsSold.spin += n; rodsSold.baitcast += n;
    kitUse[`${shirt}|${shirtSize}`] = (kitUse[`${shirt}|${shirtSize}`] || 0) + n;
    kitUse[`${shop.kit.shorts}|${shortsSize}`] = (kitUse[`${shop.kit.shorts}|${shortsSize}`] || 0) + n;
  }
  const allRods = rodsSold.spin + rodsSold.baitcast;
  const left = {
    spin: Math.max(0, shop.rods["rod-spin"].stock - rodsSold.spin),
    baitcast: Math.max(0, shop.rods["rod-baitcast"].stock - rodsSold.baitcast),
  };
  const extras = {};
  for (const [sku, x] of Object.entries(shop.extras)) {
    for (const [size, n] of Object.entries(x.sizes)) {
      extras[`${sku}|${size}`] = Math.max(0, n - (totals[`${sku}|${size}`] || 0) - (kitUse[`${sku}|${size}`] || 0));
    }
  }
  // Founding prices end when the limit is reached OR at "founding_ends", whichever comes first.
  const ends = Date.parse(shop.founding_ends || "");
  const inTime = Number.isNaN(ends) || Date.now() < ends;
  return { founding: allRods < shop.founding_limit && inTime, foundingLeft: Math.max(0, shop.founding_limit - allRods), foundingEnds: Number.isNaN(ends) ? null : shop.founding_ends, left, extras,
    kitsLeft: Math.max(0, shop.kit.limit - kitsSold) };
}

// Which rods can take a deposit right now: sold out, and the waitlist is switched on.
function waitlistOpen(shop, st) {
  const w = shop.waitlist || {};
  const on = w.enabled === true && w.deposit_pct > 0 && w.deposit_pct < 100;
  return { spin: on && st.left.spin < 1, baitcast: on && st.left.baitcast < 1, pct: on ? w.deposit_pct : 0 };
}

// The next-batch price a deposit locks in. Never the Founding price: if one is not set, it is the full price.
function waitlistPrice(shop, sku) {
  const p = shop.waitlist && shop.waitlist.prices && shop.waitlist.prices[sku];
  return Number.isInteger(p) && p > 0 ? p : shop.rods[sku].full;
}
const dollars = (c) => "$" + (c % 100 ? (c / 100).toFixed(2) : c / 100);

// The line beside the Pay button on the Stripe page ("checkout_notes" in walkabout-shop.json). Plain words, no links.
function checkoutNote(shop) {
  const n = shop.checkout_notes;
  if (!n) return "";
  for (const step of Array.isArray(n.steps) ? n.steps : []) {
    const until = Date.parse((step && step.until) || "");
    if (step && step.text && !Number.isNaN(until) && Date.now() < until) return String(step.text).slice(0, 1000);
  }
  return n.after ? String(n.after).slice(0, 1000) : "";
}

export default async function handler(req, res) {
  const host = req.headers["x-forwarded-host"] || req.headers.host;
  let shop;
  try { shop = await loadShop(host); }
  catch (e) { return res.status(502).json({ ok: false, error: "The shop settings did not load. Please try again." }); }

  const ready = !!process.env.STRIPE_SECRET_KEY && shop.open === true;

  if (req.method === "GET") {
    if (!ready) return res.status(200).json({ ok: true, open: false, message: shop.closed_message });
    try {
      const st = status(shop, await sold(shop));
      res.setHeader("Cache-Control", "s-maxage=20");
      return res.status(200).json({ ok: true, open: true, ...st, waitlist: waitlistOpen(shop, st) });
    } catch (e) {
      return res.status(200).json({ ok: true, open: false, message: "The checkout is having a moment. Please try again shortly." });
    }
  }

  if (req.method !== "POST") {
    res.setHeader("Allow", "GET, POST");
    return res.status(405).json({ ok: false, error: "Method not allowed" });
  }
  if (!ready) return res.status(503).json({ ok: false, error: shop.closed_message });

  let body = req.body;
  if (typeof body === "string") { try { body = JSON.parse(body); } catch (e) { body = null; } }
  if (!body || !Array.isArray(body.items) || !body.items.length) {
    return res.status(400).json({ ok: false, error: "Your order is empty." });
  }

  let st;
  try { st = status(shop, await sold(shop)); }
  catch (e) { return res.status(502).json({ ok: false, error: "Could not check stock just now. Please try again." }); }

  const origin = `https://${host}`;
  const back = `${origin}${body.from === "/walkabout-early" ? "/walkabout-early" : "/walkabout"}#offer`;

  // Deposit to hold a rod from the next batch. No postage yet: that is sorted with the balance.
  if (body.deposit === true) {
    const w = waitlistOpen(shop, st);
    const dLines = [], dMeta = [];
    let balance = 0;
    for (const it of body.items.slice(0, 5)) {
      const qty = Math.min(4, Math.max(0, parseInt(it.qty, 10) || 0));
      const sku = String(it.sku || "");
      const rod = shop.rods[sku];
      if (!qty || !rod) continue;
      if (!Object.keys(rod.rods).some((kind) => w[kind])) {
        return res.status(409).json({ ok: false, error: "The waitlist is not open for that rod. If it is still in stock you can buy it now." });
      }
      const price = waitlistPrice(shop, sku);
      const deposit = Math.round(price * w.pct / 100);
      balance += (price - deposit) * qty;
      dLines.push({ name: `${rod.name}: ${w.pct}% deposit, next batch, locked in at ${dollars(price)}`, amount: deposit, qty });
      dMeta.push(`${sku}:${qty}`);
    }
    if (!dLines.length) return res.status(400).json({ ok: false, error: "Please choose a rod to hold." });
    const dParams = {
      mode: "payment",
      success_url: `${origin}/walkabout-thanks?deposit=1`,
      cancel_url: back,
      phone_number_collection: { enabled: true },
      line_items: Object.assign({}, dLines.map((l) => ({
        quantity: l.qty,
        price_data: { currency: "aud", unit_amount: l.amount, product_data: { name: l.name } },
      }))),
      custom_text: { submit: { message: shop.waitlist.checkout_note || `This is a ${w.pct}% deposit to hold a rod from the next batch at the price shown. The deposit is not refundable if you change your mind. If the next batch does not happen, you get your deposit back. The balance and postage are due when the next batch lands in Darwin.` } },
      metadata: {
        shop: "walkabout-waitlist",
        items: dMeta.join(",").slice(0, 480),
        deposit_pct: String(w.pct),
        balance_cents: String(balance),
        barra_brain_waitlist: body.waitlist ? "yes" : "no",
      },
      payment_intent_data: { description: "Barefoot Walkabout deposit, next batch" },
    };
    try {
      const session = await stripe("POST", "/checkout/sessions", dParams);
      return res.status(200).json({ ok: true, url: session.url });
    } catch (e) {
      return res.status(502).json({ ok: false, error: "The checkout did not open. Please try again, or flick Watty an email at glenn@barefootfishingsafaris.com.au." });
    }
  }

  const region = REGIONS[body.region] ? body.region : null;
  if (!region) return res.status(400).json({ ok: false, error: "Please choose where we are posting it." });

  const lines = [];
  const meta = [];
  const want = { spin: 0, baitcast: 0 };
  let rodCount = 0;
  let wantKits = 0;
  const wantX = {};
  const xName = {};

  for (const it of body.items.slice(0, 30)) {
    const qty = Math.min(20, Math.max(0, parseInt(it.qty, 10) || 0));
    if (!qty) continue;
    const sku = String(it.sku || "");
    if (shop.rods[sku]) {
      const rod = shop.rods[sku];
      for (const [kind, each] of Object.entries(rod.rods)) { want[kind] += qty * each; rodCount += qty * each; }
      lines.push({ name: rod.name + (st.founding ? " — Founding rod" : ""), amount: st.founding ? rod.founding : rod.full, qty });
      meta.push(`${sku}:${qty}`);
      continue;
    }
    if (sku.startsWith("kit|")) {
      const [, shirt, shirtSize, shortsSize] = sku.split("|");
      const sh = shop.extras[shirt], so = shop.extras[shop.kit.shorts];
      if (!shop.kit.shirts.includes(shirt) || !sh || !(shirtSize in sh.sizes) || !(shortsSize in so.sizes)) {
        return res.status(400).json({ ok: false, error: "Something in your order is no longer available. Please refresh the page." });
      }
      wantKits += qty;
      want.spin += qty; want.baitcast += qty; rodCount += 2 * qty;
      for (const k of [`${shirt}|${shirtSize}`, `${shop.kit.shorts}|${shortsSize}`]) wantX[k] = (wantX[k] || 0) + qty;
      xName[`${shirt}|${shirtSize}`] = `${sh.name} in ${shirtSize}`;
      xName[`${shop.kit.shorts}|${shortsSize}`] = `${so.name} in ${shortsSize}`;
      lines.push({ name: `Walkabout Expedition Kit: the Pair (each rod with a spare tip), ${sh.name} (${shirtSize}), footy shorts (${shortsSize})` + (st.founding ? " — Founding rods" : ""),
        amount: st.founding ? shop.kit.founding : shop.kit.full, qty });
      meta.push(`${sku}:${qty}`);
      continue;
    }
    const [base, size] = sku.split("|");
    const x = shop.extras[base];
    if (!x || !(size in x.sizes)) return res.status(400).json({ ok: false, error: "Something in your order is no longer available. Please refresh the page." });
    wantX[sku] = (wantX[sku] || 0) + qty;
    xName[sku] = `${x.name} in ${size}`;
    lines.push({ name: `${x.name}, ${size}`, amount: x.price, qty });
    meta.push(`${sku}:${qty}`);
  }
  if (!lines.length) return res.status(400).json({ ok: false, error: "Your order is empty." });
  if (wantKits > st.kitsLeft) {
    return res.status(409).json({ ok: false, error: st.kitsLeft ? `Sorry, only ${st.kitsLeft} Expedition Kit${st.kitsLeft === 1 ? "" : "s"} left.` : "Sorry, the Expedition Kits have sold." });
  }
  for (const [k, n] of Object.entries(wantX)) {
    if (n > st.extras[k]) return res.status(409).json({ ok: false, error: `Sorry, only ${st.extras[k]} left of the ${xName[k]}.` });
  }
  for (const kind of ["spin", "baitcast"]) {
    if (want[kind] > st.left[kind]) {
      return res.status(409).json({ ok: false, error: `Sorry, only ${st.left[kind]} ${kind} rod${st.left[kind] === 1 ? "" : "s"} left.` });
    }
  }

  // Postage
  const p = shop.postage[region];
  const options = [];
  const rate = (label, cents) => options.push({ shipping_rate_data: {
    type: "fixed_amount", display_name: label, fixed_amount: { amount: cents, currency: "aud" } } });
  if (rodCount > 0) {
    if (region === "AU" && st.founding) rate("Free postage (Founding rod), posted from Darwin", p.founding_rod);
    else if (region === "AU") { rate("Parcel Post from Darwin", p.rod); rate("Express Post from Darwin", p.rod_express); }
    else rate(`Posted from Darwin to ${p.label}. You pay any import taxes.`, p.rod);
  } else if (region === "AU") {
    rate("Australia Post satchel from Darwin", p.no_rod);
  } else {
    return res.status(400).json({ ok: false, error: "For clothing posted overseas without a rod, email glenn@barefootfishingsafaris.com.au and Watty will sort the postage." });
  }

  const params = {
    mode: "payment",
    success_url: `${origin}/walkabout-thanks`,
    cancel_url: back,
    phone_number_collection: { enabled: true },
    shipping_address_collection: { allowed_countries: Object.assign({}, REGIONS[region]) },
    shipping_options: Object.assign({}, options),
    line_items: Object.assign({}, lines.map((l) => ({
      quantity: l.qty,
      price_data: { currency: "aud", unit_amount: l.amount, product_data: { name: l.name } },
    }))),
    metadata: {
      shop: "walkabout",
      items: meta.join(",").slice(0, 480),
      founding: st.founding ? "yes" : "no",
      barra_brain_waitlist: body.waitlist ? "yes" : "no",
    },
    payment_intent_data: { description: "Barefoot Walkabout order" },
  };
  const note = rodCount > 0 ? checkoutNote(shop) : "";
  if (note) params.custom_text = { submit: { message: note } };

  try {
    const session = await stripe("POST", "/checkout/sessions", params);
    return res.status(200).json({ ok: true, url: session.url });
  } catch (e) {
    return res.status(502).json({ ok: false, error: "The checkout did not open. Please try again, or flick Watty an email at glenn@barefootfishingsafaris.com.au." });
  }
}
