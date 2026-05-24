// Stacked toast notifications. Up to 5 visible at once; extras queue and
// appear (staggered) as older ones finish their countdown — so every toast
// is shown, none are dropped. Each rises in, runs a countdown bar, has a ×.
//   window.toast(msg, kind)  — kind: 'error' (default) | 'info' | 'alert'
(() => {
  const MAX = 5;
  const LIFE_MS = 7000;
  const queue = [];

  function host() {
    let h = document.querySelector('#toast-host');
    if (!h) {
      h = document.createElement('div');
      h.id = 'toast-host';
      document.body.appendChild(h);
    }
    return h;
  }

  function dismiss(el) {
    if (el._gone) return;
    el._gone = true;
    clearTimeout(el._timer);
    el.classList.add('toast-out');
    setTimeout(() => { el.remove(); flush(); }, 300);
  }

  // Show queued toasts once there is room.
  function flush() {
    const h = host();
    while (h.children.length < MAX && queue.length) render(h, queue.shift());
  }

  function render(h, item) {
    const el = document.createElement('div');
    el.className = 'toast toast-' + item.kind;

    const text = document.createElement('span');
    text.className = 'toast-msg';
    text.textContent = item.msg;

    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'toast-x';
    close.setAttribute('aria-label', 'Dismiss');
    close.textContent = '×';
    close.addEventListener('click', () => dismiss(el));

    const bar = document.createElement('div');
    bar.className = 'toast-bar';
    bar.style.animationDuration = LIFE_MS + 'ms';

    el.append(text, close, bar);
    h.appendChild(el);
    el._timer = setTimeout(() => dismiss(el), LIFE_MS);
  }

  window.toast = function (msg, kind = 'error') {
    const h = host();
    const item = { msg, kind };
    if (h.children.length < MAX) render(h, item);
    else queue.push(item);
  };
})();
