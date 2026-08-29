'use strict';

const $ = (s) => document.querySelector(s);
const el = (tag, cls, txt) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (txt != null) n.textContent = txt;
  return n;
};

const CAT_ORDER = ['letters', 'numbers', 'punct', 'basic', 'nav', 'fkeys',
  'mods', 'layers', 'keypad', 'media', 'mouse', 'app', 'system', 'intl', 'special'];
const CAT_LABEL = {
  letters: 'Letters', numbers: 'Numbers', punct: 'Punctuation', basic: 'Basic',
  nav: 'Navigation', fkeys: 'F-keys', mods: 'Modifiers', layers: 'Layers',
  keypad: 'Keypad', media: 'Media', mouse: 'Mouse', app: 'Apps',
  system: 'System', intl: 'International', special: 'Special',
};

let S = null;          // server state
let layer = 0;         // selected layer
let selected = null;   // key index being remapped
let reviewAll = false;
let cat = 'letters';

/* ---------------------------------------------------------------- fetch */
async function api(path, opts) {
  const r = await fetch(path, opts);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.error || `${r.status} ${r.statusText}`);
  return body;
}

async function load(path = '/api/state', opts) {
  try {
    S = await api(path, opts);
  } catch (e) {
    S = { ok: false, error: e.message };
  }
  render();
}

/* ---------------------------------------------------------------- toast */
let toastTimer;
function toast(msg, bad) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.toggle('bad', !!bad);
  t.classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add('hidden'), bad ? 5000 : 1800);
}

/* --------------------------------------------------------------- render */
function render() {
  const banner = $('#banner');
  if (!S || !S.ok) {
    $('#devline').textContent = 'not connected';
    banner.classList.remove('hidden');
    banner.textContent = (S && S.error ? S.error : 'unknown error') +
      (S && S.hint ? '\n\n' + S.hint : '');
    $('#layers').innerHTML = '';
    $('#board-wrap').innerHTML = '';
    return;
  }
  banner.classList.add('hidden');

  const d = S.device || {};
  const bits = [];
  if (S.demo) bits.push('DEMO — no hardware');
  else {
    bits.push(`${d.name || 'keyboard'} on ${d.path}`);
    bits.push(`VIA protocol 0x${(S.protocol || 0).toString(16).toUpperCase().padStart(4, '0')}`);
    if (S.vial) bits.push(`Vial v${S.vial_protocol}`);
    bits.push(`${S.layers} layers`);
    bits.push(`${S.era} keycodes${S.era_forced ? ' (forced)' : ''}`);
  }
  $('#devline').textContent = bits.join('  ·  ');
  $('#era').value = S.era_forced ? S.era : 'auto';

  renderLayers();
  renderBoards();
}

function renderLayers() {
  const nav = $('#layers');
  nav.innerHTML = '';
  if (reviewAll) {
    nav.appendChild(el('span', 'sub', 'Reviewing every layer — click any key to remap it.'));
    return;
  }
  for (let i = 0; i < S.layers; i++) {
    const b = el('button', i === layer ? 'on' : '', `Layer ${i}`);
    b.onclick = () => { layer = i; render(); };
    nav.appendChild(b);
  }
  const used = S.keymap[layer].filter((e) => e.code !== 0 && e.code !== 1).length;
  nav.appendChild(el('span', 'sub', `${used} of 42 keys assigned`));
}

function renderBoards() {
  const wrap = $('#board-wrap');
  wrap.innerHTML = '';
  if (reviewAll) {
    for (let i = 0; i < S.layers; i++) {
      const used = S.keymap[i].filter((e) => e.code !== 0 && e.code !== 1).length;
      wrap.appendChild(el('div', 'board-title', `Layer ${i} — ${used} assigned`));
      wrap.appendChild(board(i, 42));
    }
  } else {
    wrap.appendChild(board(layer, 62));
  }
}

