const player = document.querySelector('#project-video');
const youtubeUrl = player.dataset.youtubeUrl.trim();

if (youtubeUrl) {
  try {
    const url = new URL(youtubeUrl);
    const host = url.hostname.replace(/^www\./, '');
    const id = host === 'youtu.be' ? url.pathname.split('/')[1]
      : ['youtube.com', 'm.youtube.com', 'youtube-nocookie.com'].includes(host)
        ? url.searchParams.get('v') || /^\/(?:embed|shorts)\/([^/]+)$/.exec(url.pathname)?.[1]
        : null;

    if (/^[\w-]{11}$/.test(id || '')) {
      const frame = document.createElement('iframe');
      frame.src = 'https://www.youtube-nocookie.com/embed/' + id;
      frame.title = 'Video explicativo de TerraSprout';
      frame.loading = 'lazy';
      frame.setAttribute('credentialless', '');
      frame.allow = 'encrypted-media; picture-in-picture; fullscreen';
      frame.allowFullscreen = true;

      const link = document.createElement('a');
      link.href = 'https://www.youtube.com/watch?v=' + id;
      link.target = '_blank';
      link.rel = 'noopener';
      link.textContent = 'Ver en YouTube ↗';
      player.replaceChildren(frame, link);
    }
  } catch {
    // Keep the local explainer if the configured URL is invalid.
  }
}
