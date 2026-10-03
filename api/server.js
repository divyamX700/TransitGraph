const express = require('express');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const readline = require('readline');
const zlib = require('zlib');
const PrefixTrie = require('./trie');
const LRUCache = require('./lru');

const app = express();
app.disable('x-powered-by');
const port = process.env.PORT || 3000;
const GTFS_DIR = path.join(__dirname, '../data/gtfs');
const REQUEST_TIMEOUT_MS = 5000;
const RESTART_DELAY_MS = 1000;

// CORS for all origins (needed for Vercel -> Render communication)
app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET');
  next();
});

// 1. Station index: a Prefix Trie gives O(m) lookup of the stations whose name, or any word of
//    it, starts with what the user typed ("road" finds "Matunga Road").
const normalize = (s) => s.toLowerCase().replace(/['.]/g, '');
const trie = new PrefixTrie();
const stationsMap = {};

// Reads a GTFS file into objects keyed by its header row (no quoted commas in our feed)
function readTable(name) {
  const [header, ...lines] = fs.readFileSync(path.join(GTFS_DIR, name), 'utf8').split('\n');
  const columns = header.trim().split(',');
  return lines.filter((l) => l.trim()).map((l) => Object.fromEntries(
    splitCsv(l.trim()).map((cell, i) => [columns[i], cell])));
}

// One CSV line; a cell may be double-quoted to contain commas ("Metro Line 2B (Yellow, phase 1)")
function splitCsv(line) {
  const cells = [];
  let cell = '';
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (quoted) {
      if (c === '"' && line[i + 1] === '"') { cell += '"'; i++; }
      else if (c === '"') quoted = false;
      else cell += c;
    } else if (c === '"') quoted = true;
    else if (c === ',') { cells.push(cell); cell = ''; }
    else cell += c;
  }
  cells.push(cell);
  return cells;
}

// The lines that call at each stop, so a local station can show which railways it is on
const routeOfTrip = Object.fromEntries(readTable('trips.txt').map((t) => [t.trip_id, t.route_id]));
const linesAt = {};
for (const line of fs.readFileSync(path.join(GTFS_DIR, 'stop_times.txt'), 'utf8').split('\n').slice(1)) {
  const [tripId, , , stopId] = line.split(',');
  if (routeOfTrip[tripId]) (linesAt[stopId] ||= new Set()).add(routeOfTrip[tripId]);
}

// Other names people search a station by
const ALIASES = { CSMT: ['csmt', 'cst', 'vt', 'victoria terminus'] };

for (const s of readTable('stops.txt')) {
  stationsMap[s.stop_id] = {
    name: s.stop_name, lat: parseFloat(s.stop_lat), lon: parseFloat(s.stop_lon),
    mode: s.stop_mode, line: s.stop_line || null, lines: [...(linesAt[s.stop_id] || [])].sort(),
  };
  const key = normalize(s.stop_name);
  for (let w = 0; w < key.length; w++) {
    if (w === 0 || key[w - 1] === ' ') trie.insert(key.slice(w), s.stop_id);
  }
  for (const alias of ALIASES[s.stop_id] || []) trie.insert(alias, s.stop_id);
}

// Lines: id, name, colour and mode, for the legend and for colouring journeys
const linesMap = Object.fromEntries(readTable('routes.txt').map((r) => [r.route_id, {
  name: r.route_long_name, short_name: r.route_short_name, color: r.route_color,
  mode: r.route_type === '1' ? 'METRO' : r.route_type === '12' ? 'MONORAIL' : 'LOCAL',
}]));

// 2. The C++ engine: one persistent child process, queries multiplexed over stdin/stdout by id.
//    Responses are one line each, `id|json`. If the engine dies, every waiting request gets an
//    error and the engine is started again.
const engineExt = process.platform === 'win32' ? '.exe' : '';
const enginePath = path.join(__dirname, `../engine/raptor${engineExt}`);
// ENGINE_CMD (a JSON array) replaces the engine command; the tests use it to inject a fake engine.
const [engineCmd, ...engineArgs] = process.env.ENGINE_CMD ? JSON.parse(process.env.ENGINE_CMD) : [enginePath, GTFS_DIR];
let engine = null;
let engineReady = false;
let reqCounter = 0;
const pendingRequests = new Map(); // id -> { resolve, timer }

function settle(id, result) {
  const pending = pendingRequests.get(id);
  if (!pending) return;
  clearTimeout(pending.timer);
  pendingRequests.delete(id);
  pending.resolve(result);
}

function startEngine() {
  engineReady = false;
  const child = spawn(engineCmd, engineArgs);
  engine = child;

  readline.createInterface({ input: child.stdout }).on('line', (line) => {
    if (line === 'READY') {
      engineReady = true;
      console.log('C++ RAPTOR Engine ready');
      return;
    }
    const pipeIdx = line.indexOf('|');
    if (pipeIdx === -1) return console.error('Invalid response format from engine:', line);
    let result;
    try {
      result = JSON.parse(line.substring(pipeIdx + 1));
    } catch {
      console.error('Failed to parse engine output:', line);
      result = { error: 'Internal engine error' };
    }
    settle(line.substring(0, pipeIdx), result);
  });
  child.stderr.on('data', (data) => process.stderr.write(`[engine] ${data}`));
  child.stdin.on('error', () => {}); // a dead engine is handled by 'close'
  child.on('close', (code) => {
    console.error(`C++ engine exited with code ${code}`);
    if (engine !== child) return;
    engineReady = false;
    for (const id of [...pendingRequests.keys()]) settle(id, { error: 'The routing engine restarted' });
    setTimeout(startEngine, RESTART_DELAY_MS);
  });
}
startEngine();

function askEngine(from, to, time) {
  if (!engineReady) return Promise.resolve({ error: 'The routing engine is starting' });
  const id = `req_${++reqCounter}`;
  return new Promise((resolve) => {
    const timer = setTimeout(() => settle(id, { error: 'The routing engine took too long to answer' }), REQUEST_TIMEOUT_MS);
    pendingRequests.set(id, { resolve, timer });
    engine.stdin.write(`${id}|${from},${to},${time}\n`);
  });
}

// 3. Map shapes: build the GeoJSON once at startup and keep a gzipped copy.
let shapesGeoJSON = null;
let shapesGzip = null;

async function buildShapesGeoJSON() {
  // shape_id -> route_id, from trips.txt
  const shapeToRoute = {};
  const tripLines = fs.readFileSync(path.join(GTFS_DIR, 'trips.txt'), 'utf8').split('\n');
  const headers = tripLines[0].trim().split(',');
  const routeIdx = headers.indexOf('route_id');
  const shapeIdx = headers.indexOf('shape_id');
  for (const line of tripLines.slice(1)) {
    const parts = line.trim().split(',');
    if (parts.length > shapeIdx) shapeToRoute[parts[shapeIdx]] = parts[routeIdx];
  }

  // Stream shapes.txt, grouping points by shape_id
  const shapeCoords = {};
  const rl = readline.createInterface({ input: fs.createReadStream(path.join(GTFS_DIR, 'shapes.txt')) });
  let firstLine = true;
  await new Promise((resolve) => {
    rl.on('line', (line) => {
      if (firstLine) { firstLine = false; return; }
      const [shapeId, lat, lon, seq] = line.trim().split(',');
      if (!shapeId || isNaN(parseFloat(lat)) || isNaN(parseFloat(lon))) return;
      (shapeCoords[shapeId] ||= []).push([parseInt(seq), parseFloat(lon), parseFloat(lat)]);
    });
    rl.on('close', resolve);
  });

  const features = Object.entries(shapeCoords).map(([shapeId, points]) => ({
    type: 'Feature',
    properties: { shape_id: shapeId, route_id: shapeToRoute[shapeId] || null },
    geometry: { type: 'LineString', coordinates: points.sort((a, b) => a[0] - b[0]).map(([, lon, lat]) => [lon, lat]) },
  }));
  shapesGeoJSON = { type: 'FeatureCollection', features };
  shapesGzip = zlib.gzipSync(JSON.stringify(shapesGeoJSON));
  console.log(`Shapes GeoJSON built: ${features.length} shapes.`);
}
buildShapesGeoJSON().catch(console.error);

// 4. API endpoints
const routeCache = new LRUCache(500);

app.get('/api/shapes', (req, res) => {
  if (!shapesGzip) return res.status(503).json({ error: 'Shapes not ready yet' });
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Cache-Control', 'public, max-age=3600');
  if (req.acceptsEncodings('gzip')) {
    res.setHeader('Content-Encoding', 'gzip');
    res.send(shapesGzip);
  } else {
    res.json(shapesGeoJSON);
  }
});

app.get('/api/lines', (req, res) => res.json(linesMap));

app.get('/api/stations', (req, res) => {
  const prefix = normalize(String(req.query.prefix || '').trim().slice(0, 60));
  if (!prefix) return res.json(stationsMap); // all stations
  const startsWith = (id) => normalize(stationsMap[id].name).startsWith(prefix);
  const ids = trie.searchPrefix(prefix).sort((a, b) =>
    (startsWith(b) - startsWith(a)) || stationsMap[a].name.localeCompare(stationsMap[b].name) ||
    (stationsMap[a].mode === 'LOCAL' ? -1 : 1));
  res.json(ids.map((id) => ({ id, ...stationsMap[id] })));
});

app.get('/api/route', async (req, res) => {
  const { from, to } = req.query;
  const time = String(req.query.time);
  if (!Object.hasOwn(stationsMap, from) || !Object.hasOwn(stationsMap, to)) return res.status(400).json({ error: 'Unknown station' });
  if (!/^\d{1,4}$/.test(time) || +time >= 24 * 60) {
    return res.status(400).json({ error: 'time must be minutes since midnight (0-1439)' });
  }

  const cacheKey = `${from}|${to}|${+time}`;
  const cached = routeCache.get(cacheKey);
  if (cached) return res.json({ ...cached, cached: true });

  const result = await askEngine(from, to, +time);
  if (result.error) return res.status(503).json(result);
  routeCache.set(cacheKey, result);
  res.json(result);
});

app.listen(port, () => {
  console.log(`TransitGraph API listening on port ${port}`);
});
