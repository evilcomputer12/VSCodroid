'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const {spawnSync} = require('node:child_process');
const loader = require('../../android/app/src/main/assets/ide-loader');
function fixture(t) {
    const server = fs.mkdtempSync(path.join(os.tmpdir(), 'ide-loader-'));
    t.after(() => fs.rmSync(server,{recursive:true,force:true}));
    const write = (p,v) => {const f=path.join(server,p);fs.mkdirSync(path.dirname(f),{recursive:true});fs.writeFileSync(f,JSON.stringify(v));};
    write('vscode-reh/product.json',{version:'1.139.1',commit:'base'});
    write('ide-compat.json',{buildId:'19'});
    const id='a'.repeat(64);
    write(`ide-updates/versions/${id}/verified.json`,{sha256:id});
    write(`ide-updates/versions/${id}/vscode-reh/product.json`,{version:'1.140.0',commit:'new'});
    write(`ide-updates/versions/${id}/vscode-reh/out/server-main.js`,{});
    write('ide-updates/state.json',{baseCommit:'base',baseApp:'19',pending:id});
    return {server,id,write,state:()=>JSON.parse(fs.readFileSync(path.join(server,'ide-updates/state.json')))};
}
test('activates a staged tree at startup and repairs native paths',t=>{
    const f=fixture(t), selection=loader.select(f.server,'/apk/native');
    assert.equal(selection.trial,f.id);
    assert.equal(fs.readlinkSync(path.join(selection.tree,'node_modules/@vscode/ripgrep/bin/rg')),'/apk/native/libripgrep.so');
    loader.markHealthy(f.server,selection.tree);
    const next=loader.select(f.server,'/new-apk/native');
    assert.equal(next.tree,selection.tree);
    assert.equal(next.trial,undefined);
    assert.equal(fs.readlinkSync(path.join(next.tree,'node_modules/@vscode/ripgrep/bin/rg')),'/new-apk/native/libripgrep.so');
});
test('failed or interrupted trial rolls back and blocks the failed digest',t=>{
    const f=fixture(t);
    loader.select(f.server,'/apk/native');
    const next=loader.select(f.server,'/apk/native');
    assert.equal(next.tree,path.join(f.server,'vscode-reh'));
    assert.deepEqual(f.state().blocked,[f.id]);
});
test('new APK resets the compatibility baseline',t=>{
    const f=fixture(t);
    f.write('ide-compat.json',{buildId:'20'});
    assert.equal(loader.select(f.server,'/apk/native').tree,path.join(f.server,'vscode-reh'));
});
test('path traversal and missing candidate cannot become active',t=>{
    const f=fixture(t);
    f.write('ide-updates/state.json',{baseCommit:'base',baseApp:'19',active:'../../escape',pending:'b'.repeat(64)});
    assert.equal(loader.select(f.server,'/apk/native').tree,path.join(f.server,'vscode-reh'));
});
test('health from another tree does not commit the trial',t=>{
    const f=fixture(t);
    loader.select(f.server,'/apk/native');
    loader.markHealthy(f.server,path.join(f.server,'vscode-reh'));
    assert.equal(loader.select(f.server,'/apk/native').tree,path.join(f.server,'vscode-reh'));
});
test('Android private-storage aliases can confirm the same running tree',t=>{
    const f=fixture(t);
    const alias=path.join(f.server,'android-files-alias');
    fs.symlinkSync(f.server,alias);
    const selected=loader.select(f.server,'/apk/native');
    loader.markHealthy(alias,selected.tree);
    assert.equal(loader.select(f.server,'/apk/native').tree,selected.tree);
    assert.equal(f.state().trial,undefined);
});
test('manual rollback uses the bundled tree on the next start',t=>{
    const f=fixture(t);
    const selected=loader.select(f.server,'/apk/native');
    loader.markHealthy(f.server,selected.tree);
    f.write('ide-updates/state.json',{...f.state(),pending:'bundled'});
    assert.equal(loader.select(f.server,'/apk/native').tree,path.join(f.server,'vscode-reh'));
});
test('the editor trial deadline does not depend on a living bootstrap',t=>{
    const f=fixture(t), modulePath=require.resolve('../../android/app/src/main/assets/ide-loader');
    const run=spawnSync(process.execPath,['-e',`require(${JSON.stringify(modulePath)}).startTrialGuard(${JSON.stringify(f.server)},'trial',25);setInterval(()=>{},1000);`],{timeout:5000});
    assert.equal(run.status,70);
});
test('an editor with a health marker survives its independent deadline',t=>{
    const f=fixture(t), modulePath=require.resolve('../../android/app/src/main/assets/ide-loader');
    fs.writeFileSync(path.join(f.server,'healthy-trial'),'ok');
    const run=spawnSync(process.execPath,['-e',`require(${JSON.stringify(modulePath)}).startTrialGuard(${JSON.stringify(f.server)},'trial',25);setTimeout(()=>process.exit(0),75);`],{timeout:5000});
    assert.equal(run.status,0);
});
