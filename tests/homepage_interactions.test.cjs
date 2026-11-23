const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../docs/index.html'), 'utf8');
const source = fs.readFileSync(path.join(__dirname, '../docs/app.js'), 'utf8')
  .replace(/^configure\w+\(\);$/gm, '').replace(/^loadLatestRelease\(\);$/gm, '');

function fixture(platform = 'Win32') {
  const elements = new Map();
  const attributes = (text) => Object.fromEntries([...text.matchAll(/([\w-]+)="([^"]*)"/g)].map((m) => [m[1], m[2]]));
  function element(attrs = {}, text = '') {
    const el = {
      attrs, textContent: text, hidden: false, dataset: {}, events: {},
      classList: { contains: (name) => (attrs.class || '').split(' ').includes(name), add() {} },
      getAttribute: (name) => attrs[name],
      setAttribute(name, value) { attrs[name] = value; },
      addEventListener(name, callback) { this.events[name] = callback; },
      focus() { this.focused = true; },
    };
    for (const [name, value] of Object.entries(attrs)) {
      if (name.startsWith('data-')) el.dataset[name.slice(5)] = value;
    }
    return el;
  }
  for (const match of html.matchAll(/<\w+\b([^>]*\bid="[^"]+"[^>]*)>/g)) {
    const attrs = attributes(match[1]);
    elements.set(attrs.id, element(attrs));
  }
  const groups = [...html.matchAll(/<div class="[^"]*tab-list"([^>]*)>([\s\S]*?)<\/div>/g)].map((match) => {
    const tabs = [...match[2].matchAll(/<button\b([^>]*)>/g)].map((m) => elements.get(attributes(m[1]).id));
    const list = element();
    list.querySelectorAll = () => tabs;
    const group = element({ class: match[1].includes('CLI 운영체제') ? 'setup-console'
      : tabs[0].getAttribute('aria-controls').startsWith('mode-') ? 'product-stage' : '' });
    group.querySelector = () => list;
    return { group, list, tabs };
  });
  const copies = [...html.matchAll(/<button\b([^>]*data-copy="[^"]+"[^>]*)>/g)].map((m) => element(attributes(m[1])));
  for (const match of html.matchAll(/<pre id="([^"]+)"><code[^>]*>(.*?)<\/code><\/pre>/g)) elements.get(match[1]).textContent = match[2];
  const downloads = [...html.matchAll(/<a\b([^>]*data-asset="[^"]+"[^>]*)>/g)].map((m) => element(attributes(m[1])));
  const writes = [];
  const selection = { removeAllRanges() {}, addRange(range) { this.range = range; } };
  const context = vm.createContext({
    document: {
      getElementById: (id) => elements.get(id),
      querySelector: (selector) => selector.startsWith('#') ? elements.get(selector.slice(1)) : element(),
      querySelectorAll: (selector) => ({
        '[data-tabset]': groups.map((g) => g.group),
        '[data-copy]': copies,
        '[data-asset]': [...downloads, ...[...elements.values()].filter((el) => el.dataset.asset)],
      })[selector],
      createRange: () => ({ selectNodeContents(node) { this.node = node; } }),
    },
    navigator: { userAgent: platform, platform, clipboard: { async writeText(text) { writes.push(text); } } },
    window: { getSelection: () => selection },
    Intl, Map, Date, setTimeout: () => 1, clearTimeout() {},
  });
  vm.runInContext(source, context);
  return { context, elements, groups, copies, downloads, writes, selection };
}

test('preview, OS/service and error status tabs switch by click and keyboard', () => {
  const f = fixture();
  f.context.configureTabs();
  assert.equal(f.groups.length, 5);
  for (const { tabs, list, group } of f.groups) {
    assert.equal(list.hidden, false);
    for (let i = 0; i < tabs.length; i++) {
      tabs[i].events.click();
      if (group.classList.contains('product-stage')) {
        assert.equal(group.dataset.previewMode, ['expanded', 'bar', 'tray'][i]);
      }
      tabs.forEach((tab, n) => {
        assert.equal(tab.getAttribute('aria-selected'), String(n === i));
        assert.equal(tab.tabIndex, n === i ? 0 : -1);
        assert.equal(f.elements.get(tab.getAttribute('aria-controls')).hidden, n !== i);
      });
    }
    let prevented = false;
    tabs.at(-1).events.keydown({ key: 'ArrowRight', preventDefault() { prevented = true; } });
    assert.ok(prevented);
    assert.equal(tabs[0].getAttribute('aria-selected'), 'true');
    tabs[0].events.keydown({ key: 'ArrowLeft', preventDefault() {} });
    assert.equal(tabs.at(-1).getAttribute('aria-selected'), 'true');
    tabs.at(-1).events.keydown({ key: 'Home', preventDefault() {} });
    assert.equal(tabs[0].getAttribute('aria-selected'), 'true');
    tabs[0].events.keydown({ key: 'End', preventDefault() {} });
    assert.equal(tabs.at(-1).getAttribute('aria-selected'), 'true');
  }
});

test('OS detection keeps platform downloads and architecture selection connected', () => {
  const base = 'https://github.com/kimNarr/SynapCap/releases/latest/download/';
  for (const [platform, primary, alternate, asset] of [
    ['Win32', base + 'SynapCap-Windows-x64-Setup.exe', '#download', 'SynapCap-Windows-x64-Setup.exe'],
    ['MacIntel', '#download', base + 'SynapCap-Windows-x64-Setup.exe', undefined],
    ['Linux', '#download', 'https://github.com/kimNarr/SynapCap', undefined],
  ]) {
    const f = fixture(platform);
    f.context.configurePrimaryDownload();
    assert.equal(f.elements.get('primary-download').href, primary);
    assert.equal(f.elements.get('alternate-download').href, alternate);
    assert.equal(f.elements.get('primary-download').dataset.asset, asset);
  }
});

test('macOS starts on the macOS CLI guide', () => {
  const f = fixture('MacIntel');
  f.context.configureTabs();
  assert.equal(f.elements.get('cli-windows').hidden, true);
  assert.equal(f.elements.get('cli-macos').hidden, false);
});

test('all 18 copy buttons write only their own command', async () => {
  const f = fixture();
  f.context.configureCommandCopy();
  assert.equal(f.copies.length, 18);
  for (const button of f.copies) {
    await button.events.click();
    assert.equal(f.writes.at(-1), f.elements.get(button.dataset.copy).textContent);
    assert.equal(button.textContent, '복사됨');
  }
});

test('clipboard denial selects the command and announces manual copying', async () => {
  const f = fixture();
  f.context.configureCommandCopy();
  await f.copies[0].events.click();
  f.context.navigator.clipboard.writeText = async () => { throw new Error('denied'); };
  await f.copies[0].events.click();
  assert.equal(f.selection.range.node, f.elements.get('command-1'));
  assert.match(f.elements.get('copy-status').textContent, /직접 복사/);
  assert.equal(f.copies[0].textContent, '직접 복사');
  assert.equal(f.copies[0].dataset.copied, undefined);
});

test('GitHub release assets update download URLs, with missing assets falling back', async () => {
  const f = fixture();
  f.context.configurePrimaryDownload();
  const url = 'https://github.com/kimNarr/SynapCap/releases/download/v1/test.exe';
  f.context.fetch = async () => ({ ok: true, json: async () => ({
    tag_name: 'v1.0.0', published_at: '2026-11-20T00:00:00Z', html_url: 'https://github.com/kimNarr/SynapCap/releases/tag/v1.0.0',
    assets: [{ name: 'SynapCap-Windows-x64-Setup.exe', browser_download_url: url, download_count: 2 }],
  }) });
  await f.context.loadLatestRelease();
  assert.equal(f.elements.get('primary-download').href, url);
  assert.match(f.elements.get('release-status').textContent, /v1.0.0/);
  assert.equal(f.downloads[1].href, 'https://github.com/kimNarr/SynapCap/releases/tag/v1.0.0');
  f.context.fetch = async () => { throw new Error('offline'); };
  await f.context.loadLatestRelease();
  assert.equal(f.elements.get('primary-download').href, url);
  assert.match(f.elements.get('release-meta').textContent, /GitHub Release/);
});
