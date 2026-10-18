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
test('regular Linux user is passed as a distinct runtime option', () => {
    const p = core.paths({VSCODROID_FILES_DIR:'/data/a b',VSCODROID_NATIVE_DIR:'/data/lib'});
    const args = core.guestArgs(p, ['/bin/bash','-l'], '/data/a b/projects', 'developer');
    assert.deepEqual(args.slice(-8), ['exec','--cwd','/data/a b/projects','--user','developer','--','/bin/bash','-l']);
});
test('dashboard escapes guest output', () => {
    assert.equal(core.escapeHtml('<script>"&\''), '&lt;script&gt;&quot;&amp;&#39;');
});
test('restored terminals are owned only by this runtime executable and rootfs', () => {
    const p = {native:'/apk/lib',rootfs:'/data/user/0/app/files/linux/rootfs'};
    const canonical = value => value.replace('/data/data/', '/data/user/0/');
    const args = ['/apk/lib/libproot.so','--kill-on-exit','-r','/data/data/app/files/linux/rootfs'];
    assert.equal(core.ownsGuestProcess(args,p,canonical),true);
    assert.equal(core.ownsGuestProcess(['/other/libproot.so',...args.slice(1)],p,canonical),false);
    assert.equal(core.ownsGuestProcess([...args.slice(0,3),'/another/rootfs'],p,canonical),false);
    assert.equal(core.ownsGuestProcess(['/bin/bash'],p,canonical),false);
    assert.equal(core.ownsGuestProcess(args,p,()=>{throw new Error('Process exited');}),false);
});
test('cleanup identity rejects PID reuse, exited processes and non-runtime terminals', () => {
    const p={native:'/apk/lib',rootfs:'/linux/rootfs'};
    let start='123', command='/apk/lib/libproot.so\0--kill-on-exit\0-r\0/linux/rootfs\0';
    const read = file => file.endsWith('cmdline') ? command : `42 (proot (worker)) ${Array(19).fill('0').join(' ')} ${start} 0`;
    const canonical = value => value;
    assert.equal(core.guestProcessIdentity(42,p,read,canonical),'42:123');
    start='456'; assert.equal(core.guestProcessIdentity(42,p,read,canonical),'42:456');
    command='/bin/bash\0'; assert.equal(core.guestProcessIdentity(42,p,read,canonical),null);
    assert.equal(core.guestProcessIdentity(-1,p,read,canonical),null);
    assert.equal(core.guestProcessIdentity(42,p,()=>{throw new Error('Exited');},canonical),null);
});
