// Statistics over the desktop data plus the entries of this phone. Pure functions, no DOM, no imports.
// "Climbing" merges climbing days and sport routes, so a day with both counts once.
export const BUCKETS = ['climbing', 'alpine_climbs', 'mountain_tours', 'training_sessions', 'cycling', 'paragliding',
  'competitions'];
const BUCKET_OF = { sport_routes: 'climbing', climbing_days: 'climbing' };
const PARTNER_KINDS = ['climbing_days', 'alpine_climbs', 'mountain_tours', 'trips', 'cycling', 'paragliding'];
const MAX_SPAN_DAYS = 120;
const DAY = 864e5;
const ISO = /^\d{4}-\d{2}-\d{2}/;

const utc = (iso) => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10));
const isoOf = (ms) => new Date(ms).toISOString().slice(0, 10);
const hours = (minutes) => (minutes < 120 ? `${minutes} min` : `${(minutes / 60).toFixed(1)} h`);
const top = (map, n) => [...map].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, n);

/** Every ISO day of an entry (multi-day entries span date..date_to). */
export function daysOf(record) {
  if (!ISO.test(record.date || '')) return [];
  const start = utc(record.date);
  let end = ISO.test(record.date_to || '') ? utc(record.date_to) : start;
  if (end < start || (end - start) / DAY > MAX_SPAN_DAYS) end = start;
  const days = [];
  for (let t = start; t <= end; t += DAY) days.push(isoOf(t));
  return days;
}

export function splitNames(text) {
  let s = String(text || '');
  for (const sep of [';', '&', '/', ' und ', ' and ', '+']) s = s.split(sep).join(',');
  return s.split(',').map((p) => p.trim()).filter(Boolean);
}

/** Same index as grades.py: UIAA 3 = 22 ... 12 = 58, French 5a = 30 ... 9c = 58. */
export function gradeTools({ french, uiaa }) {
  const fIndex = new Map(french.map((g, i) => [g, 30 + i]));
  const uIndex = new Map(uiaa.map((g, i) => [g, 22 + i]));
  const fName = new Map(french.map((g, i) => [30 + i, g]));
  return {
    index: (grade) => fIndex.get(String(grade || '').trim()) ?? uIndex.get(String(grade || '').trim()) ?? -1,
    french: (index) => fName.get(index) || '',
  };
}

/**
 * entries: [{kind, record}], grades: kinds.json "grades", year: number, today: ISO date.
 * Everything is derived from these, nothing is stored.
 */
