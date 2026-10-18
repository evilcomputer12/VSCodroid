// Local debug WebView checks; never prints the editor URL or connection token.
import fs from 'node:fs';
const pages = await (await fetch('http://127.0.0.1:9222/json/list')).json();
const page = pages.find(p => p.type === 'page' && /VSCodroid/.test(p.title));
if (!page) throw new Error('VSCodroid workbench not found');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve,reject) => {ws.onopen=resolve;ws.onerror=reject;});
let serial=0; const pending=new Map();
ws.onmessage = event => {const m=JSON.parse(event.data); if(m.id && pending.has(m.id)){const q=pending.get(m.id);pending.delete(m.id);m.error?q.reject(new Error(m.error.message)):q.resolve(m.result);}};
const call=(method,params={})=>new Promise((resolve,reject)=>{
 const id=++serial;
 const timer=setTimeout(()=>{pending.delete(id);reject(new Error(method+' timed out'));},30000);
 pending.set(id,{resolve:value=>{clearTimeout(timer);resolve(value);},reject:error=>{clearTimeout(timer);reject(error);}});
 ws.send(JSON.stringify({id,method,params}));
});
const evaluate=async(expression)=>{
 const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true,userGesture:true});
 if(r.exceptionDetails) throw new Error(r.exceptionDetails.text+': '+r.result.description);
 return r.result.value;
};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
const key=async(key,code,keyCode,modifiers=0)=>{
 const event={key,code,windowsVirtualKeyCode:keyCode,nativeVirtualKeyCode:keyCode,modifiers};
 await call('Input.dispatchKeyEvent',{...event,type:'keyDown'});
 await call('Input.dispatchKeyEvent',{...event,type:'keyUp'});
};
try {
 const action=process.argv[2] || 'baseline';
 if(action==='eval') {console.log(JSON.stringify(await evaluate(fs.readFileSync(process.argv[3],'utf8')),null,2));}
 else if(action==='command') {
   await key('Escape','Escape',27);
   await key('P','KeyP',80,10); await wait(600);
   if (!await evaluate('Array.from(document.querySelectorAll(".quick-input-widget")).some(e => e.offsetParent !== null)')) throw new Error('Command palette did not open');
   await call('Input.insertText',{text:process.argv.slice(3).join(' ')}); await wait(1000);
   const requested = process.argv.slice(3).join(' ');
   const rows = await evaluate('Array.from(document.querySelectorAll(".quick-input-list .monaco-list-row")).map(e=>e.querySelector(".label-name")?.textContent)');
   const index = rows.indexOf(requested);
   if (index < 0) { await key('Escape','Escape',27); throw new Error('Exact command not found: '+requested+'; matches: '+JSON.stringify(rows)); }
   await key('Home','Home',36,2);
   // Filtering starts with the first row selected; input Home only moves its caret.
   for (let i=0;i<index;i++) await key('ArrowDown','ArrowDown',40);
   await key('Enter','Enter',13); await wait(1200);
   console.log('Command submitted');
 } else if(action==='open') {
   await key('Escape','Escape',27); await key('p','KeyP',80,2); await wait(500);
   await call('Input.insertText',{text:process.argv[3]}); await wait(1000);
   await key('Enter','Enter',13); await wait(1000); console.log('File opened');
 } else if(action==='terminal' || action==='terminal-file') {
   if (!await evaluate('document.activeElement?.classList.contains("xterm-helper-textarea")')) throw new Error('The terminal must have focus before sending shell input');
   const command=action==='terminal-file'?fs.readFileSync(process.argv[3],'utf8').trim():process.argv[3];
   if (/[\r\n]/.test(command)) throw new Error('Send a single command; write multiline scripts to a workspace file and run bash on that file');
   await call('Input.insertText',{text:command});
   await wait(150);
   await key('Enter','Enter',13); await wait(1000); console.log('Terminal input submitted');
 } else if(action==='interrupt') {
   await key('c','KeyC',67,2); await wait(500); console.log('Ctrl+C submitted');
 } else {
   const result={workbench:await evaluate('!!document.querySelector(".monaco-workbench")')};
   await key('P','KeyP',80,10); await wait(700);
   result.ctrlShiftP=await evaluate('Array.from(document.querySelectorAll(".quick-input-widget")).some(e => e.offsetParent !== null && !!e.querySelector("input"))');
   await key('Escape','Escape',27); await key('p','KeyP',80,2); await wait(500);
   result.ctrlP=await evaluate('Array.from(document.querySelectorAll(".quick-input-widget")).some(e => e.offsetParent !== null && !!e.querySelector("input"))');
   await key('Escape','Escape',27);
   console.log(JSON.stringify(result,null,2));
   if(Object.values(result).some(x=>x!==true)) process.exitCode=1;
 }
} finally {ws.close();}
