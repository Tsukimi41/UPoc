import { animate, createScope } from 'https://esm.sh/animejs';

const artCanvas = document.getElementById('artCanvas');
const overlayCanvas = document.getElementById('overlayCanvas');
const ctx = artCanvas ? artCanvas.getContext('2d') : null;
const overlayCtx = overlayCanvas ? overlayCanvas.getContext('2d') : null;

let gridWidth = 40;
let gridHeight = 25;
let totalPixels = 1000;
let pixelSize = 16;
let caps = [];
let capsByIndex = new Map();
let animationQueue = [];
let animating = false;
let wsConnected = false;
let activeCheckinToken = '';

const elements = {
  remainingCount: document.getElementById('remainingCount'),
  progressCount: document.getElementById('progressCount'),
  totalCount: document.getElementById('totalCount'),
  progressPercent: document.getElementById('progressPercent'),
  progressFill: document.getElementById('progressFill'),
  latestMessage: document.getElementById('latestMessage'),
  leaderboard: document.getElementById('leaderboard'),
  colorStats: document.getElementById('colorStats'),
  suggestionSummary: document.getElementById('suggestionSummary'),
  suggestionThemes: document.getElementById('suggestionThemes'),
  suggestionPalette: document.getElementById('suggestionPalette'),
  themeVotes: document.getElementById('themeVotes'),
  eventStatus: document.getElementById('eventStatus'),
  eventTitle: document.getElementById('eventTitle'),
  participantBadge: document.getElementById('participantBadge'),
  activeCheckinToken: document.getElementById('activeCheckinToken'),
  checkinNickname: document.getElementById('checkinNickname'),
  checkinTokenLabel: document.getElementById('checkinToken'),
  checkinTokenInput: document.getElementById('checkinTokenInput'),
  checkinQr: document.getElementById('checkinQr'),
  checkinShareLink: document.getElementById('checkinShareLink'),
  checkinStatus: document.getElementById('checkinStatus'),
  toastContainer: document.getElementById('toastContainer'),
};

const mockState = {
  progress: 620,
  total: 1000,
  remaining: 380,
  width: 40,
  height: 25,
  caps: [],
  leaderboard: [
    { nickname: 'まり', count: 45 },
    { nickname: 'ゆうた', count: 38 },
    { nickname: 'chofu', count: 30 },
  ],
  colorStats: [
    { label: '赤', count: 120, ratio: 0.19, hex: '#f0454b' },
    { label: '青', count: 110, ratio: 0.17, hex: '#1e88e5' },
    { label: '黄', count: 96, ratio: 0.15, hex: '#f6c445' },
  ],
  suggestions: {
    summary: 'トップカラーは赤と青。夕景や水辺のテーマが人気です。',
    suggestedThemes: ['夕焼けの街並み', '水辺の調布', '花火の夜'],
    palette: [
      { hex: '#f0454b' },
      { hex: '#ffb26a' },
      { hex: '#1e88e5' },
    ],
  },
  themes: [
    { id: 'chofu-water', title: '調布の水辺', description: '水景をイメージ', votes: 26 },
    { id: 'gegege', title: '鬼太郎と仲間たち', description: 'ドット絵で再現', votes: 18 },
  ],
  event: { title: 'UPoc 2026', status: 'active' },
};

function setText(el, value) {
  if (el) {
    el.textContent = value;
  }
}

function updateCanvasSize(width, height) {
  if (!artCanvas || !overlayCanvas) {
    return;
  }
  gridWidth = width;
  gridHeight = height;
  const wrapper = document.querySelector('.canvas-wrapper');
  const maxWidth = wrapper ? Math.min(720, wrapper.clientWidth - 24) : 640;
  pixelSize = Math.max(8, Math.floor(maxWidth / gridWidth));
  artCanvas.width = pixelSize * gridWidth;
  artCanvas.height = pixelSize * gridHeight;
  overlayCanvas.width = artCanvas.width;
  overlayCanvas.height = artCanvas.height;
}

function clearCanvas() {
  if (!ctx) {
    return;
  }
  ctx.fillStyle = '#fff8f4';
  ctx.fillRect(0, 0, artCanvas.width, artCanvas.height);
}

function drawCap(cap) {
  if (!ctx) {
    return;
  }
  ctx.fillStyle = cap.color.hex;
  ctx.fillRect(cap.x * pixelSize, cap.y * pixelSize, pixelSize, pixelSize);
}

