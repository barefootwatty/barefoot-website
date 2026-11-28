// Walkabout shop checkout — runs on Vercel, on Watty's own domain.
//
// WHAT IT DOES: the Walkabout page sends a list of items and where they are
// being posted. This works out the prices and postage from
// assets/walkabout-shop.json (never from what the browser says), checks
// nothing is sold out, and opens a Stripe checkout page for the buyer.
//
// SETUP (three environment variables, set in the Vercel dashboard, never in this repo):
//   STRIPE_SECRET_KEY            a Stripe secret key (test key on Preview, live on Production)
//   GOOGLE_SERVICE_ACCOUNT_KEY   the whole key file (JSON) of a Google service account that
//                                has been given Viewer access to the Barefoot Merch Manifest Sheet
//   WALKABOUT_STOCK_SHEET_ID     that Sheet's id (the long code in its web address)
// Until the Stripe key is set, or while "open" is false in walkabout-shop.json, the page
// shows the "opens Sunday" message and nobody can be charged.
//
// DEPOSIT WAITLIST: once a rod has sold out, and only while "waitlist.enabled"
// is true in walkabout-shop.json, a buyer can pay a deposit (a share of the
// next-batch price in "waitlist.prices") to hold a rod from the next batch. Deposits are marked
// "walkabout-waitlist" so they are never counted as stock sold.
//
// ROD STOCK AND THE FOUNDING 100: there is no database. Every completed order
// carries a short list of what was bought (in Stripe "metadata"). This adds
// those up to know how many rods are left.
//
// SHIRT AND SHORTS STOCK comes from the Google Sheet "Barefoot Merch Manifest".
// No shirt or shorts number is typed into this repo. The rule, for each size:
//
//   left to sell = "Available" on the Sheet's Stock tab
//                  minus paid website orders the Sheet has not caught up with yet
//
// The Sheet's Available already has everything on its Orders tab taken off (Paid,
// Posted, Reserved, Kept or given away, and the Freebies tab). A website order is
// typed onto the Orders tab after the fact, with the order ref "WKB-" plus the
// last 6 characters of its Stripe id. So:
//   - until that ref is on the Orders tab with a Status on every one of its
//     lines, this takes the order off by itself (so a sale is never missed);
//   - from then on the Sheet's own numbers cover it and this stops taking it off
//     (so a sale is never taken off twice).
// To put a refunded shirt back on sale, set its Orders line to "Cancelled".
// Do not delete the line: with no ref on the Sheet the order counts as sold again.
//
// IF THE SHEET CANNOT BE READ: the last good reading is used for up to 30
// minutes, still taking off new paid orders. With no reading at all, shirts,
// shorts and Expedition Kits cannot be ordered ("checking stock") until the
// Sheet is back. Rods keep selling the whole time. Nothing is ever guessed.

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

// Adds up everything sold so far from completed Stripe checkouts. "orders" keeps each
// paid order's items beside the last 6 characters of its Stripe id (its ref on the Sheet).
async function sold(shop) {
  const totals = {};
  const orders = [];
  let after;
  for (let page = 0; page < 20; page++) {
    const res = await stripe("GET", "/checkout/sessions", {
      limit: 100, status: "complete", created: { gte: shop.launch_ts }, starting_after: after,
    });
    for (const s of res.data) {
      if (!s.metadata || s.metadata.shop !== "walkabout" || s.payment_status !== "paid") continue;
      const items = parseItems(s.metadata.items);
      orders.push({ tail: String(s.id).slice(-6), items });
      for (const [k, n] of Object.entries(items)) totals[k] = (totals[k] || 0) + n;
    }
    if (!res.has_more) break;
    after = res.data[res.data.length - 1].id;
  }
  return { totals, orders };
}

// ---------- Shirt and shorts stock: the "Barefoot Merch Manifest" Google Sheet ----------

const SHEET_FRESH_MS = 20 * 1000;      // the Sheet is re-read at most this often
const SHEET_TRUST_MS = 30 * 60 * 1000; // if it cannot be read, the last good reading is used for this long
const GOOGLE_WAIT_MS = 4000;           // a buyer is never kept waiting on Google longer than this
let googlePass = null;                 // { token, until }: Google's hour-long pass, kept between requests
let sheetSeen = null;                  // the last good reading of the Sheet

function b64url(bytes) {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
}

// Problems are named with short codes (shown under "stock" in the GET answer) so a fault can be
// found without the server logs. Nothing secret is ever in a code.
const fault = (code) => Object.assign(new Error(code), { fault: code });

function serviceAccount() {
  let raw = String(process.env.GOOGLE_SERVICE_ACCOUNT_KEY || "").trim();
  if (!raw) throw fault("no-google-key");
  let key;
  try { key = JSON.parse(raw[0] === "{" ? raw : atob(raw)); } catch (e) { throw fault("bad-google-key"); }
  if (!key || !key.client_email || !key.private_key) throw fault("bad-google-key");
  return key;
}

