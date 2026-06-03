const SERVER = 'http://127.0.0.1:7799';

// On fresh install, check if the server is running. If not, open onboarding.
chrome.runtime.onInstalled.addListener(({ reason }) => {
  if (reason !== 'install') return;
  fetch(`${SERVER}/stats`)
    .then(r => r.json())
    .then(() => {
      // server already running — all good
    })
    .catch(() => {
      // server not running — open onboarding tab
      chrome.tabs.create({ url: 'onboarding.html' });
    });
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'save') {
    fetch(`${SERVER}/save`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(msg.data)
    })
      .then(r => r.json())
      .then(data => sendResponse({ok: true, data}))
      .catch(() => sendResponse({ok: false}));
    return true;
  }

  if (msg.type === 'transcript') {
    const {videoId, segments} = msg.data;
    if (!videoId || !segments || !segments.length) return;
    fetch(`${SERVER}/transcript`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({videoId, segments})
    }).catch(() => {});
  }
});
