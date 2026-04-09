(function () {
  'use strict';

  /* ── Mobile nav toggle ── */
  var toggle   = document.querySelector('.nav-toggle');
  var navLinks = document.querySelector('.nav-links');

  function openNav() {
    navLinks.classList.add('is-open');
    toggle.setAttribute('aria-expanded', 'true');
    toggle.setAttribute('aria-label', 'Close menu');
    document.body.classList.add('nav-open');
  }

  function closeNav() {
    navLinks.classList.remove('is-open');
    toggle.setAttribute('aria-expanded', 'false');
    toggle.setAttribute('aria-label', 'Open menu');
    document.body.classList.remove('nav-open');
  }

  if (toggle && navLinks) {
    toggle.addEventListener('click', function () {
      if (navLinks.classList.contains('is-open')) { closeNav(); } else { openNav(); }
    });

    /* Close when a nav link is clicked */
    navLinks.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', closeNav);
    });

    /* Close on resize to desktop */
    window.addEventListener('resize', function () {
      if (window.matchMedia('(min-width: 769px)').matches) { closeNav(); }
    });
  }

  /* ── Active nav link ── */
  (function () {
    var rawPath = window.location.pathname.replace(/\\/g, '/');
    var parts   = rawPath.split('/');
    var current = parts[parts.length - 1] || 'index.html';
    if (current === '') current = 'index.html';

    document.querySelectorAll('.nav-links a').forEach(function (a) {
      var href  = (a.getAttribute('href') || '').replace(/\\/g, '/');
      var hfile = href.split('/').pop();
      if (hfile === current) { a.classList.add('active'); }
    });
  })();

  /* ── Smooth scroll for anchor links ── */
  document.querySelectorAll('a[href^="#"]').forEach(function (a) {
    a.addEventListener('click', function (e) {
      var selector = a.getAttribute('href');
      var target   = document.querySelector(selector);
      if (!target) return;
      e.preventDefault();
      var header = document.querySelector('.site-header');
      var offset = header ? header.offsetHeight : 72;
      var top    = target.getBoundingClientRect().top + window.pageYOffset - offset - 16;
      window.scrollTo({ top: top, behavior: 'smooth' });
    });
  });

})();