// Signs in to Google as the service account (read-only access to Sheets) and returns the pass.
async function googleToken(signal) {
  if (googlePass && Date.now() < googlePass.until) return googlePass.token;
  const key = serviceAccount();
  const now = Math.floor(Date.now() / 1000);
  const enc = new TextEncoder();
  const part = (o) => b64url(enc.encode(JSON.stringify(o)));
  const unsigned = part({ alg: "RS256", typ: "JWT" }) + "." + part({
    iss: key.client_email, scope: "https://www.googleapis.com/auth/spreadsheets.readonly",
    aud: "https://oauth2.googleapis.com/token", iat: now, exp: now + 3600,
  });
  let signature;
  try {
    const subtle = (globalThis.crypto && globalThis.crypto.subtle) || (await import("node:crypto")).webcrypto.subtle;
    const der = Uint8Array.from(atob(String(key.private_key).replace(/-----[^-]+-----/g, "").replace(/\s+/g, "")), (c) => c.charCodeAt(0));
    const k = await subtle.importKey("pkcs8", der, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["sign"]);
    signature = new Uint8Array(await subtle.sign("RSASSA-PKCS1-v1_5", k, enc.encode(unsigned)));
  } catch (e) { throw fault("bad-google-key"); }
  const r = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST", signal,
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: "grant_type=" + encodeURIComponent("urn:ietf:params:oauth:grant-type:jwt-bearer") + "&assertion=" + unsigned + "." + b64url(signature),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || !j.access_token) throw fault(`google-sign-in-${r.status}`);
  googlePass = { token: j.access_token, until: Date.now() + (Math.min(3600, Number(j.expires_in) || 3600) - 300) * 1000 };
  return googlePass.token;
}

