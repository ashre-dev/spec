// Persist and apply theme before paint
(function () {
  const saved = localStorage.getItem('ashre-theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = saved || (prefersDark ? 'dark' : 'light');
  if (theme === 'light') document.documentElement.setAttribute('data-theme', 'light');
})();

function initToggle() {
  const btn = document.getElementById('theme-toggle');
  if (!btn) return;

  function getTheme() {
    return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
  }

  function setIcon() {
    btn.textContent = getTheme() === 'dark' ? '☀️' : '🌙';
    btn.setAttribute('aria-label', getTheme() === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
  }

  setIcon();

  btn.addEventListener('click', function () {
    const next = getTheme() === 'dark' ? 'light' : 'dark';
    if (next === 'light') {
      document.documentElement.setAttribute('data-theme', 'light');
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
    localStorage.setItem('ashre-theme', next);
    setIcon();
  });
}

document.addEventListener('DOMContentLoaded', initToggle);