const http = require('http');
const fs = require('fs');
const path = require('path');

// Read all station IDs to pick random ones
const stopsData = fs.readFileSync(path.join(__dirname, '../data/gtfs/stops.txt'), 'utf8');
const stationIds = [];
stopsData.split('\n').forEach((line, i) => {
    if (i === 0 || !line) return;
    const parts = line.split(',');
    if (parts.length >= 1) {
        stationIds.push(parts[0]);
    }
});

const NUM_REQUESTS = 1000;
const CONCURRENCY = 10;
const latencies = [];
let completed = 0;
let errors = 0;

function getRandomStation() {
    return stationIds[Math.floor(Math.random() * stationIds.length)];
}

function getRandomTime() {
    // Random minute between 0 (00:00) and 1439 (23:59)
    return Math.floor(Math.random() * 1440);
}

function makeRequest(url) {
    return new Promise((resolve) => {
        const start = performance.now();
        http.get(url, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                const end = performance.now();
                if (res.statusCode === 200) {
                    latencies.push(end - start);
                } else {
                    errors++;
                }
                resolve();
            });
        }).on('error', (err) => {
            errors++;
            resolve();
        });
    });
}

async function runBenchmark() {
    console.log(`Starting benchmark with ${NUM_REQUESTS} requests at concurrency ${CONCURRENCY}...`);
    console.log(`Total stations loaded: ${stationIds.length}`);
    const startTotal = performance.now();

    for (let i = 0; i < NUM_REQUESTS; i += CONCURRENCY) {
        const batch = [];
        for (let j = 0; j < CONCURRENCY && i + j < NUM_REQUESTS; j++) {
            const from = getRandomStation();
            let to = getRandomStation();
            while (from === to) {
                to = getRandomStation();
            }
            const time = getRandomTime();
            // Random parameters ensure cache misses for most requests
            const url = `http://localhost:3000/api/route?from=${from}&to=${to}&time=${time}`;
            batch.push(makeRequest(url));
        }
        await Promise.all(batch);
        completed += batch.length;
        process.stdout.write(`\rCompleted: ${completed}/${NUM_REQUESTS}`);
    }

    const endTotal = performance.now();
    console.log('\n\n--- Benchmark Results ---');
    console.log(`Total Time: ${((endTotal - startTotal) / 1000).toFixed(2)} seconds`);
    console.log(`Total Requests: ${NUM_REQUESTS}`);
    console.log(`Errors: ${errors}`);

    if (latencies.length > 0) {
        latencies.sort((a, b) => a - b);
        const sum = latencies.reduce((a, b) => a + b, 0);
        const avg = sum / latencies.length;
        const p50 = latencies[Math.floor(latencies.length * 0.5)];
        const p95 = latencies[Math.floor(latencies.length * 0.95)];
        const p99 = latencies[Math.floor(latencies.length * 0.99)];

        console.log(`Average Latency: ${avg.toFixed(2)} ms`);
        console.log(`p50 Latency:     ${p50.toFixed(2)} ms`);
        console.log(`p95 Latency:     ${p95.toFixed(2)} ms`);
        console.log(`p99 Latency:     ${p99.toFixed(2)} ms`);
        console.log(`Min Latency:     ${latencies[0].toFixed(2)} ms`);
        console.log(`Max Latency:     ${latencies[latencies.length - 1].toFixed(2)} ms`);
    }
}

runBenchmark();
