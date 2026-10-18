# Keyboard, touch and S Pen

Physical Android KeyEvents continue through the upstream WebView dispatch path,
including left/right Ctrl, Alt, Shift and Meta states. Android can reserve system
Meta shortcuts. A hardware keyboard hides the extra row while typing; touch brings
it back. Existing touch focus restoration and selection are preserved.

Latched Ctrl/Alt/Meta plus supported characters use real Android events with evdev
scan codes and modifier releases. Latched IME characters travel through the
origin-bound input channel. Fixed toolbar actions call an allowlisted public
VS Code command through the bundled browser extension, avoiding terminal XOFF
for Save. Existing composition-specific navigation handling is preserved.

| Action | Shortcut |
|---|---|
| Commands / file quick open | Ctrl+Shift+P / Ctrl+P |
| Search files / save | Ctrl+Shift+F / Ctrl+S |
| Undo / redo | Ctrl+Z / Ctrl+Shift+Z |
| Select text / words | Shift+arrows / Ctrl+Shift+arrows |
| Editor copy / paste | Ctrl+C / Ctrl+V |
| Terminal copy / paste | Ctrl+Shift+C / Ctrl+Shift+V |
| Terminal interrupt | Ctrl+C with no selected text |

Touch and S Pen use WebView's pointer/selection paths. Long-press for selection;
terminal title controls expose Copy and Paste. See `docs/testing.md` for what has
actually been exercised; automated injected events do not prove every physical
keyboard layout or S Pen gesture.
