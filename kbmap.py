"""Keyboard-layout aware text conversion for Windows.

Builds, for every installed keyboard layout, a map  physical key (+shift/AltGr)  <->  character,
straight from Windows (ToUnicodeEx).  Converting text typed on the wrong layout is then just:
character -> physical key (in the layout it was typed on) -> character (in the intended layout).
No hand-written tables, so it works for any combination of installed languages.
"""
import ctypes
import unicodedata
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.GetKeyboardLayoutList.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
user32.GetKeyboardLayoutList.restype = ctypes.c_int
user32.MapVirtualKeyExW.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p]
user32.MapVirtualKeyExW.restype = wintypes.UINT
user32.ToUnicodeEx.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_ubyte),
                               wintypes.LPWSTR, ctypes.c_int, wintypes.UINT, ctypes.c_void_p]
user32.ToUnicodeEx.restype = ctypes.c_int
kernel32.GetLocaleInfoW.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.LPWSTR, ctypes.c_int]
kernel32.GetLocaleInfoW.restype = ctypes.c_int

LOCALE_SENGLISHDISPLAYNAME = 0x72

# scancodes of the typing area (no numpad / function keys)
SCANCODES = (list(range(0x02, 0x0E)) + list(range(0x10, 0x1C)) + list(range(0x1E, 0x2A)) +
             list(range(0x2B, 0x36)) + [0x39, 0x56])
# modifier combos: 0 none, 1 shift, 2 AltGr (ctrl+alt), 3 shift+AltGr
MOD_STATES = {
    0: (),
    1: (0x10, 0xA0),
    2: (0x11, 0x12, 0xA2, 0xA5),
    3: (0x10, 0xA0, 0x11, 0x12, 0xA2, 0xA5),
}


def installed_hkls():
    n = user32.GetKeyboardLayoutList(0, None)
    arr = (ctypes.c_void_p * n)()
    user32.GetKeyboardLayoutList(n, arr)
    return [int(a or 0) for a in arr]


class Layout:
    def __init__(self, hkl):
        self.hkl = hkl
        self.langid = hkl & 0xFFFF
        buf = ctypes.create_unicode_buffer(128)
        if kernel32.GetLocaleInfoW(self.langid, LOCALE_SENGLISHDISPLAYNAME, buf, 128):
            self.name = buf.value
        else:
            self.name = "Layout %04X" % self.langid
        self.fwd = {}   # (scancode, mod) -> char
        self.rev = {}   # char -> (scancode, mod)
        self._build()

    def _build(self):
        buf = ctypes.create_unicode_buffer(8)
        for mod, keys in MOD_STATES.items():
            for sc in SCANCODES:
                vk = user32.MapVirtualKeyExW(sc, 3, self.hkl)  # MAPVK_VSC_TO_VK_EX
                if not vk:
                    continue
                state = (ctypes.c_ubyte * 256)()
                for k in keys:
                    state[k] = 0x80
                n = user32.ToUnicodeEx(vk, sc, state, buf, 8, 4, self.hkl)  # 4: keep kbd state
                if n < 0:
                    # dead key: flush it so it does not leak into the next lookup
                    clean = (ctypes.c_ubyte * 256)()
                    user32.ToUnicodeEx(0x20, 0x39, clean, buf, 8, 4, self.hkl)
                    continue
                if n != 1:
                    continue
                ch = buf[0]
                if unicodedata.category(ch) == "Cc":
                    continue
                self.fwd[(sc, mod)] = ch
                self.rev.setdefault(ch, (sc, mod))

    def __repr__(self):
        return "<Layout %s %08X>" % (self.name, self.hkl)


def load_layouts():
    layouts, seen = [], {}
    for h in installed_hkls():
        L = Layout(h)
        seen[L.name] = seen.get(L.name, 0) + 1
        if seen[L.name] > 1:
            L.name += " (%d)" % seen[L.name]
        layouts.append(L)
    return layouts


def convert(text, src, dst):
    """Re-type `text` (typed on layout src) as if it had been typed on layout dst."""
    out = []
    for ch in text:
        key = src.rev.get(ch)
        out.append(dst.fwd.get(key, ch) if key else ch)
    return "".join(out)


def _coverage(text, layout):
    return sum(1 for ch in text if ch.isalpha() and ch in layout.rev)


def analyze(text, layouts, active_hkl, history):
    """Guess which layout `text` was typed on and which layouts it may have been meant for.

    layouts : enabled Layout objects, in system order
    active_hkl : layout active in the focused window right now
    history : hkls, most recently used first
    Returns (src, [targets in priority order]) or None if nothing convertible.
    """
    def hist_idx(L):
        return history.index(L.hkl) if L.hkl in history else 999

    best, cands = 0, []
    for L in layouts:
        c = _coverage(text, L)
        if c > best:
            best, cands = c, [L]
        elif c == best and c > 0:
            cands.append(L)
    if not cands:
        return None
    src = min(cands, key=lambda L: (0 if L.hkl == active_hkl else 1, hist_idx(L), layouts.index(L)))

    letters = sum(1 for ch in text if ch.isalpha())
    others = [L for L in layouts if L is not src]
    # layouts of a different script than the text come first (Latin text -> Persian, not -> French)
    others.sort(key=lambda L: (1 if _coverage(text, L) * 2 >= letters else 0, hist_idx(L), layouts.index(L)))
    active = [L for L in others if L.hkl == active_hkl]
    targets = active + [L for L in others if L.hkl != active_hkl]
    return src, targets


if __name__ == "__main__":
    ls = load_layouts()
    for L in ls:
        print(L, len(L.fwd), "keys")