function drawAllCaps() {
  if (!ctx) {
    return;
  }
  clearCanvas();
  caps.forEach(drawCap);
}

function updateStats(progress, remaining, total) {
  const percent = total ? Math.round((progress / total) * 100) : 0;
  setText(elements.progressCount, progress);
  setText(elements.remainingCount, remaining);
  setText(elements.totalCount, total);
  if (elements.progressPercent) {
    elements.progressPercent.textContent = `${percent}%`;
  }
  if (elements.progressFill) {
    elements.progressFill.style.width = `${percent}%`;
  }
}

function updateLatest(cap) {
  if (elements.latestMessage) {
    elements.latestMessage.textContent = `${cap.color.label} / 第${cap.index}番 (${cap.nickname})`;
  }
}

function renderEvent(event) {
  if (!event) {
    setText(elements.eventStatus, '準備中');
    setText(elements.eventTitle, 'UPoc 2026');
    return;
  }
  setText(elements.eventTitle, event.title || 'UPoc 2026');
  setText(elements.eventStatus, event.status === 'completed' ? '完成' : '開催中');
}

function renderLeaderboard(items) {
  if (!elements.leaderboard) {
    return;
  }
  elements.leaderboard.innerHTML = '';
  if (!items || items.length === 0) {
    const empty = document.createElement('li');
    empty.textContent = 'まだランキングがありません';
    elements.leaderboard.appendChild(empty);
    return;
  }
  items.forEach((entry, index) => {
    const li = document.createElement('li');
    li.innerHTML = `<span>#${index + 1} ${entry.nickname}</span><span>${entry.count}本</span>`;
    elements.leaderboard.appendChild(li);
  });
}

function renderColorStats(items) {
  if (!elements.colorStats) {
    return;
  }
  elements.colorStats.innerHTML = '';
  if (!items || items.length === 0) {
    return;
  }
  items.slice(0, 8).forEach((stat) => {
    const chip = document.createElement('div');
    chip.className = 'color-chip';
    const dot = document.createElement('span');
    dot.style.background = stat.hex;
    const text = document.createElement('span');
    const ratio = stat.ratio ? Math.round(stat.ratio * 100) : 0;
    text.textContent = `${stat.label} ${stat.count}本 (${ratio}%)`;
    chip.appendChild(dot);
    chip.appendChild(text);
    elements.colorStats.appendChild(chip);
  });
}

function renderSuggestions(data) {
  if (!data) {
    return;
  }
  if (elements.suggestionSummary) {
    elements.suggestionSummary.textContent = data.summary || '分析中...';
  }
  if (elements.suggestionThemes) {
    elements.suggestionThemes.innerHTML = '';
    (data.suggestedThemes || []).forEach((theme) => {
      const li = document.createElement('li');
      li.textContent = theme;
      elements.suggestionThemes.appendChild(li);
    });
  }
  if (elements.suggestionPalette) {
    elements.suggestionPalette.innerHTML = '';
    (data.palette || []).forEach((color) => {
      const swatch = document.createElement('div');
      swatch.className = 'swatch';
      swatch.style.background = color.hex;
      elements.suggestionPalette.appendChild(swatch);
    });
  }
}

function renderThemes(themes) {
  if (!elements.themeVotes) {
    return;
  }
  elements.themeVotes.innerHTML = '';
  (themes || []).forEach((theme) => {
    const card = document.createElement('div');
    card.className = 'theme-vote-card';
    const info = document.createElement('div');
    const title = document.createElement('strong');
    title.textContent = theme.title;
    const desc = document.createElement('div');
    desc.textContent = theme.description;
    desc.className = 'theme-description';
    info.appendChild(title);
    info.appendChild(desc);
    const action = document.createElement('div');
    const count = document.createElement('div');
    count.textContent = `${theme.votes}票`;
    count.className = 'muted';
    const button = document.createElement('button');
    button.className = 'secondary';
    button.textContent = '投票する';
    button.addEventListener('click', () => voteTheme(theme.id));
    action.appendChild(count);
    action.appendChild(button);
    card.appendChild(info);
    card.appendChild(action);
    elements.themeVotes.appendChild(card);
  });
}

function showToast(message, variant = 'default') {
  if (!elements.toastContainer) {
    return;
  }
  const toast = document.createElement('div');
  toast.className = `toast ${variant}`;
  toast.textContent = message;
  elements.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 3000);
}

