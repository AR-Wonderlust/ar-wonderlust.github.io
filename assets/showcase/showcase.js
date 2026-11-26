'use strict';
(function () {
  var stage = document.getElementById('stage');
  var index = 0;
  var data;
  var paused = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var elapsed = 0;
  var last = 0;
  var timer;
  var wake;
  var hideTimer;
  var audio;
  var musicTracks = [];
  var musicIndex = -1;
  var musicButton = document.getElementById('music');
  var pause = document.getElementById('pause');
  var full = document.getElementById('fullscreen');
  var root = document.getElementById('presentation');
  var labels = {
    whatsapp: '+54 9 388 538-3215',
    instagram: '@somosromaturismo',
    tiktok: '@romaturismo',
    google: 'Agencia ROMA · Google Maps'
  };
  var poolBags = {};
  var poolLast = {};
  // Las 9 plantillas se mantienen; solo cambia el recurso visual.
  var slidePools = [
    'paisajes', 'alojamiento', 'traslados', 'paisajes', 'paisajes',
    null, 'actividades', 'opinion', 'despedida'
  ];

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text) node.textContent = text;
    return node;
  }

  function external(url) {
    var link = el('a');
    link.href = url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    return link;
  }

  function notice(text) {
    document.getElementById('notice').textContent = text;
    clearTimeout(timer);
    timer = setTimeout(function () { document.getElementById('notice').textContent = ''; }, 7000);
  }

  function musicState() {
    if (!musicButton) return;
    if (!audio) { musicButton.hidden = true; return; }
    musicButton.hidden = false;
    musicButton.textContent = audio.muted ? 'Activar música ♫' : 'Silenciar música 🔇';
    musicButton.setAttribute('aria-pressed', String(!audio.muted));
  }

  function enableMusic() {
    if (!audio) return;
    audio.muted = false;
    var attempt = audio.play();
    if (attempt && attempt.catch) attempt.catch(function () {
      audio.muted = true;
      notice('Tocá “Activar música” para iniciar el audio.');
    });
    musicState();
  }

  function toggleMusic() {
    if (!audio) return;
    if (audio.muted) enableMusic();
    else { audio.muted = true; musicState(); }
  }

  function playCurrentTrack() {
    if (!audio || musicIndex < 0 || !musicTracks[musicIndex]) return;
    audio.src = musicTracks[musicIndex].src || musicTracks[musicIndex];
    audio.load();
    var attempt = audio.play();
    if (attempt && attempt.catch) attempt.catch(function () {
      notice('Tocá “Activar música” para iniciar el audio.');
    });
  }

  function nextTrack() {
    if (!musicTracks.length) return;
    var next = musicIndex;
    if (musicTracks.length > 1) {
      while (next === musicIndex) next = Math.floor(Math.random() * musicTracks.length);
    } else {
      next = 0;
    }
    musicIndex = next;
    playCurrentTrack();
  }

  function setupMusic(tracks) {
    if (!tracks || !tracks.length) { musicState(); return; }
    musicTracks = tracks.filter(function (track) { return track && (track.src || typeof track === 'string'); });
    if (!musicTracks.length) { musicState(); return; }
    audio = new Audio();
    audio.preload = 'auto';
    audio.autoplay = true;
    audio.loop = false;
    audio.muted = true;
    audio.volume = 0.35;
    audio.addEventListener('ended', nextTrack);
    audio.addEventListener('error', nextTrack);
    nextTrack();
    musicState();
    // Chrome/Android allow muted autoplay; audible playback requires a gesture.
  }

  function shuffled(values) {
    var result = values.slice();
    for (var i = result.length - 1; i > 0; i -= 1) {
      var j = Math.floor(Math.random() * (i + 1));
      var swap = result[i];
      result[i] = result[j];
      result[j] = swap;
    }
    return result;
  }

  function pickMedia(pool) {
    if (!pool || !data || !data.media_pools || !data.media_pools[pool]) return null;
    var source = data.media_pools[pool];
    if (!source.length) return null;
    if (!poolBags[pool] || !poolBags[pool].length) {
      poolBags[pool] = shuffled(source);
      if (poolBags[pool].length > 1 && poolLast[pool] && poolBags[pool][poolBags[pool].length - 1].src === poolLast[pool]) {
        poolBags[pool].unshift(poolBags[pool].pop());
      }
    }
    var selected = poolBags[pool].pop();
    poolLast[pool] = selected.src;
    return selected;
  }

  function mediaForSlide(slide, visual, selected) {
    if (selected && selected.type === 'video' && selected.src) {
      var video = el('video');
      video.src = selected.src;
      video.poster = selected.poster || '';
      video.autoplay = true;
      video.muted = true;
      video.loop = true;
      video.playsInline = true;
      video.setAttribute('aria-label', selected.alt || slide.alt || slide.title || 'Video ROMA');
      visual.appendChild(video);
      var attempt = video.play();
      if (attempt && attempt.catch) attempt.catch(function () {});
      return;
    }
    if (selected && selected.src) {
      var selectedPicture = el('img');
      selectedPicture.src = selected.src;
      selectedPicture.alt = selected.alt || slide.alt;
      visual.appendChild(selectedPicture);
      return;
    }
    if (slide.crop) {
      var ns = 'http://www.w3.org/2000/svg';
      var svg = document.createElementNS(ns, 'svg');
      var image = document.createElementNS(ns, 'image');
      svg.setAttribute('viewBox', slide.crop);
      svg.setAttribute('preserveAspectRatio', 'xMidYMid slice');
      svg.setAttribute('role', 'img');
      svg.setAttribute('aria-label', slide.alt);
      image.setAttribute('href', '/assets/showcase/servicios.jpg');
      image.setAttribute('width', '2048');
      image.setAttribute('height', '1143');
      svg.appendChild(image);
      visual.appendChild(svg);
      return;
    }
    var picture = el('img');
    picture.src = slide.image;
    picture.alt = slide.alt;
    visual.appendChild(picture);
  }

  function show(number) {
    if (!data || !data.slides.length) return;
    index = (number + data.slides.length) % data.slides.length;
    elapsed = 0;
    last = performance.now();
    var slide = data.slides[index];
    var selected = pickMedia(slidePools[index] || slide.pool);
    var article = el('article', 'slide');
    article.setAttribute('aria-label', (index + 1) + ' de ' + data.slides.length);
    var visual = el('div', 'visual');
    mediaForSlide(slide, visual, selected);
    var note = el('div', 'photo-note', 'AGENCIA ROMA');
    note.appendChild(el('b', '', slide.kind === 'google' ? 'Gracias por elegirnos.' : 'Viví el Norte.'));
    note.appendChild(el('span', '', 'VIAJES QUE SE CONVIERTEN EN RECUERDOS'));
    visual.appendChild(note);
    visual.appendChild(el('span', 'ribbon'));
    article.appendChild(visual);

    var copy = el('div', 'copy');
    copy.appendChild(el('p', 'eyebrow', slide.tag));
    copy.appendChild(el('h1', '', slide.title));
    copy.appendChild(el('p', 'description', slide.text));
    var action = el('div', 'action');
    var qr = external(data.links[slide.kind]);
    qr.className = 'qr-link';
    qr.setAttribute('aria-label', slide.label);
    var qrImage = el('img');
    qrImage.src = '/assets/showcase/' + slide.kind + '.svg';
    qrImage.alt = 'QR: ' + slide.label;
    qrImage.width = 230;
    qrImage.height = 230;
    qr.appendChild(qrImage);
    action.appendChild(qr);
    var info = el('div', 'action-text');
    info.appendChild(el('small', '', 'ESCANEÁ O TOCÁ EL QR'));
    var link = external(data.links[slide.kind]);
    link.textContent = slide.label + ' ↗';
    info.appendChild(link);
    info.appendChild(el('p', 'handle', labels[slide.kind] || 'Agencia ROMA'));
    if (slide.kind === 'whatsapp') info.appendChild(el('p', 'handle', 'Abrí el chat y tocá Enviar.'));
    action.appendChild(info);
    copy.appendChild(action);
    article.appendChild(copy);
    stage.replaceChildren(article);
    document.getElementById('counter').textContent = String(index + 1).padStart(2, '0') + ' / ' + String(data.slides.length).padStart(2, '0');
    document.getElementById('progress').style.width = '0%';
  }

  function state() {
    pause.textContent = paused ? 'Continuar ▶' : 'Pausar Ⅱ';
    pause.setAttribute('aria-pressed', String(paused));
  }

  function toggle() { paused = !paused; last = performance.now(); state(); }

  function activity() {
    root.classList.remove('hide-controls');
    clearTimeout(hideTimer);
    if (document.fullscreenElement) hideTimer = setTimeout(function () {
      if (!root.contains(document.activeElement) || document.activeElement === full) root.classList.add('hide-controls');
    }, 6000);
  }

  function move(direction) { show(index + direction); activity(); }

  async function keepAwake() {
    try {
      if (navigator.wakeLock && document.fullscreenElement && !document.hidden) wake = await navigator.wakeLock.request('screen');
    } catch (error) { /* Wake lock is optional. */ }
  }

  full.addEventListener('click', async function () {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if (root.requestFullscreen) await root.requestFullscreen();
      else notice('Usá el modo pantalla completa del navegador o del televisor.');
    } catch (error) { notice('Este navegador no permite pantalla completa. La presentación continúa.'); }
  });
  musicButton.addEventListener('click', toggleMusic);
  pause.addEventListener('click', toggle);
  document.getElementById('prev').addEventListener('click', function () { move(-1); });
  document.getElementById('next').addEventListener('click', function () { move(1); });
  root.addEventListener('pointerdown', function () { if (audio && audio.muted) enableMusic(); activity(); });
  root.addEventListener('mousemove', activity);
  root.addEventListener('focusin', activity);
  document.addEventListener('fullscreenchange', function () {
    var active = !!document.fullscreenElement;
    root.classList.toggle('presentation-mode', active);
    full.textContent = active ? 'Salir de pantalla completa ⛶' : 'Pantalla completa ⛶';
    if (active) keepAwake();
    else { root.classList.remove('hide-controls'); if (wake) wake.release(); }
    activity();
  });
  document.addEventListener('keydown', function (event) {
    activity();
    if (audio && audio.muted && event.code !== 'Tab') enableMusic();
    if (event.key === 'ArrowRight') { event.preventDefault(); move(1); }
    if (event.key === 'ArrowLeft') { event.preventDefault(); move(-1); }
    if (event.code === 'Space' && !/BUTTON|A|INPUT/.test(event.target.tagName)) { event.preventDefault(); toggle(); }
  });
  document.addEventListener('visibilitychange', function () { last = performance.now(); if (!document.hidden) keepAwake(); });

  setInterval(function () {
    var now = performance.now();
    var delta = last ? now - last : 0;
    last = now;
    if (!data || paused || document.hidden || stage.contains(document.activeElement)) return;
    elapsed += Math.min(delta, 1000);
    var duration = data.slides[index].duration || 15000;
    if (elapsed >= duration) show(index + 1);
    document.getElementById('progress').style.width = (100 * elapsed / duration) + '%';
  }, 200);

  fetch('/assets/showcase/slides.json?v=3')
    .then(function (response) { if (!response.ok) throw Error('data'); return response.json(); })
    .then(function (loaded) {
      if (!loaded.slides || !loaded.slides.length) throw Error('empty');
      data = loaded;
      if (data.music && data.music.length) return data;
      return fetch('/assets/showcase/media-manifest.json?v=3')
        .then(function (manifestResponse) {
          if (!manifestResponse.ok) return data;
          return manifestResponse.json();
        })
        .then(function (manifest) {
          data.music = manifest.music || [];
          data.media_pools = manifest.pools || {};
          return data;
        });
    })
    .then(function (loaded) {
      data = loaded;
      setupMusic(data.music || []);
      show(0);
      state();
    })
    .catch(function () {
      stage.querySelector('.loading p').textContent = 'No pudimos cargar la presentación. Podés usar los enlaces de contacto o recargar la página.';
      pause.disabled = true;
      if (musicButton) musicButton.hidden = true;
    });
}());
