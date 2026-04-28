const SERVER = 'http://127.0.0.1:7799';

const $stats = document.getElementById('stats');
const $status = document.getElementById('status');
const $btn = document.getElementById('wipe');
const $version = document.getElementById('version');

$version.textContent = 'v' + chrome.runtime.getManifest().version;

async function loadStats() {
  try {
    const res = await fetch(`${SERVER}/stats`);
    const data = await res.json();
    $stats.innerHTML =
      `<span class="indexed">${data.indexed}</span> of ` +
      `<span class="total">${data.total}</span> saved videos have transcripts.`;
    $btn.disabled = data.total === 0;
    return data;
  } catch (e) {
    $stats.textContent = 'Server not running on localhost:7799.';
    $btn.disabled = true;
    return null;
  }
}

async function wipe() {
  const stats = await loadStats();
  if (!stats || stats.total === 0) return;

  const ok = confirm(
    `Delete all ${stats.total} saved videos and their transcripts?\n\n` +
    `This cannot be undone.`
  );
  if (!ok) return;

  $btn.disabled = true;
  $status.classList.remove('error');
  $status.textContent = 'Wiping…';

  try {
    const res = await fetch(`${SERVER}/wipe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}'
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    $status.textContent = `Wiped ${data.deleted} videos.`;
    await loadStats();
  } catch (e) {
    $status.classList.add('error');
    $status.textContent = `Error: ${e.message}`;
    $btn.disabled = false;
  }
}

$btn.addEventListener('click', wipe);
loadStats();