function setActiveCheckin(token, nickname) {
  activeCheckinToken = token;
  setText(elements.activeCheckinToken, token || '未設定');
  if (elements.participantBadge) {
    elements.participantBadge.textContent = token
      ? `${nickname || '参加者'} さん参加中`
      : 'まだ参加していません';
  }
}

function buildQrUrl(url) {
  const encoded = encodeURIComponent(url);
  return `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encoded}`;
}

function enqueueAnimation(cap) {
  animationQueue.push(cap);
  if (!animating) {
    playNextAnimation();
  }
}

function playNextAnimation() {
  if (animationQueue.length === 0 || !overlayCtx) {
    animating = false;
    return;
  }
  animating = true;
  const cap = animationQueue.shift();
  const targetX = cap.x * pixelSize + pixelSize / 2;
  const targetY = cap.y * pixelSize + pixelSize / 2;
  const startY = -pixelSize;
  const duration = 600;
  const start = performance.now();

  function animateFrame(now) {
    const progress = Math.min((now - start) / duration, 1);
    const currentY = startY + (targetY - startY) * progress;
    overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
    overlayCtx.beginPath();
    overlayCtx.fillStyle = cap.color.hex;
    overlayCtx.arc(targetX, currentY, pixelSize / 2, 0, Math.PI * 2);
    overlayCtx.fill();
    if (progress < 1) {
      requestAnimationFrame(animateFrame);
    } else {
      overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
      drawCap(cap);
      updateLatest(cap);
      animating = false;
      playNextAnimation();
    }
  }

  requestAnimationFrame(animateFrame);
}

function applyState(state) {
  if (!state) {
    return;
  }
  updateCanvasSize(state.width, state.height);
  totalPixels = state.total || totalPixels;
  caps = state.caps || [];
  capsByIndex = new Map(caps.map((cap) => [cap.index, cap]));
  drawAllCaps();
  updateStats(state.progress, state.remaining, state.total);
  renderLeaderboard(state.leaderboard || []);
  renderColorStats(state.colorStats || []);
  renderSuggestions(state.suggestions);
  renderThemes(state.themes || []);
  renderEvent(state.event);
}

async function submitCap() {
  const nicknameInput = document.getElementById('nickname');
  const colorInput = document.getElementById('capColor');
  if (!colorInput) {
    return;
  }
  const nickname = nicknameInput ? nicknameInput.value.trim() : '';
  const color = colorInput.value;
  const response = await fetch('/api/caps', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      hex: color,
      nickname: nickname || (elements.checkinNickname ? elements.checkinNickname.value.trim() : ''),
      source: 'demo',
      checkin_token: activeCheckinToken || null,
    }),
  });
  if (!response.ok) {
    const error = await response.json();
    showToast(error.detail || '投入に失敗しました', 'error');
    return;
  }
  const data = await response.json();
  if (!wsConnected) {
    const cap = data.cap;
    caps.push(cap);
    capsByIndex.set(cap.index, cap);
    enqueueAnimation(cap);
    updateStats(data.progress, data.remaining, data.total);
    renderLeaderboard(data.leaderboard || []);
    renderColorStats(data.colorStats || []);
  }
  if (elements.participantBadge) {
    elements.participantBadge.textContent = `${nickname || '参加者'} さん参加中`;
  }
  showToast('キャップを投入しました', 'success');
}

async function voteTheme(themeId) {
  const safeThemeId = encodeURIComponent(themeId);
  const response = await fetch(`/api/themes/${safeThemeId}/vote`, { method: 'POST' });
  if (!response.ok) {
    return;
  }
  const data = await response.json();
  renderThemes(data.themes || []);
  showToast('投票を受け付けました', 'success');
}

