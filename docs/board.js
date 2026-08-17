// ASHRE chalkboard explainer — step machine.
//
// Every drawable element in the SVG carries data-s (the step it appears on) and,
// optionally, data-e (the last step it stays visible for). This walks a step
// counter from 0 to TOTAL and toggles `.on` accordingly. Without JS the CSS
// leaves the finished board on screen, so nothing here is load-bearing for content.

(function () {
  var board = document.getElementById('board');
  if (!board) return;

  var TOTAL = 8;
  var BEAT = 2000; // ms per step while autoplaying

  var svg = board.querySelector('.board-svg');
  var count = document.getElementById('board-count');
  var caps = document.querySelectorAll('.board-caps [data-cap]');
  var stages = svg.querySelectorAll('[data-s]');
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var step = 0;
  var timer = null;
  var userDriven = false;

  // Dash-offset each stroke by its own length so it draws at a natural rate
  // regardless of how long the path is.
  //
  // Deliberately skips .dash elements: the draw-on effect and a dashed line are
  // both stroke-dasharray, so they cannot coexist. Dashed strokes carry meaning
  // here (a response, a callback, ASHRE's absence), so the pattern wins and they
  // fade in instead of drawing.
  stages.forEach(function (el) {
    if (!el.classList.contains('draw') || el.classList.contains('dash')) return;
    if (!el.getTotalLength) return;
    var len;
    try { len = el.getTotalLength(); } catch (e) { return; }
    if (!len) return;
    el.style.setProperty('--len', len);
    el.style.strokeDasharray = len;
  });

  function render() {
    stages.forEach(function (el) {
      var from = +el.getAttribute('data-s');
      var until = el.hasAttribute('data-e') ? +el.getAttribute('data-e') : Infinity;
      el.classList.toggle('on', step >= from && step <= until);
    });

    caps.forEach(function (li) {
      var n = +li.getAttribute('data-cap');
      li.classList.toggle('on', step >= n);
      li.classList.toggle('now', step === n);
    });

    board.setAttribute('data-step', step);
    count.textContent = 'step ' + step + ' of ' + TOTAL;
  }

  function go(n) {
    step = Math.max(0, Math.min(TOTAL, n));
    render();
  }

  function stop() {
    if (timer) { clearInterval(timer); timer = null; }
    board.classList.remove('playing');
  }

  function play(from) {
    stop();
    if (reduced) { go(TOTAL); return; }
    go(typeof from === 'number' ? from : step);
    board.classList.add('playing');
    timer = setInterval(function () {
      if (step >= TOTAL) { stop(); return; }
      go(step + 1);
    }, BEAT);
  }

  board.querySelectorAll('[data-act]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var act = btn.getAttribute('data-act');
      if (act === 'replay') {
        userDriven = false;
        go(0);
        play(0);
        return;
      }
      userDriven = true;
      stop();
      go(act === 'next' ? step + 1 : step - 1);
    });
  });

  // Reduced motion: show the finished board straight away rather than waiting
  // for a scroll that may never trip the observer. The controls still step.
  if (reduced) {
    go(TOTAL);
  } else if ('IntersectionObserver' in window) {
    var seen = false;
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting && !seen && !userDriven) {
          seen = true;
          play(0);
        } else if (!entry.isIntersecting && !userDriven) {
          stop(); // don't burn ticks while it's scrolled away
        }
      });
    }, { threshold: 0.35 });
    io.observe(board);
    go(0);
  } else {
    go(TOTAL);
  }
})();
