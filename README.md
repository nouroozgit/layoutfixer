# LayoutFixer

Typed in the wrong keyboard layout? Press one global shortcut (default **Ctrl+Shift+Space**) and the text is converted to what you meant to type. No selection needed. Works between **any** keyboard layouts installed in Windows (Persian ⇄ English, Arabic ⇄ French, Russian ⇄ German, ...).

`sghl` → `سلام` &nbsp;·&nbsp; `سلام` → `sghl`

## Features
- Global shortcut, changeable in Settings (double-click the tray icon)
- No selection required: converts the text before the cursor (whole line or last word). If text is selected, converts exactly that.
- Language-agnostic: key maps are read from Windows itself, nothing is hard-coded
- Auto-detects which layout the text was typed on; press the shortcut again to cycle through other layouts and finally back to the original
- Optionally switches the keyboard layout to the corrected language
- Restores your clipboard afterwards; optional start with Windows

## Install
**Exe:** download `LayoutFixer.exe` from [Releases](../../releases) and run it. A tray icon appears (right-click: Settings / Start with Windows / Exit).

**From source** (Python 3.9+, Windows, no dependencies):
```
python layoutfixer.py
```
Build the exe yourself: `pip install pyinstaller` then `pyinstaller --onefile --noconsole --name LayoutFixer layoutfixer.py`.

## Notes
- Not supported in terminals (Ctrl+C there interrupts programs).
- Config: `%APPDATA%\LayoutFixer\config.json`, log: `%APPDATA%\LayoutFixer\log.txt`.
- The unsigned exe may trigger a Windows SmartScreen warning; the source is all here.

## فارسی
وقتی اشتباهی با کیبورد انگلیسی فارسی تایپ می‌کنید، با یک شورت‌کات (پیش‌فرض Ctrl+Shift+Space) بدون انتخاب متن، همان متن به معادل درستش تبدیل می‌شود. بین هر دو زبانی که در ویندوز نصب باشد کار می‌کند. شورت‌کات از تنظیمات (دابل‌کلیک روی آیکن سینی) قابل تغییر است.

## License
MIT
