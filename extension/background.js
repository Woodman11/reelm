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
    const {videoId, captionUrl} = msg.data;

    const toJson3 = (url) => {
      try {
        const u = new URL(url);
        u.searchParams.set('fmt', 'json3');
        return u.toString();
      } catch { return null; }
    };

    const tryUrl = (url) => {
      if (!url) return Promise.resolve(null);
      return fetch(url, {credentials: 'include'})
        .then(r => r.text())
        .then(text => {
          if (!text || text[0] !== '{') return null;
          const data = JSON.parse(text);
          const segs = [];
          for (const ev of (data.events || [])) {
            if (!ev.segs) continue;
            const start = (ev.tStartMs || 0) / 1000;
            const txt = ev.segs.map(s => s.utf8 || '').join('').trim();
            if (txt && txt !== '\n') segs.push({start, text: txt});
          }
          return segs.length ? segs : null;
        })
        .catch(() => null);
    };

    const base = `https://www.youtube.com/api/timedtext?v=${videoId}&lang=en&fmt=json3`;
    const primary = captionUrl ? toJson3(captionUrl) : null;

    tryUrl(primary)
      .then(segs => segs || tryUrl(base + '&kind=asr'))
      .then(segs => segs || tryUrl(base))
      .then(segs => {
        if (!segs) return;
        return fetch('http://localhost:7799/transcript', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({videoId, segments: segs})
        });
      })
      .catch(() => {});
  }
});
