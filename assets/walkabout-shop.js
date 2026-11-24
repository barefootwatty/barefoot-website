/* Walkabout shop — the order panel on walkabout.html.
   Prices, sizes and stock come from assets/walkabout-shop.json. The checkout
   itself (api/walkabout-checkout.js) re-checks every price and stock count on
   the server, so nothing here is trusted with money. */
(function(){
  var shop, live = {open:false}, cart = {};
  var $ = function(id){ return document.getElementById(id); };
  var money = function(c){ return '$' + (c % 100 ? (c/100).toFixed(2) : (c/100)); };

  function founding(){ return !live.open || live.founding !== false; }
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
    if (!live.open) st.textContent = live.message || shop.closed_message;
    else if (post.blocked) st.textContent = 'For clothing posted overseas without a rod, email glenn@barefootfishingsafaris.com.au and Watty will sort the postage.';
    else st.textContent = '';
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
      if (n) n.textContent = founding() ? 'Founding price. Then ' + money(shop.rods[sku].full) + '.' : 'The Founding rods have sold.';
    });
    var kp = document.querySelector('[data-price="kit"]'), kn = document.querySelector('[data-note="kit"]'), kl = document.querySelector('[data-kitleft]');
    if (kp) kp.textContent = money(kitPrice());
    if (kn) kn.textContent = founding() ? 'Founding price. Then ' + money(shop.kit.full) + '.' : 'The Founding rods have sold.';
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
    render();
  }

  document.addEventListener('click', function(e){
    var t = e.target.closest('[data-add],[data-addx],[data-inc],[data-dec]');
    if (!t || !shop) return;
    if (t.dataset.add === 'kit') { add('kit|' + $('kit-shirt').value + '|' + $('kit-shirt-size').value + '|' + $('kit-shorts-size').value); $('shop-cart').scrollIntoView({behavior:'smooth', block:'center'}); }
    else if (t.dataset.add) { add(t.dataset.add); $('shop-cart').scrollIntoView({behavior:'smooth', block:'center'}); }
    else if (t.dataset.addx) add(t.dataset.addx + '|' + $('size-' + t.dataset.addx).value);
    else if (t.dataset.inc) add(t.dataset.inc);
    else if (t.dataset.dec) { cart[t.dataset.dec]--; if (cart[t.dataset.dec] < 1) delete cart[t.dataset.dec]; render(); }
  });

  function start(){
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
          $('cart-status').textContent = 'The checkout did not open. Please try again, or call Watty on 0417 272 871.';
          go.disabled = false; go.textContent = 'Go to checkout';
        });
    });
    fetch('assets/walkabout-shop.json', {cache:'no-store'}).then(function(r){ return r.json(); }).then(function(s){
      shop = s; build();
      return fetch('/api/walkabout-checkout').then(function(r){ return r.json(); }).then(function(j){ if (j && j.ok) { live = j; build(); } });
    }).catch(function(){ if (shop) render(); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
