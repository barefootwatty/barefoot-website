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
        say("Got it — that's landed with Watty. He'll come back to you, usually within a day or two. He's out on the water most days.", 'ok');
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
