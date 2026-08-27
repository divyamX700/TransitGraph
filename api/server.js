const express = require('express');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const readline = require('readline');
const PrefixTrie = require('./trie');
const LRUCache = require('./lru');

const app = express();
const port = 3000;

// CORS for all origins (needed for Vercel -> Render communication)
app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET');
  next();
});

// 1. Initialize Prefix Trie for O(m) Autocompletion
const trie = new PrefixTrie();
const stationsMap = {};

const stopsData = fs.readFileSync(path.join(__dirname, '../data/gtfs/stops.txt'), 'utf8');
stopsData.split('\n').forEach((line, i) => {
    if (i === 0 || !line) return;
    const parts = line.split(',');
    if (parts.length >= 4) {
        const id = parts[0];
        const name = parts[1];
        const lat = parseFloat(parts[2]);
        const lon = parseFloat(parts[3]);
        const cleanName = name.replace('\r', '');
        
        stationsMap[id] = { name: cleanName, lat, lon };
        trie.insert(cleanName, id);
    }
});

// 2. Spawn Persistent C++ Worker Process
const engineExt = process.platform === 'win32' ? '.exe' : '';
const enginePath = path.join(__dirname, `../engine/raptor${engineExt}`);
const engine = spawn(enginePath, [path.join(__dirname, '../data/gtfs')]);

// Multiplexing state
let reqCounter = 0;
const pendingRequests = new Map();

// Read JSON responses from stdout
engine.stdout.on('data', (data) => {
    const lines = data.toString().split('\n');
    for (const line of lines) {
        const str = line.trim();
        if (!str) continue;
        
        if (str === "READY") {
            console.log("C++ RAPTOR Engine Ready! Waiting for queries...");
            continue;
        }
        
        // Expected format: ID|JSON
        const pipeIdx = str.indexOf('|');
        if (pipeIdx === -1) {
            console.error("Invalid response format from engine:", str);
            continue;
        }
        
        const id = str.substring(0, pipeIdx);
        const jsonStr = str.substring(pipeIdx + 1);
        
        if (pendingRequests.has(id)) {
            const resolve = pendingRequests.get(id);
            pendingRequests.delete(id);
            try {
                const result = JSON.parse(jsonStr);
                resolve(result);
            } catch (e) {
                console.error("Failed to parse engine output:", jsonStr);
                resolve({ error: "Internal engine error" });
            }
        }
    }
});

engine.stderr.on('data', (data) => {
    console.error(`[C++ Engine Error]: ${data}`);
});

engine.on('close', (code) => {
    console.log(`C++ engine exited with code ${code}`);
});

// 3. Build GeoJSON from shapes.txt once on startup
let shapesGeoJSON = null;

