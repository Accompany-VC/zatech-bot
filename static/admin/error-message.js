// Auto-hide error messages after 5 seconds
(function () {
  function hide() {
    var el = document.getElementById('error-message');
    if (!el) return;
    el.classList.add('hide');
    setTimeout(function () {
      if (el && el.parentNode) el.remove();
    }, 500);
  }

  function setup() {
    var el = document.getElementById('error-message');
    if (el) setTimeout(hide, 5000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setup);
  } else {
    setup();
  }
})();

