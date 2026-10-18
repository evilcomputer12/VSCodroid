'use strict';
const path = require('node:path');
const fs = require('node:fs');

function paths(env = process.env, execPath = process.execPath) {
    const files = env.VSCODROID_FILES_DIR || (env.PREFIX && path.dirname(env.PREFIX));
    const native = env.VSCODROID_NATIVE_DIR || path.dirname(execPath);
    if (!files || !path.isAbsolute(files) || !path.isAbsolute(native)) {
        throw new Error('Linux Edition requires the Android runtime environment');
    }
    const workspace = env.VSCODROID_WORKSPACE || path.join(files, 'projects');
    return { files, native, workspace, home: path.join(files, 'linux/home'),
        rootfs: path.join(files, 'linux/rootfs'), python: path.join(native, 'libpython.so') };
}

function pythonEnv(p) {
    return { HOME: path.join(p.files, 'home'), PATH: '/system/bin',
        TMPDIR: path.join(p.files, 'linux/tmp'), PYTHONHOME: path.join(p.files, 'usr'),
        LD_LIBRARY_PATH: `${p.native}:${p.files}/usr/lib`,
        SSL_CERT_FILE: path.join(p.files, 'usr/etc/tls/cert.pem'),
        LANG: 'C.UTF-8', LD_PRELOAD: '', NODE_OPTIONS: '', BASH_ENV: '' };
}

function runtimeArgs(p, action, args = []) {
    return [path.join(__dirname, 'runtime.py'), '--files', p.files, '--native', p.native,
        '--workspace', p.workspace, action, ...args];
}

function guestArgs(p, command, cwd) {
    return runtimeArgs(p, 'exec', [...(cwd ? ['--cwd', cwd] : []), '--', ...command]);
}

function dockerEndpoint(value) {
    if (typeof value !== 'string' || /[\s\x00-\x1f]/.test(value)) throw new Error('Use ssh://user@host:port');
    const url = new URL(value);
    if (url.protocol !== 'ssh:' || url.password || url.search || url.hash ||
        (url.pathname && url.pathname !== '/') || !/^[A-Za-z_][A-Za-z0-9_.-]*$/.test(url.username) ||
        !/^(?:[A-Za-z0-9][A-Za-z0-9.-]*|\[[0-9a-fA-F:]+\])$/.test(url.hostname) ||
        (url.port && (+url.port < 1 || +url.port > 65535))) {
        throw new Error('Only SSH endpoints without passwords or remote paths are supported');
    }
    return { endpoint: `ssh://${url.username}@${url.hostname}${url.port ? ':' + url.port : ''}`,
        destination: `${url.username}@${url.hostname}`, port: url.port || '22' };
}

function contextArgs(name, endpoint) {
    if (!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$/.test(name) || name === 'default') {
        throw new Error('Choose a context name of 1–63 letters, digits, dot, underscore or dash, other than default');
    }
    const remote = dockerEndpoint(endpoint);
    return ['docker', 'context', 'create', name, '--docker', `host=${remote.endpoint}`];
}

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, x => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[x]));
}
function ownsGuestProcess(argv, p, canonical = fs.realpathSync) {
    // Restored VS Code terminals omit their original creation options. Match
    // only that terminal's live process, using our executable and rootfs.
    try {
        const root = argv.indexOf('-r');
        return root > 0 && argv.includes('--kill-on-exit') &&
            canonical(argv[0]) === canonical(path.join(p.native, 'libproot.so')) &&
            canonical(argv[root + 1]) === canonical(p.rootfs);
    } catch { return false; }
}
function guestProcessIdentity(pid, p, read = file => fs.readFileSync(file, 'utf8'), canonical = fs.realpathSync) {
    if (!Number.isInteger(pid) || pid <= 0) return null;
    try {
        if (!ownsGuestProcess(read(`/proc/${pid}/cmdline`).split('\0'), p, canonical)) return null;
        const stat = read(`/proc/${pid}/stat`);
        const start = stat.slice(stat.lastIndexOf(')') + 2).trim().split(/\s+/)[19];
        return /^\d+$/.test(start || '') ? `${pid}:${start}` : null;
    } catch { return null; }
}
module.exports = { paths, pythonEnv, runtimeArgs, guestArgs, dockerEndpoint, contextArgs, escapeHtml, ownsGuestProcess, guestProcessIdentity };