// One reading of the Sheet: the Available number for every size the shop sells, and which
// website order refs the Orders tab already holds. Only the cells named in "stock_sheet"
// (walkabout-shop.json) are asked for, so no buyer's name or contact ever leaves the Sheet.
async function readSheet(shop) {
  const cfg = shop.stock_sheet || {};
  const id = String(process.env.WALKABOUT_STOCK_SHEET_ID || "").trim();
  if (!id) throw fault("no-sheet-id");
  if (!cfg.stock || !cfg.order_refs || !cfg.order_status) throw fault("no-sheet-settings");
  const signal = AbortSignal.timeout(GOOGLE_WAIT_MS);
  const token = await googleToken(signal);
  const r = await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(id)}/values:batchGet` +
    "?valueRenderOption=UNFORMATTED_VALUE&majorDimension=ROWS&" +
    [cfg.stock, cfg.order_refs, cfg.order_status].map((a) => "ranges=" + encodeURIComponent(a)).join("&"),
    { headers: { Authorization: `Bearer ${token}` }, signal });
  if (r.status === 401) googlePass = null;
  if (!r.ok) throw fault(`sheet-${r.status}`);
  const j = await r.json();
  const [stock, refs, states] = [0, 1, 2].map((i) => (j.valueRanges && j.valueRanges[i] && j.valueRanges[i].values) || []);
  const text = (v) => String(v === undefined || v === null ? "" : v).trim();

  // Stock tab: find the SKU and Available columns by their headings, so a column added beside them does no harm.
  // Available must sit in the same unbroken run of headings as SKU: the "Totals by item" block further
  // along the tab has an Available heading of its own, and that one must never be read as stock.
  const head = (stock[0] || []).map((h) => text(h).toLowerCase());
  const skuCol = head.indexOf("sku");
  const gap = head.indexOf("", skuCol + 1);
  const availCol = head.indexOf("available", skuCol + 1);
  if (skuCol < 0 || availCol < 0 || (gap > -1 && availCol > gap)) throw fault("stock-tab-headings");
  const bySku = new Map();
  for (const row of stock.slice(1)) {
    const sku = text(row[skuCol]).toUpperCase();
    if (sku && typeof row[availCol] === "number" && Number.isFinite(row[availCol])) bySku.set(sku, Math.floor(row[availCol]));
  }
  const available = {};
  const missing = [];
  let found = 0;
  for (const [sku, x] of Object.entries(shop.extras)) {
    for (const [size, line] of Object.entries(x.sizes)) {
      const code = text(line).toUpperCase();
      if (bySku.has(code)) { available[`${sku}|${size}`] = Math.max(0, bySku.get(code)); found++; }
      else { available[`${sku}|${size}`] = 0; missing.push(code); } // a line that is missing or not a number sells as sold out
    }
  }
  if (!found) throw fault("stock-tab-lines");

  // Orders tab: a ref counts as "on the Sheet" only when every one of its lines has a Status.
  if (!text((refs[0] || [])[0]).toLowerCase().startsWith("order ref") || text((states[0] || [])[0]).toLowerCase() !== "status") throw fault("orders-tab-headings");
  const lines = new Map();
  for (let i = 1; i < refs.length; i++) {
    const ref = text((refs[i] || [])[0]).toLowerCase();
    if (!ref) continue;
    const hasStatus = !!text((states[i] || [])[0]);
    lines.set(ref, lines.has(ref) ? lines.get(ref) && hasStatus : hasStatus);
  }
  const recorded = new Set([...lines.keys()].filter((ref) => lines.get(ref)));
  return { at: Date.now(), available, recorded, missing };
}

// The stock reading to use right now. Never throws: "from" says where the numbers came from.
//   "sheet"  read from the Sheet within the last 20 seconds
//   "saved"  the Sheet could not be read; this is the last good reading (under 30 minutes old)
//   "none"   no reading at all: shirts, shorts and kits wait until the Sheet is back
async function sheetStock(shop) {
  if (sheetSeen && Date.now() - sheetSeen.at < SHEET_FRESH_MS) return { ...sheetSeen, from: "sheet" };
  try {
    sheetSeen = await readSheet(shop);
    return { ...sheetSeen, from: "sheet" };
  } catch (e) {
    const problem = e && e.fault ? e.fault : (e && (e.name === "TimeoutError" || e.name === "AbortError") ? "google-too-slow" : "google-unreachable");
    if (sheetSeen && Date.now() - sheetSeen.at < SHEET_TRUST_MS) return { ...sheetSeen, from: "saved", problem };
    return { from: "none", problem };
  }
}

// Everything the page and the checkout need to know about stock, in one go.
async function stockNow(shop) {
  const [paid, sheet] = await Promise.all([sold(shop), sheetStock(shop)]);
  return status(shop, paid, sheet);
}

const CHECKING_CLOTHING = "Sorry, we are checking shirt and shorts stock right now, so they can't be ordered for a few minutes. Rods are fine to order. Please try again shortly.";

function status(shop, paid, sheet) {
  const totals = paid.totals;
  const rodsSold = { spin: 0, baitcast: 0 };
  for (const [sku, rod] of Object.entries(shop.rods)) {
    const n = totals[sku] || 0;
    for (const [kind, each] of Object.entries(rod.rods)) rodsSold[kind] += n * each;
  }
  // Expedition Kits: "kit|shirt-collared|L|XL" = one Pair, that shirt, those shorts.
  let kitsSold = 0;
  for (const [key, n] of Object.entries(totals)) {
    if (!key.startsWith("kit|")) continue;
    kitsSold += n;
    rodsSold.spin += n; rodsSold.baitcast += n;
  }
  const allRods = rodsSold.spin + rodsSold.baitcast;
  const left = {
    spin: Math.max(0, shop.rods["rod-spin"].stock - rodsSold.spin),
    baitcast: Math.max(0, shop.rods["rod-baitcast"].stock - rodsSold.baitcast),
  };
  // Shirts and shorts: the Sheet's Available, less paid website orders the Sheet has not caught up with.
  const haveSheet = !!sheet.available;
  const waiting = {};
  const prefix = String((shop.stock_sheet || {}).order_ref_prefix || "").toLowerCase();
  if (haveSheet) for (const order of paid.orders) {
    if (sheet.recorded.has(prefix + order.tail.toLowerCase())) continue;
    for (const [key, n] of Object.entries(order.items)) {
      let keys = [];
      if (key.startsWith("kit|")) {
        const [, shirt, shirtSize, shortsSize] = key.split("|");
        keys = [`${shirt}|${shirtSize}`, `${shop.kit.shorts}|${shortsSize}`];
      } else if (!shop.rods[key]) keys = [key];
      for (const k of keys) waiting[k] = (waiting[k] || 0) + n;
    }
  }
  const extras = {};
  for (const [sku, x] of Object.entries(shop.extras)) {
    for (const size of Object.keys(x.sizes)) {
      const key = `${sku}|${size}`;
      extras[key] = haveSheet ? Math.max(0, (sheet.available[key] || 0) - (waiting[key] || 0)) : 0;
    }
  }
  // "stock" is for fault-finding: where the shirt and shorts numbers came from, and anything odd about them.
  const stock = { from: sheet.from };
  if (haveSheet) stock.read = new Date(sheet.at).toISOString();
  if (sheet.problem) stock.problem = sheet.problem;
  if (haveSheet && sheet.missing.length) stock.missing = sheet.missing;
  if (Object.keys(waiting).length) stock.waiting = waiting;
  // Founding prices end when the limit is reached OR at "founding_ends", whichever comes first.
  const ends = Date.parse(shop.founding_ends || "");
  const inTime = Number.isNaN(ends) || Date.now() < ends;
  return { founding: allRods < shop.founding_limit && inTime, foundingLeft: Math.max(0, shop.founding_limit - allRods), foundingEnds: Number.isNaN(ends) ? null : shop.founding_ends, left, extras,
    kitsLeft: Math.max(0, shop.kit.limit - kitsSold), clothing: haveSheet ? "ok" : "checking", stock };
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
      const st = await stockNow(shop);
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
  try { st = await stockNow(shop); }
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
  if (st.clothing !== "ok" && Object.keys(wantX).length) return res.status(503).json({ ok: false, error: CHECKING_CLOTHING });
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
