/* Enquiry form — posts to /api/enquiry so the message always lands.
 *
 * The old version opened the visitor's own mail app with a mailto: link. On a
 * desktop with no mail client configured that does nothing at all, and the
 * enquiry is lost without either side knowing. This posts to the server.
 *
 * If the server is unreachable or not configured yet, it falls back to the old
 * mailto behaviour rather than dropping the enquiry — worst case the visitor
 * gets what they used to get, never nothing.
 */

/* Availability tiles — tap a window and it goes into the "Your dates" box.
 * The tiles and date lists are generated from assets/availability.json by
 * tools/build_availability.py. Anything whose end date has passed hides
 * itself, so a stale page never offers a trip that's already been.
 */
(function () {
  var today = new Date().toISOString().slice(0, 10);
  Array.prototype.forEach.call(document.querySelectorAll('[data-end]'), function (el) {
    if (el.getAttribute('data-end') < today) el.hidden = true;
  });

  var when = document.getElementById('enq-when');
  var tiles = document.querySelectorAll('[data-avpick] .avtile');
  if (!when || !tiles.length) return;

  var picked = [];
  var lastSet = '';

  Array.prototype.forEach.call(tiles, function (t) {
    t.addEventListener('click', function () {
      var label = t.getAttribute('data-label');
      var i = picked.indexOf(label);
      if (i === -1) picked.push(label); else picked.splice(i, 1);
      t.setAttribute('aria-pressed', i === -1 ? 'true' : 'false');

      // Keep anything the visitor typed themselves; only replace what the
      // tiles put there last time.
      var own = when.value.trim();
      if (lastSet && own.indexOf(lastSet) === 0) own = own.slice(lastSet.length).replace(/^[;\s]+/, '');
      lastSet = picked.join('; ');
      when.value = [lastSet, own].filter(Boolean).join('; ');
    });
  });

  var form = document.getElementById('enqform');
  if (form) form.addEventListener('reset', function () {
    picked = []; lastSet = '';
    Array.prototype.forEach.call(tiles, function (t) { t.setAttribute('aria-pressed', 'false'); });
  });
})();

(function () {
  var f = document.getElementById('enqform');
  if (!f) return;

  var status = document.getElementById('enq-status');
  var button = f.querySelector('button[type=submit]');
  var TO = 'glenn@barefootfishingsafaris.com.au';

  function val(id) {
    var el = document.getElementById(id);
    return el ? String(el.value || '').trim() : '';
  }

  function say(msg, kind) {
    if (!status) return;
    status.textContent = msg;
    status.className = 'enq-status ' + (kind || '');
    status.hidden = false;
  }

  function asText(d) {
    var t = "G'day Watty — keen on a Top End trip.";
    if (d.name) t += '\nName: ' + d.name;
    if (d.email) t += '\nEmail: ' + d.email;
    if (d.phone) t += '\nPhone: ' + d.phone;
    t += '\nGroup: ' + d.size;
    if (d.when) t += '\nWhen: ' + d.when;
    t += '\nDays fishing: ' + d.days;
    if (d.message) t += '\n' + d.message;
    return t;
  }

  function mailtoFallback(d) {
    say('Opening your email app instead — if nothing happens, email ' + TO + ' directly.', 'warn');
    location.href = 'mailto:' + TO + '?subject=' +
      encodeURIComponent('Safari enquiry') + '&body=' + encodeURIComponent(asText(d));
  }

  f.addEventListener('submit', function (e) {
    e.preventDefault();

    var d = {
      name: val('enq-name'),
      email: val('enq-email'),
      phone: val('enq-phone'),
      size: val('enq-size'),
      when: val('enq-when'),
      days: val('enq-days'),
      message: val('enq-msg'),
      website: val('enq-website'), // honeypot — real people never see this
      source: (f.getAttribute('data-source') || document.title || 'website')
    };

    if (!d.name) { say('Please add your name.', 'warn'); return; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(d.email)) {
      say("Please check your email address — that's how Watty gets back to you.", 'warn');
      return;
    }

    if (button) { button.disabled = true; button.textContent = 'Sending…'; }
    say('Sending…', '');

    fetch('/api/enquiry', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(d)
    }).then(function (r) {
      // A non-JSON response means the API isn't there at all (e.g. previewing
      // the static files, or a deploy without the function). Fall back rather
      // than showing an error the visitor can do nothing about.
      return r.json().catch(function () { return { ok: r.ok, fallback: !r.ok }; });
    }).then(function (res) {
      if (res && res.ok) {
        f.reset();
        say(res.autoreply
          ? "Got it — that's landed with Watty. Check your inbox: the full list of open dates is on its way now. He'll come back to you properly within a day or two — he's out on the water most days."
          : "Got it — that's landed with Watty. He'll come back to you, usually within a day or two. He's out on the water most days.", 'ok');
      } else if (res && res.fallback) {
        mailtoFallback(d);
      } else {
        say((res && res.error) || 'Something went wrong — please try again.', 'warn');
      }
    }).catch(function () {
      mailtoFallback(d);
    }).then(function () {
      if (button) { button.disabled = false; button.textContent = 'Send enquiry'; }
    });
  });
})();
