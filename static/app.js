// ─── 火星基地 · 前端交互逻辑 ───

let state = null;
let animTimer = null;
let animating = false;
let paused = false;
let compareMode = false;
let storyMode = false;
let materials = [];

// ─── Init ───
async function init() {
  const res = await fetch('/api/state');
  state = await res.json();
  materials = state.materials;
  buildLayerSelects();
  buildLegend();
  initPlot();
  updateAll();
  bindEvents();
}

function buildLayerSelects() {
  const opts = ['<option value="">(空)</option>'];
  materials.forEach(m => opts.push(`<option value="${m.key}">${m.name}</option>`));
  document.querySelectorAll('.layer-select').forEach(sel => {
    sel.innerHTML = opts.join('');
  });
}

function buildLegend() {
  document.getElementById('legend').innerHTML = materials
    .map(m => `<div class="legend-item"><div class="legend-swatch" style="background:${m.color}"></div>${m.name} α=${m.alpha} k=${m.k}</div>`)
    .join('');
}

// ─── Plotly ───
let heatmapLayout, profileLayout, compareLayout;

function initPlot() {
  heatmapLayout = {
    paper_bgcolor: '#161b22', plot_bgcolor: '#161b22',
    font: { color: '#e6edf3', size: 11 },
    margin: { l: 50, r: 10, t: 10, b: 40 },
    xaxis: { title: '水平位置', showgrid: false, zeroline: false },
    yaxis: { title: '垂直位置', showgrid: false, zeroline: false, autorange: 'reversed' },
    coloraxis: {
      colorscale: [[0,'#1a1a2e'],[0.2,'#16213e'],[0.4,'#0f3460'],[0.6,'#e94560'],[0.8,'#ff9f45'],[1,'#fcbf49']],
      cmin: -100, cmax: 100, colorbar: { title: '°C', thickness: 15 }
    },
    shapes: [
      { type:'line', x0:16, x1:16, y0:0, y1:49, line:{ color:'white', dash:'dot', width:1 } },
      { type:'line', x0:56, x1:56, y0:0, y1:49, line:{ color:'white', dash:'dot', width:1 } },
    ]
  };

  profileLayout = {
    paper_bgcolor: '#161b22', plot_bgcolor: '#161b22',
    font: { color: '#e6edf3', size: 11 },
    margin: { l: 50, r: 10, t: 10, b: 40 },
    xaxis: { title: '水平位置', range: [0, 79] },
    yaxis: { title: '温度 (°C)', range: [-100, 100] },
    shapes: [{ type:'line', x0:0, x1:79, y0:20, y1:20, line:{ color:'#3fb950', dash:'dot', width:1 } }]
  };

  compareLayout = JSON.parse(JSON.stringify(heatmapLayout));
  compareLayout.shapes = [];
  compareLayout.annotations = [
    { text:'方案A: 基础保温', x:0.25, y:1.05, xref:'paper', font:{ color:'#58a6ff', size:13, family:'Microsoft YaHei' }, showarrow:false },
    { text:'方案B: 优化设计', x:0.75, y:1.05, xref:'paper', font:{ color:'#3fb950', size:13, family:'Microsoft YaHei' }, showarrow:false },
  ];

  updateHeatmap(state.T, state.profile, state.metrics);
}

function updateHeatmap(T, profile, metrics) {
  const traceHeat = { type:'heatmap', z:T, colorscale: heatmapLayout.coloraxis.colorscale, zmin:-100, zmax:100, showscale:true, colorbar:heatmapLayout.coloraxis.colorbar };
  Plotly.react('heatmap', [traceHeat], heatmapLayout);
  const traceProf = { type:'scatter', mode:'lines', line:{ color:'#58a6ff', width:2 }, x:Array.from({length:profile.length},(_,i)=>i), y:profile };
  Plotly.react('profile-plot', [traceProf], profileLayout);
}

