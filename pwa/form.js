// Builds the input form of a kind from its field list (kinds.json, generated from schema.py by make_pwa.py).
// Values come out in exactly the shape the desktop app stores them (see inbox.py).
let uid = 0;

export function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  return node;
}

export const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

const COMPACT = new Set(['int', 'float', 'time', 'rating', 'date', 'bool']);
const isEmpty = (v) => v == null || v === '' || v === 0 || v === false || (Array.isArray(v) && !v.length);

/** Modal bottom sheet. actions: [{label, primary, danger, onClick}]; onClick may return false to stay open. */
export function openSheet({ title, body, actions }) {
  const overlay = el('div', 'sheet-overlay');
  const sheet = el('div', 'sheet');
  const content = el('div', 'sheet-body');
  const foot = el('div', 'sheet-foot');
  const close = () => overlay.remove();
  content.append(body);
  for (const a of actions) {
    const b = el('button', `btn${a.primary ? ' primary' : ''}${a.danger ? ' danger' : ''}`, a.label);
    b.type = 'button';
    b.onclick = async () => { if ((await a.onClick?.()) !== false) close(); };
    foot.append(b);
  }
  overlay.onclick = (e) => { if (e.target === overlay) close(); };
  sheet.append(el('h2', 'sheet-title', title), content, foot);
  overlay.append(sheet);
  document.body.append(overlay);
  return close;
}

function chips(options, selected, multi, onChange) {
  const box = el('div', 'chips');
  const chosen = new Set(selected);
  const draw = () => {
    box.replaceChildren();
    for (const option of options) {
      const b = el('button', `chip${chosen.has(option) ? ' on' : ''}`, option);
      b.type = 'button';
      b.onclick = () => {
        const was = chosen.has(option);
        if (!multi) chosen.clear();
        was ? chosen.delete(option) : chosen.add(option);
        draw();
        onChange?.();
      };
      box.append(b);
    }
  };
  const include = (values) => values.forEach((v) => { if (!options.includes(v)) options.push(v); chosen.add(v); });
  include(selected);
  draw();
  return {
    node: box,
    values: () => options.filter((o) => chosen.has(o)),
    add: (v) => { include([v]); draw(); },
  };
}

function fillList(list, options) {
  list.replaceChildren(...options.slice(0, 300).map((o) => Object.assign(el('option'), { value: o })));
}

function datalist(input, options) {
  const list = el('datalist');
  list.id = `dl${++uid}`;
  fillList(list, options);
  input.setAttribute('list', list.id);
  return list;
}

function withSuffix(input, suffix) {
  if (!suffix) return input;
  const row = el('div', 'suffix-row');
  row.append(input, el('span', 'suffix', suffix));
  return row;
}

export function formatValue(f, v) {
  if (isEmpty(v) || (f.type === 'time' && v === '00:00')) return '';
  if (f.type === 'bool') return '✓';
  if (f.type === 'rating') return '★'.repeat(v);
  if (f.type === 'multichoice') return v.join(', ');
  if (f.type === 'list') return `${v.length} × ${f.item_label}`;
  if (f.type === 'gps') return `${v.lat.toFixed(4)}, ${v.lon.toFixed(4)}`;
  if (f.type === 'date') return v.split('-').reverse().join('.');
  return f.suffix ? `${v} ${f.suffix}` : String(v);
}