export function computeStats(entries, grades, year, today) {
  const G = gradeTools(grades);
  const y = String(year);
  const dayBuckets = new Map();                                 // ISO day -> Set of buckets
  for (const { kind, record } of entries) {
    const bucket = BUCKET_OF[kind] ?? kind;
    if (!BUCKETS.includes(bucket)) continue;
    for (const day of daysOf(record)) {
      if (!dayBuckets.has(day)) dayBuckets.set(day, new Set());
      dayBuckets.get(day).add(bucket);
    }
  }

  const daysPerYear = {};
  const perBucket = Object.fromEntries(BUCKETS.map((b) => [b, 0]));
  const months = Array.from({ length: 12 }, () => Object.fromEntries(BUCKETS.map((b) => [b, 0])));
  for (const [day, buckets] of dayBuckets) {
    daysPerYear[day.slice(0, 4)] = (daysPerYear[day.slice(0, 4)] || 0) + 1;
    if (!day.startsWith(y)) continue;
    for (const b of buckets) { perBucket[b]++; months[+day.slice(5, 7) - 1][b]++; }
  }
  const years = Object.keys(daysPerYear).map(Number).sort((a, b) => b - a);

  const inYear = (kind, yr = y) => entries.filter((e) => e.kind === kind && String(e.record.date || '').startsWith(yr))
    .map((e) => e.record);
  const sum = (list, key) => list.reduce((n, r) => n + (Number(r[key]) || 0), 0);
  const routes = inYear('sport_routes');
  const alpine = inYear('alpine_climbs');
  const tours = inYear('mountain_tours');
  const rides = inYear('cycling');
  const flights = inYear('paragliding').flatMap((r) => r.flights || []);
  const easy = routes.filter((r) => r.attempts === 'onsight' || r.attempts === 'flash').length;
  const tiles = [
    { label: 'Active days', value: dayBuckets.size ? [...dayBuckets.keys()].filter((d) => d.startsWith(y)).length : 0 },
    { label: 'Climbing days', value: perBucket.climbing },
    { label: 'Ticks', value: routes.length, sub: routes.length ? `${Math.round((100 * easy) / routes.length)} % flash / onsight` : '' },
    { label: 'Alpine climbs', value: alpine.length, sub: sum(alpine, 'meters') ? `${sum(alpine, 'meters')} m climbed` : '' },
    { label: 'Mountain tours', value: tours.length, sub: sum(tours, 'elevation_gain') ? `${sum(tours, 'elevation_gain').toLocaleString('en')} Hm` : '' },
    { label: 'Training sessions', value: perBucket.training_sessions },
    { label: 'Cycling', value: rides.length, sub: sum(rides, 'distance') ? `${Math.round(sum(rides, 'distance'))} km` : '' },
    { label: 'Flights', value: flights.length, sub: sum(flights, 'airtime') ? `${hours(sum(flights, 'airtime'))} airtime` : '' },
  ].filter((t) => t.value > 0);

  // route grades (boulder grades are a different scale and left out), bucketed by French base grade
  const label = (index) => (index < 36 ? '<6a' : G.french(index).replace('+', ''));
  const histogram = (list) => {
    const counts = new Map();
    for (const r of list) {
      const index = G.index(r.grade);
      if (index >= 0 && r.discipline !== 'Boulder') counts.set(label(index), (counts.get(label(index)) || 0) + 1);
    }
    return counts;
  };
  const now = histogram(routes);
  const before = histogram(inYear('sport_routes', String(year - 1)));
  const scale = ['<6a', ...[...new Set(grades.french.map((g) => g.replace('+', '')))].filter((g) => g >= '6a')];
  const used = scale.map((g, i) => (now.has(g) || before.has(g) ? i : -1)).filter((i) => i >= 0);
  const grade = used.length ? scale.slice(used[0], used[used.length - 1] + 1)
    .map((g) => ({ label: g, now: now.get(g) || 0, before: before.get(g) || 0 })) : [];

  const hardest = routes.filter((r) => r.discipline !== 'Boulder' && G.index(r.grade) >= 0)
    .sort((a, b) => G.index(b.grade) - G.index(a.grade) || (a.date < b.date ? -1 : 1)).slice(0, 3);

  const cragDays = new Map();                                   // crag -> days with climbing there
  for (const { kind, record } of entries) {
    const place = record.crag || record.area;
    if ((kind === 'climbing_days' || kind === 'sport_routes') && place && String(record.date || '').startsWith(y)) {
      if (!cragDays.has(place)) cragDays.set(place, new Set());
      cragDays.get(place).add(record.date);
    }
  }
  const partnerCount = new Map();
  for (const { kind, record } of entries) {
    if (PARTNER_KINDS.includes(kind) && String(record.date || '').startsWith(y)) {
      for (const name of new Set(splitNames(record.partner))) partnerCount.set(name, (partnerCount.get(name) || 0) + 1);
    }
  }

  const monthDay = today.slice(5);
  const memories = new Map();                                   // same kind on the same day (several ticks) -> one line
  for (const { kind, record } of entries) {
    if (kind === 'body_metrics') continue;
    const hit = daysOf(record).find((d) => d.slice(5) === monthDay && d.slice(0, 4) < today.slice(0, 4));
    if (!hit) continue;
    const key = `${kind}|${hit}`;
    if (memories.has(key)) memories.get(key).count++;
    else memories.set(key, { kind, record, day: hit, count: 1 });
  }
  const onThisDay = [...memories.values()].sort((a, b) => (a.day < b.day ? 1 : -1)).slice(0, 8);

  return {
    year, years, tiles, perBucket, months, daysPerYear, grade, hardest, onThisDay,
    crags: top(new Map([...cragDays].map(([k, v]) => [k, v.size])), 5),
    partners: top(partnerCount, 5),
  };
}