function board(li, unit) {
  const size = unit - 6;
  const b = el('div', 'board');
  let maxX = 0, maxY = 0;
  S.keys.forEach((k, idx) => {
    maxX = Math.max(maxX, k.x); maxY = Math.max(maxY, k.y);
    const e = S.keymap[li][idx];
    const n = el('button', `key k-${e.cat}`);
    n.style.left = `${k.x * unit}px`;
    n.style.top = `${k.y * unit}px`;
    n.style.width = n.style.height = `${size}px`;
    n.style.fontSize = `${Math.max(9, Math.round(unit * 0.20))}px`;
    n.title = `${k.id}  (matrix r${k.row} c${k.col}, ${k.finger})\n` +
              `${e.name}  =  0x${e.code.toString(16).toUpperCase().padStart(4, '0')}`;
    const parts = String(e.label).split('\n');
    if (parts.length > 1) {
      const box = el('span');
      box.appendChild(el('span', 'l2', parts[0]));
      box.appendChild(document.createElement('br'));
      box.appendChild(el('span', 'l1', parts[1] || '·'));
      n.appendChild(box);
    } else {
      n.appendChild(el('span', 'l1', parts[0] || ' '));
    }
    if (selected === idx && layer === li) n.classList.add('sel');
    n.onclick = () => openPicker(idx, li);
    b.appendChild(n);
  });
  b.style.width = `${maxX * unit + size}px`;
  b.style.height = `${maxY * unit + size + 4}px`;
  return b;
}

/* --------------------------------------------------------------- picker */
function openPicker(idx, li) {
  selected = idx;
  layer = li;
  const k = S.keys[idx];
  const e = S.keymap[li][idx];
  $('#pick-title').textContent = `Layer ${li} · ${k.id}`;
  $('#pick-sub').textContent =
    `${k.half} ${k.finger}, matrix r${k.row} c${k.col} — currently ` +
    `${e.name} (0x${e.code.toString(16).toUpperCase().padStart(4, '0')})`;
  $('#picker').classList.remove('hidden');
  $('#search').value = '';
  $('#search').focus();
  $('#raw-hex').value = '0x' + e.code.toString(16).toUpperCase().padStart(4, '0');
  updateRawPreview();
  renderCats();
  renderGrid();
  render();
}

function closePicker() {
  $('#picker').classList.add('hidden');
  selected = null;
  render();
}

function renderCats() {
  const c = $('#cats');
  c.innerHTML = '';
  const groups = S.catalog.groups;
  const cats = CAT_ORDER.filter((x) => groups[x] && groups[x].length);
  if (!cats.includes(cat)) cat = cats[0];
  cats.forEach((name) => {
    const b = el('button', name === cat ? 'on' : '', CAT_LABEL[name] || name);
    b.onclick = () => { cat = name; $('#search').value = ''; renderCats(); renderGrid(); };
    c.appendChild(b);
  });
}

function renderGrid() {
  const g = $('#grid');
  g.innerHTML = '';
  const q = $('#search').value.trim().toLowerCase();
  let items;
  if (q) {
    items = [];
    Object.values(S.catalog.groups).forEach((list) => items.push(...list));
    items = items.filter((i) =>
      i.name.toLowerCase().includes(q) || i.label.toLowerCase().includes(q));
  } else {
    items = S.catalog.groups[cat] || [];
  }
  if (!items.length) {
    g.appendChild(el('div', 'empty', 'nothing matches that search'));
    return;
  }
  items.slice(0, 400).forEach((i) => {
    const b = el('button', `k-${i.cat}`);
    b.appendChild(el('span', '', i.label.replace('\n', ' ') || '␀'));
    b.appendChild(el('span', 'nm', i.name));
    b.title = `${i.name} = 0x${i.code.toString(16).toUpperCase().padStart(4, '0')}`;
    b.onclick = () => assign(i.code);
    g.appendChild(b);
  });
}

async function assign(code) {
  if (selected == null) return;
  const idx = selected, li = layer;
  try {
    const r = await api('/api/key', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ layer: li, index: idx, code }),
    });
    S.keymap[li][idx] = r.entry;
    if (!r.matched) {
      toast(`keyboard stored ${r.entry.name} instead — firmware may not support that keycode`, true);
    } else {
      toast(`${S.keys[idx].id} → ${r.entry.name}`);
    }
    closePicker();
  } catch (e) {
    toast(e.message, true);
  }
}

/* -------------------------------------------------------------- builders */
function fillBuilders() {
  const mods = S.catalog.mods;
  const mm = $('#mt-mod');
  mm.innerHTML = '';
  mods.forEach((m) => {
    const o = el('option', '', `${m.name} — ${m.desc}`);
    o.value = m.bits;
    mm.appendChild(o);
  });
  const ml = $('#mt-layer');
  ml.innerHTML = '';
  for (let i = 0; i < S.layers; i++) {
    const o = el('option', '', `Layer ${i}`);
    o.value = i;
    ml.appendChild(o);
  }
  const mk = $('#mt-key');
  mk.innerHTML = '';
  const basics = [];
  Object.entries(S.catalog.groups).forEach(([name, list]) => {
    if (name === 'layers') return;
    list.forEach((i) => { if (i.code <= 0xFF) basics.push(i); });
  });
  basics.sort((a, b) => a.code - b.code);
  basics.forEach((i) => {
    const o = el('option', '', `${i.name}${i.label ? ' — ' + i.label : ''}`);
    o.value = i.code;
    mk.appendChild(o);
  });
  mk.value = 0x2C;                       // KC_SPC: the usual tap-hold target
  updateMtPreview();
}

