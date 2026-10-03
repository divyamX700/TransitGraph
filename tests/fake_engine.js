// Stand-in for the C++ engine, used by api.test.js to check how the API behaves when the engine
// misbehaves. Answers every query with no routes, except: target VIRAR kills it, target KALYAN
// is never answered.
const readline = require('readline');

console.log('READY');
readline.createInterface({ input: process.stdin }).on('line', (line) => {
  const [id, query] = line.split('|');
  const target = query.split(',')[1];
  if (target === 'VIRAR') process.exit(3);
  if (target === 'KALYAN') return;
  console.log(`${id}|{"cached": false, "routes": []}`);
});
