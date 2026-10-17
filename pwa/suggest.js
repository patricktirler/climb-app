// Autocomplete values for the form, taken from the desktop data plus the entries made on this phone, and the
// dependent dropdowns (country -> region -> area -> crag ...) like the desktop's RecordForm. No imports: pure logic.
const SHARED_KEYS = ['country', 'region', 'area', 'crag', 'sector', 'range', 'mountain', 'partner'];

const byFrequency = (counts) => [...counts]
  .sort((a, b) => b[1] - a[1] || a[0].toLowerCase().localeCompare(b[0].toLowerCase())).map(([v]) => v);

function walk(counts, key, value) {
  if (Array.isArray(value)) {                                   // nested items (sets, flights): their keys count too
    value.forEach((item) => (item && typeof item === 'object'
      ? Object.entries(item).forEach(([k, v]) => walk(counts, k, v)) : walk(counts, key, item)));
  } else if (typeof value === 'string') {
    for (const part of key === 'partner' ? value.split(/[,;&]/) : [value]) {
      const text = part.trim();
      if (text) {
        const map = (counts[key] ||= new Map());
        map.set(text, (map.get(text) || 0) + 1);
      }
    }
  }
}

/**
 * kind: the kind being entered, spec: kinds.json, data: the cached desktop dataset (or null),
 * local: entries of this phone that the desktop does not have yet ({kind, record}).
 * Returns {suggest(key), chain, chainOptions(key, current)}.
 */
export function makeContext(kind, spec, data, local) {
  const records = (k) => [...(data?.entries?.[k] || []), ...local.filter((e) => e.kind === k).map((e) => e.record)];
  const kinds = [...new Set([...Object.keys(data?.entries || {}), ...Object.keys(spec.kinds)])];
  const counts = {};
  for (const k of kinds) {
    for (const record of records(k)) {
      for (const [key, value] of Object.entries(record)) {
        if (k === kind || SHARED_KEYS.includes(key)) walk(counts, key, value);   // places, partners: all kinds
      }
    }
  }
  for (const list of Object.values(data?.places || {})) {
    for (const place of list) for (const key of SHARED_KEYS) walk(counts, key, place[key]);
  }
  for (const method of data?.methods || []) {
    walk(counts, 'method', method.name);
    walk(counts, 'hold', method.holds);
  }

  const cascade = spec.kinds[kind]?.cascade;
  const chainOptions = (key, current) => {
    const i = cascade.chain.indexOf(key);
    const selected = cascade.chain.slice(0, i).map((k) => [k, (current[k] || '').trim()]).filter(([, t]) => t);
    const found = new Map();
    const consider = (record) => {
      // the nearest selected parent must match, higher ones only if the record has a value there
      const fits = selected.every(([k, text], n) => record[k] === text || (n < selected.length - 1 && !record[k]));
      if (fits && record[key]) found.set(String(record[key]), (found.get(String(record[key])) || 0) + 1);
    };
    const pool = cascade.pools[key];
    pool.kinds.forEach((k) => records(k).forEach(consider));
    pool.catalogs.forEach((name) => (data?.places?.[name] || []).forEach(consider));
    return byFrequency(found);
  };

  return {
    suggest: (key) => byFrequency(counts[key] || new Map()),
    chain: cascade?.chain || [],
    chainOptions,
  };
}
