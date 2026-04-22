const qEl      = document.getElementById('q');
const btn      = document.getElementById('btn');
const status   = document.getElementById('status');
const results  = document.getElementById('results');

function fmtTime(secs) {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  return h
    ? `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`
    : `${m}:${String(s).padStart(2,'0')}`;
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

    for (const r of items) {
      const a = document.createElement('a');
      a.className = 'result';
      a.href = r.url;
      a.target = '_blank';
      const date = r.savedAt
        ? new Date(r.savedAt * 1000).toLocaleDateString(undefined, {year:'numeric',month:'short',day:'numeric'})
        : '';
      a.innerHTML = `
        <div class="result-title">${r.title}</div>
        <div class="result-time">@ ${fmtTime(r.startSecs)}<span class="result-date">${date}</span></div>
      `;
      results.appendChild(a);
    }
  } catch {
    status.textContent = 'Server not running — start server.py';
  }
}

btn.addEventListener('click', doSearch);
qEl.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });
