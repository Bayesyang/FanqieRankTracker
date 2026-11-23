const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const configs = JSON.parse(fs.readFileSync(path.join(root, 'channels.json'), 'utf8'));
const script = fs.readFileSync(path.join(root, 'js/channels.js'), 'utf8');

async function load(url) {
    const links = [];
    const context = {
        URL, URLSearchParams, Date, Object,
        window: { location: new URL(url) },
        document: {
            title: '番茄男女频',
            querySelectorAll: selector => selector === '[data-channel-switch]'
                ? [{ appendChild: link => links.push(link) }] : [],
            createElement: () => ({ setAttribute(name, value) { this[name] = value; } }),
        },
        fetch: async () => ({ ok: true, json: async () => configs }),
    };
    vm.runInNewContext(script, context);
    const channel = await context.window.RankChannels.init();
    return { channel, links, context };
}

test('male paths and detail links remain in male channel', async () => {
    const { channel, links, context } = await load('https://example.com/FanqieRankTracker/?channel=male');
    assert.equal(channel.dataPath('dates.json'), 'data/male/dates.json');
    assert.equal(channel.apiPath('lastest/all.json'), 'api/male/lastest/all.json');
    assert.equal(channel.snapshotPath('2026-11-23'), 'data/male/fanqie_male_new_ranks_20261123.json');
    assert.equal(channel.url('book.html?id=123'), '/FanqieRankTracker/book.html?id=123&channel=male');
    assert.equal(context.document.title, '番茄男频');
    assert.equal(links[1]['aria-current'], 'page');
});

test('legacy links default to female without moving its data', async () => {
    const { channel } = await load('https://example.com/FanqieRankTracker/index.html');
    assert.equal(channel.id, 'female');
    assert.equal(channel.dataPath('dates.json'), 'data/dates.json');
    assert.equal(channel.apiPath('lastest.json'), 'api/lastest.json');
});

test('invalid or inherited channel keys cannot select arbitrary paths', async () => {
    for (const key of ['../../male', 'toString', '__proto__']) {
        const { channel } = await load(`https://example.com/index.html?channel=${key}`);
        assert.equal(channel.id, 'female');
    }
});

test('switching from book detail returns to selected channel homepage', async () => {
    const { links } = await load('https://example.com/FanqieRankTracker/book.html?id=123&channel=male');
    assert.equal(links[0].href, '/FanqieRankTracker/index.html?channel=female');
    assert.equal(links[1].href, '/FanqieRankTracker/index.html?channel=male');
});

test('switching trend channels clears previous channel category', async () => {
    const { links } = await load('https://example.com/trend.html?channel=female&type=古风世情');
    assert.equal(links[1].href, '/trend.html?channel=male');
});
