// API behaviour tests (no dependencies): node --test tests/
// The engine tests (check_engine.py) cover whether the routes are right; these cover what a client
// sees: bad input is refused, a dead or stuck engine does not hang requests, autocomplete finds
// stations the way a rider types them.
const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const path = require('node:path');

const API = path.join(__dirname, '../api/server.js');
const fs = require('node:fs');
const GTFS = path.join(__dirname, '../data/gtfs');
const lineCount = (file) => fs.readFileSync(path.join(GTFS, file), 'utf8').trim().split('\n').length - 1;

function startApi(port, env = {}) {
  const proc = spawn(process.execPath, [API], { env: { ...process.env, PORT: port, ...env } });
  let log = '';
  proc.stdout.on('data', (d) => (log += d));
  proc.stderr.on('data', (d) => (log += d));
  const ready = new Promise((resolve, reject) => {
    const started = Date.now();
    const poll = setInterval(() => {
      if (/engine ready/i.test(log) && /Shapes GeoJSON built/.test(log)) { clearInterval(poll); resolve(); }
      else if (Date.now() - started > 30000) { clearInterval(poll); reject(new Error('API did not start:\n' + log)); }
    }, 100);
  });
  return { proc, ready, base: `http://localhost:${port}` };
}

const get = (base, p) => fetch(base + p).then(async (r) => ({ status: r.status, body: await r.json() }));

let real, fake;
before(async () => {
  real = startApi(3911);
  fake = startApi(3912, { ENGINE_CMD: JSON.stringify([process.execPath, path.join(__dirname, 'fake_engine.js')]) });
  await Promise.all([real.ready, fake.ready]);
});
after(() => { real.proc.kill(); fake.proc.kill(); });

test('a normal query returns journeys, and the repeat is served from the cache', async () => {
  const q = '/api/route?from=CHURCHGATE&to=VIRAR&time=480';
  const first = await get(real.base, q);
  assert.equal(first.status, 200);
  assert.ok(first.body.routes.length >= 1);
  assert.equal(first.body.routes[0][0].from, 'CHURCHGATE');
  assert.equal(first.body.cached, false);
  assert.equal((await get(real.base, q)).body.cached, true);
});

test('bad input is refused with 400 and does not disturb the engine', async () => {
  const bad = [
    '/api/route?from=CHURCHGATE&to=VIRAR&time=abc', '/api/route?from=CHURCHGATE&to=VIRAR&time=-1',
    '/api/route?from=CHURCHGATE&to=VIRAR&time=1440', '/api/route?from=CHURCHGATE&to=VIRAR&time=1e3',
    '/api/route?from=CHURCHGATE&to=VIRAR', '/api/route?from=CHURCHGATE&to=VIRAR&time=480&time=500',
    '/api/route?to=VIRAR&time=480', '/api/route?from=NOWHERE&to=VIRAR&time=480',
    '/api/route?from=__proto__&to=VIRAR&time=480', '/api/route?from=constructor&to=VIRAR&time=480',
    '/api/route?from=CHURCHGATE%0Ax|CHURCHGATE,VIRAR,1&to=VIRAR&time=480',
    '/api/route?from=CHURCHGATE,VIRAR&to=VIRAR&time=480',
  ];
  for (const q of bad) assert.equal((await get(real.base, q)).status, 400, q);
  assert.equal((await get(real.base, '/api/route?from=CHURCHGATE&to=KALYAN&time=480')).status, 200);
});

test('same origin and target gives an empty result, not an error', async () => {
  const r = await get(real.base, '/api/route?from=DADAR&to=DADAR&time=600');
  assert.equal(r.status, 200);
  assert.deepEqual(r.body.routes, []);
});

test('autocomplete finds stations by name prefix, by any word, and ignores apostrophes', async () => {
  const ids = async (prefix) => (await get(real.base, `/api/stations?prefix=${encodeURIComponent(prefix)}`)).body.map((s) => s.id);
  assert.deepEqual(await ids('Kand'), ['M2A_KANDARPADA', 'KANDIVALI', 'M2A_KANDIVALI_WEST']); // by name, the local station before the metro one of the same name
  assert.ok((await ids('road')).includes('MATUNGA_ROAD'));
  assert.deepEqual((await ids('Matunga'))[0], 'MATUNGA'); // name-prefix matches rank first
  assert.ok((await ids('kings')).includes("KING'S_CIRCLE"));
  assert.deepEqual(await ids('zzz'), []);
  assert.equal(Object.keys((await get(real.base, '/api/stations')).body).length, lineCount('stops.txt'));
});