async function createCheckin() {
  const nickname = elements.checkinNickname ? elements.checkinNickname.value.trim() : '';
  try {
    const response = await fetch('/api/checkins', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nickname, source: 'qr' }),
    });
    if (!response.ok) {
      throw new Error('failed');
    }
    const data = await response.json();
    const token = data.token;
    const shareUrl = `${window.location.origin}/?checkin=${token}`;
    if (elements.checkinTokenLabel) {
      elements.checkinTokenLabel.textContent = token;
    }
    if (elements.checkinShareLink) {
      elements.checkinShareLink.href = shareUrl;
      elements.checkinShareLink.textContent = shareUrl;
    }
    if (elements.checkinQr) {
      elements.checkinQr.src = buildQrUrl(shareUrl);
    }
    if (elements.checkinTokenInput) {
      elements.checkinTokenInput.value = token;
    }
    if (elements.checkinStatus) {
      elements.checkinStatus.textContent = 'QRを表示しました。参加者に読み取ってもらってください。';
    }
    showToast('QRチェックインを発行しました', 'success');
  } catch (error) {
    const fallbackToken = `mock-${Math.floor(Math.random() * 9999)}`;
    const shareUrl = `${window.location.origin}/?checkin=${fallbackToken}`;
    if (elements.checkinTokenLabel) {
      elements.checkinTokenLabel.textContent = fallbackToken;
    }
    if (elements.checkinShareLink) {
      elements.checkinShareLink.href = shareUrl;
      elements.checkinShareLink.textContent = shareUrl;
    }
    if (elements.checkinQr) {
      elements.checkinQr.src = buildQrUrl(shareUrl);
    }
    if (elements.checkinStatus) {
      elements.checkinStatus.textContent = 'モックのQRを生成しました。';
    }
  }
}

async function confirmCheckin() {
  const token = elements.checkinTokenInput ? elements.checkinTokenInput.value.trim() : '';
  if (!token) {
    showToast('トークンを入力してください', 'error');
    return;
  }
  try {
    const response = await fetch(`/api/checkins/${encodeURIComponent(token)}/confirm`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error('failed');
    }
    const data = await response.json();
    setActiveCheckin(data.checkin.token, data.checkin.nickname);
    if (elements.checkinStatus) {
      elements.checkinStatus.textContent = 'チェックイン完了。キャップ投入が紐づきます。';
    }
    showToast('チェックインしました', 'success');
  } catch (error) {
    setActiveCheckin(token, 'モック参加者');
    if (elements.checkinStatus) {
      elements.checkinStatus.textContent = 'モックとしてチェックイン済み。';
    }
  }
}

async function copyCheckinLink() {
  const url = elements.checkinShareLink ? elements.checkinShareLink.href : '';
  if (!url || url === '#') {
    showToast('まずQRを発行してください', 'error');
    return;
  }
  try {
    await navigator.clipboard.writeText(url);
    showToast('リンクをコピーしました', 'success');
  } catch (error) {
    showToast('コピーに失敗しました', 'error');
  }
}

async function generateCertificate() {
  const indexInput = document.getElementById('capIndex');
  if (!indexInput) {
    return;
  }
  const indexValue = Number(indexInput.value);
  if (!indexValue) {
    showToast('投入番号を入力してください', 'error');
    return;
  }
  let cap = capsByIndex.get(indexValue);
  if (!cap) {
    try {
      const response = await fetch(`/api/caps/${indexValue}`);
      if (!response.ok) {
        throw new Error('missing');
      }
      cap = await response.json();
    } catch (error) {
      showToast('その番号のキャップが見つかりません', 'error');
      return;
    }
  }
  if (!artCanvas || !ctx) {
    showToast('ライブページで生成してください', 'error');
    return;
  }
  const shareCanvas = document.createElement('canvas');
  const padding = 90;
  shareCanvas.width = artCanvas.width;
  shareCanvas.height = artCanvas.height + padding;
  const sctx = shareCanvas.getContext('2d');
  sctx.fillStyle = '#ffffff';
  sctx.fillRect(0, 0, shareCanvas.width, shareCanvas.height);
  sctx.drawImage(artCanvas, 0, 0);
  sctx.strokeStyle = '#f0454b';
  sctx.lineWidth = 4;
  sctx.strokeRect(cap.x * pixelSize + 2, cap.y * pixelSize + 2, pixelSize - 4, pixelSize - 4);
  sctx.fillStyle = '#1b1b1f';
  sctx.font = '18px "Zen Kaku Gothic New", "M PLUS 1p", sans-serif';
  sctx.fillText(`あなたのキャップは第${cap.index}番 (${cap.color.label}) です`, 16, artCanvas.height + 40);
  sctx.fillStyle = '#6b7280';
  sctx.font = '14px "M PLUS 1p", sans-serif';
  sctx.fillText('みんなで完成させる調布リサイクルアート', 16, artCanvas.height + 65);
  const url = shareCanvas.toDataURL('image/png');
  const image = document.getElementById('certificateImage');
  const download = document.getElementById('downloadCertificate');
  if (image) {
    image.src = url;
  }
  if (download) {
    download.href = url;
  }
  showToast('証明書を生成しました', 'success');
}