// ------------------------------------------------------------------ field widgets
function makeField(f, value, ctx) {
  const suggestions = ctx.suggest(f.key);
  switch (f.type) {
    case 'date': {
      const input = Object.assign(el('input'), { type: 'date', value: value ?? (f.key === 'date' ? today() : '') });
      return { node: input, get: () => input.value || null };
    }
    case 'time': {
      const input = Object.assign(el('input'), { type: 'time', value: value || '00:00' });
      return { node: input, get: () => input.value || '00:00' };
    }
    case 'int': {
      const input = Object.assign(el('input'), { type: 'number', inputMode: 'numeric', min: 0, value: value || '' });
      return { node: withSuffix(input, f.suffix), get: () => Math.max(0, Math.round(Number(input.value)) || 0) };
    }
    case 'float': {
      const input = Object.assign(el('input'), { type: 'text', value: value || '' });
      if (f.minimum >= 0) input.inputMode = 'decimal';      // the iOS decimal keyboard has no minus sign
      const get = () => {
        const n = parseFloat(input.value.replace(',', '.'));
        return Number.isFinite(n) ? Number(n.toFixed(f.decimals ?? 1)) : 0;
      };
      return { node: withSuffix(input, f.suffix), get };
    }
    case 'bool': {
      const input = Object.assign(el('input'), { type: 'checkbox', checked: !!value });
      return { node: input, get: () => input.checked };
    }
    case 'rating': {
      let stars = value || 0;
      const row = el('div', 'stars');
      const draw = () => {
        row.replaceChildren();
        for (let i = 1; i <= 5; i++) {
          const b = el('button', `star${i <= stars ? ' on' : ''}`, '★');
          b.type = 'button';
          b.onclick = () => { stars = stars === i ? 0 : i; draw(); };
          row.append(b);
        }
      };
      draw();
      return { node: row, get: () => stars };
    }
    case 'multiline': {
      const input = Object.assign(el('textarea'), { rows: 3, value: value || '' });
      return { node: input, get: () => input.value.trim() };
    }
    case 'choice': {
      if (f.choices?.length && f.choices.length <= 8) {
        const c = chips([...f.choices], value ? [value] : [], false);
        return { node: c.node, get: () => c.values()[0] || '' };
      }
      const input = Object.assign(el('input'), { type: 'text', value: value || '', autocomplete: 'off' });
      const merged = (extra) => [...new Set([...(f.choices || []), ...extra])];
      const list = datalist(input, merged(suggestions));
      const wrap = el('div');
      wrap.append(input, list);
      return { node: wrap, get: () => input.value.trim(), setOptions: (o) => fillList(list, merged(o)) };
    }
    case 'partners': {
      const input = Object.assign(el('input'), { type: 'text', value: value || '', autocapitalize: 'words' });
      const row = el('div', 'chips small');
      for (const name of suggestions.slice(0, 8)) {
        const b = el('button', 'chip', name);
        b.type = 'button';
        b.onclick = () => {
          const names = input.value.split(',').map((n) => n.trim()).filter(Boolean);
          if (!names.includes(name)) input.value = [...names, name].join(', ');
        };
        row.append(b);
      }
      const wrap = el('div');
      wrap.append(input, row);
      return { node: wrap, get: () => input.value.trim() };
    }
    case 'multichoice': return multiChoice(f, value, suggestions);
    case 'gps': return gpsField(value);
    case 'list': return listField(f, value, ctx);
    default: {
      const input = Object.assign(el('input'), { type: 'text', value: value || '', autocomplete: 'off' });
      const list = datalist(input, suggestions);
      const wrap = el('div');
      wrap.append(input, list);
      return { node: wrap, get: () => input.value.trim(), setOptions: (o) => fillList(list, o) };
    }
  }
}

function multiChoice(f, value, suggestions) {
  const c = chips([...new Set([...(f.choices || []), ...suggestions.slice(0, 30)])], value || [], true);
  const input = Object.assign(el('input'), { type: 'text', placeholder: 'Add your own …' });
  const add = el('button', 'btn', 'Add');
  add.type = 'button';
  add.onclick = () => { if (input.value.trim()) { c.add(input.value.trim()); input.value = ''; } };
  const row = el('div', 'inline-row');
  row.append(input, add);
  const wrap = el('div');
  wrap.append(c.node, row);
  return { node: wrap, get: () => c.values() };
}

function gpsField(value) {
  const input = Object.assign(el('input'), {
    type: 'text', placeholder: 'lat, lon', value: value?.lat != null ? `${value.lat}, ${value.lon}` : '',
  });
  const here = el('button', 'btn', 'Use my position');
  const clear = el('button', 'btn', '✕');
  const status = el('div', 'hint');
  here.type = clear.type = 'button';
  here.onclick = () => {
    status.textContent = 'Locating …';
    navigator.geolocation?.getCurrentPosition(
      (p) => { input.value = `${p.coords.latitude.toFixed(5)}, ${p.coords.longitude.toFixed(5)}`; status.textContent = ''; },
      (e) => { status.textContent = `Position unavailable (${e.message})`; },
      { enableHighAccuracy: true, timeout: 15000 });
  };
  clear.onclick = () => { input.value = ''; status.textContent = ''; };
  const row = el('div', 'inline-row');
  row.append(input, here, clear);
  const wrap = el('div');
  wrap.append(row, status);
  const get = () => {
    const m = input.value.match(/(-?\d+(?:[.,]\d+)?)\s*[,;\s]\s*(-?\d+(?:[.,]\d+)?)/);
    if (!m) return null;
    const [lat, lon] = [m[1], m[2]].map((n) => parseFloat(n.replace(',', '.')));
    return Math.abs(lat) <= 90 && Math.abs(lon) <= 180 ? { lat, lon } : null;
  };
  return { node: wrap, get };
}

