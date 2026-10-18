'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const core = require('../../linux/extension/core');
test('Docker accepts SSH with explicit port, not TCP or credentials', () => {
    assert.deepEqual(core.dockerEndpoint('ssh://dev@build.example:2222'), {
        endpoint: 'ssh://dev@build.example:2222', destination: 'dev@build.example', port: '2222'
    });
    for (const value of ['tcp://host:2375', 'ssh://root:secret@host', 'ssh://-o@host',
        'ssh://dev@host/path', 'ssh://dev@host?x=1', 'ssh://dev@host\ncommand', 'ssh://host']) {
        assert.throws(() => core.dockerEndpoint(value), undefined, value);
    }
});
test('context name cannot become an option; endpoint stays one argv entry', () => {
    assert.throws(() => core.contextArgs('--help', 'ssh://dev@host'));
    assert.throws(() => core.contextArgs('default', 'ssh://dev@host'));
    assert.deepEqual(core.contextArgs('tablet', 'ssh://dev@host'),
        ['docker', 'context', 'create', 'tablet', '--docker', 'host=ssh://dev@host']);
});
test('launcher keeps spaces, Unicode, metacharacters out of the shell', () => {
    const p = core.paths({VSCODROID_FILES_DIR:'/data/a b',VSCODROID_NATIVE_DIR:'/data/lib'});
    const args = core.guestArgs(p, ['printf', '世界\n$(touch secret)'], '/data/a b/projects');
    assert.equal(args.at(-1), '世界\n$(touch secret)');
    assert.ok(args.includes('/data/a b'));
    assert.equal(core.pythonEnv(p).LD_PRELOAD, '');
    assert.equal(core.pythonEnv(p).NODE_OPTIONS, '');
});
test('dashboard escapes guest output', () => {
    assert.equal(core.escapeHtml('<script>"&\''), '&lt;script&gt;&quot;&amp;&#39;');
});
