// Focus a Linux terminal in the dedicated test workspace before running.
(async () => {
    const native = window.__vscodroidNativeInput;
    const original = await native({op:'read'});
  if (typeof original !== 'string') throw new Error('Bring the app to the foreground before testing clipboard; original text could not be read');
    try {
        await native({op:'key',key:'c',ctrlKey:true});
        await new Promise(resolve => setTimeout(resolve,200));
        const text = "printf 'TERMINAL_PASTE 世界\\n' > /workspace/.vscodroid-tests/terminal-clipboard.txt\n" +
            "printf 'MULTILINE_OK\\n' >> /workspace/.vscodroid-tests/terminal-clipboard.txt\n";
        await native({op:'write',text});
        await native({op:'key',key:'v',ctrlKey:true,shiftKey:true});
        await new Promise(resolve => setTimeout(resolve,500));
        const dialog = document.querySelector('.monaco-dialog-box');
        if (dialog && dialog.getBoundingClientRect().height > 0) throw new Error('Review the multiline paste confirmation before continuing');
        await native({op:'key',key:'Enter'});
        return {submitted:true, verifyFile:'/workspace/.vscodroid-tests/terminal-clipboard.txt'};
    } finally { await native({op:'write',text:original}); }
})();