function connectWebSocket() {
  if (!window.location.host) {
    return;
  }
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const socket = new WebSocket(`${protocol}://${window.location.host}/ws`);
  socket.addEventListener('open', () => {
    wsConnected = true;
  });
  socket.addEventListener('message', (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'state') {
      applyState(data.state);
      return;
    }
    if (data.type === 'cap_added') {
      const cap = data.cap;
      caps.push(cap);
      capsByIndex.set(cap.index, cap);
      enqueueAnimation(cap);
      updateStats(data.progress, data.remaining, data.total);
      renderLeaderboard(data.leaderboard || []);
      renderColorStats(data.colorStats || []);
      renderSuggestions(data.suggestions);
      if (data.event) {
        renderEvent(data.event);
      }
    }
    if (data.type === 'theme_voted') {
      renderThemes(data.themes || []);
    }
  });
  socket.addEventListener('close', () => {
    wsConnected = false;
    setTimeout(connectWebSocket, 2000);
  });
}

function highlightNav() {
  const page = document.body.dataset.page;
  document.querySelectorAll('.nav-link').forEach((link) => {
    if (link.dataset.page === page) {
      link.classList.add('is-active');
    } else {
      link.classList.remove('is-active');
    }
  });
}

function initCarousel() {
  document.querySelectorAll('[data-carousel]').forEach((carousel) => {
    const track = carousel.querySelector('.carousel-track');
    const cards = track ? Array.from(track.children) : [];
    if (!track || cards.length === 0) {
      return;
    }
    let index = 0;
    const controls = carousel.parentElement.querySelector('.carousel-controls');
    const prevButton = controls ? controls.querySelector('[data-carousel-prev]') : null;
    const nextButton = controls ? controls.querySelector('[data-carousel-next]') : null;

    function update(nextIndex) {
      index = (nextIndex + cards.length) % cards.length;
      const cardWidth = cards[0].getBoundingClientRect().width;
      const gap = parseFloat(getComputedStyle(track).gap || '16');
      const offset = index * (cardWidth + gap);
      animate(track, {
        x: -offset,
        duration: 500,
        ease: 'outQuad',
      });
    }

    if (prevButton) {
      prevButton.addEventListener('click', () => update(index - 1));
    }
    if (nextButton) {
      nextButton.addEventListener('click', () => update(index + 1));
    }

    window.addEventListener('resize', () => update(index));
  });
}

function initAnimations() {
  createScope({
    mediaQueries: {
      reduceMotion: '(prefers-reduced-motion: reduce)',
    },
  }).add((self) => {
    if (self.matches.reduceMotion) {
      return;
    }
    animate('.card', {
      opacity: [0, 1],
      y: [16, 0],
      delay: (el, i) => i * 80,
      duration: 650,
      ease: 'outQuad',
    });
    animate('.site-header', {
      opacity: [0, 1],
      y: [-12, 0],
      duration: 500,
      ease: 'outQuad',
    });
  });
}

async function init() {
  highlightNav();
  initCarousel();
  initAnimations();
  try {
    const response = await fetch('/api/state');
    if (!response.ok) {
      throw new Error('fallback');
    }
    const state = await response.json();
    applyState(state);
  } catch (error) {
    applyState(mockState);
  }
  connectWebSocket();
}

window.addEventListener('resize', () => {
  updateCanvasSize(gridWidth, gridHeight);
  drawAllCaps();
});

window.addEventListener('DOMContentLoaded', () => {
  const submitButton = document.getElementById('submitCap');
  if (submitButton) {
    submitButton.addEventListener('click', submitCap);
  }
  const certButton = document.getElementById('generateCertificate');
  if (certButton) {
    certButton.addEventListener('click', generateCertificate);
  }
  const checkinButton = document.getElementById('generateCheckin');
  if (checkinButton) {
    checkinButton.addEventListener('click', createCheckin);
  }
  const confirmButton = document.getElementById('confirmCheckin');
  if (confirmButton) {
    confirmButton.addEventListener('click', confirmCheckin);
  }
  const copyButton = document.getElementById('copyCheckinLink');
  if (copyButton) {
    copyButton.addEventListener('click', copyCheckinLink);
  }
  const params = new URLSearchParams(window.location.search);
  const checkinParam = params.get('checkin');
  if (checkinParam && elements.checkinTokenInput) {
    elements.checkinTokenInput.value = checkinParam;
    confirmCheckin();
  }
  init();
});