test('shapes are served gzipped when accepted and plain otherwise', async () => {
  const gz = await fetch(real.base + '/api/shapes', { headers: { 'Accept-Encoding': 'gzip' } });
  // fetch decompresses transparently; the header tells us it was compressed on the wire
  assert.equal(gz.headers.get('content-encoding'), 'gzip');
  const body = await gz.json();
  assert.equal(body.type, 'FeatureCollection');
  assert.equal(body.features.length, new Set(fs.readFileSync(path.join(GTFS, 'trips.txt'), 'utf8').trim().split('\n').slice(1).map((l) => l.split(',')[4])).size);
  assert.ok(body.features.every((f) => f.properties.route_id && f.geometry.coordinates.length >= 2));
  const plain = await fetch(real.base + '/api/shapes', { headers: { 'Accept-Encoding': 'identity' } });
  assert.equal(plain.headers.get('content-encoding'), null);
  assert.equal((await plain.json()).features.length, body.features.length);
});

test('if the engine dies mid-request the client gets an error quickly, and service resumes', async () => {
  const started = Date.now();
  const crashed = await get(fake.base, '/api/route?from=CSMT&to=VIRAR&time=480');
  assert.equal(crashed.status, 503);
  assert.ok(Date.now() - started < 2000, 'must not wait for a timeout');
  await new Promise((r) => setTimeout(r, 1800)); // restart delay
  const after = await get(fake.base, '/api/route?from=CSMT&to=THANE&time=480');
  assert.equal(after.status, 200);
});

test('a request the engine never answers times out instead of hanging', async () => {
  const started = Date.now();
  const r = await get(fake.base, '/api/route?from=CSMT&to=KALYAN&time=480');
  assert.equal(r.status, 503);
  assert.ok(Date.now() - started < 8000);
  assert.equal((await get(fake.base, '/api/route?from=CSMT&to=THANE&time=481')).status, 200);
});

test('metro stations are listed with their mode and line, and share names with local stations', async () => {
  const andheri = (await get(real.base, '/api/stations?prefix=andheri')).body;
  const byId = Object.fromEntries(andheri.map((s) => [s.id, s]));
  assert.equal(byId.ANDHERI.mode, 'LOCAL');
  assert.equal(byId.M1_ANDHERI.mode, 'METRO');
  assert.equal(byId.M1_ANDHERI.line, 'M1');
  assert.equal(byId.M2A_ANDHERI_WEST?.line, 'M2A');
  assert.equal(andheri[0].id, 'ANDHERI', 'the local station comes first for the same name');
});

test('lines are described with a name, colour and mode', async () => {
  const lines = (await get(real.base, '/api/lines')).body;
  assert.equal(lines.M3.mode, 'METRO');
  assert.match(lines.M3.color, /^#[0-9A-Fa-f]{6}$/);
  assert.equal(lines.CR_MAIN.mode, 'LOCAL');
});

test('a journey between a local and a metro station walks between them', async () => {
  const r = await get(real.base, '/api/route?from=CHURCHGATE&to=M1_VERSOVA&time=600');
  assert.equal(r.status, 200);
  assert.ok(r.body.routes.length >= 1);
  const modes = r.body.routes.flat().map((l) => l.mode);
  assert.ok(['LOCAL', 'WALK', 'METRO'].every((m) => modes.includes(m)), `modes were ${[...new Set(modes)]}`);
  const walk = (await get(real.base, '/api/route?from=ANDHERI&to=M1_ANDHERI&time=600')).body.routes[0];
  assert.deepEqual(walk.map((l) => [l.is_walk, l.mode]), [[true, 'WALK']]);
  assert.ok(walk[0].walk_m > 0 && walk[0].arr_min > walk[0].dep_min);
});
