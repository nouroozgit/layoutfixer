"""LayoutFixer - fix text typed on the wrong keyboard layout with one global shortcut.

Runs in the system tray.  Press the shortcut (default Ctrl+Shift+Space):
  * if text is selected, that text is converted;
  * otherwise the text before the cursor (whole line or last word) is grabbed and converted.
Works between ANY keyboard layouts installed in Windows.   `pythonw layoutfixer.py --settings` opens settings.
"""
import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes

import kbmap

APP = "LayoutFixer"
HERE = os.path.dirname(os.path.abspath(__file__))
CFG_DIR = os.path.join(os.environ.get("APPDATA", HERE), APP)
CFG_PATH = os.path.join(CFG_DIR, "config.json")
ICON_PATH = os.path.join(CFG_DIR, "icon.ico")
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

DEFAULT_CFG = {
    "hotkey": {"mods": ["ctrl", "shift"], "vk": 0x20},
    "scope": "line",            # "line" | "word"  (used only when nothing is selected)
    "switch_layout": True,      # switch the keyboard layout to the target after converting
    "disabled_layouts": [],     # hkl ints the user excluded
}

# ----------------------------------------------------------------------------- config

def load_cfg():
    cfg = json.loads(json.dumps(DEFAULT_CFG))
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save_cfg(cfg):
    os.makedirs(CFG_DIR, exist_ok=True)
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


FROZEN = getattr(sys, "frozen", False)


def _launch_cmd(*args):
    """Command line that re-launches this app (works both as script and as PyInstaller exe)."""
    if FROZEN:
        return [sys.executable] + list(args)
    return [_pythonw(), os.path.join(HERE, "layoutfixer.py")] + list(args)


def _pythonw():
    exe = sys.executable
    w = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return w if os.path.exists(w) else exe


def autostart_enabled():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP)
            return True
    except OSError:
        return False


def set_autostart(on):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, APP, 0, winreg.REG_SZ,
                              " ".join('"%s"' % p for p in _launch_cmd()))
        else:
            try:
                winreg.DeleteValue(k, APP)
            except OSError:
                pass

# ----------------------------------------------------------------------------- key names

VK_NAMES = {0x20: "Space", 0x13: "Pause", 0x2D: "Insert", 0x2E: "Delete", 0x24: "Home", 0x23: "End",
            0x21: "PageUp", 0x22: "PageDown", 0x09: "Tab", 0x0D: "Enter", 0x08: "Backspace",
            0x91: "ScrollLock", 0x2C: "PrintScreen", 0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-",
            0xBE: ".", 0xBF: "/", 0xC0: "`", 0xDB: "[", 0xDC: "\\", 0xDD: "]", 0xDE: "'",
            0x25: "Left", 0x26: "Up", 0x27: "Right", 0x28: "Down"}
MOD_ORDER = ["ctrl", "alt", "shift", "win"]
MOD_FLAG = {"alt": 1, "ctrl": 2, "shift": 4, "win": 8}
MOD_VK = {"ctrl": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B}


def vk_name(vk):
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        return chr(vk)
    if 0x70 <= vk <= 0x87:
        return "F%d" % (vk - 0x6F)
    return VK_NAMES.get(vk, "VK%02X" % vk)


def hotkey_text(hk):
    mods = [m.capitalize() for m in MOD_ORDER if m in hk["mods"]]
    return " + ".join(mods + [vk_name(hk["vk"])])

# ----------------------------------------------------------------------------- win32 helpers

u32, k32, s32 = kbmap.user32, kbmap.kernel32, ctypes.WinDLL("shell32", use_last_error=True)
HWND, UINT, DWORD = wintypes.HWND, wintypes.UINT, wintypes.DWORD
LRESULT = ctypes.c_ssize_t