function listField(f, value, ctx) {
  const items = (value || []).map((i) => ({ ...i }));
  const rows = el('div', 'list-rows');
  const add = el('button', 'btn', `+ ${f.item_label}`);
  add.type = 'button';
  const summary = (item) => f.columns
    .map((key) => formatValue(f.sub.find((s) => s.key === key), item[key])).filter(Boolean).join(' · ');
  const draw = () => {
    rows.replaceChildren();
    items.forEach((item, i) => {
      const row = el('button', 'list-row', summary(item) || `${f.item_label} ${i + 1}`);
      row.type = 'button';
      row.onclick = () => edit(i);
      rows.append(row);
    });
  };
  const edit = (index) => {
    const isNew = index < 0;
    const base = { ...(isNew ? {} : items[index]) };
    if (isNew && items.length) {                 // series of sets: start from the previous item
      const last = items[items.length - 1];
      for (const s of f.sub) if (['choice', 'text', 'date'].includes(s.type) && last[s.key]) base[s.key] = last[s.key];
    }
    const form = buildForm(f.sub, base, ctx);
    openSheet({
      title: f.item_label, body: form.el,
      actions: [
        { label: 'Save', primary: true, onClick: () => {
          if (form.missing().length) return false;
          const result = { ...base, ...form.read() };
          isNew ? items.push(result) : (items[index] = result);
          draw();
        } },
        ...(isNew ? [] : [{ label: 'Remove', danger: true, onClick: () => { items.splice(index, 1); draw(); } }]),
        { label: 'Cancel' },
      ],
    });
  };
  add.onclick = () => edit(-1);
  draw();
  const wrap = el('div');
  wrap.append(rows, add);
  return { node: wrap, get: () => items };
}

/**
 * fields: field specs, values: existing record (or prefill), ctx: {suggest(key) -> string[]}.
 * Returns {el, read(), missing()}; missing() marks and returns the required fields left empty.
 */
export function buildForm(fields, values, ctx) {
  const root = el('div', 'form');
  const parts = fields.map((f) => {
    const { node, get, setOptions } = makeField(f, values[f.key], ctx);
    const wrap = el('div', `field${COMPACT.has(f.type) ? ' half' : ''}${f.type === 'bool' ? ' toggle' : ''}`);
    wrap.dataset.key = f.key;
    wrap.append(el('label', 'label', f.label + (f.required ? ' *' : '')), node);
    root.append(wrap);
    return { f, get, setOptions, wrap };
  });

  // dependent dropdowns: each level only offers what was seen under the values chosen above it
  const chain = (ctx.chain || []).filter((key) => parts.some((p) => p.f.key === key));
  if (chain.length > 1 && ctx.chainOptions) {
    const part = (key) => parts.find((p) => p.f.key === key);
    const refresh = (from) => {
      const current = Object.fromEntries(chain.map((key) => [key, part(key).get()]));
      chain.slice(from + 1).forEach((key) => part(key).setOptions?.(ctx.chainOptions(key, current)));
    };
    root.addEventListener('input', (e) => {
      const at = chain.indexOf(e.target.closest('.field')?.dataset.key);
      if (at >= 0) refresh(at);
    });
    refresh(-1);
  }

  return {
    el: root,
    read: () => Object.fromEntries(parts.map(({ f, get }) => [f.key, get()])),
    missing() {
      const missing = [];
      for (const { f, get, wrap } of parts) {
        const bad = !!f.required && isEmpty(get());
        wrap.classList.toggle('invalid', bad);
        if (bad) missing.push(f.label);
      }
      return missing;
    },
  };
}
