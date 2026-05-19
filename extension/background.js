chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'save') {
    fetch('http://localhost:7799/save', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(msg.data)
    })
      .then(r => r.json())
      .then(data => sendResponse({ok: true, data}))
      .catch(() => sendResponse({ok: false}));
    return true; // keep channel open for async response
  }

  if (msg.type === 'transcript') {
    const {videoId, segments} = msg.data;
    if (!videoId || !segments || !segments.length) return;
    fetch('http://localhost:7799/transcript', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({videoId, segments})
    }).catch(() => {});
  }
});
