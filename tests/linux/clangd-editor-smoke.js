// Run after opening the smoke C source at the square() call and Trigger Suggest.
(async () => {
    const deadline = Date.now() + 10000;
    do {
        const widgets = Array.from(document.querySelectorAll('.suggest-widget.visible'));
        const entries = widgets.filter(e => e.getBoundingClientRect().height > 0).map(e => e.innerText).join('\n');
        if (entries.includes('square') && entries.includes('int value')) return {clangdCompletion:true, entries};
        await new Promise(resolve => setTimeout(resolve, 200));
    } while (Date.now() < deadline);
    throw new Error('clangd completion was not displayed');
})();
