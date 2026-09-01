import fs from 'node:fs/promises';
import WebSocket from './frontend/node_modules/ws/index.js';

const api = 'http://127.0.0.1:18059/api/v1';
const frontend = 'http://127.0.0.1:5173';
const widths = [1440, 1200, 900, 768, 650, 480, 420, 375, 320];
const routes = [
  '/research', '/research/runs', '/research/questions',
  '/library/sources', '/library/documents', '/memory', '/knowledge-graph',
  '/notebook', '/dialogue', '/settings', '/research/runs/not-real',
  '/library/documents/not-real', '/knowledge-graph/not-real', '/notebook/not-real',
];

function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

async function cdp(wsUrl) {
  const socket = new WebSocket(wsUrl);
  const pending = new Map();
  let sequence = 0;
  socket.on('message', (raw) => {
    const message = JSON.parse(raw.toString());
    if (message.id && pending.has(message.id)) {
      pending.get(message.id)(message);
      pending.delete(message.id);
    }
  });
  await new Promise((resolve, reject) => {
    socket.once('open', resolve);
    socket.once('error', reject);
  });
  const send = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    const id = ++sequence;
    pending.set(id, (message) => message.error ? reject(new Error(JSON.stringify(message.error))) : resolve(message.result));
    socket.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
  });
  const browser = await send('Target.getTargets');
  const page = browser.targetInfos.find((target) => target.type === 'page');
  if (!page) throw new Error('No Chrome page target available');
  const attached = await send('Target.attachToTarget', { targetId: page.targetId, flatten: true });
  const sessionId = attached.sessionId;
  const pageSend = (method, params = {}) => send(method, params, sessionId);
  await pageSend('Runtime.enable');
  await pageSend('Log.enable');
  const runtimeErrors = [];
  socket.on('message', (raw) => {
    const message = JSON.parse(raw.toString());
    if (message.method === 'Runtime.exceptionThrown') runtimeErrors.push('exception');
    if (message.method === 'Log.entryAdded' && ['error', 'assert'].includes(message.params.entry.level)) runtimeErrors.push(message.params.entry.text);
  });
  const evaluate = async (expression, awaitPromise = true) => {
    const result = await pageSend('Runtime.evaluate', { expression, awaitPromise, returnByValue: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || 'Browser evaluation failed');
    return result.result?.value;
  };
  const navigate = async (url) => {
    await pageSend('Page.navigate', { url });
    for (let i = 0; i < 80; i += 1) {
      await sleep(75);
      const ready = await evaluate('Boolean(document.querySelector(".app-shell")) || document.readyState === "complete"');
      if (ready) break;
    }
    await sleep(120);
  };
  const setViewport = async (width) => {
    await pageSend('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: false });
  };
  const inspect = async (route) => evaluate(`(() => {
    const visible = (element) => {
      const style = getComputedStyle(element); const rect = element.getBoundingClientRect();
      return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
    };
    const viewport = window.innerWidth;
    const overflow = [...document.querySelectorAll('main, main *, .global-header, .status-bar, .command-dialog, .workspace-mode-selector')]
      .filter(visible).map((element) => ({ tag: element.tagName, className: String(element.className).slice(0, 80), right: Math.round(element.getBoundingClientRect().right), left: Math.round(element.getBoundingClientRect().left) }))
      .filter(({ right, left }) => right > viewport + 1 || left < -1).slice(0, 4);
    return { route: location.pathname, viewport, scrollWidth: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth),
      noHorizontalOverflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) <= viewport + 1,
      overflow, modeTabs: document.querySelectorAll('.workspace-mode-tab').length,
      navButtons: document.querySelectorAll('.left-sidebar button, .left-sidebar a').length,
      alert: document.querySelector('[role="alert"]')?.textContent?.trim() || null,
      status: document.querySelector('[role="status"]')?.textContent?.trim() || null,
      shell: Boolean(document.querySelector('.app-shell')) };
  })()`, true);
  const register = await fetch(`${api}/users`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: `step59_browser_${Date.now()}` }) });
  if (!register.ok) throw new Error(`Registration failed: ${register.status}`);
  const session = await register.json();
  await navigate(`${frontend}/research`);
  await evaluate(`localStorage.setItem('anvikshiki.session', ${JSON.stringify(JSON.stringify({ accessToken: session.access_token, user: { user_id: session.user_id, username: session.username } }))}); location.reload();`);
  await sleep(800);
  const auth = await evaluate(`fetch('${api}/auth/me', {headers: {Authorization: 'Bearer ' + JSON.parse(localStorage.getItem('anvikshiki.session')).accessToken}}).then((response) => response.status)`);
  const routeResults = {};
  for (const width of widths) {
    await setViewport(width);
    routeResults[width] = [];
    for (const route of routes) {
      await navigate(`${frontend}${route}`);
      routeResults[width].push(await inspect(route));
    }
  }
  const interaction = {};
  await setViewport(420);
  await navigate(`${frontend}/research`);
  interaction.mobileMenuBefore = await evaluate('Boolean(document.querySelector(".left-sidebar.mobile-open"))');
  await evaluate('(() => { const button = document.querySelector("button[aria-label=\\"Open navigation\\"]"); if (!button) return false; button.click(); return true; })()');
  await sleep(100);
  interaction.mobileMenuOpen = await evaluate('Boolean(document.querySelector(".left-sidebar.mobile-open"))');
  await evaluate('(() => { const button = document.querySelector("button[aria-label=\\"Close navigation\\"]"); if (!button) return false; button.click(); return true; })()');
  await sleep(100);
  interaction.mobileMenuClosed = await evaluate('!document.querySelector(".left-sidebar.mobile-open")');
  await evaluate('window.dispatchEvent(new KeyboardEvent("keydown", {key: "k", ctrlKey: true, bubbles: true}))');
  await sleep(120);
  interaction.paletteOpen = await evaluate('Boolean(document.querySelector("[role=dialog]"))');
  interaction.paletteOptions = await evaluate('document.querySelectorAll("[role=dialog] [role=option]").length');
  interaction.paletteFits = await evaluate('(() => { const e = document.querySelector("[role=dialog]"); return Boolean(e && e.getBoundingClientRect().right <= innerWidth + 1 && e.getBoundingClientRect().left >= -1); })()');
  await evaluate('document.querySelector("[role=dialog] input")?.dispatchEvent(new KeyboardEvent("keydown", {key: "Escape", bubbles: true}))');
  await sleep(100);
  interaction.paletteClosed = await evaluate('!document.querySelector("[role=dialog]")');
  await navigate(`${frontend}/research`);
  await pageSend('Page.captureScreenshot', { format: 'png' }).then(async ({ data }) => { await fs.writeFile('.step59-420.png', Buffer.from(data, 'base64')); });
  await setViewport(900);
  await navigate(`${frontend}/research`);
  await pageSend('Page.captureScreenshot', { format: 'png' }).then(async ({ data }) => { await fs.writeFile('.step59-900.png', Buffer.from(data, 'base64')); });
  await setViewport(320);
  await navigate(`${frontend}/research`);
  await pageSend('Page.captureScreenshot', { format: 'png' }).then(async ({ data }) => { await fs.writeFile('.step59-320.png', Buffer.from(data, 'base64')); });
  const summary = Object.fromEntries(widths.map((width) => [width, {
    routes: routeResults[width].length,
    overflowFailures: routeResults[width].filter((result) => !result.noHorizontalOverflow).length,
    shellFailures: routeResults[width].filter((result) => !result.shell).length,
    maxScrollWidth: Math.max(...routeResults[width].map((result) => result.scrollWidth)),
    routePaths: [...new Set(routeResults[width].map((result) => result.route))],
  }]));
  const issues = Object.fromEntries(widths.map((width) => [width, routeResults[width].filter((result) => !result.noHorizontalOverflow || !result.shell || result.overflow.length > 0)]));
  console.log(JSON.stringify({ authStatus: auth, widths, summary, interaction, runtimeErrors: runtimeErrors.slice(0, 10), issues }, null, 2));
  socket.close();
}

const version = await fetch('http://127.0.0.1:9259/json/version').then((response) => response.json());
await cdp(version.webSocketDebuggerUrl);
