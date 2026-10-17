// Statistics screen: draws the numbers of statscalc.js with plain DOM / CSS bars.
import { el, formatValue } from './form.js';
import { BUCKETS } from './statscalc.js';

const MONTHS = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];

const section = (title) => el('h2', 'section', title);

function bar(percent, color) {
  const track = el('div', 'track');
  const fill = el('div', 'fill');
  fill.style.width = `${Math.max(percent, 0)}%`;
  if (color) fill.style.background = color;
  track.append(fill);
  return track;
}

function rank(rows, color) {
  const box = el('div', 'rank');
  const max = Math.max(...rows.map((r) => r[1]), 1);
  for (const [name, n] of rows) {
    const row = el('div', 'rank-row');
    const head = el('div', 'rank-head');
    head.append(el('span', null, name), el('b', null, String(n)));
    row.append(head, bar((100 * n) / max, color));
    box.append(row);
  }
  return box;
}

/**
 * calc: computeStats(...), ctx: {spec, titleOf(entry), onYear(year), status (text about the data)}.
 * Returns the nodes to show.
 */
export function renderStats(calc, { spec, titleOf, onYear, status }) {
  const color = (bucket) => spec.kinds[bucket === 'climbing' ? 'climbing_days' : bucket].color;
  const label = (bucket) => (bucket === 'climbing' ? 'Climbing' : spec.kinds[bucket].plural);
  const nodes = [];

  const years = el('div', 'chips');
  for (const year of calc.years.slice(0, 12)) {
    const chip = el('button', `chip${year === calc.year ? ' on' : ''}`, String(year));
    chip.onclick = () => onYear(year);
    years.append(chip);
  }
  nodes.push(years, el('p', 'hint', status));

  const tiles = el('div', 'tiles');
  for (const t of calc.tiles) {
    const tile = el('div', 'tile');
    tile.append(el('b', null, t.value.toLocaleString('en')), el('span', null, t.label));
    if (t.sub) tile.append(el('small', null, t.sub));
    tiles.append(tile);
  }
  nodes.push(tiles.childElementCount ? tiles : el('p', 'hint', `No entries in ${calc.year}.`));

  // days per month, stacked by activity
  const totals = calc.months.map((m) => BUCKETS.reduce((n, b) => n + m[b], 0));
  const max = Math.max(...totals, 1);
  const chart = el('div', 'mchart');
  calc.months.forEach((month, i) => {
    const col = el('div', 'mcol');
    const stack = el('div', 'mstack');
    for (const b of BUCKETS) {
      if (!month[b]) continue;
      const seg = el('div', 'mseg');
      seg.style.height = `${(100 * month[b]) / max}%`;
      seg.style.background = color(b);
      seg.title = `${label(b)}: ${month[b]}`;
      stack.append(seg);
    }
    col.append(el('small', 'mval', totals[i] ? String(totals[i]) : ''), stack, el('small', null, MONTHS[i]));
    chart.append(col);
  });
  const legend = el('div', 'legend');
  for (const b of BUCKETS.filter((x) => calc.perBucket[x])) {
    const item = el('span', 'legend-item', `${label(b)} ${calc.perBucket[b]}`);
    item.style.setProperty('--c', color(b));
    legend.append(item);
  }
  nodes.push(section(`Days per month ${calc.year}`), chart, legend);

  if (calc.grade.length) {
    const top = Math.max(...calc.grade.flatMap((g) => [g.now, g.before]), 1);
    const grades = el('div', 'rank');
    for (const g of calc.grade) {
      const row = el('div', 'grade-row');
      const bars = el('div', 'grade-bars');
      bars.append(bar((100 * g.now) / top, color('sport_routes')), bar((100 * g.before) / top, 'var(--border)'));
      row.append(el('span', 'grade-label', g.label), bars, el('b', null, `${g.now}`), el('small', null, g.before ? `(${g.before})` : ''));
      grades.append(row);
    }
    nodes.push(section(`Route grades ${calc.year} (bars below: ${calc.year - 1})`), grades);
  }

  if (calc.hardest.length) {
    const list = el('div', 'rank');
    for (const r of calc.hardest) {
      const row = el('div', 'plain-row');
      row.append(el('b', null, `${r.name}  ${r.grade}`),
        el('small', null, [r.attempts, r.crag || r.area, formatValue({ type: 'date' }, r.date)].filter(Boolean).join(' · ')));
      list.append(row);
    }
    nodes.push(section(`Hardest routes ${calc.year}`), list);
  }
  if (calc.crags.length) nodes.push(section('Most visited crags (days)'), rank(calc.crags, color('climbing')));
  if (calc.partners.length) nodes.push(section('Most frequent partners (entries)'), rank(calc.partners));

  const perYear = Object.entries(calc.daysPerYear).sort((a, b) => b[0] - a[0]).slice(0, 12);
  if (perYear.length) {
    const topDays = Math.max(...perYear.map((p) => p[1]));
    const list = el('div', 'rank');
    for (const [year, n] of perYear) {
      const row = el('button', `rank-row year-row${Number(year) === calc.year ? ' current' : ''}`);
      const head = el('div', 'rank-head');
      head.append(el('span', null, year), el('b', null, `${n} days`));
      row.append(head, bar((100 * n) / topDays));
      row.onclick = () => onYear(Number(year));
      list.append(row);
    }
    nodes.push(section('Active days per year'), list);
  }

  if (calc.onThisDay.length) {
    const list = el('div', 'rank');
    for (const m of calc.onThisDay) {
      const row = el('div', 'plain-row');
      row.append(el('b', null, titleOf(m) + (m.count > 1 ? `  (+${m.count - 1} more)` : '')),
        el('small', null, `${spec.kinds[m.kind].label} · ${m.day.slice(0, 4)}`));
      list.append(row);
    }
    nodes.push(section('On this day'), list);
  }
  return nodes;
}
