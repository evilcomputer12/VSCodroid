'use strict';
const vscode = require('vscode');
const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const crypto = require('node:crypto');
const core = require('./core');

function activate(context) {
    let p;
    try { p = core.paths(); } catch { return; }
    const output = vscode.window.createOutputChannel('VSCodroid Linux');
    const sessions = new Set();
    const jobs = new Set();
    let panel, busy = false, health = null;
    const status = vscode.window.createStatusBarItem('linuxRuntime', vscode.StatusBarAlignment.Left, 20);
    status.command = 'vscodroid.linux.dashboard';
    status.name = 'Debian Linux';
    status.show();
    fs.mkdirSync(path.join(p.files, 'linux/tmp'), {recursive:true});
    fs.mkdirSync(p.workspace, {recursive:true});
    const installed = () => fs.existsSync(path.join(p.files, 'linux/state.json'));
    const trusted = () => {
        if (!vscode.workspace.isTrusted) throw new Error('Trust this workspace before running Linux commands.');
    };
    const update = () => {
        status.text = busy ? '$(sync~spin) Linux setup' : installed() ? '$(terminal-linux) Debian' : '$(cloud-download) Set up Linux';
        status.tooltip = `${sessions.size} managed Linux terminals · ${installed() ? 'Debian installed' : 'Setup required'}`;
        if (panel) render();
    };
    function stopJob(child) {
        // Only a process group created by this extension. Never scan or kill by name.
        try { process.kill(-child.pid, 'SIGTERM'); } catch { child.kill('SIGTERM'); }
    }
    function run(action, args = [], timeout = 600000, progress, token) {
        return new Promise((resolve, reject) => {
            const child = cp.spawn(p.python, core.runtimeArgs(p, action, args), {
                env: core.pythonEnv(p), cwd: p.workspace, detached: true, stdio: ['ignore','pipe','pipe']
            });
            jobs.add(child);
            let text = '', cancelled = false, expired = false, line = '';
            const timer = setTimeout(() => { expired = true; stopJob(child); }, timeout);
            const cancellation = token?.onCancellationRequested(() => { cancelled = true; stopJob(child); });
            const collect = data => {
                const chunk = data.toString();
                output.append(chunk);
                text = (text + chunk).slice(-131072);
                line += chunk;
                const lines = line.split('\n'); line = lines.pop().slice(-8192);
                for (const entry of lines) {
                    try {
                        const event = JSON.parse(entry);
                        if (event.message) progress?.report({message: event.message +
                            (event.total ? ` (${Math.floor(event.bytes / event.total * 100)}%)` : '')});
                    } catch { /* apt emits ordinary text, retained in the output channel */ }
                }
            };
            child.stdout.on('data', collect); child.stderr.on('data', collect);
            const cleanup = () => { clearTimeout(timer); cancellation?.dispose(); jobs.delete(child); };
            child.once('error', error => { cleanup(); reject(error); });
            child.once('close', code => {
                cleanup();
                if (cancelled) reject(new Error('Setup cancelled. Run setup again to retry; your home and workspace remain.'));
                else if (expired) reject(new Error('Linux command timed out. See VSCodroid Linux output.'));
                else if (code !== 0) reject(new Error(`Linux command exited ${code}. ${text.slice(-1800)}`));
                else resolve(text);
            });
        });
    }
    async function operation(title, action) {
        trusted();
        if (busy) throw new Error('A setup operation is already running.');
        busy = true; update(); output.show(true);
        try {
            await vscode.window.withProgress({location:vscode.ProgressLocation.Notification, title, cancellable:true},
                (progress, token) => run(action, [], action === 'toolchains' ? 4200000 : 900000, progress, token));
            await diagnostics();
        } finally { busy = false; update(); }
    }
    function terminalOptions(command = ['/bin/bash', '-l']) {
        trusted();
        if (!installed()) throw new Error('Open Linux: Setup and Runtime Dashboard and install Debian first.');
        const folder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        const cwd = folder && (folder === p.workspace || folder.startsWith(p.workspace + path.sep) ||
            folder === p.home || folder.startsWith(p.home + path.sep)) ? folder : p.workspace;
        return {name:'Debian ARM64', shellPath:p.python, shellArgs:core.guestArgs(p, command, cwd),
            cwd, env:core.pythonEnv(p), strictEnv:true, iconPath:new vscode.ThemeIcon('terminal-linux')};
    }
    function openTerminal(command) {
        const terminal = vscode.window.createTerminal(terminalOptions(command));
        sessions.add(terminal); terminal.show(); update(); return terminal;
    }
    async function diagnostics() {
        trusted();
        const text = await run('diagnostics', [], 45000);
        health = JSON.parse(text);
        health.checkedAt = new Date().toISOString();
        update();
        if (health.exitCode && health.exitCode !== 0) {
            vscode.window.showWarningMessage('Debian is installed, but its runtime probe failed. Open the Linux dashboard for details.');
        }
        return health;
    }
    async function dockerSetup() {
        trusted();
        const endpoint = await vscode.window.showInputBox({title:'Remote Docker · SSH endpoint',
            prompt:'Use an existing SSH key in Linux home/.ssh. The Docker daemon stays on your remote host.',
            placeHolder:'ssh://developer@build-host:22',
            validateInput:value => { try { core.dockerEndpoint(value); } catch (e) { return e.message; } }});
        if (!endpoint) return;
        const name = await vscode.window.showInputBox({title:'Docker context name', value:'tablet-remote',
            validateInput:value => { try { core.contextArgs(value, endpoint); } catch (e) { return e.message; } }});
        if (!name) return;
        // No passwords, keys or tokens enter extension state.
        await run('exec', ['--', ...core.contextArgs(name, endpoint)], 30000);
        await context.globalState.update('dockerContext', name);
        await context.globalState.update('dockerEndpoint', endpoint);
        const remote = core.dockerEndpoint(endpoint);
        const action = await vscode.window.showInformationMessage(
            `Context ${name} created. Verify the SSH host fingerprint in the terminal before connecting. Remote bind mounts use paths on the remote host.`,
            'Verify SSH host', 'Check Docker');
        if (action === 'Verify SSH host') openTerminal(['ssh', '-o', 'StrictHostKeyChecking=ask',
            '-o', 'PreferredAuthentications=publickey', '-p', remote.port, remote.destination, 'true']);
        if (action === 'Check Docker') await dockerStatus();
        update();
    }
    async function dockerStatus() {
        trusted();
        const name = context.globalState.get('dockerContext');
        if (!name) throw new Error('Configure a remote Docker context first.');
        output.show(true);
        await run('exec', ['--', 'docker', '--context', name, 'info', '--format', '{{json .ServerVersion}}'], 30000);
        await run('exec', ['--', 'docker', 'compose', 'version'], 30000);
        vscode.window.showInformationMessage(`Docker context ${name} is reachable; Compose is available.`);
    }
    async function configureClangd() {
        trusted();
        const folder = vscode.workspace.workspaceFolders?.[0];
        if (!folder || ![p.workspace, p.home].some(base =>
            folder.uri.fsPath === base || folder.uri.fsPath.startsWith(base + path.sep))) {
            throw new Error('Open the shared Linux workspace or Linux home before configuring clangd.');
        }
        await run('exec', ['--', '/usr/bin/clangd', '--version'], 30000);
        const id = 'llvm-vs-code-extensions.vscode-clangd';
        if (!vscode.extensions.getExtension(id)) {
            await vscode.commands.executeCommand('workbench.extensions.installExtension', id);
        }
        const config = vscode.workspace.getConfiguration('clangd', folder.uri);
        // Launch an APK-native interpreter; a script in writable app storage is
        // not itself executable on modern Android. No shell or external service.
        await config.update('path', p.python, vscode.ConfigurationTarget.WorkspaceFolder);
        await config.update('arguments', core.guestArgs(p, ['/usr/bin/clangd', '--background-index', '-j=2'],
            folder.uri.fsPath), vscode.ConfigurationTarget.WorkspaceFolder);
        await config.update('checkUpdates', false, vscode.ConfigurationTarget.WorkspaceFolder);
        await config.update('useScriptAsExecutable', false, vscode.ConfigurationTarget.WorkspaceFolder);
        await vscode.commands.executeCommand('clangd.restart');
        vscode.window.showInformationMessage('Linux clangd configured for this folder. Open a C/C++ file. Rerun this command after an APK update to refresh Android executable paths.');
    }
    function shortcuts() {
        const lines = [
            'Command palette: Ctrl+Shift+P', 'Quick open: Ctrl+P', 'Search files: Ctrl+Shift+F',
            'Save: Ctrl+S', 'Undo / redo: Ctrl+Z / Ctrl+Shift+Z',
            'Select text: Shift+arrows; Ctrl+Shift+arrows selects words',
            'Editor copy / paste: Ctrl+C / Ctrl+V',
            'Terminal copy / paste: Ctrl+Shift+C / Ctrl+Shift+V',
            'Terminal Ctrl+C sends interrupt when no text is selected.',
            'Use terminal title menu Copy / Paste on touch screens. Long-press for touch selection.',
            'Multiline paste uses the terminal’s normal confirmation and bracketed-paste handling.',
            'Physical Ctrl, Alt, Shift and Meta are preserved. Android may reserve system Meta shortcuts.',
            'S Pen uses the same pointer and selection path as touch.'
        ];
        vscode.workspace.openTextDocument({content:lines.join('\n\n'), language:'plaintext'})
            .then(doc => vscode.window.showTextDocument(doc));
    }
    function render() {
        if (!panel) return;
        const nonce = crypto.randomBytes(16).toString('hex');
        const e = core.escapeHtml;
        const actions = [
            ['install','1 · Install Debian'], ['diagnostics','2 · Check runtime'], ['toolchains','3 · Install toolchains'],
            ['terminal','New Linux terminal'], ['workspace','Open workspace'], ['home','Open Linux home'],
            ['clangd','Set up C/C++ language server'],
            ['docker','Configure Docker SSH'], ['dockerStatus','Check Docker'], ['shortcuts','Keyboard help'],
            ['cleanCache','Clean APT cache'], ['stop','Stop sessions'], ['restart','Restart terminal']
        ];
        panel.webview.html = `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}';">
<style nonce="${nonce}">
body{font-family:var(--vscode-font-family);color:var(--vscode-foreground);background:var(--vscode-editor-background);padding:24px;max-width:1000px;margin:auto;line-height:1.5}
h1{font-size:28px;margin-bottom:8px} .muted{color:var(--vscode-descriptionForeground)} .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:24px 0}
button{background:var(--vscode-button-background);color:var(--vscode-button-foreground);border:0;border-radius:5px;padding:16px;text-align:left;font:inherit;min-height:48px;cursor:pointer}button:hover{background:var(--vscode-button-hoverBackground)}button:focus{outline:2px solid var(--vscode-focusBorder);outline-offset:3px}button:disabled{opacity:.5;cursor:wait}
section{border:1px solid var(--vscode-panel-border);border-radius:8px;padding:20px;margin:16px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-family:var(--vscode-editor-font-family)}code{overflow-wrap:anywhere}h2{font-size:18px} @media(max-width:500px){body{padding:12px}.cards{grid-template-columns:1fr 1fr}button{padding:12px;font-size:13px}}
</style></head><body>
<p class="muted">VSCodroid Linux Edition · ARM64</p><h1>Your Debian development environment</h1>
<p>${busy ? 'Setup is running. Follow progress in the notification or Linux output.' : installed() ? 'Debian is installed. Run the health check to verify it on this device.' : 'Install a verified Debian image, check compatibility, then add your development tools.'}</p>
<p class="muted">Requires 4 GiB free and an internet connection during setup. Home and workspace persist between sessions. Rootless Linux shares Android’s kernel.</p>
<div class="cards">${actions.map(([action,label]) => `<button data-action="${action}" ${busy && ['install','toolchains','cleanCache'].includes(action) ? 'disabled' : ''}>${e(label)}</button>`).join('')}</div>
<section><h2>Runtime health</h2><p>${sessions.size} managed terminals · ${jobs.size} active operations</p><pre>${e(health ? JSON.stringify(health,null,2) : 'No probe has run yet. Select Check runtime.')}</pre></section>
<section><h2>Persistent storage</h2><p>Workspace: <code>${e(p.workspace)}</code></p><p>Linux home: <code>${e(p.home)}</code></p><p>Clean APT cache removes downloaded package archives only. App uninstall removes this app’s private Linux files; back up projects first.</p></section>
<section><h2>Remote Docker</h2><p>Context: ${e(context.globalState.get('dockerContext') || 'Not configured')}</p><p>Docker Engine runs on your SSH host. Build contexts are uploaded; bind mounts refer to the remote host’s filesystem. SSH keys stay in your private home. No local Docker Engine is provided.</p></section>
<section><h2>Recovery</h2><p>A failed download or extraction can be retried. Existing installations, home and projects are never replaced by setup. If the runtime probe fails, its error appears above. Android process or executable restrictions are reported without weakening device security.</p></section>
<script nonce="${nonce}">const api=acquireVsCodeApi();document.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>api.postMessage({action:b.dataset.action})));</script></body></html>`;
    }
    function dashboard() {
        if (panel) { panel.reveal(); update(); return; }
        panel = vscode.window.createWebviewPanel('vscodroidLinux', 'Linux Runtime', vscode.ViewColumn.One,
            {enableScripts:true, localResourceRoots:[], retainContextWhenHidden:true});
        panel.onDidDispose(() => { panel = undefined; });
        panel.webview.onDidReceiveMessage(message => {
            const allowed = new Set(['install','diagnostics','toolchains','terminal','workspace','home',
                'docker','dockerStatus','shortcuts','cleanCache','stop','restart','clangd']);
            if (allowed.has(message?.action)) vscode.commands.executeCommand(`vscodroid.linux.${message.action}`);
        });
        render();
    }
    const commands = {
        dashboard, shortcuts, diagnostics, docker:dockerSetup, dockerStatus, clangd:configureClangd,
        install:() => operation('Installing Debian ARM64', 'install'),
        toolchains:() => operation('Installing Linux development tools', 'toolchains'),
        terminal:() => openTerminal(),
        workspace:() => { trusted(); return vscode.commands.executeCommand('vscode.openFolder', vscode.Uri.file(p.workspace), false); },
        home:() => { trusted(); fs.mkdirSync(p.home,{recursive:true}); return vscode.commands.executeCommand('vscode.openFolder', vscode.Uri.file(p.home), false); },
        copy:() => vscode.commands.executeCommand('workbench.action.terminal.copySelection'),
        paste:() => vscode.commands.executeCommand('workbench.action.terminal.paste'),
        stop:() => { for (const terminal of sessions) terminal.dispose(); for (const job of jobs) stopJob(job); update(); },
        restart:() => { trusted(); commands.stop(); return openTerminal(); },
        cleanCache:async () => { trusted(); if (busy) throw new Error('Wait for setup to finish.'); await run('exec',['--','apt-get','clean'],30000); await diagnostics(); }
    };
    for (const [name, handler] of Object.entries(commands)) {
        context.subscriptions.push(vscode.commands.registerCommand(`vscodroid.linux.${name}`, async () => {
            try { return await handler(); } catch (error) {
                output.appendLine(error.stack || String(error));
                vscode.window.showErrorMessage(error.message || String(error));
            }
        }));
    }
    context.subscriptions.push(vscode.window.registerTerminalProfileProvider('vscodroid.linux.terminal', {
        provideTerminalProfile:() => new vscode.TerminalProfile(terminalOptions())
    }));
    context.subscriptions.push(vscode.window.onDidOpenTerminal(terminal => {
        if (terminal.creationOptions?.shellPath === p.python && terminal.name === 'Debian ARM64') sessions.add(terminal);
        update();
    }));
    context.subscriptions.push(vscode.window.onDidCloseTerminal(terminal => {sessions.delete(terminal); update();}));
    context.subscriptions.push(vscode.tasks.registerTaskProvider('vscodroid-linux', {
        provideTasks:() => [],
        resolveTask:task => {
            trusted();
            const def = task.definition;
            if (typeof def.command !== 'string' || !Array.isArray(def.args || []) ||
                !(def.args || []).every(x => typeof x === 'string')) throw new Error('Invalid Linux task command or arguments');
            return new vscode.Task(def, task.scope, task.name, 'Linux', new vscode.ProcessExecution(p.python,
                core.guestArgs(p,[def.command,...(def.args || [])],def.cwd), {cwd:p.workspace,env:core.pythonEnv(p)}), task.problemMatchers);
        }
    }));
    context.subscriptions.push(status, output, {dispose:() => {
        // Terminals are owned by VS Code and can survive extension-host reloads.
        for (const job of jobs) stopJob(job);
        panel?.dispose();
    }});
    update();
    if (!context.globalState.get('welcomed')) {
        context.globalState.update('welcomed', true);
        dashboard();
    }
}
module.exports = { activate };
