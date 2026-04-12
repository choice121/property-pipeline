/**
 * components.js — shared nav + footer loader
 *
 * If the server has already injected nav+footer into the page
 * (data-server-injected="1" on the slot), we skip the fetch() calls
 * and go straight to wiring up interactive behaviour.
 * On Cloudflare Pages (no server injection) we fall back to the
 * original fetch() approach so nothing breaks in production.
 */

(function () {
  'use strict';

  var navSlot    = document.getElementById('site-nav');
  var footerSlot = document.getElementById('site-footer');

  var navPreloaded    = navSlot    && navSlot.getAttribute('data-server-injected') === '1';
  var footerPreloaded = footerSlot && footerSlot.getAttribute('data-server-injected') === '1';

  if (navPreloaded && footerPreloaded) {
    // Server already injected both — run init immediately, no fetch needed
    initComponents();
  } else {
    /* ── Fetch both components in parallel ── */
    var navReq    = navPreloaded    ? Promise.resolve(null) : fetch('/components/nav.html').then(function (r) { return r.text(); });
    var footerReq = footerPreloaded ? Promise.resolve(null) : fetch('/components/footer.html').then(function (r) { return r.text(); });

    Promise.all([navReq, footerReq]).then(function (results) {
      if (results[0] && navSlot)    navSlot.innerHTML    = results[0];
      if (results[1] && footerSlot) footerSlot.innerHTML = results[1];
      initComponents();
    }).catch(function (err) {
      console.error('[components.js] Failed to load nav/footer components:', err);
    });
  }

  /* ── Customize nav for apply pages ── */
  function applyPageCustomizations() {
    if (!window.location.pathname.startsWith('/apply/')) return;
    var navInner = document.querySelector('.nav-inner');
    if (navInner) {
      var backLink = document.createElement('a');
      backLink.href = '/listings.html';
      backLink.className = 'nav-back-link';
      backLink.innerHTML = '← <span>Back to Listings</span>';
      var navLogo = navInner.querySelector('.nav-logo');
      if (navLogo) navInner.insertBefore(backLink, navLogo);

      var navLinks = navInner.querySelector('.nav-links');
      if (navLinks) {
        var langBtn = document.createElement('button');
        langBtn.type = 'button';
        langBtn.id = 'langToggle';
        langBtn.className = 'nav-lang-toggle';
        langBtn.innerHTML = '<i class="fas fa-language"></i> <span id="langText">Español</span>';
        navLinks.appendChild(langBtn);
      }
    }
    var drawerBody = document.querySelector('.nav-drawer-body');
    if (drawerBody) {
      var langBtnDrawer = document.createElement('button');
      langBtnDrawer.type = 'button';
      langBtnDrawer.id = 'langToggleDrawer';
      langBtnDrawer.className = 'nav-drawer-link';
      langBtnDrawer.innerHTML = '<i class="fas fa-language"></i> <span id="langTextDrawer">Español</span>';
      drawerBody.appendChild(langBtnDrawer);
    }
  }

  function initComponents() {
    /* ── I-030: Set og:url to the real current URL ── */
    var ogUrlMeta = document.querySelector('meta[property="og:url"]');
    if (ogUrlMeta) ogUrlMeta.setAttribute('content', location.href);

    /* ── Apply-page customizations ── */
    applyPageCustomizations();

    /* ── Set active nav link by pathname ── */
    var path = window.location.pathname;
    document.querySelectorAll('[data-nav-path]').forEach(function (el) {
      var targetPath = el.getAttribute('data-nav-path');
      if (!targetPath) return;
      if (targetPath === path) { el.classList.add('active'); return; }
      if (targetPath === '/landlord/register.html' && path.indexOf('/landlord/') === 0) { el.classList.add('active'); return; }
      if (targetPath === '/admin/login.html'       && path.indexOf('/admin/')    === 0) { el.classList.add('active'); return; }
    });

    /* ── Wire mobile drawer ── */
    setupMobileDrawer();

    /* ── Wire nav scroll shadow ── */
    setupNavScroll();

    /* ── Hydrate CONFIG email/phone ── */
    hydrateConfig();

    /* ── Call updateNav once window.CP is ready ── */
    waitForCP(function () { window.CP.updateNav(); });
  }

  /* ─────────────────────────────────────────────────────────────
   * setupMobileDrawer
   * ───────────────────────────────────────────────────────────── */
  function setupMobileDrawer() {
    var toggle  = document.getElementById('mobileToggle');
    var drawer  = document.getElementById('navDrawer');
    var overlay = document.getElementById('drawerOverlay');
    var close   = document.getElementById('drawerClose');
    if (!toggle || !drawer || !overlay || !close) return;

    function openDrawer() {
      overlay.classList.add('visible');
      setTimeout(function () {
        overlay.classList.add('open');
        drawer.classList.add('open');
      }, 10);
      document.body.style.overflow = 'hidden';
      toggle.setAttribute('aria-expanded', 'true');
      toggle.setAttribute('aria-label', 'Close menu');
    }

    function closeDrawer() {
      overlay.classList.remove('open');
      drawer.classList.remove('open');
      document.body.style.overflow = '';
      setTimeout(function () { overlay.classList.remove('visible'); }, 360);
      toggle.setAttribute('aria-expanded', 'false');
      toggle.setAttribute('aria-label', 'Open menu');
    }

    toggle.addEventListener('click', openDrawer);
    close.addEventListener('click', closeDrawer);
    overlay.addEventListener('click', closeDrawer);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && drawer.classList.contains('open')) closeDrawer();
    });
  }

  /* ─────────────────────────────────────────────────────────────
   * setupNavScroll
   * ───────────────────────────────────────────────────────────── */
  function setupNavScroll() {
    var nav = document.getElementById('mainNav');
    if (!nav) return;
    window.addEventListener('scroll', function () {
      nav.classList.toggle('scrolled', window.scrollY > 10);
    }, { passive: true });
  }

  /* ─────────────────────────────────────────────────────────────
   * hydrateConfig
   * ───────────────────────────────────────────────────────────── */
  function hydrateConfig() {
    if (!window.CONFIG) return;
    document.querySelectorAll('[data-cfg-email]').forEach(function (el) {
      el.href = 'mailto:' + CONFIG.COMPANY_EMAIL;
      el.textContent = CONFIG.COMPANY_EMAIL;
    });
    document.querySelectorAll('[data-cfg-phone]').forEach(function (el) {
      el.href = 'tel:' + CONFIG.COMPANY_PHONE.replace(/\D/g, '');
      el.textContent = CONFIG.COMPANY_PHONE;
    });
    var drawerEmail = document.getElementById('drawerFooterEmail');
    if (drawerEmail) {
      drawerEmail.href = 'mailto:' + CONFIG.COMPANY_EMAIL;
      drawerEmail.textContent = CONFIG.COMPANY_EMAIL;
    }
  }

  /* ─────────────────────────────────────────────────────────────
   * waitForCP
   * ───────────────────────────────────────────────────────────── */
  function waitForCP(cb) {
    if (window.CP && window.CP.updateNav) { cb(); return; }
    var attempts = 0;
    var timer = setInterval(function () {
      attempts++;
      if (window.CP && window.CP.updateNav) {
        clearInterval(timer);
        cb();
      } else if (attempts > 60) {
        clearInterval(timer);
      }
    }, 50);
  }

})();
