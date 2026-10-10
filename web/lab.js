'use strict';
// Shared helpers for both lab pages. All data comes from the local server; nothing is invented client-side.
const $ = id => document.getElementById(id);
function node(tag, text, cls) {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (cls) n.className = cls;
  return n;
}
function svgEl(tag, attrs, text) {
  const n = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (text !== undefined) n.textContent = text;
  return n;
}
async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) {
    let message = `Local data unavailable (HTTP ${r.status}).`;
    try { message = (await r.json()).error || message; } catch {}
    throw new Error(message);
  }
  return r.json();
}
const pad = n => String(n).padStart(2, '0');
const tally = m => m?.total ? `${m.count}/${m.total}` : 'Pending';

// Training loss (thin, muted) against validation loss (blue, with checkpoints).
function drawLoss(svg, rows, note) {
  svg.replaceChildren();
  const W = 520, H = 230, L = 40, R = 12, T = 12, B = 34;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  const train = rows.filter(r => r.kind === 'train'), valid = rows.filter(r => r.kind === 'validation');
  if (!rows.length) {
    svg.append(svgEl('text', {x: L, y: H / 2}, 'No training loss was recorded for this run.'));
    if (note) note.textContent = '';
    return;
  }
  const values = rows.map(r => r.train_loss ?? r.val_loss);
  const top = Math.ceil(Math.max(...values) * 1.05), steps = Math.max(...rows.map(r => r.iteration)) || 1;
  const x = s => L + s / steps * (W - L - R), y = v => H - B - v / top * (H - T - B);
  const yStep = top > 4 ? 2 : 1;
  for (let v = 0; v <= top; v += yStep) {
    svg.append(svgEl('line', {x1: L, x2: W - R, y1: y(v), y2: y(v), class: 'axis'}),
               svgEl('text', {x: L - 8, y: y(v) + 4, 'text-anchor': 'end'}, String(v)));
  }
  const xTicks = 4;
  for (let i = 0; i <= xTicks; i++) {
    const s = Math.round(steps * i / xTicks);
    svg.append(svgEl('text', {x: x(s), y: H - B + 18, 'text-anchor': i === 0 ? 'start' : i === xTicks ? 'end' : 'middle'}, String(s)));
  }
  svg.append(svgEl('text', {x: W - R, y: H - 2, 'text-anchor': 'end'}, 'Training updates'));
  const line = (pts, key, cls, width) => svg.append(svgEl('polyline', {
    points: pts.map(r => `${x(r.iteration)},${y(r[key])}`).join(' '),
    fill: 'none', class: cls, 'stroke-width': width, 'stroke-linejoin': 'round', 'stroke-linecap': 'round'}));
  line(train, 'train_loss', 'train', 1.4);
  line(valid, 'val_loss', 'valid', 2.4);
  if (valid.length <= 40) valid.forEach(r => svg.append(svgEl('circle', {cx: x(r.iteration), cy: y(r.val_loss), r: 3.2, class: 'valid-dot'})));
  const span = valid.length > 1 ? `${valid[0].val_loss.toFixed(2)} to ${valid.at(-1).val_loss.toFixed(2)}` : 'recorded at one checkpoint';
  svg.setAttribute('aria-label', `Validation loss went from ${span} over ${steps} updates.`);
  if (note) note.textContent = valid.length > 1
    ? `Validation loss went from ${valid[0].val_loss.toFixed(2)} to ${valid.at(-1).val_loss.toFixed(2)}. That is a teacher-forced score; it does not measure the answers the model generates.`
    : 'Validation loss is shown at each recorded checkpoint.';
}

// Segmented radio control for choosing which run a page shows.
function bindSwitch(name, onChange) {
  const inputs = [...document.querySelectorAll(`input[name=${name}]`)];
  inputs.forEach(i => i.addEventListener('change', () => { if (i.checked) onChange(i.value); }));
  return {
    get value() { return inputs.find(i => i.checked)?.value; },
    set value(v) { const i = inputs.find(i => i.value === v); if (i) i.checked = true; },
    input: v => inputs.find(i => i.value === v),
  };
}

// The charting marks animate in once, on first load only.
function revealOnce(el) {
  if (el.dataset.revealed) return;
  el.dataset.revealed = '1';
  el.classList.add('reveal');
  setTimeout(() => el.classList.remove('reveal'), 1600);
}

// Move the chart's selection mark without rebuilding (and re-animating) the grid.
function markCurrent(grid, id) {
  grid.querySelectorAll('.cell').forEach(c => c.classList.toggle('current', c.dataset.id === id));
}
