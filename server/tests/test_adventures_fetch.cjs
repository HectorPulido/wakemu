const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '../objectives-service/static/adventures.js'), 'utf8');

for (const prefix of ['', '/adventures']) {
  test(`API requests preserve same-origin authentication at ${prefix || '/'} without replacing the player bearer`, async () => {
    const calls = [];
    const context = {
      document: { querySelectorAll: () => [], addEventListener: () => {} },
      sessionStorage: { getItem: () => 'player-session', setItem() {}, removeItem() {} },
      location: { pathname: `${prefix}/player/` },
      AbortController, setTimeout, clearTimeout,
      fetch: async (url, options) => {
        calls.push({ url, options });
        return { ok: true, json: async () => ({ status: 'ok' }) };
      },
    };
    // Expose the real request helper while suppressing DOM rendering and polling.
    vm.runInNewContext(source.replace(/  start\(\);\n\}\)\(\);\s*$/, '  globalThis.request = api;\n})();'), context);
    for (const [endpoint, options] of [
      ['/session', { method: 'POST', body: '{"token":"launch"}' }],
      ['/adventures', {}],
      ['/actions', { method: 'POST', body: '{"action_key":"travel"}' }],
      ['/actions/receipt', {}],
    ]) {
      await context.request(endpoint, options);
      const call = calls.at(-1);
      assert.equal(call.url, `${prefix}/player-api${endpoint}`);
      assert.equal(call.options.credentials, 'same-origin');
      assert.equal(call.options.headers.Authorization, 'Bearer player-session');
      assert.equal(call.options.referrerPolicy, 'no-referrer');
      assert.equal(call.options.cache, 'no-store');
      if (options.body) assert.equal(call.options.headers['Content-Type'], 'application/json');
    }
  });
}
