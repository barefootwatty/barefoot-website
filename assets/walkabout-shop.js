/* Walkabout shop — the order panel on walkabout.html.
   Prices, sizes and stock come from assets/walkabout-shop.json. The checkout
   itself (api/walkabout-checkout.js) re-checks every price and stock count on
   the server, so nothing here is trusted with money. */
(function(){
  var shop, live = {open:false}, cart = {};
  var checked = false; // true once the stock check has answered; until then the box says it is checking
  var $ = function(id){ return document.getElementById(id); };
  var money = function(c){ return '$' + (c % 100 ? (c/100).toFixed(2) : (c/100)); };

  function founding(){ return !live.open || live.founding !== false; }
  function foundingOver(){ return live.foundingLeft > 0 ? 'The Founding price has ended.' : 'The Founding rods have sold.'; }

  // Countdown under the offer heading. While Founding prices are on it counts down to "founding_ends",
  // with the rods-left line above it once fewer than "founding_count_below" are left.
  // Once Founding prices have ended it counts down to "christmas_order_by", then shows nothing.
  // The checkout itself decides the price on the server: this is only the clock people see.
  // Once Founding prices have ended, the Founding-only words step aside for the ones that are still true.
  function switchWords(){
    var over = live.open === true && live.founding === false;
    [].forEach.call(document.querySelectorAll('[data-founding-only]'), function(el){ el.hidden = over; });
    [].forEach.call(document.querySelectorAll('[data-after-founding]'), function(el){ el.hidden = !over; });
    var h = document.querySelector('[data-after-heading]');
    if (h) h.textContent = live.foundingLeft > 0 ? 'The Founding price has ended.' : 'The Founding hundred have sold.';
    [].forEach.call(document.querySelectorAll('[data-buy-label]'), function(el){ el.textContent = over ? 'Get a Walkabout' : 'Founding rods'; });
  }

  var clockOn = false;
  function clock(){
    var el = $('founding-clock');
    if (!el || !shop) return;
    if (!live.open) { el.hidden = true; return; }
    var two = function(n){ return (n < 10 ? '0' : '') + n; };
    var time = function(ms){
      var s = Math.floor(ms / 1000), d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60);
      return '<span class="fc-time"><b>' + d + '</b> ' + (d === 1 ? 'day' : 'days') + ' <b>' + two(h) + '</b> hrs <b>' + two(m) + '</b> min <b>' + two(s % 60) + '</b> sec</span>';
    };
    var html = '';
    if (live.founding !== false) {
      var ends = shop.founding_ends ? Date.parse(shop.founding_ends) : NaN, ms = ends - Date.now();
      if (ms <= 0) { el.hidden = true; live.founding = false; build(); return; }
      if (!isNaN(ends)) {
        var gone = shop.founding_limit - live.foundingLeft;
        var leftWords = live.foundingLeft === 1 ? 'is 1 Founding rod' : 'are ' + live.foundingLeft + ' Founding rods';
        var countWords = gone > 0 ? gone + (gone === 1 ? ' rod has' : ' rods have') + ' gone so far, and there ' + leftWords + ' left.' : live.foundingLeft + ' of ' + shop.founding_limit + ' Founding rods left.';
        var count = live.foundingLeft > 0 && live.foundingLeft < shop.founding_count_below ? '<span class="fc-count">' + countWords + '</span> ' : '';
        html = count + 'Founding price ends in ' + time(ms) + ', or when the first ' + shop.founding_limit + ' rods are gone.';
      }
    } else {
      var by = shop.christmas_order_by ? Date.parse(shop.christmas_order_by) : NaN, left = by - Date.now();
      if (left > 0) html = 'Order in the next ' + time(left) + ' for Parcel Post before Christmas.';
    }
    el.hidden = !html;
    if (!html) return;
    el.innerHTML = html;
    if (!clockOn) { clockOn = true; setInterval(clock, 1000); }
  }
  function rodPrice(sku){ var r = shop.rods[sku]; return founding() ? r.founding : r.full; }
  function kitPrice(){ return founding() ? shop.kit.founding : shop.kit.full; }
  function item(sku){
    if (sku.indexOf('kit|') === 0){
      var k = sku.split('|');
      return {name: 'Expedition Kit: ' + (k[1] === 'shirt-hooded' ? 'hooded' : 'collared') + ' shirt ' + k[2] + ', shorts ' + k[3], price: kitPrice(), rod: true};
    }
    if (shop.rods[sku]) return {name: shop.rods[sku].short === 'The Pair' ? 'The Pair, each with a spare tip' : 'Single, ' + shop.rods[sku].short + ', with a spare tip', price: rodPrice(sku), rod: true};
    var p = sku.split('|'), x = shop.extras[p[0]];
    return {name: x.name + ', ' + p[1], price: x.price, rod: false};
  }
  function leftOf(sku){
    if (!live.open) return 99;
    if (sku.indexOf('kit|') === 0){
      var k = sku.split('|');
      return Math.min(live.kitsLeft, live.left.spin, live.left.baitcast, live.extras[k[1] + '|' + k[2]] || 0, live.extras[shop.kit.shorts + '|' + k[3]] || 0);
    }
    if (sku === 'pair') return Math.min(live.left.spin, live.left.baitcast);
    if (sku === 'rod-spin') return live.left.spin;
    if (sku === 'rod-baitcast') return live.left.baitcast;
    return live.extras[sku] == null ? 0 : live.extras[sku];
  }

  function postage(){
    var region = $('cart-region').value, p = shop.postage[region], hasRod = false, any = false;
    Object.keys(cart).forEach(function(s){ any = true; if (shop.rods[s] || s.indexOf('kit|') === 0) hasRod = true; });
    if (!any) return {cents: 0, text: '–'};
    if (hasRod){
      if (region === 'AU' && founding()) return {cents: 0, text: 'Free (Founding rod)'};
      return {cents: p.rod, text: money(p.rod) + (region === 'AU' ? ' (Express ' + money(p.rod_express) + ' at checkout)' : '')};
    }
    if (region === 'AU') return {cents: p.no_rod, text: money(p.no_rod)};
    return {cents: 0, text: 'Email Watty', blocked: true};
  }

  function render(){
    var lines = $('cart-lines'), total = 0, html = '';
    Object.keys(cart).forEach(function(sku){
      var it = item(sku), q = cart[sku];
      total += it.price * q;
      html += '<div class="cartline"><span>' + it.name + '<br><strong>' + money(it.price) + '</strong></span>' +
        '<span class="qty"><button type="button" aria-label="One less ' + it.name + '" data-dec="' + sku + '">&minus;</button>' +
        '<span>' + q + '</span><button type="button" aria-label="One more ' + it.name + '" data-inc="' + sku + '">+</button></span></div>';
    });
    lines.innerHTML = html || '<p class="cartempty">Nothing in your order yet.</p>';
    var post = postage();
    $('cart-post').textContent = post.text;
    $('cart-total').textContent = money(total + post.cents);
    var go = $('cart-go');
    go.disabled = !html || !live.open || !!post.blocked;
    var st = $('cart-status');
    if (!live.open) st.textContent = checked ? (live.message || shop.closed_message) : 'Checking stock. If this stays, refresh the page.';
    else if (post.blocked) st.textContent = 'For clothing posted overseas without a rod, email glenn@barefootfishingsafaris.com.au and Watty will sort the postage.';
    else st.textContent = '';
  }

  // Deposit waitlist: shows only for a rod that has sold out, and only when the shop file switches it on.
  function waitlist(){
    var box = $('shop-waitlist'), rows = $('waitlist-rows');
    if (!box || !rows) return;
    var w = live.open && live.waitlist && live.waitlist.pct ? live.waitlist : null, html = '';
    if (w) Object.keys(shop.rods).forEach(function(sku){
      var r = shop.rods[sku];
      if (!Object.keys(r.rods).some(function(kind){ return w[kind]; })) return;
      var wp = shop.waitlist && shop.waitlist.prices && shop.waitlist.prices[sku] || r.full;
      var dep = Math.round(wp * w.pct / 100), bal = wp - dep;
      var what = r.short === 'The Pair' ? 'The Pair, each with a spare tip' : '1 ' + r.short + ', with a spare tip';
      html += '<div class="waitrow"><span><strong>' + what + '</strong><br>' + money(dep) + ' deposit today. ' + money(bal) + ' plus postage when the next batch lands.</span>' +
        '<button type="button" class="btn btn-primary" data-deposit="' + sku + '">Pay the ' + money(dep) + ' deposit</button></div>';
    });
    rows.innerHTML = html;
    box.hidden = !html;
  }
  function deposit(sku, btn){
    var st = $('waitlist-status'), label = btn.textContent;
    btn.disabled = true; btn.textContent = 'Opening checkout…';
    var fail = function(msg){ if (st) st.textContent = msg; btn.disabled = false; btn.textContent = label; };
    fetch('/api/walkabout-checkout', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({deposit: true, from: location.pathname.replace(/\.html$/, ''), waitlist: $('cart-waitlist').checked, items: [{sku: sku, qty: 1}]})})
      .then(function(r){ return r.json(); })
      .then(function(j){ if (j.ok && j.url) { location.href = j.url; return; } fail(j.error || 'The checkout did not open. Please try again.'); })
      .catch(function(){ fail('The checkout did not open. Please try again, or flick Watty an email at glenn@barefootfishingsafaris.com.au.'); });
  }

  function add(sku){
    var have = cart[sku] || 0;
    if (have + 1 > leftOf(sku)) { $('cart-status').textContent = 'Sorry, that is all we have left of that one.'; return; }
    cart[sku] = have + 1; render();
  }

  function build(){
    Object.keys(shop.rods).forEach(function(sku){
      var p = document.querySelector('[data-price="' + sku + '"]'), n = document.querySelector('[data-note="' + sku + '"]');
      if (p) p.textContent = money(rodPrice(sku));
      if (n) n.textContent = founding() ? 'Founding price. Then ' + money(shop.rods[sku].full) + '.' : foundingOver();
    });
    var kp = document.querySelector('[data-price="kit"]'), kn = document.querySelector('[data-note="kit"]'), kl = document.querySelector('[data-kitleft]');
    if (kp) kp.textContent = money(kitPrice());
    if (kn) kn.textContent = founding() ? 'Founding price. Then ' + money(shop.kit.full) + '.' : foundingOver();
    if (kl) kl.textContent = !live.open ? 'First ' + shop.kit.limit + ' only' : (live.kitsLeft > 0 ? live.kitsLeft + ' of ' + shop.kit.limit + ' left' : 'Sold out');
    var sizeOpts = function(sku){
      var o = '', x = shop.extras[sku];
      Object.keys(x.sizes).forEach(function(size){
        var left = live.open ? leftOf(sku + '|' + size) : x.sizes[size];
        o += '<option value="' + size + '"' + (left < 1 ? ' disabled' : '') + '>' + size + (left < 1 ? ' (sold out)' : '') + '</option>';
      });
      return o;
    };
    var ks = $('kit-shirt'), kss = $('kit-shirt-size'), kso = $('kit-shorts-size');
    if (ks && kss && kso){
      var keep = [kss.value, kso.value];
      kss.innerHTML = sizeOpts(ks.value); kso.innerHTML = sizeOpts(shop.kit.shorts);
      if (keep[0]) kss.value = keep[0]; if (keep[1]) kso.value = keep[1];
    }
    var box = $('shop-extras'), html = '';
    Object.keys(shop.extras).forEach(function(sku){
      var x = shop.extras[sku], opts = '';
      Object.keys(x.sizes).forEach(function(size){
        var left = live.open ? leftOf(sku + '|' + size) : x.sizes[size];
        opts += '<option value="' + size + '"' + (left < 1 ? ' disabled' : '') + '>' + size + (left < 1 ? ' (sold out)' : '') + '</option>';
      });
      html += '<div class="card shopextra"><h4>' + x.name + '</h4><div class="xprice">' + money(x.price) + '</div>' +
        '<label class="small" for="size-' + sku + '">Size</label><select id="size-' + sku + '">' + opts + '</select>' +
        '<button type="button" class="btn btn-primary" data-addx="' + sku + '">Add to order</button></div>';
    });
    box.innerHTML = html;
    waitlist();
    render();
    switchWords();
    clock();
  }

  document.addEventListener('click', function(e){
    var t = e.target.closest('[data-add],[data-addx],[data-inc],[data-dec],[data-deposit]');
    if (!t || !shop) return;
    if (t.dataset.deposit) { deposit(t.dataset.deposit, t); return; }
    if (t.dataset.add === 'kit') { add('kit|' + $('kit-shirt').value + '|' + $('kit-shirt-size').value + '|' + $('kit-shorts-size').value); $('shop-cart').scrollIntoView({behavior:'smooth', block:'center'}); }
    else if (t.dataset.add) { add(t.dataset.add); $('shop-cart').scrollIntoView({behavior:'smooth', block:'center'}); }
    else if (t.dataset.addx) { add(t.dataset.addx + '|' + $('size-' + t.dataset.addx).value); $('shop-cart').scrollIntoView({behavior:'smooth', block:'center'}); }
    else if (t.dataset.inc) add(t.dataset.inc);
    else if (t.dataset.dec) { cart[t.dataset.dec]--; if (cart[t.dataset.dec] < 1) delete cart[t.dataset.dec]; render(); }
  });

  function start(){
    // Lines marked data-until="<time>" take themselves down once that time has passed.
    [].forEach.call(document.querySelectorAll('[data-until]'), function(el){
      var t = Date.parse(el.getAttribute('data-until'));
      if (!isNaN(t) && Date.now() >= t) el.hidden = true;
    });
    $('cart-region').addEventListener('change', render);
    if ($('kit-shirt')) $('kit-shirt').addEventListener('change', build);
    $('cart-go').addEventListener('click', function(){
      var go = this; go.disabled = true; go.textContent = 'Opening checkout…';
      fetch('/api/walkabout-checkout', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({from: location.pathname.replace(/\.html$/, ''), region: $('cart-region').value, waitlist: $('cart-waitlist').checked,
          items: Object.keys(cart).map(function(s){ return {sku:s, qty:cart[s]}; })})})
        .then(function(r){ return r.json(); })
        .then(function(j){
          if (j.ok && j.url) { location.href = j.url; return; }
          $('cart-status').textContent = j.error || 'The checkout did not open. Please try again.';
          go.disabled = false; go.textContent = 'Go to checkout';
        })
        .catch(function(){
          $('cart-status').textContent = 'The checkout did not open. Please try again, or flick Watty an email at glenn@barefootfishingsafaris.com.au.';
          go.disabled = false; go.textContent = 'Go to checkout';
        });
    });
    fetch('assets/walkabout-shop.json', {cache:'no-store'}).then(function(r){ return r.json(); }).then(function(s){
      shop = s; build();
      return fetch('/api/walkabout-checkout').then(function(r){ return r.json(); }).then(function(j){ if (j && j.ok) { checked = true; live = j; build(); } });
    }).catch(function(){ if (shop) render(); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
