'use strict';

// RomAi web voice bridge. The browser records only while the button is held;
// n8n remains responsible for transcription, catalog rules, response and TTS.
(function () {
  const cfg = window.ROMA_CONFIG || {};
  const voiceCfg = cfg.voice || window.ROMA_VOICE_CONFIG || {};
  const recordButton = document.querySelector('#voice-record');
  const liveButton = document.querySelector('#live-voice');
  const launcher = document.querySelector('#voice-launcher');
  const chat = document.querySelector('#chat');
  const voiceStatus = document.querySelector('#voice-status');
  const chatStatus = document.querySelector('#chat-status');
  const messages = document.querySelector('#messages');
  if (!recordButton || !chat) return;

  const endpoint = String(voiceCfg.webhook_url || '').trim();
  const liveEndpoint = String(voiceCfg.live_url || '').trim();
  let recorder = null;
  let stream = null;
  let chunks = [];
  let stopTimer = null;
  let recording = false;
  let pressing = false;
  let sessionId = sessionStorage.getItem('romai-session-id');
  if (!sessionId) {
    sessionId = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random());
    sessionStorage.setItem('romai-session-id', sessionId);
  }

  function status(text) {
    if (voiceStatus) voiceStatus.textContent = text || '';
    if (chatStatus && text) chatStatus.textContent = text;
  }

  function addMessage(role, text) {
    if (!text || !messages) return;
    const bubble = document.createElement('div');
    bubble.className = 'bubble' + (role === 'user' ? ' user' : '');
    bubble.textContent = text;
    messages.append(bubble);
    messages.scrollTop = messages.scrollHeight;
  }

  function preferredMime() {
    const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/ogg'];
    return candidates.find(type => window.MediaRecorder && MediaRecorder.isTypeSupported(type)) || '';
  }

  function stopTracks() {
    if (stream) stream.getTracks().forEach(track => track.stop());
    stream = null;
  }

  function resetButton() {
    recording = false;
    recordButton.classList.remove('is-recording');
    recordButton.setAttribute('aria-pressed', 'false');
    recordButton.innerHTML = '<span aria-hidden="true">🎙️</span> Mantener presionado para hablar';
  }

  async function startRecording(event) {
    event?.preventDefault();
    if (recording) return;
    if (!endpoint) {
      status('La voz web está preparada, pero falta configurar el webhook de n8n.');
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      status('Este navegador no permite grabar audio. Podés escribir tu consulta.');
      return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!pressing) { stopTracks(); return; }
      const mime = preferredMime();
      recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      chunks = [];
      recorder.addEventListener('dataavailable', item => { if (item.data.size) chunks.push(item.data); });
      recorder.addEventListener('stop', sendRecording, { once: true });
      recorder.start();
      recording = true;
      recordButton.classList.add('is-recording');
      recordButton.setAttribute('aria-pressed', 'true');
      recordButton.innerHTML = '<span aria-hidden="true">⏺</span> Soltá para enviar';
      status('Grabando…');
      clearTimeout(stopTimer);
      stopTimer = setTimeout(stopRecording, 30000);
    } catch {
      stopTracks();
      resetButton();
      status('No se pudo acceder al micrófono. Revisá el permiso del navegador.');
    }
  }

  function stopRecording(event) {
    event?.preventDefault();
    pressing = false;
    clearTimeout(stopTimer);
    if (!recorder || recorder.state === 'inactive') return;
    recorder.stop();
    recorder = null;
    resetButton();
    status('Procesando tu consulta…');
  }

  async function playResponse(data) {
    const source = data.audio_url || (data.audio_base64 ? `data:${data.audio_mime || 'audio/mpeg'};base64,${data.audio_base64}` : '');
    if (!source) return;
    try {
      const player = new Audio(source);
      await player.play();
    } catch {
      status('La respuesta está lista. Tocá la pantalla para reproducir el audio.');
    }
  }

  async function sendRecording() {
    const type = recorder?.mimeType || preferredMime() || 'audio/webm';
    const extension = type.includes('ogg') ? 'ogg' : 'webm';
    const blob = new Blob(chunks, { type });
    stopTracks();
    if (!blob.size) { status('No se detectó audio. Intentá nuevamente.'); return; }
    const form = new FormData();
    form.append('audio', blob, `romai-${Date.now()}.${extension}`);
    form.append('source', 'web_ar_wonderlust');
    form.append('session_id', sessionId);
    try {
      const response = await fetch(endpoint, { method: 'POST', body: form, signal: AbortSignal.timeout(45000) });
      if (!response.ok) throw new Error('voice request');
      const data = await response.json();
      if (data.transcript) addMessage('user', data.transcript);
      if (data.reply) addMessage('model', data.reply);
      await playResponse(data);
      status('');
    } catch {
      status('No pudimos procesar el audio. Podés escribir la consulta o continuar por WhatsApp.');
    }
  }

  recordButton.addEventListener('pointerdown', event => { pressing = true; startRecording(event); });
  recordButton.addEventListener('pointerup', stopRecording);
  recordButton.addEventListener('pointercancel', stopRecording);
  recordButton.addEventListener('pointerleave', event => { if (recording && event.buttons === 0) stopRecording(event); });
  recordButton.addEventListener('keydown', event => {
    if ((event.code === 'Space' || event.code === 'Enter') && !event.repeat) { pressing = true; startRecording(event); }
  });
  recordButton.addEventListener('keyup', event => {
    if (event.code === 'Space' || event.code === 'Enter') stopRecording(event);
  });

  if (liveEndpoint) {
    liveButton.disabled = false;
    liveButton.textContent = 'Conversación en vivo ↗';
    liveButton.addEventListener('click', () => window.open(liveEndpoint, '_blank', 'noopener,noreferrer'));
  }
  launcher?.addEventListener('click', () => {
    window.setTimeout(() => recordButton.focus(), 0);
  });
}());
