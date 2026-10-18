'use strict';
const vscode = require('vscode');
const allowed = new Set(['workbench.action.showCommands','workbench.action.quickOpen',
    'workbench.action.findInFiles','workbench.action.files.save','workbench.action.toggleSidebarVisibility',
    'workbench.action.togglePanel','workbench.action.terminal.toggleTerminal']);
function activate(context) {
    const channel = new BroadcastChannel('vscodroid-linux-commands');
    channel.onmessage = event => {
        if (allowed.has(event.data?.command)) vscode.commands.executeCommand(event.data.command);
    };
    context.subscriptions.push({dispose:() => channel.close()});
}
module.exports = {activate};