function updateCompare(Ta, Tb, profileA, profileB) {
  const ta = { type:'heatmap', z:Ta, colorscale: heatmapLayout.coloraxis.colorscale, zmin:-100, zmax:100, showscale:false, xaxis:'x', yaxis:'y' };
  const tb = { type:'heatmap', z:Tb, colorscale: heatmapLayout.coloraxis.colorscale, zmin:-100, zmax:100, showscale:true, colorbar:heatmapLayout.coloraxis.colorbar, xaxis:'x2', yaxis:'y2' };
  const cl = {
    grid: { rows:1, columns:2, subplots:[['xy','xy2']], roworder:'top_to_bottom' },
    paper_bgcolor: '#161b22', plot_bgcolor: '#161b22',
    font: { color: '#e6edf3', size: 11 },
    margin: { l:50, r:10, t:30, b:40 },
    xaxis: { title:'A', showgrid:false, zeroline:false, domain:[0, 0.48] },
    yaxis: { title:'垂直', showgrid:false, zeroline:false, autorange:'reversed', domain:[0, 1] },
    xaxis2: { title:'B', showgrid:false, zeroline:false, domain:[0.52, 1] },
    yaxis2: { showgrid:false, zeroline:false, autorange:'reversed', domain:[0, 1] },
    annotations: [
      { text:'方案A: 基础保温', x:0.24, y:1.05, xref:'paper', font:{ color:'#58a6ff', size:12 }, showarrow:false },
      { text:'方案B: 优化设计', x:0.76, y:1.05, xref:'paper', font:{ color:'#3fb950', size:12 }, showarrow:false },
    ]
  };
  Plotly.react('heatmap', [ta, tb], cl);
}

// ─── Update All ───
function updateAll() {
  updateHeatmap(state.T, state.profile, state.metrics);
  updateMetrics(state.metrics);
}

function updateMetrics(m) {
  document.getElementById('m-room').textContent = m.room_avg.toFixed(1) + '°C';
  document.getElementById('m-rvalue').textContent = m.R_value.toFixed(3) + ' m²K/W';
  document.getElementById('m-flux').textContent = m.heat_flux.toFixed(1) + ' W/m²';
  document.getElementById('m-dt').textContent = m.delta_T.toFixed(1) + '°C';
  document.getElementById('m-cost').textContent = '$' + m.cost.toFixed(1);
  document.getElementById('m-weight').textContent = m.weight.toFixed(1) + ' kg';
  document.getElementById('m-std').textContent = '±' + m.room_std.toFixed(1) + '°C';
  document.getElementById('m-wtemp').textContent = m.wall_avg.toFixed(1) + '°C';
  document.getElementById('frame-display').textContent = '步数: ' + m.frame;
}

// ─── Animation ───
async function animStep() {
  if (!animating || paused) return;
  try {
    if (compareMode) {
      const r = await fetch('/api/compare/step', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({n:5}) });
      const d = await r.json();
      updateCompare(d.a.T, d.b.T, d.a.profile, d.b.profile);
      updateMetrics(d.a.metrics);
    } else if (storyMode) {
      const r = await fetch('/api/story/next', { method:'POST' });
      const d = await r.json();
      state = d;
      if (d.done) { stopStory(); return; }
      updateHeatmap(d.T, d.profile, d.metrics);
      updateMetrics(d.metrics);
      document.getElementById('story-info').innerHTML =
        `<div class="story-name">${d.name}</div><div class="story-progress">场景 ${d.scene+1}/${d.total} · 帧 ${d.scene_frame}/${d.scene_frames}</div>`;
    } else {
      const r = await fetch('/api/step', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({n:5}) });
      state = await r.json();
      updateAll();
    }
  } catch(e) { console.error(e); }
  animTimer = setTimeout(animStep, 80);
}

function startAnim() {
  animating = true; paused = false;
  setStatus('running');
  document.getElementById('btn-start').disabled = true;
  document.getElementById('btn-pause').disabled = false;
  animStep();
}