u32.GetForegroundWindow.restype = HWND
u32.GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(DWORD)]
u32.GetWindowThreadProcessId.restype = DWORD
u32.GetKeyboardLayout.argtypes = [DWORD]
u32.GetKeyboardLayout.restype = ctypes.c_void_p
u32.GetClassNameW.argtypes = [HWND, wintypes.LPWSTR, ctypes.c_int]
u32.PostMessageW.argtypes = [HWND, UINT, wintypes.WPARAM, wintypes.LPARAM]
u32.RegisterHotKey.argtypes = [HWND, ctypes.c_int, UINT, UINT]
u32.UnregisterHotKey.argtypes = [HWND, ctypes.c_int]
u32.GetAsyncKeyState.argtypes = [ctypes.c_int]
u32.GetAsyncKeyState.restype = ctypes.c_short
u32.DefWindowProcW.argtypes = [HWND, UINT, wintypes.WPARAM, wintypes.LPARAM]
u32.DefWindowProcW.restype = LRESULT
u32.CreateWindowExW.argtypes = [DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, DWORD, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, HWND, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
u32.CreateWindowExW.restype = HWND
u32.LoadImageW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, UINT, ctypes.c_int, ctypes.c_int, UINT]
u32.LoadImageW.restype = ctypes.c_void_p
u32.CreatePopupMenu.restype = ctypes.c_void_p
u32.AppendMenuW.argtypes = [ctypes.c_void_p, UINT, ctypes.c_size_t, wintypes.LPCWSTR]
u32.TrackPopupMenu.argtypes = [ctypes.c_void_p, UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, HWND, ctypes.c_void_p]
u32.DestroyMenu.argtypes = [ctypes.c_void_p]
u32.SetTimer.argtypes = [HWND, ctypes.c_size_t, UINT, ctypes.c_void_p]
u32.SetForegroundWindow.argtypes = [HWND]
u32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
u32.RegisterWindowMessageW.restype = UINT
u32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), HWND, UINT, UINT]
u32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
u32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
u32.OpenClipboard.argtypes = [HWND]
u32.GetClipboardData.argtypes = [UINT]
u32.GetClipboardData.restype = ctypes.c_void_p
u32.SetClipboardData.argtypes = [UINT, ctypes.c_void_p]
u32.SetClipboardData.restype = ctypes.c_void_p
u32.EnumClipboardFormats.argtypes = [UINT]
u32.EnumClipboardFormats.restype = UINT
k32.GlobalAlloc.argtypes = [UINT, ctypes.c_size_t]
k32.GlobalAlloc.restype = ctypes.c_void_p
k32.GlobalLock.argtypes = [ctypes.c_void_p]
k32.GlobalLock.restype = ctypes.c_void_p
k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
k32.GlobalSize.argtypes = [ctypes.c_void_p]
k32.GlobalSize.restype = ctypes.c_size_t
k32.GlobalFree.argtypes = [ctypes.c_void_p]
k32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
k32.GetModuleHandleW.restype = ctypes.c_void_p
k32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
k32.CreateMutexW.restype = ctypes.c_void_p
s32.Shell_NotifyIconW.argtypes = [DWORD, ctypes.c_void_p]

CF_UNICODETEXT = 13


def _open_clip():
    for _ in range(20):
        if u32.OpenClipboard(None):
            return True
        time.sleep(0.01)
    return False


def get_clip_text():
    if not _open_clip():
        return None
    try:
        h = u32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ""
        p = k32.GlobalLock(h)
        if not p:
            return ""
        try:
            return ctypes.wstring_at(p)
        finally:
            k32.GlobalUnlock(h)
    finally:
        u32.CloseClipboard()


def _put(fmt, data):
    h = k32.GlobalAlloc(0x2, len(data))  # GMEM_MOVEABLE
    if not h:
        return
    p = k32.GlobalLock(h)
    ctypes.memmove(p, data, len(data))
    k32.GlobalUnlock(h)
    if not u32.SetClipboardData(fmt, h):
        k32.GlobalFree(h)


def set_clip_text(s):
    if not _open_clip():
        return False
    try:
        u32.EmptyClipboard()
        _put(CF_UNICODETEXT, (s + "\0").encode("utf-16-le"))
        return True
    finally:
        u32.CloseClipboard()


def save_clip():
    """Snapshot every memory-based clipboard format so the user's clipboard survives."""
    items = []
    if not _open_clip():
        return items
    try:
        fmt = 0
        while True:
            fmt = u32.EnumClipboardFormats(fmt)
            if not fmt:
                break
            if fmt in (2, 3, 9, 14) or 0x80 <= fmt <= 0x8F or 0x200 <= fmt <= 0x3FF:
                continue  # GDI-handle / display-only formats
            h = u32.GetClipboardData(fmt)
            if not h:
                continue
            size, p = k32.GlobalSize(h), k32.GlobalLock(h)
            if p and size:
                items.append((fmt, ctypes.string_at(p, size)))
            if p:
                k32.GlobalUnlock(h)
    except Exception:
        pass
    finally:
        u32.CloseClipboard()
    return items


