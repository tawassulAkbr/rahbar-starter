// Capture the real browser page and its actual API response through Edge CDP.
// Start Edge with --remote-debugging-port=9333 before running this script.
import fs from 'node:fs';
import path from 'node:path';

const out = path.resolve('docs/evidence/screenshots/website-actual');
fs.mkdirSync(out, {recursive: true});
const pages = await (await fetch('http://127.0.0.1:9333/json')).json();
const page = pages.find(p => p.type === 'page');
if (!page) throw new Error('No browser page is available');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  ws.addEventListener('open', resolve, {once: true});
  ws.addEventListener('error', reject, {once: true});
});
let next = 0;
const pending = new Map();
ws.addEventListener('message', event => {
  const value = JSON.parse(event.data);
  const callback = pending.get(value.id);
  if (callback) {
    pending.delete(value.id);
    value.error ? callback.reject(new Error(JSON.stringify(value.error))) : callback.resolve(value.result);
  }
});
function call(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++next;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(method + ' timed out')); }, 100000);
    pending.set(id, {resolve: r => {clearTimeout(timer); resolve(r);}, reject});
    ws.send(JSON.stringify({id, method, params}));
  });
}
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const evaluate = expression => call('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
async function screenshot(name) {
  const metrics = await call('Page.getLayoutMetrics');
  const clip = {x: 0, y: 0, width: 1440, height: Math.max(1000, metrics.cssContentSize.height), scale: 1};
  const result = await call('Page.captureScreenshot', {format: 'png', captureBeyondViewport: true, clip});
  fs.writeFileSync(path.join(out, name + '.png'), Buffer.from(result.data, 'base64'));
}
try {
  await call('Emulation.setDeviceMetricsOverride', {width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false});
  await call('Page.navigate', {url: 'http://127.0.0.1:18081'});
  await sleep(2500);
  const loaded = await evaluate("Boolean(document.getElementById('question'))");
  if (!loaded.result.value) throw new Error('The RAHBAR website did not load');
  await screenshot('01-homepage');
  const question = process.argv[2] || 'What is the 2026-27 tuition fee per credit hour for BBA and BS?';
  const captureName = process.argv[3] || '02-query-result';
  await evaluate(`document.getElementById('question').value=${JSON.stringify(question)}; document.getElementById('ask').requestSubmit();`);
  const deadline = Date.now() + 90000;
  while (Date.now() < deadline) {
    await sleep(1000);
    const state = await evaluate("Boolean(document.querySelector('.pending'))");
    if (!state.result.value) break;
  }
  await evaluate("document.querySelectorAll('details').forEach(x=>x.open=true); window.scrollTo(0,0)");
  await screenshot(captureName);
  const body = await evaluate('document.body.innerText');
  fs.writeFileSync(path.join(out, captureName + '.json'), JSON.stringify({captured_at: new Date().toISOString(),
    url: 'http://localhost:18081', question, actual_page_text: body.result.value,
    note: 'Actual browser captures. Website images do not replace required terminal evidence.'}, null, 2));
  console.log('Saved actual website captures to ' + out);
  console.log(body.result.value);
} finally {
  ws.close();
}
