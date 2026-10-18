'use strict';
// Called only when starting a new server. Never replaces a live editor tree.
const fs = require('fs');
const path = require('path');
const ID = /^[a-f0-9]{64}$/;
const read = (file, fallback = {}) => { try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return fallback; } };
function atomic(file, value) {
    fs.writeFileSync(file + '.tmp', JSON.stringify(value));
    fs.renameSync(file + '.tmp', file);
}
function select(server, native) {
    const bundled = path.join(server, 'vscode-reh');
    const root = path.join(server, 'ide-updates');
    fs.mkdirSync(root, {recursive:true});
    const base = read(path.join(bundled, 'product.json'));
    const app = read(path.join(server, 'ide-compat.json')).buildId;
    let state = read(path.join(root, 'state.json'));
    // A newly installed APK defines a new compatibility baseline.
    if (state.baseCommit !== base.commit || state.baseApp !== app) state = {baseCommit:base.commit, baseApp:app};
    const treeFor = id => path.join(root, 'versions', id, 'vscode-reh');
    const valid = id => ID.test(id || '') &&
        read(path.join(root, 'versions', id, 'verified.json')).sha256 === id &&
        fs.existsSync(path.join(treeFor(id), 'out/server-main.js'));
    if (state.trial) {
        if (!fs.existsSync(path.join(root, 'healthy-' + state.trial))) {
            state.blocked = [...new Set([...(state.blocked || []), state.trial])];
            state.active = valid(state.previous) ? state.previous : null;
            atomic(path.join(root, 'status.json'), {message:'The IDE update did not finish starting. Restored the previous IDE.', rolledBack:true});
        }
        delete state.trial;
    }
    if (state.pending === 'bundled') {
        state.previous = state.active;
        state.active = null;
        delete state.pending;
    } else if (valid(state.pending)) {
        state.previous = state.active;
        state.active = state.pending;
        state.trial = state.pending;
        // Re-testing a previously staged tree must earn its health marker again.
        fs.rmSync(path.join(root, 'healthy-' + state.trial), {force:true});
        delete state.pending;
    }
    if (!valid(state.active)) state.active = null;
    let tree = state.active ? treeFor(state.active) : bundled;
    if (state.active) {
        try {
            // APK installation changes nativeLibraryDir. Rebind on every start.
            fs.rmSync(path.join(tree, 'node'), {force:true});
            fs.symlinkSync(path.join(native, 'libnode.so'), path.join(tree, 'node'));
            for (const dir of ['@vscode/ripgrep-universal/bin/linux-arm64', '@vscode/ripgrep/bin']) {
                const target = path.join(tree, 'node_modules', dir, 'rg');
                fs.mkdirSync(path.dirname(target), {recursive:true});
                fs.rmSync(target, {force:true});
                fs.symlinkSync(path.join(native, 'libripgrep.so'), target);
            }
            const aliases = [
                [path.join(tree, 'node_modules/@vscode/ripgrep-universal/bin/android-arm64'), 'linux-arm64'],
                [path.join(tree, 'extensions/copilot/node_modules/@github/copilot-android-arm64/sdk'), '../copilot/sdk']
            ];
            for (const [target, source] of aliases) {
                fs.mkdirSync(path.dirname(target), {recursive:true});
                try { fs.lstatSync(target); } catch (error) {
                    if (error.code !== 'ENOENT') throw error;
                    fs.symlinkSync(source, target);
                }
            }
        } catch (error) {
            state.blocked = [...new Set([...(state.blocked || []), state.active])];
            state.active = null;
            delete state.trial;
            tree = bundled;
            atomic(path.join(root, 'status.json'), {message:'Could not prepare the IDE update. Using the bundled IDE: ' + error.message, rolledBack:true});
        }
    }
    atomic(path.join(root, 'state.json'), state);
    const product = read(path.join(tree, 'product.json'));
    atomic(path.join(server, 'ide-running.json'), {id:state.active, version:product.version,
        relativeRoot:path.relative(server, tree), baseCommit:base.commit});
    return {tree, trial:state.trial, root};
}
function markHealthy(server, runningRoot) {
    const running = read(path.join(server, 'ide-running.json'));
    if (!ID.test(running.id || '') || running.relativeRoot !== path.join('ide-updates', 'versions', running.id, 'vscode-reh')) return;
    // Android exposes private storage through both /data/data and /data/user/0.
    // Node's entry path and Android's filesDir can use different aliases.
    try {
        if (!runningRoot || fs.realpathSync(path.join(server, running.relativeRoot)) !== fs.realpathSync(runningRoot)) return;
    } catch { return; }
    fs.writeFileSync(path.join(server, 'ide-updates', 'healthy-' + running.id), 'Editor extension host activated\n');
}
function guardTrial(selection, child, timeout = 180000) {
    if (!selection.trial) return;
    const timer = setTimeout(() => {
        if (!fs.existsSync(path.join(selection.root, 'healthy-' + selection.trial))) {
            child.kill('SIGTERM');
            const kill = setTimeout(() => child.kill('SIGKILL'), 800);
            kill.unref();
        }
    }, timeout);
    timer.unref();
    child.once('exit', () => clearTimeout(timer));
}
function startTrialGuard(root, id, timeout = 180000) {
    const timer = setTimeout(() => {
        if (!fs.existsSync(path.join(root, 'healthy-' + id))) process.exit(70);
    }, timeout);
    timer.unref();
    return timer;
}
// The editor can survive a killed bootstrap and be adopted by a new Android
// process. Keep the trial deadline in that survivor as well as its parent.
const trial = process.env.VSCODROID_IDE_TRIAL_ID;
const trialRoot = process.env.VSCODROID_IDE_TRIAL_DIR;
delete process.env.VSCODROID_IDE_TRIAL_ID;
delete process.env.VSCODROID_IDE_TRIAL_DIR;
if (ID.test(trial || '') && trialRoot === path.join(__dirname, 'ide-updates')) {
    process.execArgv = process.execArgv.filter(arg => arg !== `--require=${__filename}`);
    startTrialGuard(trialRoot, trial);
}
module.exports = {select, markHealthy, guardTrial, startTrialGuard};