def restore_clip(items):
    if not _open_clip():
        return
    try:
        u32.EmptyClipboard()
        for fmt, data in items:
            _put(fmt, data)
    finally:
        u32.CloseClipboard()

# ---- SendInput

class _MI(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", DWORD), ("dwFlags", DWORD),
                ("time", DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _KI(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", DWORD), ("time", DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class _IU(ctypes.Union):
    _fields_ = [("mi", _MI), ("ki", _KI)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", DWORD), ("u", _IU)]


u32.SendInput.argtypes = [UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
EXT_KEYS = {0x25, 0x26, 0x27, 0x28, 0x24, 0x23, 0x2D, 0x2E, 0x21, 0x22}
VK_CTRL, VK_SHIFT, VK_LEFT, VK_RIGHT, VK_HOME = 0x11, 0x10, 0x25, 0x27, 0x24


def chord(*vks):
    evs = []
    for up, seq in ((False, vks), (True, reversed(vks))):
        for vk in seq:
            i = _INPUT(type=1)
            i.u.ki = _KI(vk, u32.MapVirtualKeyW(vk, 0), (1 if vk in EXT_KEYS else 0) | (2 if up else 0), 0, 0)
            evs.append(i)
    arr = (_INPUT * len(evs))(*evs)
    u32.SendInput(len(evs), arr, ctypes.sizeof(_INPUT))


def foreground_hkl():
    hwnd = u32.GetForegroundWindow()
    tid = u32.GetWindowThreadProcessId(hwnd, None)
    return int(u32.GetKeyboardLayout(tid) or 0), hwnd


def wait_keys_released(vks, timeout=2.0):
    end = time.time() + timeout
    while time.time() < end:
        if not any(u32.GetAsyncKeyState(v) & 0x8000 for v in vks):
            return
        time.sleep(0.01)

# ----------------------------------------------------------------------------- the fix

class Fixer:
    def __init__(self, notify, log=lambda m: None):
        self.notify = notify
        self.notify_log = log
        self.layouts = kbmap.load_layouts()
        self.history = []       # hkls, most recently used first
        self.last = None        # (original, result, src, cycle, idx, time)

    def enabled_layouts(self, cfg):
        off = set(cfg.get("disabled_layouts", []))
        ls = [L for L in self.layouts if L.hkl not in off]
        return ls if len(ls) >= 2 else self.layouts

    def track(self):
        hkl, _ = foreground_hkl()
        if hkl:
            if hkl in self.history:
                self.history.remove(hkl)
            self.history.insert(0, hkl)

    def _copy_selection(self):
        sentinel = "⁣LF%f" % time.time()
        set_clip_text(sentinel)
        for keys in ((VK_CTRL, ord("C")), (VK_CTRL, 0x2D)):   # Ctrl+C, then Ctrl+Insert
            chord(*keys)
            for _ in range(30):
                time.sleep(0.02)
                t = get_clip_text()
                if t and t != sentinel:
                    return t
        return ""

    def _grab(self, scope):
        t = self._copy_selection()
        if t:
            return t
        if scope == "word":
            chord(VK_CTRL, VK_SHIFT, VK_LEFT)
            t = self._copy_selection()
            if not t.strip():          # RTL paragraphs: "left" moves forward, so go the other way
                chord(VK_CTRL, VK_SHIFT, VK_RIGHT)
                t = self._copy_selection()
        else:
            chord(VK_SHIFT, VK_HOME)
            t = self._copy_selection()
        return t

    def run(self, cfg, hk_vks):
        wait_keys_released(hk_vks)
        active, hwnd = foreground_hkl()
        cls = ctypes.create_unicode_buffer(128)
        u32.GetClassNameW(hwnd, cls, 128)
        if cls.value in ("ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS"):
            self.notify("Terminals are not supported (Ctrl+C would interrupt your program).")
            return
        saved = save_clip()
        try:
            text = self._grab(cfg["scope"])
            self.notify_log("window=%s layout=%x scope=%s grabbed=%r" % (cls.value, active, cfg["scope"], text[:40]))
            if not text.strip():
                self.notify("Nothing to convert here (window: %s)." % cls.value)
                return
            layouts = self.enabled_layouts(cfg)
            target = None
            last = self.last
            if last and text == last[1] and time.time() - last[5] < 120:
                original, src, cycle, idx = last[0], last[2], last[3], (last[4] + 1) % len(last[3])
                target = cycle[idx]
            else:
                found = kbmap.analyze(text, layouts, active, self.history)
                if not found:
                    self.notify("Couldn't recognise this text in your keyboard layouts.")
                    return
                original, (src, targets) = text, found
                cycle, idx = targets + [None], 0       # None = back to the original
                target = cycle[0]
            result = original if target is None else kbmap.convert(original, src, target)
            self.last = (original, result, src, cycle, idx, time.time())
            if result == text:
                self.notify("Text is already correct.")
                return
            set_clip_text(result)
            time.sleep(0.03)
            chord(VK_CTRL, ord("V"))
            time.sleep(0.25)
            if cfg.get("switch_layout") and target is not None and hwnd:
                u32.PostMessageW(hwnd, 0x50, 0, target.hkl)   # WM_INPUTLANGCHANGEREQUEST
        finally:
            restore_clip(saved)

# ----------------------------------------------------------------------------- tray app

WM_HOTKEY, WM_TIMER, WM_COMMAND, WM_DESTROY, WM_TRAY = 0x312, 0x113, 0x111, 0x2, 0x8001
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
ID_TOGGLE, ID_SETTINGS, ID_STARTUP, ID_EXIT = 1, 2, 3, 4
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HWND, UINT, wintypes.WPARAM, wintypes.LPARAM)


class _GUID(ctypes.Structure):
    _fields_ = [("a", DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]


class NOTIFYICONDATA(ctypes.Structure):
    _fields_ = [("cbSize", DWORD), ("hWnd", HWND), ("uID", UINT), ("uFlags", UINT), ("uCallbackMessage", UINT),
                ("hIcon", ctypes.c_void_p), ("szTip", ctypes.c_wchar * 128), ("dwState", DWORD),
                ("dwStateMask", DWORD), ("szInfo", ctypes.c_wchar * 256), ("uTimeout", UINT),
                ("szInfoTitle", ctypes.c_wchar * 64), ("dwInfoFlags", DWORD), ("guid", _GUID),
                ("hBalloonIcon", ctypes.c_void_p)]


class WNDCLASS(ctypes.Structure):
    _fields_ = [("style", UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", ctypes.c_void_p), ("hIcon", ctypes.c_void_p),
                ("hCursor", ctypes.c_void_p), ("hbrBackground", ctypes.c_void_p),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


def make_icon_file(path):
    """Draw a small blue 'swap arrows' icon (32x32) and write it as .ico - no image libs needed."""
    S = 32
    px = [[(0, 0, 0, 0)] * S for _ in range(S)]
    blue, white = (0xDF, 0x6C, 0x2D, 255), (255, 255, 255, 255)  # BGRA
    for y in range(S):
        for x in range(S):
            dx, dy = min(x, S - 1 - x), min(y, S - 1 - y)
            if dx < 6 and dy < 6 and (6 - dx) ** 2 + (6 - dy) ** 2 > 36:
                continue
            px[y][x] = blue
    for x in range(7, 22):
        for y in (11, 12):
            px[y][x] = white
    for i in range(6):
        for y in range(11 - (5 - i), 13 + (5 - i)):
            px[y][19 + i] = white
    for x in range(10, 25):
        for y in (19, 20):
            px[y][x] = white
    for i in range(6):
        for y in range(19 - (5 - i), 21 + (5 - i)):
            px[y][12 - i] = white
    pixels = b"".join(bytes(c) for row in reversed(px) for c in row)
    and_mask = bytes(4 * S)
    hdr = (40).to_bytes(4, "little") + S.to_bytes(4, "little") + (2 * S).to_bytes(4, "little") + \
        (1).to_bytes(2, "little") + (32).to_bytes(2, "little") + bytes(24)
    body = hdr + pixels + and_mask
    ico = bytes([0, 0, 1, 0, 1, 0, S, S, 0, 0, 1, 0, 32, 0]) + len(body).to_bytes(4, "little") + \
        (22).to_bytes(4, "little") + body
    with open(path, "wb") as f:
        f.write(ico)


class TrayApp:
    def __init__(self):
        self.cfg = load_cfg()
        self.cfg_mtime = self._mtime()
        self.enabled = True
        self.settings_proc = None
        self.fixer = Fixer(self.notify, self.log)
        self.hotkey_active = False
        self._wndproc = WNDPROC(self.wndproc)  # keep a reference alive
        self.taskbar_msg = u32.RegisterWindowMessageW("TaskbarCreated")
        hinst = k32.GetModuleHandleW(None)
        wc = WNDCLASS()
        wc.lpfnWndProc, wc.hInstance, wc.lpszClassName = self._wndproc, hinst, APP + "Window"
        ctypes.windll.user32.RegisterClassW(ctypes.byref(wc))
        self.hwnd = u32.CreateWindowExW(0, APP + "Window", APP, 0, 0, 0, 0, 0, None, None, hinst, None)
        os.makedirs(CFG_DIR, exist_ok=True)
        if not os.path.exists(ICON_PATH):
            make_icon_file(ICON_PATH)
        self.hicon = u32.LoadImageW(None, ICON_PATH, 1, 0, 0, 0x10 | 0x40)
        self.add_icon()
        self.register_hotkey()
        u32.SetTimer(self.hwnd, 1, 300, None)

    # -- helpers
    def _mtime(self):
        try:
            return os.path.getmtime(CFG_PATH)
        except OSError:
            return 0

    def _nid(self):
        n = NOTIFYICONDATA()
        n.cbSize, n.hWnd, n.uID = ctypes.sizeof(NOTIFYICONDATA), self.hwnd, 1
        return n

    def add_icon(self):
        n = self._nid()
        n.uFlags = 0x1 | 0x2 | 0x4  # MESSAGE | ICON | TIP
        n.uCallbackMessage, n.hIcon = WM_TRAY, self.hicon
        n.szTip = "%s - %s" % (APP, hotkey_text(self.cfg["hotkey"]))
        s32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(n))

    def log(self, msg):
        try:
            with open(os.path.join(CFG_DIR, "log.txt"), "a", encoding="utf-8") as f:
                f.write("%s  %s\n" % (time.strftime("%H:%M:%S"), msg))
        except OSError:
            pass

    def notify(self, msg):
        self.log(msg)
        n = self._nid()
        n.uFlags = 0x10  # INFO
        n.szInfoTitle, n.szInfo, n.dwInfoFlags = APP, msg, 1
        s32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(n))

    def hk_vks(self):
        return [MOD_VK[m] for m in self.cfg["hotkey"]["mods"]] + [self.cfg["hotkey"]["vk"]] + [0x5C]

    def register_hotkey(self):
        self.unregister_hotkey()
        if not self.enabled:
            return
        hk = self.cfg["hotkey"]
        flags = sum(MOD_FLAG[m] for m in hk["mods"]) | 0x4000  # NOREPEAT
        if u32.RegisterHotKey(self.hwnd, 1, flags, hk["vk"]):
            self.hotkey_active = True
        else:
            self.notify("Shortcut %s is used by another program. Choose another one in Settings."
                        % hotkey_text(hk))

    def unregister_hotkey(self):
        if self.hotkey_active:
            u32.UnregisterHotKey(self.hwnd, 1)
            self.hotkey_active = False

    def open_settings(self):
        if self.settings_proc and self.settings_proc.poll() is None:
            return
        self.settings_proc = subprocess.Popen(_launch_cmd("--settings"), cwd=HERE)

    def menu(self):
        m = u32.CreatePopupMenu()
        u32.AppendMenuW(m, 0x8 if self.enabled else 0, ID_TOGGLE,
                        "Enabled  (%s)" % hotkey_text(self.cfg["hotkey"]))
        u32.AppendMenuW(m, 0, ID_SETTINGS, "Settings...")
        u32.AppendMenuW(m, 0x8 if autostart_enabled() else 0, ID_STARTUP, "Start with Windows")
        u32.AppendMenuW(m, 0x800, 0, None)  # separator
        u32.AppendMenuW(m, 0, ID_EXIT, "Exit")
        pt = wintypes.POINT()
        u32.GetCursorPos(ctypes.byref(pt))
        u32.SetForegroundWindow(self.hwnd)
        cmd = u32.TrackPopupMenu(m, 0x100 | 0x2, pt.x, pt.y, 0, self.hwnd, None)  # RETURNCMD|RIGHTBUTTON
        u32.PostMessageW(self.hwnd, 0, 0, 0)
        u32.DestroyMenu(m)
        if cmd == ID_TOGGLE:
            self.enabled = not self.enabled
            self.register_hotkey()
        elif cmd == ID_SETTINGS:
            self.open_settings()
        elif cmd == ID_STARTUP:
            set_autostart(not autostart_enabled())
        elif cmd == ID_EXIT:
            u32.DestroyWindow(self.hwnd)

    def wndproc(self, hwnd, msg, wp, lp):
        try:
            if msg == WM_HOTKEY:
                self.fixer.run(self.cfg, self.hk_vks())
                return 0
            if msg == WM_TIMER:
                self.fixer.track()
                mt = self._mtime()
                if mt != self.cfg_mtime:
                    self.cfg_mtime, self.cfg = mt, load_cfg()
                    self.register_hotkey()
                    self.add_icon_tip()
                return 0
            if msg == WM_TRAY:
                if lp == 0x205:        # right click
                    self.menu()
                elif lp == 0x203:      # double click
                    self.open_settings()
                return 0
            if msg == self.taskbar_msg:
                self.add_icon()
                return 0
            if msg == WM_DESTROY:
                n = self._nid()
                s32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(n))
                self.unregister_hotkey()
                u32.PostQuitMessage(0)
                return 0
        except Exception as e:  # never let an exception escape into the message loop
            try:
                self.notify("Error: %s" % e)
            except Exception:
                pass
            return 0
        return u32.DefWindowProcW(hwnd, msg, wp, lp)

    def add_icon_tip(self):
        n = self._nid()
        n.uFlags = 0x4
        n.szTip = "%s - %s" % (APP, hotkey_text(self.cfg["hotkey"]))
        s32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(n))

    def loop(self):
        msg = wintypes.MSG()
        while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            u32.TranslateMessage(ctypes.byref(msg))
            u32.DispatchMessageW(ctypes.byref(msg))


u32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
u32.DestroyWindow.argtypes = [HWND]
u32.MapVirtualKeyW.argtypes = [UINT, UINT]
u32.MapVirtualKeyW.restype = UINT

# ----------------------------------------------------------------------------- settings window

def settings_window():
    import tkinter as tk
    from tkinter import ttk, messagebox

    cfg = load_cfg()
    layouts = kbmap.load_layouts()
    hk = {"mods": list(cfg["hotkey"]["mods"]), "vk": cfg["hotkey"]["vk"]}

    root = tk.Tk()
    root.title(APP + " settings")
    root.resizable(False, False)
    frm = ttk.Frame(root, padding=16)
    frm.grid()

    # --- shortcut
    ttk.Label(frm, text="Shortcut", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
    hk_var = tk.StringVar(value=hotkey_text(hk))
    hk_lbl = ttk.Label(frm, textvariable=hk_var, font=("Segoe UI", 12), width=26, relief="groove", anchor="center")
    hk_lbl.grid(row=1, column=0, sticky="we", pady=(4, 0), ipady=4)
    capturing = {"on": False}
    btn = ttk.Button(frm, text="Change...")
    btn.grid(row=1, column=1, padx=(8, 0), pady=(4, 0))

    def start_capture():
        capturing["on"] = True
        hk_var.set("Press the new shortcut...  (Esc = cancel)")
        btn.state(["disabled"])
        root.focus_force()

    def stop_capture():
        capturing["on"] = False
        hk_var.set(hotkey_text(hk))
        btn.state(["!disabled"])

    def on_key(e):
        if not capturing["on"]:
            return
        if e.keysym in ("Control_L", "Control_R", "Shift_L", "Shift_R", "Alt_L", "Alt_R", "Win_L", "Win_R",
                        "Super_L", "Super_R", "Caps_Lock", "Num_Lock"):
            return "break"
        if e.keysym == "Escape":
            stop_capture()
            return "break"
        mods = []
        if e.state & 0x4:
            mods.append("ctrl")
        if e.state & 0x20000:
            mods.append("alt")
        if e.state & 0x1:
            mods.append("shift")
        vk = e.keycode
        free_keys = vk in (0x13, 0x91, 0x2C, 0x2D) or 0x70 <= vk <= 0x87
        if not mods and not free_keys:
            messagebox.showinfo(APP, "Please include Ctrl, Alt or Shift (or use a key like Pause / F9).")
            stop_capture()
            return "break"
        hk["mods"], hk["vk"] = mods, vk
        stop_capture()
        return "break"

    btn.config(command=start_capture)
    root.bind_all("<KeyPress>", on_key)

    # --- scope
    ttk.Label(frm, text="When nothing is selected, convert", font=("Segoe UI", 10, "bold")).grid(
        row=2, column=0, columnspan=2, sticky="w", pady=(14, 0))
    scope = tk.StringVar(value=cfg["scope"])
    ttk.Radiobutton(frm, text="Everything before the cursor on this line", variable=scope, value="line").grid(
        row=3, column=0, columnspan=2, sticky="w")
    ttk.Radiobutton(frm, text="Only the last word", variable=scope, value="word").grid(
        row=4, column=0, columnspan=2, sticky="w")
    ttk.Label(frm, text="If you select text first, exactly that text is converted.",
              foreground="#666").grid(row=5, column=0, columnspan=2, sticky="w")

    # --- options
    sw = tk.BooleanVar(value=cfg["switch_layout"])
    ttk.Checkbutton(frm, text="Switch the keyboard layout to the corrected language", variable=sw).grid(
        row=6, column=0, columnspan=2, sticky="w", pady=(12, 0))
    su = tk.BooleanVar(value=autostart_enabled())
    ttk.Checkbutton(frm, text="Start with Windows", variable=su).grid(row=7, column=0, columnspan=2, sticky="w")

    # --- layouts
    ttk.Label(frm, text="Keyboard layouts to use", font=("Segoe UI", 10, "bold")).grid(
        row=8, column=0, columnspan=2, sticky="w", pady=(14, 0))
    off = set(cfg["disabled_layouts"])
    lvars = []
    for i, L in enumerate(layouts):
        v = tk.BooleanVar(value=L.hkl not in off)
        lvars.append(v)
        ttk.Checkbutton(frm, text=L.name, variable=v).grid(row=9 + i, column=0, columnspan=2, sticky="w")
    ttk.Label(frm, text="Add more languages in Windows settings; they appear here automatically.",
              foreground="#666").grid(row=9 + len(layouts), column=0, columnspan=2, sticky="w")

    def save():
        new = load_cfg()
        new["hotkey"] = hk
        new["scope"] = scope.get()
        new["switch_layout"] = sw.get()
        new["disabled_layouts"] = [L.hkl for L, v in zip(layouts, lvars) if not v.get()]
        if len(layouts) - len(new["disabled_layouts"]) < 2:
            messagebox.showwarning(APP, "Keep at least two keyboard layouts enabled.")
            return
        save_cfg(new)
        try:
            set_autostart(su.get())
        except Exception:
            pass
        root.destroy()

    row = 10 + len(layouts)
    bf = ttk.Frame(frm)
    bf.grid(row=row, column=0, columnspan=2, sticky="e", pady=(14, 0))
    ttk.Button(bf, text="Cancel", command=root.destroy).grid(row=0, column=0, padx=6)
    ttk.Button(bf, text="Save", command=save).grid(row=0, column=1)
    root.mainloop()

# ----------------------------------------------------------------------------- main

def main():
    if "--settings" in sys.argv:
        settings_window()
        return
    if "--test" in sys.argv:        # print what the engine knows, then exit
        for L in kbmap.load_layouts():
            print(L, len(L.fwd))
        return
    k32.CreateMutexW(None, False, "Local\\" + APP + "Mutex")
    if ctypes.get_last_error() == 183:   # already running
        return
    TrayApp().loop()


if __name__ == "__main__":
    main()
