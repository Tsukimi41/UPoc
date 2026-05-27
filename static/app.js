const artCanvas = document.getElementById('artCanvas');
const overlayCanvas = document.getElementById('overlayCanvas');
const ctx = artCanvas.getContext('2d');
const overlayCtx = overlayCanvas.getContext('2d');

let gridWidth = 40;
let gridHeight = 25;
let totalPixels = 1000;
let pixelSize = 16;
let caps = [];
let capsByIndex = new Map();
let animationQueue = [];
let animating = false;

const remainingCount = document.getElementById('remainingCount');
const progressCount = document.getElementById('progressCount');
const totalCount = document.getElementById('totalCount');
const latestMessage = document.getElementById('latestMessage');
const leaderboard = document.getElementById('leaderboard');
const colorStats = document.getElementById('colorStats');
const suggestionSummary = document.getElementById('suggestionSummary');
const suggestionThemes = document.getElementById('suggestionThemes');
const themeVotes = document.getElementById('themeVotes');

function updateCanvasSize(width, height) {
  gridWidth = width;
  gridHeight = height;
  pixelSize = Math.floor(640 / gridWidth);
  artCanvas.width = pixelSize * gridWidth;
  artCanvas.height = pixelSize * gridHeight;
  overlayCanvas.width = artCanvas.width;
  overlayCanvas.height = artCanvas.height;
}

function clearCanvas() {
  ctx.fillStyle = '#f8fafc';
  ctx.fillRect(0, 0, artCanvas.width, artCanvas.height);
}

function drawCap(cap) {
  ctx.fillStyle = cap.color.hex;
  ctx.fillRect(cap.x * pixelSize, cap.y * pixelSize, pixelSize, pixelSize);
}

function drawAllCaps() {
  clearCanvas();
  caps.forEach(drawCap);
}

function updateStats(progress, remaining, total) {
  progressCount.textContent = progress;
  remainingCount.textContent = remaining;
  totalCount.textContent = total;
}

function updateLatest(cap) {
  latestMessage.textContent = `${cap.color.label} / 第${cap.index}番 (${cap.nickname})`;
}

function renderLeaderboard(items) {
  leaderboard.innerHTML = '';
  if (!items || items.length === 0) {
    const empty = document.createElement('li');
    empty.textContent = 'まだランキングがありません';
    leaderboard.appendChild(empty);
    return;
  }
  items.forEach((entry) => {
    const li = document.createElement('li');
    li.textContent = `${entry.nickname} - ${entry.count}本`;
    leaderboard.appendChild(li);
  });
}

function renderColorStats(items) {
  colorStats.innerHTML = '';
  if (!items || items.length === 0) {
    return;
  }
  items.slice(0, 8).forEach((stat) => {
    const chip = document.createElement('div');
    chip.className = 'color-chip';
    const dot = document.createElement('span');
    dot.style.background = stat.hex;
    const text = document.createElement('span');
    text.textContent = `${stat.label} ${stat.count}本`;
    chip.appendChild(dot);
    chip.appendChild(text);
    colorStats.appendChild(chip);
  });
}

function renderSuggestions(data) {
  if (!data) {
    return;
  }
  suggestionSummary.textContent = data.summary || '分析中...';
  suggestionThemes.innerHTML = '';
  (data.suggestedThemes || []).forEach((theme) => {
    const li = document.createElement('li');
    li.textContent = theme;
    suggestionThemes.appendChild(li);
  });
}

function renderThemes(themes) {
  themeVotes.innerHTML = '';
  (themes || []).forEach((theme) => {
    const card = document.createElement('div');
    card.className = 'theme-card';
    const info = document.createElement('div');
    const title = document.createElement('strong');
    title.textContent = theme.title;
    const desc = document.createElement('div');
    desc.textContent = theme.description;
    desc.style.fontSize = '12px';
    desc.style.color = '#6b7280';
    info.appendChild(title);
    info.appendChild(desc);
    const action = document.createElement('div');
    const count = document.createElement('div');
    count.textContent = `${theme.votes}票`;
    count.style.fontSize = '12px';
    count.style.color = '#6b7280';
    const button = document.createElement('button');
    button.className = 'secondary';
    button.textContent = '投票する';
    button.addEventListener('click', () => voteTheme(theme.id));
    action.appendChild(count);
    action.appendChild(button);
    card.appendChild(info);
    card.appendChild(action);
    themeVotes.appendChild(card);
  });
}

function enqueueAnimation(cap) {
  animationQueue.push(cap);
  if (!animating) {
    playNextAnimation();
  }
}

