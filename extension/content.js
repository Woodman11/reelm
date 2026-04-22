document.addEventListener('keydown', (e) => {
  // Shift+Y — use capture phase (third arg true) so YouTube's stopPropagation() can't swallow it
  if (e.code !== 'KeyY' || !e.shiftKey || e.altKey || e.ctrlKey || e.metaKey) return;
  const t = e.target;
  if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
  e.preventDefault();

  const video = document.querySelector('video');
  if (!video) {
    showToast('No video found on page', 'error');
    return;
  }

  const params = new URLSearchParams(window.location.search);
  const videoId = params.get('v');
  if (!videoId) return; // not on a watch page, ignore silently

  const currentTime = Math.floor(video.currentTime);
  const title = document.title.replace(/ - YouTube$/, '').trim();

  fetch('http://localhost:7799/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ videoId, currentTime, title })
  })
    .then(r => r.json())
    .then(data => showToast(data.message))
    .catch(() => showToast('Server not running — start server.py', 'error'));
}, true);

function showToast(msg, type = 'ok') {
  // Remove any existing toast
  document.getElementById('yt-search-toast')?.remove();

  const el = document.createElement('div');
  el.id = 'yt-search-toast';
  el.textContent = msg;
  el.style.cssText = [
    'position:fixed',
    'top:72px',
    'right:20px',
    'z-index:99999',
    `background:${type === 'error' ? '#c0392b' : '#1a1a2e'}`,
    'color:#fff',
    'padding:10px 18px',
    'border-radius:6px',
    'font:bold 13px/1.4 "YouTube Noto",Roboto,sans-serif',
    'box-shadow:0 4px 14px rgba(0,0,0,.45)',
    'transition:opacity .3s ease',
    'opacity:1',
  ].join(';');

  document.body.appendChild(el);

  setTimeout(() => {
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 300);
  }, 2700);
}