function mtCode() {
  const kc = parseInt($('#mt-key').value, 10) & 0xFF;
  if ($('#mt-kind').value === 'mod') {
    const bits = parseInt($('#mt-mod').value, 10) & 0x1F;
    return S.catalog.qk_mod_tap | (bits << 8) | kc;
  }
  const l = parseInt($('#mt-layer').value, 10) & 0x0F;
  return S.catalog.qk_layer_tap | (l << 8) | kc;
}

function updateMtPreview() {
  const isMod = $('#mt-kind').value === 'mod';
  $('#mt-mod-wrap').classList.toggle('hidden', !isMod);
  $('#mt-layer-wrap').classList.toggle('hidden', isMod);
  const code = mtCode();
  $('#mt-preview').textContent =
    `0x${code.toString(16).toUpperCase().padStart(4, '0')} — hold for ` +
    (isMod ? $('#mt-mod').selectedOptions[0].textContent
           : $('#mt-layer').selectedOptions[0].textContent) +
    `, tap for ${$('#mt-key').selectedOptions[0].textContent}`;
}

function parseHex(s) {
  const v = parseInt(String(s).trim().replace(/^0x/i, ''), 16);
  return Number.isFinite(v) && v >= 0 && v <= 0xFFFF ? v : null;
}

function updateRawPreview() {
  const v = parseHex($('#raw-hex').value);
  $('#raw-preview').textContent = v == null ? 'enter 0x0000 – 0xFFFF' : `= ${v}`;
}

/* ----------------------------------------------------------------- wire */
function wire() {
  $('#pick-close').onclick = closePicker;
  $('#picker').onclick = (e) => { if (e.target.id === 'picker') closePicker(); };
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !$('#picker').classList.contains('hidden')) closePicker();
  });
  $('#search').oninput = renderGrid;

  $('#btn-view').onclick = () => {
    reviewAll = !reviewAll;
    $('#btn-view').textContent = reviewAll ? 'Edit one layer' : 'Review all layers';
    render();
  };
  $('#btn-reload').onclick = async () => {
    toast('re-reading the keyboard…');
    await load('/api/reload', { method: 'POST' });
    if (S.ok) { fillBuilders(); toast('reloaded from device'); }
  };
  $('#btn-export').onclick = () => { window.location = '/api/export'; };
  $('#btn-import').onclick = () => $('#file').click();
  $('#file').onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    try {
      const data = JSON.parse(await f.text());
      if (!Array.isArray(data.keymap)) throw new Error('file has no "keymap" array');
      if (!confirm(`Write ${data.keymap.length} layers from ${f.name} to the keyboard?`)) return;
      const r = await api('/api/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keymap: data.keymap }),
      });
      await load();
      toast(`imported — ${r.written} keys changed`);
    } catch (err) {
      toast(err.message, true);
    }
    e.target.value = '';
  };
  $('#btn-reset').onclick = async () => {
    if (!confirm('Reset every layer to the keymap compiled into the firmware?\n' +
                 'This discards all VIA changes on the keyboard.')) return;
    try {
      await api('/api/reset', { method: 'POST' });
      await load();
      toast('keymap reset to firmware defaults');
    } catch (e) { toast(e.message, true); }
  };
  $('#era').onchange = async (e) => {
    await load('/api/era', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ era: e.target.value === 'auto' ? null : e.target.value }),
    });
    if (S.ok) fillBuilders();
  };

  ['#mt-kind', '#mt-mod', '#mt-layer', '#mt-key'].forEach((s) => {
    $(s).onchange = updateMtPreview;
  });
  $('#mt-apply').onclick = () => assign(mtCode());
  $('#raw-hex').oninput = updateRawPreview;
  $('#raw-apply').onclick = () => {
    const v = parseHex($('#raw-hex').value);
    if (v == null) return toast('not a valid 16-bit hex keycode', true);
    assign(v);
  };
}

wire();
load().then(() => { if (S && S.ok) fillBuilders(); });
