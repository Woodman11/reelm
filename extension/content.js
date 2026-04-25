document.addEventListener('keydown', async (e) => {
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

  // Fetch transcript from the page itself — avoids any server-side YouTube requests
  const segments = await fetchTranscriptFromPage();

  fetch('http://localhost:7799/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ videoId, currentTime, title, segments })
  })
    .then(r => r.json())
    .then(data => showToast(data.message))
    .catch(() => showToast('Server not running — start server.py', 'error'));
}, true);

function fetchTranscriptFromPage() {
  return new Promise(resolve => {
    const eventName = '__yt_caps_' + Date.now();
    let script;

    const timer = setTimeout(() => {
      window.removeEventListener(eventName, onUrl);
      if (script) script.remove();
      resolve(null);
    }, 3000);

    function onUrl(e) {
      clearTimeout(timer);
      window.removeEventListener(eventName, onUrl);
      if (script) script.remove();

      const baseUrl = e.detail;
      if (!baseUrl) { resolve(null); return; }

      // Fetch the timedtext JSON from within the browser using the existing YouTube session
      fetch(baseUrl + '&fmt=json3')
        .then(r => r.json())
        .then(data => {
          const segs = [];
          for (const ev of (data.events || [])) {
            if (!ev.segs) continue;
            const start = (ev.tStartMs || 0) / 1000;
            const text = ev.segs.map(s => s.utf8 || '').join('').trim();
            if (text && text !== '\n') segs.push({ start, text });
          }
          resolve(segs.length ? segs : null);
        })
        .catch(() => resolve(null));
    }

    window.addEventListener(eventName, onUrl);

    // Inject into page's main world to read ytInitialPlayerResponse
    script = document.createElement('script');
    script.textContent = `(function(){
      try {
        const tracks = window.ytInitialPlayerResponse
          ?.captions?.playerCaptionsTracklistRenderer?.captionTracks;
        const track = tracks && (tracks.find(t => /^en/.test(t.languageCode)) || tracks[0]);
        window.dispatchEvent(new CustomEvent('${eventName}', {detail: track ? track.baseUrl : null}));
      } catch(e) {
        window.dispatchEvent(new CustomEvent('${eventName}', {detail: null}));
      }
    })();`;
    document.head.appendChild(script);
  });
}

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
