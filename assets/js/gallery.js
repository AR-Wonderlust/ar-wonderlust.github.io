'use strict';
(() => {
 const section = document.getElementById('landscape-gallery');
 const stage = document.getElementById('media-stage');
 const status = document.getElementById('media-status');
 const toggle = document.getElementById('media-toggle');
 const api = (window.ROMA_CONFIG?.api_url || '').replace(/\/$/, '');
 if (!section || !api) return;
 const small = matchMedia('(max-width: 700px)');
 const reduced = matchMedia('(prefers-reduced-motion: reduce)');
 let items = [], region = 'all', paused = reduced.matches || !!navigator.connection?.saveData;
 let visible = false, failedPlay = false;
 const labels = {general: 'Jujuy', quebrada: 'Quebrada', puna: 'Puna', yungas: 'Yungas', valles: 'Valles'};
 const videos = () => Array.from(stage.querySelectorAll('video'));
 function buttonLabel() { toggle.textContent = paused || failedPlay ? 'Reproducir' : 'Pausar'; }
 function syncPlayback() {
  videos().forEach(v => {
   if (paused || !visible || document.hidden) v.pause();
   else v.play().catch(() => { failedPlay = true; buttonLabel(); });
  });
  buttonLabel();
 }
 function render() {
  videos().forEach(v => { v.pause(); v.removeAttribute('src'); v.load(); });
  stage.replaceChildren(); failedPlay = false;
  const pool = items.filter(i => region === 'all' || i.region === region);
  // Fisher-Yates: unique choices within each visible set.
  for (let i = pool.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [pool[i], pool[j]] = [pool[j], pool[i]]; }
  const selected = pool.slice(0, small.matches ? 1 : 3);
  selected.forEach(item => {
   const figure = document.createElement('figure');
   const media = document.createElement(item.kind === 'video' ? 'video' : 'img');
   const label = labels[item.region] || 'Jujuy';
   if (item.kind === 'video') {
    media.muted = true; media.defaultMuted = true; media.loop = true; media.playsInline = true;
    media.preload = 'none'; media.setAttribute('aria-label', 'Paisajes de ' + label);
   } else { media.alt = 'Paisajes de ' + label; media.loading = 'lazy'; }
   media.src = api + item.url;
   const caption = document.createElement('figcaption'); caption.textContent = label;
   media.addEventListener('error', () => { caption.textContent = label + ' · Archivo no disponible'; });
   figure.append(media, caption); stage.append(figure);
  });
  status.textContent = selected.length ? 'Imágenes y videos de Agencia ROMA · Sin sonido' : 'Próximamente compartiremos imágenes de esta región.';
  toggle.disabled = selected.length === 0;
  syncPlayback();
 }
 toggle.addEventListener('click', () => { paused = failedPlay ? false : !paused; failedPlay = false; syncPlayback(); });
 document.getElementById('media-next').addEventListener('click', render);
 section.querySelectorAll('[data-gallery-region]').forEach(b => b.addEventListener('click', () => {
  region = b.dataset.galleryRegion;
  section.querySelectorAll('[data-gallery-region]').forEach(el => el.setAttribute('aria-pressed', String(el === b)));
  render();
 }));
 small.addEventListener('change', () => { if (items.length) render(); });
 reduced.addEventListener('change', () => { paused = reduced.matches; syncPlayback(); });
 document.addEventListener('visibilitychange', syncPlayback);
 new IntersectionObserver(entries => { visible = entries[0].isIntersecting; syncPlayback(); }, {threshold: 0.15}).observe(section);
 setInterval(() => { if (items.length && visible && !paused && !failedPlay && !document.hidden) render(); }, 18000);
 fetch(api + '/gallery', {signal: AbortSignal.timeout(25000)})
  .then(r => { if (!r.ok) throw new Error('gallery'); return r.json(); })
  .then(data => {
   items = (Array.isArray(data.items) ? data.items : []).filter(i =>
    ['image', 'video'].includes(i.kind) && Object.hasOwn(labels, i.region) && /^\/media\/[\w-]+$/.test(i.url));
   if (items.length) { section.hidden = false; document.getElementById('fallback-regions').hidden = true; document.getElementById('photo-credit').hidden = true; document.querySelector('.hero').classList.add('has-gallery'); render(); }
  }).catch(() => { /* Existing hero landscapes remain available while the server is offline. */ });
})();