function pauseAnim() {
  if (!animating) return;
  paused = !paused;
  setStatus(paused ? 'paused' : 'running');
  document.getElementById('btn-pause').textContent = paused ? '▶ 继续' : '⏸ 暂停';
  if (!paused) animStep();
}

function stopAnim() {
  animating = false; paused = false; clearTimeout(animTimer);
  compareMode = false;
  document.getElementById('compare-heatmap').classList.add('hidden');
  document.getElementById('heatmap').classList.remove('hidden');
  setStatus('ready');
  document.getElementById('btn-start').disabled = false;
  document.getElementById('btn-pause').disabled = true;
  document.getElementById('btn-pause').textContent = '⏸ 暂停';
}

// ─── Story ───
async function startStory() {
  stopAnim(); storyMode = true; animating = true;
  const r = await fetch('/api/story/start', { method:'POST' });
  state = await r.json();
  updateAll();
  document.getElementById('story-info').classList.remove('hidden');
  setStatus('story');
  document.getElementById('btn-start').disabled = true;
  document.getElementById('btn-pause').disabled = false;
  animStep();
}

function stopStory() {
  storyMode = false; stopAnim();
  document.getElementById('story-info').classList.add('hidden');
}

// ─── Compare ───
async function startCompare() {
  stopAnim(); compareMode = true; animating = true;
  const r = await fetch('/api/compare/start', { method:'POST' });
  const d = await r.json();
  updateCompare(d.a.T, d.b.T, d.a.profile, d.b.profile);
  updateMetrics(d.a.metrics);
  setStatus('compare');
  document.getElementById('btn-start').disabled = true;
  document.getElementById('btn-pause').disabled = false;
  animStep();
}

// ─── Status ───
function setStatus(s) {
  const b = document.getElementById('status-badge');
  b.className = 'badge';
  const map = { ready:'badge-ready', running:'badge-running', paused:'badge-paused', story:'badge-story', compare:'badge-compare' };
  b.classList.add(map[s] || 'badge-ready');
  b.textContent = { ready:'就绪', running:'仿真中', paused:'已暂停', story:'故事模式', compare:'对比模式' }[s] || s;
}

// ─── Events ───
function bindEvents() {
  document.getElementById('btn-start').onclick = startAnim;
  document.getElementById('btn-pause').onclick = pauseAnim;
  document.getElementById('btn-reset').onclick = async () => {
    stopAnim(); stopStory();
    const r = await fetch('/api/reset', { method:'POST' });
    state = await r.json(); updateAll();
  };

  document.getElementById('btn-apply').onclick = async () => {
    const layers = [];
    document.querySelectorAll('.layer-select').forEach(s => { if (s.value) layers.push(s.value); });
    const r = await fetch('/api/design', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({layers}) });
    state = await r.json(); updateAll();
  };

  document.querySelectorAll('.btn-preset').forEach(b => {
    b.onclick = async () => {
      const r = await fetch('/api/preset', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:b.dataset.preset}) });
      state = await r.json(); updateAll();
    };
  });

  document.getElementById('btn-defect').onclick = async () => {
    const t = document.getElementById('defect-type').value;
    if (!t) return;
    const r = await fetch('/api/defect', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({type:t, y:20, x:25, h:5, w:10}) });
    state = await r.json(); updateAll();
  };

  document.getElementById('btn-story').onclick = startStory;
  document.getElementById('btn-compare').onclick = startCompare;

  // Sliders
  ['room-temp','mars-min','mars-max'].forEach(id => {
    document.getElementById(id).oninput = async function() {
      const rt = parseFloat(document.getElementById('room-temp').value);
      const mn = parseFloat(document.getElementById('mars-min').value);
      const mx = parseFloat(document.getElementById('mars-max').value);
      document.getElementById('room-temp-val').textContent = rt + '°C';
      document.getElementById('mars-min-val').textContent = mn + '°C';
      document.getElementById('mars-max-val').textContent = mx + '°C';
      await fetch('/api/params', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({room_temp:rt, mars_min:mn, mars_max:mx}) });
    };
  });
}

// ─── Start ───
init();
