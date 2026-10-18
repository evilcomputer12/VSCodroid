(async () => {
 const native = window.__vscodroidNativeInput;
 const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
 const original = await native({op:'read'});
  if (typeof original !== 'string') throw new Error('Bring the app to the foreground before testing clipboard; original text could not be read');
 const result = {};
 try {
   const text = 'Editor Unicode 世界 🙂\nsecond line\n';
   await native({op:'write', text});
   await native({op:'key',key:'v',ctrlKey:true}); await wait(900);
   await native({op:'key',key:'a',ctrlKey:true}); await wait(100);
   await native({op:'key',key:'c',ctrlKey:true}); await wait(500);
   result.editorUnicodePasteCopy = (await native({op:'read'})) === text;
   await native({op:'key',key:'s',ctrlKey:true}); await wait(600);
   await native({op:'key',key:'z',ctrlKey:true}); await wait(300);
   await native({op:'key',key:'z',ctrlKey:true,shiftKey:true}); await wait(500);
   await native({op:'key',key:'a',ctrlKey:true});
   await native({op:'key',key:'c',ctrlKey:true}); await wait(300);
   result.undoRedo = (await native({op:'read'})) === text;
   await native({op:'key',key:'s',ctrlKey:true}); await wait(500);
   const frame = document.createElement('iframe'); frame.src = 'about:blank'; document.body.append(frame);
   await wait(300);
   const channel = frame.contentWindow.VSCodroidInput;
   let replied = false;
   if (channel) { channel.onmessage = () => {replied=true;}; channel.postMessage(JSON.stringify({id:'iframe-test',op:'read'})); await wait(800); }
   result.iframeClipboardDenied = !replied;
   frame.remove();
 } finally { await native({op:'write',text:original}); }
 if (Object.values(result).some(x => x !== true)) throw new Error(JSON.stringify(result));
 return result;
})();
