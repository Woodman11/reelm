const SERVER = 'http://127.0.0.1:7799';

const $step1  = document.getElementById('step1');
const $step2  = document.getElementById('step2');
const $step3  = document.getElementById('step3');
const $status = document.getElementById('status');
const $gotIt  = document.getElementById('got-it');
const $check  = document.getElementById('check-now');

let polling = false;

// --- Copy handlers ---
document.querySelectorAll('.cmd-block button').forEach(btn => {
  btn.addEventListener('click', async () => {
    const code = btn.previousElementSibling;
    try {
      await navigator.clipboard.writeText(code.textContent);
    } catch {
      // fallback for extensions without clipboard write
      const ta = document.createElement('textarea');
      ta.value = code.textContent;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    }
    btn.textContent = 'Copied!';
    btn.classList.add('copied');
    setTimeout(() => {
      btn.textContent = 'Copy';
      btn.classList.remove('copied');
    }, 2000);
  });
});

// --- Server check ---
async function checkServer() {
  $status.className = 'loading';
  $status.textContent = '⏳ Checking…';
  try {
    const res = await fetch(`${SERVER}/stats`);
    const data = await res.json();
    $status.className = 'ok';
    $status.textContent = `✅ Server connected — ${data.total} saved, ${data.indexed} indexed`;
    $step1.classList.add('done');
    $step1.classList.remove('active');
    $step2.classList.add('done');
    $step2.classList.remove('active');
    $step3.classList.add('done');
    $step3.classList.remove('active');
    $gotIt.classList.remove('hidden');
    if (polling) {
      clearInterval(polling);
      polling = false;
    }
    return true;
  } catch {
    $status.className = '';
    $status.textContent = '❌ Server not running on localhost:7799';
    return false;
  }
}

$check.addEventListener('click', (e) => {
  e.preventDefault();
  checkServer();
});

// --- Auto-poll: start checking after a delay so the user has time to read ---
setTimeout(() => {
  polling = setInterval(checkServer, 3000);
  checkServer();
}, 4000);

// --- "Got it" closes the tab ---
$gotIt.addEventListener('click', () => {
  window.close();
});