function playNextAnimation() {
  if (animationQueue.length === 0) {
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

  function animate(now) {
    const progress = Math.min((now - start) / duration, 1);
    const currentY = startY + (targetY - startY) * progress;
    overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
    overlayCtx.beginPath();
    overlayCtx.fillStyle = cap.color.hex;
    overlayCtx.arc(targetX, currentY, pixelSize / 2, 0, Math.PI * 2);
    overlayCtx.fill();
    if (progress < 1) {
      requestAnimationFrame(animate);
    } else {
      overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
      drawCap(cap);
      updateLatest(cap);
      animating = false;
      playNextAnimation();
    }
  }

  requestAnimationFrame(animate);
}

function applyState(state) {
  if (!state) {
    return;
  }
  updateCanvasSize(state.width, state.height);
  caps = state.caps || [];
  capsByIndex = new Map(caps.map((cap) => [cap.index, cap]));
  drawAllCaps();
  updateStats(state.progress, state.remaining, state.total);
  renderLeaderboard(state.leaderboard || []);
  renderColorStats(state.colorStats || []);
  renderSuggestions(state.suggestions);
  renderThemes(state.themes || []);
}

async function submitCap() {
  const nickname = document.getElementById('nickname').value.trim();
  const color = document.getElementById('capColor').value;
  const response = await fetch('/api/caps', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ hex: color, nickname, source: 'demo' }),
  });
  if (!response.ok) {
    const error = await response.json();
    alert(error.detail || '投入に失敗しました');
    return;
  }
  const data = await response.json();
  if (!window.wsConnected) {
    const cap = data.cap;
    caps.push(cap);
    capsByIndex.set(cap.index, cap);
    enqueueAnimation(cap);
    updateStats(data.progress, data.remaining, data.total);
    renderLeaderboard(data.leaderboard || []);
    renderColorStats(data.colorStats || []);
  }
}

async function voteTheme(themeId) {
  const response = await fetch(`/api/themes/${themeId}/vote`, { method: 'POST' });
  if (!response.ok) {
    return;
  }
  const data = await response.json();
  renderThemes(data.themes || []);
}

async function generateCertificate() {
  const indexValue = Number(document.getElementById('capIndex').value);
  if (!indexValue) {
    alert('投入番号を入力してください');
    return;
  }
  let cap = capsByIndex.get(indexValue);
  if (!cap) {
    const response = await fetch(`/api/caps/${indexValue}`);
    if (!response.ok) {
      alert('その番号のキャップが見つかりません');
      return;
    }
    cap = await response.json();
  }
  const shareCanvas = document.createElement('canvas');
  const padding = 90;
  shareCanvas.width = artCanvas.width;
  shareCanvas.height = artCanvas.height + padding;
  const sctx = shareCanvas.getContext('2d');
  sctx.fillStyle = '#ffffff';
  sctx.fillRect(0, 0, shareCanvas.width, shareCanvas.height);
  sctx.drawImage(artCanvas, 0, 0);
  sctx.strokeStyle = '#ff9800';
  sctx.lineWidth = 4;
  sctx.strokeRect(cap.x * pixelSize + 2, cap.y * pixelSize + 2, pixelSize - 4, pixelSize - 4);
  sctx.fillStyle = '#1f2937';
  sctx.font = '18px sans-serif';
  sctx.fillText(`あなたのキャップは第${cap.index}番 (${cap.color.label}) です`, 16, artCanvas.height + 40);
  sctx.fillStyle = '#6b7280';
  sctx.font = '14px sans-serif';
  sctx.fillText('みんなで完成させる調布リサイクルアート', 16, artCanvas.height + 65);
  const url = shareCanvas.toDataURL('image/png');
  const image = document.getElementById('certificateImage');
  image.src = url;
  const download = document.getElementById('downloadCertificate');
  download.href = url;
}

function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const socket = new WebSocket(`${protocol}://${window.location.host}/ws`);
  socket.addEventListener('open', () => {
    window.wsConnected = true;
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
    }
    if (data.type === 'theme_voted') {
      renderThemes(data.themes || []);
    }
  });
  socket.addEventListener('close', () => {
    window.wsConnected = false;
    setTimeout(connectWebSocket, 2000);
  });
}

async function init() {
  clearCanvas();
  try {
    const response = await fetch('/api/state');
    const state = await response.json();
    applyState(state);
  } catch (error) {
    console.error(error);
  }
  connectWebSocket();
}

window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('submitCap').addEventListener('click', submitCap);
  document.getElementById('generateCertificate').addEventListener('click', generateCertificate);
  init();
});