async function buildShapesGeoJSON() {
  const shapesPath = path.join(__dirname, '../data/gtfs/shapes.txt');
  const tripsPath = path.join(__dirname, '../data/gtfs/trips.txt');
  
  // Load trip_id -> route_id mapping
  const tripToRoute = {};
  const tripsContent = fs.readFileSync(tripsPath, 'utf8');
  const tripLines = tripsContent.split('\n');
  const tripHeaders = tripLines[0].trim().split(',');
  const routeIdx = tripHeaders.indexOf('route_id');
  const tripIdx = tripHeaders.indexOf('trip_id');
  const shapeIdx = tripHeaders.indexOf('shape_id');
  
  for (let i = 1; i < tripLines.length; i++) {
    const parts = tripLines[i].split(',');
    if (parts.length > shapeIdx) {
      const shapeId = parts[shapeIdx].trim().replace('\r','');
      const routeId = parts[routeIdx].trim().replace('\r','');
      if (shapeId && routeId) tripToRoute[shapeId] = routeId;
    }
  }
  
  // Stream shapes.txt — group by shape_id
  const shapeCoords = {};
  const fileStream = fs.createReadStream(shapesPath);
  const rl = readline.createInterface({ input: fileStream });
  let firstLine = true;
  
  await new Promise(resolve => {
    rl.on('line', (line) => {
      if (firstLine) { firstLine = false; return; }
      const parts = line.trim().split(',');
      if (parts.length < 4) return;
      const shapeId = parts[0].trim();
      const lat = parseFloat(parts[1]);
      const lon = parseFloat(parts[2]);
      const seq = parseInt(parts[3]);
      if (!shapeId || isNaN(lat) || isNaN(lon)) return;
      if (!shapeCoords[shapeId]) shapeCoords[shapeId] = [];
      shapeCoords[shapeId].push([seq, lon, lat]);
    });
    rl.on('close', resolve);
  });
  
  // Build GeoJSON features
  // IMPORTANT: derive route_id from shape_id name — NOT from trips.txt.
  // trips.txt misfiled some lines (e.g. Uran/Port) under CR_MAIN.
  // Shape names like SHP_CR_PORT_... or SHP_CR_HARBOUR_... are authoritative.
  function routeIdFromShapeId(shapeId) {
    // Format: SHP_<LINE>_<SUBTYPE>_...
    // Known route_ids: CR_MAIN, CR_HARBOUR, CR_TRANS, CR_PORT, WR_MAIN, WR_DAHANU
    const s = shapeId.toUpperCase();
    if (s.includes('WR_DAHANU') || s.includes('DAHANU')) return 'WR_DAHANU';
    if (s.includes('WR_MAIN') || s.includes('_WR_'))   return 'WR_MAIN';
    if (s.includes('CR_HARBOUR') || s.includes('HARBOUR')) return 'CR_HARBOUR';
    if (s.includes('CR_TRANS')   || s.includes('TRANS'))   return 'CR_TRANS';
    // Port line: Uran, CBD Belapur, Nerul area shapes
    if (s.includes('CR_PORT') || s.includes('URAN') ||
        (s.includes('NERUL') && s.includes('URAN'))) return 'CR_PORT';
    if (s.includes('CR_MAIN'))  return 'CR_MAIN';
    // Fallback to trips.txt
    return tripToRoute[shapeId] || null;
  }

  const features = [];
  for (const [shapeId, points] of Object.entries(shapeCoords)) {
    points.sort((a, b) => a[0] - b[0]);
    const coordinates = points.map(([, lon, lat]) => [lon, lat]);
    features.push({
      type: 'Feature',
      properties: {
        shape_id: shapeId,
        route_id: routeIdFromShapeId(shapeId)
      },
      geometry: { type: 'LineString', coordinates }
    });
  }
  
  shapesGeoJSON = { type: 'FeatureCollection', features };
  console.log(`Shapes GeoJSON built: ${features.length} shapes.`);
}

buildShapesGeoJSON().catch(console.error);

// 4. API Endpoints
// Initialize Cache with a capacity of 500 routes
const routeCache = new LRUCache(500);

app.get('/api/shapes', (req, res) => {
  if (!shapesGeoJSON) return res.status(503).json({ error: 'Shapes not ready yet' });
  res.json(shapesGeoJSON);
});

app.get('/api/stations', (req, res) => {
    const prefix = req.query.prefix || '';
    if (!prefix) return res.json(stationsMap); // Return all stations if no prefix
    
    // O(m) Trie Search
    const ids = trie.searchPrefix(prefix);
    const results = ids.map(id => ({ id, ...stationsMap[id] }));
    res.json(results);
});

app.get('/api/route', (req, res) => {
    const { from, to, time } = req.query;
    if (!from || !to || !time) return res.status(400).json({ error: "Missing from, to, or time parameter" });
    
    const cacheKey = `${from}-${to}-${time}`;
    const cachedResult = routeCache.get(cacheKey);
    
    if (cachedResult) {
      console.log(`[API] Cache Hit: ${from} -> ${to} at ${time}`);
      return res.json(cachedResult);
    }
    
    // Assign a unique multiplexing ID
    const reqId = `req_${++reqCounter}`;
    
    console.log(`[API] Routing ${from} -> ${to} at ${time} [ID: ${reqId}] (Cache Miss)`);
    const query = `${reqId}|${from},${to},${time}\n`;
    
    new Promise(resolve => {
        pendingRequests.set(reqId, resolve);
    }).then(result => {
        // Cache the successful result before sending
        if (!result.error) {
          routeCache.set(cacheKey, result);
        }
        res.json(result);
    });
    
    // Fire and forget asynchronously
    engine.stdin.write(query);
});

app.listen(port, () => {
    console.log(`BomRouter API listening on port ${port}`);
});
