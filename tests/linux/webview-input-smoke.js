(async () => {
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
  const check = (value, label) => { if (!value) throw new Error(label); return true; };
  const result = {workbench: check(!!document.querySelector('.monaco-workbench'), 'Workbench missing')};
  const native = window.__vscodroidNativeInput;
  result.nativeBridge = check(typeof native === 'function', 'Native input bridge missing');
  const original = await native({op:'read'});
  if (typeof original !== 'string') throw new Error('Bring the app to the foreground before testing clipboard; original text could not be read');
  try {
    for (const [name, text] of [['unicode', 'Hello 世界 🙂 Македонски\nsecond line\tend'],
                                ['long', '世界🙂 abc\n'.repeat(12500)]]) {
      await native({op:'write', text});
      const read = await native({op:'read'});
      result[name + 'Clipboard'] = check(read === text, name + ' clipboard mismatch');
      result[name + 'Characters'] = text.length;
    }
    await navigator.clipboard.writeText('Browser fallback 世界\nline 2');
    result.browserClipboard = check(await navigator.clipboard.readText() === 'Browser fallback 世界\nline 2', 'Browser clipboard mismatch');
  } finally { await native({op:'write', text:original}); }
  for (const [name, key, shift] of [['nativeCtrlShiftP','p',true], ['nativeCtrlP','p',false]]) {
    await native({op:'key',key,ctrlKey:true,shiftKey:shift}); await wait(900);
    result[name] = check(Array.from(document.querySelectorAll('.quick-input-widget')).some(e => e.offsetParent !== null), name + ' failed');
    // Hide via its close button or native key through the known toolbar command.
    await native({op:'key',key:'Escape'});
    await wait(100);
  }
  return result;
})();
