const qEl       = document.getElementById('q');
const btn       = document.getElementById('btn');
const status    = document.getElementById('status');
const results   = document.getElementById('results');
const statsEl   = document.getElementById('stats');
const healthDot = document.getElementById('health-dot');

fetch('http://localhost:7799/stats')
  .then(r => r.json())
  .then(d => {
    healthDot.className = 'ok';
    statsEl.innerHTML = `<span class="indexed">${d.indexed}</span> / ${d.total} indexed`;
  })
  .catch(() => {
    healthDot.className = 'warn';
    statsEl.textContent = 'server offline';
  });

function fmtTime(secs) {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  return h
    ? `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`
    : `${m}:${String(s).padStart(2,'0')}`;
}

function getVideoId(url) {
  try { return new URL(url).searchParams.get('v') || url; }
  catch { return url; }
}

function makeResultEl(r) {
  const a = document.createElement('a');
  a.className = 'result';
  a.href = r.url;
  a.target = '_blank';
  const date = r.savedAt
    ? new Date(r.savedAt * 1000).toLocaleDateString(undefined, {year:'numeric',month:'short',day:'numeric'})
      + ' ' + new Date(r.savedAt * 1000).toLocaleTimeString(undefined, {hour:'numeric',minute:'2-digit'})
    : '';
  a.innerHTML = `
    <div class="result-title">${r.title}</div>
    <div class="result-time">@ ${fmtTime(r.startSecs)}<span class="result-date">${date}</span></div>
  `;
  return a;
}

async function doSearch() {
  const q = qEl.value.trim();
  if (!q) return;

  status.textContent = 'Searching…';
  results.innerHTML = '';

  try {
    const res = await fetch(`http://localhost:7799/search?q=${encodeURIComponent(q)}`);
    const data = await res.json();

    if (data.error) {
      status.textContent = `Error: ${data.error}`;
      return;
    }

    const items = data.results;
    status.textContent = items.length ? `${items.length} result(s)` : 'No results found.';

    // Group hits by video ID, preserving first-seen order
    const groups = new Map();
    for (const r of items) {
      const vid = getVideoId(r.url);
      if (!groups.has(vid)) groups.set(vid, []);
      groups.get(vid).push(r);
    }

    for (const hits of groups.values()) {
      results.appendChild(makeResultEl(hits[0]));

      if (hits.length > 1) {
        const rest = hits.slice(1);
        const folder = document.createElement('div');

        const toggle = document.createElement('div');
        toggle.className = 'folder-toggle';
        toggle.textContent = `▶  ${rest.length} more timestamp${rest.length > 1 ? 's' : ''} in this video`;
        folder.appendChild(toggle);

        const inner = document.createElement('div');
        inner.className = 'folder-inner';
        inner.style.display = 'none';
        for (const r of rest) inner.appendChild(makeResultEl(r));

        toggle.addEventListener('click', () => {
          const open = inner.style.display !== 'none';
          inner.style.display = open ? 'none' : 'block';
          toggle.textContent = `${open ? '▶' : '▼'}  ${rest.length} more timestamp${rest.length > 1 ? 's' : ''} in this video`;
          if (!open) toggle.scrollIntoView({behavior: 'smooth', block: 'nearest'});
        });

        folder.appendChild(inner);
        results.appendChild(folder);
      }
    }
  } catch {
    status.textContent = 'Server not running — start server.py';
  }
}

btn.addEventListener('click', doSearch);
qEl.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });
