#!/usr/bin/env python3
r"""Text & Data Toolkit -- a pure-stdlib tkinter GUI on top of ``textkit``.

A single main window: a left sidebar listing tools (Convert, Validate/Format,
Diff, Regex tester, Hash, Encode/Decode, JWT, Text transforms) and a main panel
that swaps to the selected tool.  Every operation calls the tested core library
(never re-implements logic); file hashing runs on a background thread so the UI
stays responsive.  Results appear in an output area with a Copy button, and any
:class:`TextKitError` is shown inline (never as a traceback).

Design goals mirrored from the sibling PDF Toolkit GUI:
  * pure standard-library tkinter/ttk -- NO third-party GUI deps.  Dark mode is
    a ttk-style + palette swap.
  * Importing this module does nothing.  Only :func:`main` builds a root window,
    and it degrades gracefully (prints a message, returns 0) with no display.
  * Frozen-exe safe: bundled assets are resolved via ``sys._MEIPASS`` / the exe
    directory when ``sys.frozen`` is set -- never ``__file__``.

100% AI-built, open source, published on QuickOpen (quickopen.ai).
"""

from __future__ import annotations

import os
import sys
import threading

# NOTE: tkinter is imported lazily inside main()/build_app so that merely
# importing this module (e.g. during packaging or on a headless CI box) never
# fails.

APP_NAME = "Text & Data Toolkit"
APP_VERSION = "1.0.0"
WINDOW_TITLE = "Text & Data Toolkit — by QuickOpen (quickopen.ai)"
PROJECT_URL = "https://quickopen.ai"

TEXT_TYPES = [
    ("Text/data files", "*.json *.yaml *.yml *.xml *.csv *.txt"),
    ("All files", "*.*"),
]

# ---- colour palettes (mirror the QuickOpen palette) -------------------------
PALETTES = {
    "light": {
        "bg": "#f5f7fa", "surface": "#ffffff", "text": "#141820",
        "muted": "#5b6472", "primary": "#2f5fe0", "primary_hi": "#2450c8",
        "entry": "#ffffff", "border": "#d5dae2", "sel": "#2f5fe0",
        "sel_fg": "#ffffff", "trough": "#e2e7ef", "ok": "#1f7a3d",
        "err": "#c0392b", "hl": "#ffe58a",
    },
    "dark": {
        "bg": "#0f1115", "surface": "#1a1e24", "text": "#f1f3f7",
        "muted": "#9aa4b2", "primary": "#5b86f7", "primary_hi": "#7098ff",
        "entry": "#1a1e24", "border": "#2a2f38", "sel": "#5b86f7",
        "sel_fg": "#0f1115", "trough": "#2a2f38", "ok": "#5bd68a",
        "err": "#ff6b5e", "hl": "#6b5d1f",
    },
}

# (tool_id, label) -- tool_id maps to a _panel_<id> method.
TOOL_LIST = [
    ("convert", "Convert"),
    ("format", "Validate / Format"),
    ("diff", "Diff"),
    ("regex", "Regex tester"),
    ("hash", "Hash / Checksum"),
    ("encode", "Encode / Decode"),
    ("jwt", "JWT decoder"),
    ("text", "Text transforms"),
]

TOOL_DESCRIPTIONS = {
    "convert": "Convert between JSON, YAML, CSV and XML. Some conversions are "
               "lossy — see the notes for each format.",
    "format": "Validate and pretty-print or minify JSON, YAML, XML or CSV.",
    "diff": "Compare two texts: a unified line diff, or a structural JSON diff.",
    "regex": "Test a regular expression with live match highlighting, or run a "
             "substitution.",
    "hash": "Hash text or a file (MD5 / SHA-1 / SHA-256 / SHA-512 / CRC32). "
            "File hashing runs off the UI thread.",
    "encode": "Encode or decode base64, base32, hex or URL text.",
    "jwt": "Decode a JWT's header and payload. No signature verification.",
    "text": "Transform text: change case, sort/dedupe lines, slugify, wrap, "
            "collapse whitespace and more.",
}

FORMATS = ["json", "yaml", "csv", "xml"]
HASH_ALGOS = ["sha256", "md5", "sha1", "sha512", "crc32"]
CODECS = ["base64", "base32", "hex", "url"]
TEXT_OPS = [
    "upper", "lower", "title", "snake", "kebab", "camel", "pascal",
    "trim", "collapse", "sort", "dedupe", "reverse", "reverse-lines",
    "slugify", "wrap",
]


# ---------------------------------------------------------------------------
# Asset / frozen handling
# ---------------------------------------------------------------------------
def asset_path(name):
    """Locate a bundled asset from source OR a PyInstaller one-file build.

    For a frozen exe we look only at ``sys._MEIPASS`` and the executable's own
    directory (never ``__file__``).  From source we also consult the package
    dir, the repo root and the CWD.  Returns an absolute path or ``None``.
    """
    roots = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            roots.append(meipass)
        roots.append(os.path.dirname(os.path.abspath(sys.executable)))
    else:
        here = os.path.dirname(os.path.abspath(__file__))
        roots += [here, os.path.dirname(here), os.getcwd()]
    for root in roots:
        candidate = os.path.join(root, name)
        if os.path.exists(candidate):
            return candidate
    return None


def open_with_default_app(path):
    """Open a file or URL with the OS default application, guarded."""
    try:
        if hasattr(os, "startfile"):
            os.startfile(path)  # noqa: S606 - intended
        elif sys.platform == "darwin":
            import subprocess
            subprocess.Popen(["open", path])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# The app (built lazily; tkinter imported only inside build_app/main)
# ---------------------------------------------------------------------------
def build_app():
    """Construct and return the App class bound to a live tkinter import."""
    import tkinter as tk
    from tkinter import ttk, filedialog

    from . import guiconfig
    from .errors import TextKitError
    # Import functions directly: ``from . import convert`` would resolve to the
    # re-exported *function* of that name rather than the submodule.
    from .convert import convert as do_convert
    from .validate import validate as do_validate, pretty as do_pretty, \
        minify as do_minify
    from . import diff as diff_mod
    from . import regex_util
    from . import hashing
    from . import encoding
    from . import textops

    FONT = "Segoe UI"
    MONO = "Consolas"

    # -- small reusable widgets ------------------------------------------
    def make_scrolled_text(app, master, height=10, role="text", mono=True):
        """A ttk-framed Text widget with a vertical scrollbar, theme-tracked."""
        frame = ttk.Frame(master, style="TFrame")
        txt = tk.Text(frame, height=height, wrap="none", undo=True,
                      font=(MONO if mono else FONT, 10), borderwidth=0)
        sb = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
        hb = ttk.Scrollbar(frame, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=sb.set, xscrollcommand=hb.set)
        sb.pack(side="right", fill="y")
        hb.pack(side="bottom", fill="x")
        txt.pack(side="left", fill="both", expand=True)
        app.track(txt, role)
        return frame, txt

    def get_text(widget):
        return widget.get("1.0", "end-1c")

    def set_text(widget, value):
        widget.delete("1.0", "end")
        widget.insert("1.0", value)

    # -- the main window --------------------------------------------------
    class App(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title(WINDOW_TITLE)
            self.geometry("1080x700")
            self.minsize(900, 560)

            self.theme = guiconfig.get_theme()
            self._busy = False
            self._panels = {}
            self._current = None
            self._tracked = []
            self._img_refs = []

            self._set_icon()
            self._build_menu()
            self._build_layout()
            self._apply_theme()
            self.protocol("WM_DELETE_WINDOW", self.destroy)
            self.after(50, self._select_first_tool)

        # ---- assets / icon
        def _set_icon(self):
            try:
                ico = asset_path("text-data-toolkit.ico")
                if ico:
                    self.iconbitmap(ico)
                    return
            except Exception:
                pass
            try:
                png = asset_path("text-data-toolkit.png")
                if png:
                    img = tk.PhotoImage(file=png)
                    self._img_refs.append(img)
                    self.iconphoto(True, img)
            except Exception:
                pass  # icon is cosmetic; never block launch

        # ---- theming
        def track(self, widget, role):
            self._tracked.append((widget, role))

        def _pal(self):
            return PALETTES[self.theme]

        def _apply_theme(self):
            p = self._pal()
            style = ttk.Style(self)
            try:
                style.theme_use("clam")
            except Exception:
                pass
            self.configure(bg=p["bg"])
            style.configure(".", background=p["bg"], foreground=p["text"],
                            fieldbackground=p["entry"], bordercolor=p["border"],
                            font=(FONT, 10))
            style.configure("TFrame", background=p["bg"])
            style.configure("Sidebar.TFrame", background=p["surface"])
            style.configure("TLabel", background=p["bg"], foreground=p["text"])
            style.configure("Muted.TLabel", background=p["bg"], foreground=p["muted"])
            style.configure("Header.TLabel", background=p["bg"], foreground=p["text"],
                            font=(FONT, 15, "bold"))
            style.configure("Sub.TLabel", background=p["bg"], foreground=p["muted"],
                            font=(FONT, 10))
            style.configure("Brand.TLabel", background=p["surface"],
                            foreground=p["text"], font=(FONT, 12, "bold"))
            style.configure("Status.TLabel", background=p["surface"],
                            foreground=p["muted"])
            style.configure("TButton", background=p["surface"], foreground=p["text"],
                            bordercolor=p["border"], focuscolor=p["surface"],
                            padding=(10, 5))
            style.map("TButton",
                      background=[("active", p["trough"]), ("disabled", p["bg"])],
                      foreground=[("disabled", p["muted"])])
            style.configure("Accent.TButton", background=p["primary"],
                            foreground="#ffffff", padding=(12, 6))
            style.map("Accent.TButton",
                      background=[("active", p["primary_hi"]),
                                  ("disabled", p["border"])],
                      foreground=[("disabled", p["muted"])])
            style.configure("Toggle.TButton", background=p["surface"],
                            foreground=p["text"], padding=(8, 4))
            for name in ("TEntry", "TSpinbox"):
                style.configure(name, fieldbackground=p["entry"], foreground=p["text"],
                                insertcolor=p["text"], bordercolor=p["border"])
            style.configure("TCombobox", fieldbackground=p["entry"],
                            foreground=p["text"], background=p["surface"],
                            arrowcolor=p["text"])
            style.map("TCombobox",
                      fieldbackground=[("readonly", p["entry"])],
                      foreground=[("readonly", p["text"])])
            style.configure("TCheckbutton", background=p["bg"], foreground=p["text"])
            style.map("TCheckbutton", background=[("active", p["bg"])])
            style.configure("TRadiobutton", background=p["bg"], foreground=p["text"])
            style.map("TRadiobutton", background=[("active", p["bg"])])
            style.configure("TLabelframe", background=p["bg"], foreground=p["text"],
                            bordercolor=p["border"])
            style.configure("TLabelframe.Label", background=p["bg"],
                            foreground=p["muted"])
            style.configure("Sidebar.Treeview", background=p["surface"],
                            fieldbackground=p["surface"], foreground=p["text"],
                            bordercolor=p["border"], rowheight=26)
            style.map("Sidebar.Treeview", background=[("selected", p["primary"])],
                      foreground=[("selected", p["sel_fg"])])
            style.configure("TScrollbar", background=p["surface"],
                            troughcolor=p["bg"], bordercolor=p["border"],
                            arrowcolor=p["text"])
            style.configure("TSeparator", background=p["border"])

            for widget, role in list(self._tracked):
                try:
                    if role == "listbox":
                        widget.configure(bg=p["surface"], fg=p["text"],
                                         selectbackground=p["primary"],
                                         selectforeground=p["sel_fg"],
                                         highlightthickness=1,
                                         highlightbackground=p["border"],
                                         borderwidth=0)
                    else:  # any tk.Text
                        widget.configure(bg=p["surface"], fg=p["text"],
                                         insertbackground=p["text"],
                                         selectbackground=p["primary"],
                                         selectforeground=p["sel_fg"],
                                         highlightthickness=1,
                                         highlightbackground=p["border"],
                                         borderwidth=0)
                        try:
                            widget.tag_configure("hl", background=p["hl"])
                        except Exception:
                            pass
                except Exception:
                    pass

        def toggle_theme(self):
            self.theme = "dark" if self.theme == "light" else "light"
            guiconfig.set_theme(self.theme)
            self._apply_theme()
            self._theme_btn.configure(
                text="☀ Light mode" if self.theme == "dark" else "🌙 Dark mode")

        # ---- menu
        def _build_menu(self):
            bar = tk.Menu(self)
            filem = tk.Menu(bar, tearoff=0)
            filem.add_command(label="Open into current tool…", accelerator="Ctrl+O",
                              command=self._open_into_current)
            self._recent_menu = tk.Menu(filem, tearoff=0)
            filem.add_cascade(label="Open Recent", menu=self._recent_menu)
            self._fill_recent_menu()
            filem.add_separator()
            filem.add_command(label="Exit", command=self.destroy)
            bar.add_cascade(label="File", menu=filem)

            viewm = tk.Menu(bar, tearoff=0)
            viewm.add_command(label="Toggle dark mode", command=self.toggle_theme)
            bar.add_cascade(label="View", menu=viewm)

            helpm = tk.Menu(bar, tearoff=0)
            helpm.add_command(label="About", command=self._about)
            helpm.add_command(label="Open project page (quickopen.ai)",
                              command=lambda: open_with_default_app(PROJECT_URL))
            bar.add_cascade(label="Help", menu=helpm)
            self.configure(menu=bar)
            self.bind_all("<Control-o>", lambda e: self._open_into_current())

        def _fill_recent_menu(self):
            self._recent_menu.delete(0, "end")
            recent = guiconfig.get_recent()
            if not recent:
                self._recent_menu.add_command(label="(none)", state="disabled")
                return
            for path in recent:
                exists = os.path.exists(path)
                label = path if exists else path + "   (missing)"
                self._recent_menu.add_command(
                    label=label, state="normal" if exists else "disabled",
                    command=(lambda pp=path: self._load_file_into_current(pp)))
            self._recent_menu.add_separator()
            self._recent_menu.add_command(label="Clear list", command=self._clear_recent)

        def _clear_recent(self):
            guiconfig.clear_recent()
            self._fill_recent_menu()

        def remember_input(self, path):
            if path:
                guiconfig.add_recent(path)
                self._fill_recent_menu()

        # ---- layout
        def _build_layout(self):
            top = ttk.Frame(self, style="Sidebar.TFrame", padding=(12, 8))
            top.pack(fill="x", side="top")
            ttk.Label(top, text="Text & Data Toolkit", style="Brand.TLabel").pack(side="left")
            ttk.Label(top, style="Status.TLabel",
                      text="  offline · open source · by QuickOpen").pack(side="left")
            self._theme_btn = ttk.Button(
                top, style="Toggle.TButton", command=self.toggle_theme,
                text="☀ Light mode" if self.theme == "dark" else "🌙 Dark mode")
            self._theme_btn.pack(side="right")

            body = ttk.Frame(self, style="TFrame")
            body.pack(fill="both", expand=True)

            side = ttk.Frame(body, style="Sidebar.TFrame", width=210)
            side.pack(side="left", fill="y")
            side.pack_propagate(False)
            self.nav = ttk.Treeview(side, show="tree", selectmode="browse",
                                    style="Sidebar.Treeview")
            self.nav.pack(fill="both", expand=True, padx=6, pady=6)
            self._nav_ids = {}
            for tid, label in TOOL_LIST:
                iid = self.nav.insert("", "end", text="  " + label)
                self._nav_ids[iid] = tid
            self.nav.bind("<<TreeviewSelect>>", self._on_nav_select)

            main = ttk.Frame(body, style="TFrame", padding=(16, 12))
            main.pack(side="left", fill="both", expand=True)

            head = ttk.Frame(main, style="TFrame")
            head.pack(fill="x")
            self.title_lbl = ttk.Label(head, text="Welcome", style="Header.TLabel")
            self.title_lbl.pack(anchor="w")
            self.desc_lbl = ttk.Label(head, text="", style="Sub.TLabel",
                                      wraplength=760, justify="left")
            self.desc_lbl.pack(anchor="w", pady=(2, 8))
            ttk.Separator(main).pack(fill="x")

            self.container = ttk.Frame(main, style="TFrame")
            self.container.pack(fill="both", expand=True, pady=(10, 8))

            bar = ttk.Frame(self, style="Sidebar.TFrame", padding=(12, 6))
            bar.pack(fill="x", side="bottom")
            self.status_lbl = ttk.Label(bar, text="Ready", style="Status.TLabel",
                                        width=14, anchor="w")
            self.status_lbl.pack(side="left")
            self.result_lbl = ttk.Label(bar, text="", style="Status.TLabel",
                                        anchor="w", wraplength=760, justify="left")
            self.result_lbl.pack(side="left", fill="x", expand=True, padx=8)

        def _select_first_tool(self):
            for iid in self._nav_ids:
                self.nav.selection_set(iid)
                self.nav.see(iid)
                break

        def _on_nav_select(self, _e=None):
            sel = self.nav.selection()
            if not sel:
                return
            tid = self._nav_ids.get(sel[0])
            if tid:
                self._show_tool(tid)

        def _show_tool(self, tool_id):
            if self._current is not None:
                self._current.pack_forget()
            panel = self._panels.get(tool_id)
            if panel is None:
                panel = ttk.Frame(self.container, style="TFrame")
                builder = getattr(self, "_panel_" + tool_id, None)
                if builder:
                    builder(panel)
                else:
                    ttk.Label(panel, text="Not implemented.").pack()
                self._panels[tool_id] = panel
                self._apply_theme()
            panel.pack(fill="both", expand=True)
            self._current = panel
            for tid, label in TOOL_LIST:
                if tid == tool_id:
                    self.title_lbl.configure(text=label)
                    break
            self.desc_lbl.configure(text=TOOL_DESCRIPTIONS.get(tool_id, ""))
            self._clear_result()

        # ---- background operation runner
        def _bg(self, work, on_ok, button=None, busy="Working…"):
            """Run ``work()`` off the UI thread; call ``on_ok(result)`` back on it."""
            if self._busy:
                self._show_error("Please wait — an operation is already running.")
                return
            self._busy = True
            if button is not None:
                try:
                    button.state(["disabled"])
                except Exception:
                    pass
            self._set_status(busy, kind="working")

            def run():
                try:
                    res, err = work(), None
                except TextKitError as ex:
                    res, err = None, str(ex)
                except Exception as ex:  # never leak a traceback
                    res, err = None, f"Unexpected error: {ex}"
                self.after(0, lambda: finish(res, err))

            def finish(res, err):
                self._busy = False
                if button is not None:
                    try:
                        button.state(["!disabled"])
                    except Exception:
                        pass
                if err is not None:
                    self._set_status("error", kind="err")
                    self._show_error(err)
                    return
                self._set_status("done", kind="ok")
                try:
                    on_ok(res)
                except Exception as ex:
                    self._show_error(f"Post-processing error: {ex}")

            threading.Thread(target=run, daemon=True).start()

        # ---- result bar helpers
        def _set_status(self, text, kind="idle"):
            p = self._pal()
            color = {"working": p["primary"], "ok": p["ok"], "err": p["err"]}.get(
                kind, p["muted"])
            self.status_lbl.configure(text=text, foreground=color)

        def _clear_result(self):
            self.result_lbl.configure(text="")
            self._set_status("Ready")

        def _show_error(self, message):
            self.result_lbl.configure(text="✕ " + message, foreground=self._pal()["err"])
            self._set_status("error", kind="err")

        def report_success(self, message):
            self.result_lbl.configure(text="✓ " + message, foreground=self._pal()["ok"])
            self._set_status("done", kind="ok")

        # ---- shared small helpers
        def _copy(self, text):
            try:
                self.clipboard_clear()
                self.clipboard_append(text)
                self.report_success("Copied output to clipboard.")
            except Exception as exc:
                self._show_error(f"Could not copy: {exc}")

        def _open_file_text(self):
            path = filedialog.askopenfilename(title="Open file", filetypes=TEXT_TYPES)
            if not path:
                return None
            self.remember_input(path)
            return self._read_file(path)

        def _read_file(self, path):
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    return fh.read()
            except OSError as exc:
                self._show_error(f"Could not read {path}: {exc}")
                return None

        def _save_text(self, text, default_ext=".txt"):
            path = filedialog.asksaveasfilename(title="Save output",
                                                defaultextension=default_ext,
                                                filetypes=TEXT_TYPES)
            if not path:
                return
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(text)
                self.remember_input(path)
                self.report_success(f"Saved → {path}")
            except OSError as exc:
                self._show_error(f"Could not save: {exc}")

        # File-open menu routing: each panel may register an input Text widget.
        def _register_input(self, widget):
            self._active_input = widget

        def _open_into_current(self):
            widget = getattr(self, "_active_input", None)
            if widget is None:
                self._show_error("The current tool has no text input to load into.")
                return
            content = self._open_file_text()
            if content is not None:
                set_text(widget, content)

        def _load_file_into_current(self, path):
            widget = getattr(self, "_active_input", None)
            content = self._read_file(path)
            if content is not None and widget is not None:
                set_text(widget, content)
                self.remember_input(path)

        # =================================================================
        # PANELS
        # =================================================================
        def _io_buttons(self, parent, get_input_widget, get_output_text,
                        default_ext=".txt"):
            """A row of Open / Save-output / Copy buttons shared by most panels."""
            row = ttk.Frame(parent, style="TFrame")
            ttk.Button(row, text="Open file…",
                       command=lambda: self._panel_open(get_input_widget())).pack(side="left")
            ttk.Button(row, text="Save output…",
                       command=lambda: self._save_text(get_output_text(), default_ext)
                       ).pack(side="left", padx=6)
            ttk.Button(row, text="Copy output",
                       command=lambda: self._copy(get_output_text())).pack(side="left")
            return row

        def _panel_open(self, widget):
            content = self._open_file_text()
            if content is not None and widget is not None:
                set_text(widget, content)

        # ---------- Convert ----------
        def _panel_convert(self, parent):
            opts = ttk.Frame(parent, style="TFrame")
            opts.pack(fill="x")
            ttk.Label(opts, text="From").pack(side="left")
            from_var = tk.StringVar(value="json")
            ttk.Combobox(opts, textvariable=from_var, values=FORMATS, width=8,
                         state="readonly").pack(side="left", padx=(4, 12))
            ttk.Label(opts, text="To").pack(side="left")
            to_var = tk.StringVar(value="yaml")
            ttk.Combobox(opts, textvariable=to_var, values=FORMATS, width=8,
                         state="readonly").pack(side="left", padx=(4, 12))
            run = ttk.Button(opts, text="Convert →", style="Accent.TButton")
            run.pack(side="left")

            ttk.Label(parent, text="Input", style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
            in_frame, in_txt = make_scrolled_text(self, parent, height=12)
            in_frame.pack(fill="both", expand=True, pady=(2, 6))
            self._register_input(in_txt)
            set_text(in_txt, '{\n  "name": "Ada",\n  "langs": ["python", "c"]\n}')

            ttk.Label(parent, text="Output", style="Muted.TLabel").pack(anchor="w")
            out_frame, out_txt = make_scrolled_text(self, parent, height=12)
            out_frame.pack(fill="both", expand=True, pady=(2, 6))

            self._io_buttons(parent, lambda: in_txt, lambda: get_text(out_txt)).pack(
                anchor="w")

            def go():
                src, dst = from_var.get(), to_var.get()
                try:
                    out = do_convert(get_text(in_txt), src, dst)
                except TextKitError as exc:
                    self._show_error(str(exc))
                    return
                set_text(out_txt, out)
                self.report_success(f"Converted {src} → {dst}.")

            run.configure(command=go)

        # ---------- Validate / Format ----------
        def _panel_format(self, parent):
            opts = ttk.Frame(parent, style="TFrame")
            opts.pack(fill="x")
            ttk.Label(opts, text="Kind").pack(side="left")
            kind_var = tk.StringVar(value="json")
            ttk.Combobox(opts, textvariable=kind_var, values=FORMATS, width=8,
                         state="readonly").pack(side="left", padx=(4, 12))
            ttk.Label(opts, text="Indent").pack(side="left")
            indent_var = tk.StringVar(value="2")
            ttk.Spinbox(opts, from_=0, to=8, width=4, textvariable=indent_var).pack(
                side="left", padx=(4, 12))

            ttk.Label(parent, text="Input", style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
            in_frame, in_txt = make_scrolled_text(self, parent, height=12)
            in_frame.pack(fill="both", expand=True, pady=(2, 6))
            self._register_input(in_txt)
            set_text(in_txt, '{"b":2,"a":1,"list":[1,2,3]}')

            btns = ttk.Frame(parent, style="TFrame")
            btns.pack(fill="x", pady=(0, 6))
            b_val = ttk.Button(btns, text="Validate", style="Accent.TButton")
            b_val.pack(side="left")
            b_pretty = ttk.Button(btns, text="Pretty-print")
            b_pretty.pack(side="left", padx=6)
            b_min = ttk.Button(btns, text="Minify")
            b_min.pack(side="left")

            ttk.Label(parent, text="Output", style="Muted.TLabel").pack(anchor="w")
            out_frame, out_txt = make_scrolled_text(self, parent, height=12)
            out_frame.pack(fill="both", expand=True, pady=(2, 6))
            self._io_buttons(parent, lambda: in_txt, lambda: get_text(out_txt)).pack(
                anchor="w")

            def _indent():
                try:
                    return max(0, int(indent_var.get()))
                except ValueError:
                    return 2

            def do_validate():
                ok, err = do_validate(get_text(in_txt), kind_var.get())
                if ok:
                    self.report_success(f"Valid {kind_var.get()}.")
                    set_text(out_txt, f"✓ valid {kind_var.get()}")
                else:
                    self._show_error(f"Invalid {kind_var.get()}: {err}")
                    set_text(out_txt, f"✕ invalid {kind_var.get()}: {err}")

            def do_pretty():
                try:
                    out = do_pretty(get_text(in_txt), kind_var.get(), _indent())
                except TextKitError as exc:
                    self._show_error(str(exc))
                    return
                set_text(out_txt, out)
                self.report_success("Formatted.")

            def do_minify():
                try:
                    out = do_minify(get_text(in_txt), kind_var.get())
                except TextKitError as exc:
                    self._show_error(str(exc))
                    return
                set_text(out_txt, out)
                self.report_success("Minified.")

            b_val.configure(command=do_validate)
            b_pretty.configure(command=do_pretty)
            b_min.configure(command=do_minify)

        # ---------- Diff ----------
        def _panel_diff(self, parent):
            opts = ttk.Frame(parent, style="TFrame")
            opts.pack(fill="x")
            mode = tk.StringVar(value="text")
            ttk.Radiobutton(opts, text="Unified text diff", value="text",
                            variable=mode).pack(side="left")
            ttk.Radiobutton(opts, text="Structural JSON diff", value="json",
                            variable=mode).pack(side="left", padx=(12, 0))
            run = ttk.Button(opts, text="Compare", style="Accent.TButton")
            run.pack(side="left", padx=12)

            pair = ttk.Frame(parent, style="TFrame")
            pair.pack(fill="both", expand=True, pady=(8, 6))
            left = ttk.Frame(pair, style="TFrame")
            left.pack(side="left", fill="both", expand=True, padx=(0, 4))
            right = ttk.Frame(pair, style="TFrame")
            right.pack(side="left", fill="both", expand=True, padx=(4, 0))
            ttk.Label(left, text="A", style="Muted.TLabel").pack(anchor="w")
            a_frame, a_txt = make_scrolled_text(self, left, height=10)
            a_frame.pack(fill="both", expand=True)
            ttk.Label(right, text="B", style="Muted.TLabel").pack(anchor="w")
            b_frame, b_txt = make_scrolled_text(self, right, height=10)
            b_frame.pack(fill="both", expand=True)
            self._register_input(a_txt)
            set_text(a_txt, "one\ntwo\nthree\n")
            set_text(b_txt, "one\ntwo\nTHREE\nfour\n")

            ttk.Label(parent, text="Result", style="Muted.TLabel").pack(anchor="w")
            out_frame, out_txt = make_scrolled_text(self, parent, height=12)
            out_frame.pack(fill="both", expand=True, pady=(2, 6))
            ttk.Button(parent, text="Copy result",
                       command=lambda: self._copy(get_text(out_txt))).pack(anchor="w")

            def go():
                a, b = get_text(a_txt), get_text(b_txt)
                try:
                    if mode.get() == "json":
                        import json as _json
                        result = diff_mod.json_diff(a, b)
                        out = _json.dumps(result, indent=2, ensure_ascii=False)
                    else:
                        out = diff_mod.text_diff(a, b, a_label="A", b_label="B")
                        out = out or "(no differences)"
                except TextKitError as exc:
                    self._show_error(str(exc))
                    return
                set_text(out_txt, out)
                self.report_success("Compared.")

            run.configure(command=go)

        # ---------- Regex ----------
        def _panel_regex(self, parent):
            top = ttk.Frame(parent, style="TFrame")
            top.pack(fill="x")
            ttk.Label(top, text="Pattern").pack(side="left")
            pat_var = tk.StringVar(value=r"\b(\w+)@(\w+)\b")
            ttk.Entry(top, textvariable=pat_var).pack(side="left", fill="x",
                                                      expand=True, padx=6)

            flags = ttk.Frame(parent, style="TFrame")
            flags.pack(fill="x", pady=(6, 0))
            fi = tk.BooleanVar()
            fm = tk.BooleanVar()
            fs = tk.BooleanVar()
            ttk.Checkbutton(flags, text="ignorecase (i)", variable=fi).pack(side="left")
            ttk.Checkbutton(flags, text="multiline (m)", variable=fm).pack(side="left", padx=8)
            ttk.Checkbutton(flags, text="dotall (s)", variable=fs).pack(side="left")

            ttk.Label(parent, text="Test text", style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
            in_frame, in_txt = make_scrolled_text(self, parent, height=8)
            in_frame.pack(fill="both", expand=True, pady=(2, 6))
            self._register_input(in_txt)
            set_text(in_txt, "contact ada@lovelace and grace@hopper today")

            repl_row = ttk.Frame(parent, style="TFrame")
            repl_row.pack(fill="x", pady=(0, 6))
            ttk.Label(repl_row, text="Replace with").pack(side="left")
            repl_var = tk.StringVar()
            ttk.Entry(repl_row, textvariable=repl_var).pack(side="left", fill="x",
                                                            expand=True, padx=6)
            ttk.Button(repl_row, text="Replace",
                       command=lambda: do_replace()).pack(side="left")

            ttk.Label(parent, text="Matches / output", style="Muted.TLabel").pack(anchor="w")
            out_frame, out_txt = make_scrolled_text(self, parent, height=8)
            out_frame.pack(fill="both", expand=True, pady=(2, 6))
            ttk.Button(parent, text="Copy output",
                       command=lambda: self._copy(get_text(out_txt))).pack(anchor="w")

            def _flags():
                s = ""
                if fi.get():
                    s += "i"
                if fm.get():
                    s += "m"
                if fs.get():
                    s += "s"
                return s

            def highlight():
                in_txt.tag_remove("hl", "1.0", "end")
                try:
                    matches = regex_util.test_regex(pat_var.get(), get_text(in_txt),
                                                    flags=_flags())
                except TextKitError as exc:
                    self._set_status("error", kind="err")
                    self.result_lbl.configure(text="✕ " + str(exc),
                                              foreground=self._pal()["err"])
                    return
                for m in matches:
                    in_txt.tag_add("hl", f"1.0+{m['start']}c", f"1.0+{m['end']}c")
                lines = [f"{len(matches)} match(es):"]
                for m in matches:
                    lines.append(f"  [{m['start']}:{m['end']}] {m['match']!r}")
                    if m["groups"]:
                        lines.append(f"      groups: {m['groups']}")
                    if m["groupdict"]:
                        lines.append(f"      named:  {m['groupdict']}")
                set_text(out_txt, "\n".join(lines))
                self.report_success(f"{len(matches)} match(es).")

            def do_replace():
                try:
                    out = regex_util.replace(pat_var.get(), repl_var.get(),
                                             get_text(in_txt), flags=_flags())
                except TextKitError as exc:
                    self._show_error(str(exc))
                    return
                set_text(out_txt, out)
                self.report_success("Replaced.")

            # live highlight on edits / pattern change
            pat_var.trace_add("write", lambda *_: highlight())
            for var in (fi, fm, fs):
                var.trace_add("write", lambda *_: highlight())
            in_txt.bind("<KeyRelease>", lambda e: highlight())
            self.after(80, highlight)

        # ---------- Hash ----------
        def _panel_hash(self, parent):
            opts = ttk.Frame(parent, style="TFrame")
            opts.pack(fill="x")
            ttk.Label(opts, text="Algorithm").pack(side="left")
            algo_var = tk.StringVar(value="sha256")
            ttk.Combobox(opts, textvariable=algo_var, values=HASH_ALGOS, width=10,
                         state="readonly").pack(side="left", padx=(4, 12))
            b_text = ttk.Button(opts, text="Hash text", style="Accent.TButton")
            b_text.pack(side="left")
            b_file = ttk.Button(opts, text="Hash file…")
            b_file.pack(side="left", padx=6)

            ttk.Label(parent, text="Text to hash", style="Muted.TLabel").pack(
                anchor="w", pady=(8, 0))
            in_frame, in_txt = make_scrolled_text(self, parent, height=10)
            in_frame.pack(fill="both", expand=True, pady=(2, 6))
            self._register_input(in_txt)
            set_text(in_txt, "abc")

            ttk.Label(parent, text="Digest", style="Muted.TLabel").pack(anchor="w")
            out_frame, out_txt = make_scrolled_text(self, parent, height=6)
            out_frame.pack(fill="both", expand=True, pady=(2, 6))
            ttk.Button(parent, text="Copy digest",
                       command=lambda: self._copy(get_text(out_txt))).pack(anchor="w")

            def hash_text():
                try:
                    digest = hashing.hash_text(get_text(in_txt), algo=algo_var.get())
                except TextKitError as exc:
                    self._show_error(str(exc))
                    return
                set_text(out_txt, digest)
                self.report_success(f"{algo_var.get()} of text.")

            def hash_file():
                path = filedialog.askopenfilename(title="Choose a file to hash")
                if not path:
                    return
                self.remember_input(path)
                self._bg(
                    lambda: hashing.hash_file(path, algo=algo_var.get()),
                    lambda digest: (set_text(out_txt, f"{digest}  {path}"),
                                    self.report_success(f"{algo_var.get()} of file.")),
                    button=b_file, busy="Hashing…")

            b_text.configure(command=hash_text)
            b_file.configure(command=hash_file)

        # ---------- Encode / Decode ----------
        def _panel_encode(self, parent):
            opts = ttk.Frame(parent, style="TFrame")
            opts.pack(fill="x")
            ttk.Label(opts, text="Codec").pack(side="left")
            codec_var = tk.StringVar(value="base64")
            ttk.Combobox(opts, textvariable=codec_var, values=CODECS, width=10,
                         state="readonly").pack(side="left", padx=(4, 12))
            b_enc = ttk.Button(opts, text="Encode →", style="Accent.TButton")
            b_enc.pack(side="left")
            b_dec = ttk.Button(opts, text="Decode →")
            b_dec.pack(side="left", padx=6)

            ttk.Label(parent, text="Input", style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
            in_frame, in_txt = make_scrolled_text(self, parent, height=10)
            in_frame.pack(fill="both", expand=True, pady=(2, 6))
            self._register_input(in_txt)
            set_text(in_txt, "Hello, Text & Data Toolkit!")

            ttk.Label(parent, text="Output", style="Muted.TLabel").pack(anchor="w")
            out_frame, out_txt = make_scrolled_text(self, parent, height=10)
            out_frame.pack(fill="both", expand=True, pady=(2, 6))
            self._io_buttons(parent, lambda: in_txt, lambda: get_text(out_txt)).pack(
                anchor="w")

            def do(fn, verb):
                try:
                    out = fn(get_text(in_txt), codec_var.get())
                except TextKitError as exc:
                    self._show_error(str(exc))
                    return
                set_text(out_txt, out)
                self.report_success(f"{verb} ({codec_var.get()}).")

            b_enc.configure(command=lambda: do(encoding.encode, "Encoded"))
            b_dec.configure(command=lambda: do(encoding.decode, "Decoded"))

        # ---------- JWT ----------
        def _panel_jwt(self, parent):
            ttk.Label(parent, text="Paste a JWT (header.payload.signature):",
                      style="Muted.TLabel").pack(anchor="w")
            in_frame, in_txt = make_scrolled_text(self, parent, height=6)
            in_frame.pack(fill="both", expand=True, pady=(2, 6))
            self._register_input(in_txt)
            set_text(in_txt,
                     "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
                     "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ."
                     "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c")

            row = ttk.Frame(parent, style="TFrame")
            row.pack(fill="x", pady=(0, 6))
            run = ttk.Button(row, text="Decode", style="Accent.TButton")
            run.pack(side="left")
            ttk.Label(row, style="Sub.TLabel",
                      text="  Decode only — the signature is NOT verified.").pack(side="left")

            ttk.Label(parent, text="Decoded", style="Muted.TLabel").pack(anchor="w")
            out_frame, out_txt = make_scrolled_text(self, parent, height=14)
            out_frame.pack(fill="both", expand=True, pady=(2, 6))
            ttk.Button(parent, text="Copy output",
                       command=lambda: self._copy(get_text(out_txt))).pack(anchor="w")

            def go():
                import json as _json
                try:
                    result = encoding.jwt_decode(get_text(in_txt).strip())
                except TextKitError as exc:
                    self._show_error(str(exc))
                    return
                out = ("HEADER\n" + _json.dumps(result["header"], indent=2) +
                       "\n\nPAYLOAD\n" + _json.dumps(result["payload"], indent=2) +
                       "\n\nSIGNATURE (not verified)\n" + result["signature"])
                set_text(out_txt, out)
                self.report_success("Decoded JWT (unverified).")

            run.configure(command=go)

        # ---------- Text transforms ----------
        def _panel_text(self, parent):
            opts = ttk.Frame(parent, style="TFrame")
            opts.pack(fill="x")
            ttk.Label(opts, text="Transform").pack(side="left")
            op_var = tk.StringVar(value="snake")
            ttk.Combobox(opts, textvariable=op_var, values=TEXT_OPS, width=14,
                         state="readonly").pack(side="left", padx=(4, 12))
            rev = tk.BooleanVar()
            ttk.Checkbutton(opts, text="reverse (sort)", variable=rev).pack(side="left")
            ttk.Label(opts, text="wrap width").pack(side="left", padx=(12, 2))
            width_var = tk.StringVar(value="80")
            ttk.Spinbox(opts, from_=1, to=200, width=5, textvariable=width_var).pack(side="left")
            run = ttk.Button(opts, text="Apply", style="Accent.TButton")
            run.pack(side="left", padx=12)

            ttk.Label(parent, text="Input", style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
            in_frame, in_txt = make_scrolled_text(self, parent, height=10, mono=False)
            in_frame.pack(fill="both", expand=True, pady=(2, 6))
            self._register_input(in_txt)
            set_text(in_txt, "Hello World Example")

            ttk.Label(parent, text="Output", style="Muted.TLabel").pack(anchor="w")
            out_frame, out_txt = make_scrolled_text(self, parent, height=10, mono=False)
            out_frame.pack(fill="both", expand=True, pady=(2, 6))
            info = ttk.Label(parent, text="", style="Sub.TLabel")
            info.pack(anchor="w")
            self._io_buttons(parent, lambda: in_txt, lambda: get_text(out_txt)).pack(
                anchor="w", pady=(4, 0))

            def go():
                op = op_var.get()
                text = get_text(in_txt)
                try:
                    if op == "sort":
                        out = textops.sort_lines(text, reverse=rev.get())
                    elif op == "wrap":
                        out = textops.wrap(text, width=int(width_var.get() or 80))
                    else:
                        out = textops.apply(op, text)
                except (TextKitError, ValueError) as exc:
                    self._show_error(str(exc))
                    return
                set_text(out_txt, out)
                stats = textops.count(text)
                info.configure(text=(f"in: {stats['lines']} lines · {stats['words']} "
                                     f"words · {stats['chars']} chars"))
                self.report_success(f"Applied '{op}'.")

            run.configure(command=go)

        # ---- About
        def _about(self):
            win = tk.Toplevel(self)
            win.title("About Text & Data Toolkit")
            win.configure(bg=self._pal()["bg"])
            win.resizable(False, False)
            frm = ttk.Frame(win, style="TFrame", padding=18)
            frm.pack(fill="both", expand=True)
            ttk.Label(frm, text="Text & Data Toolkit", style="Header.TLabel").pack(anchor="w")
            ttk.Label(frm, text=f"Version {APP_VERSION}",
                      style="Sub.TLabel").pack(anchor="w", pady=(0, 8))
            ttk.Label(frm, style="TLabel", justify="left", wraplength=400,
                      text="A fast, fully-offline toolkit for text and data: convert "
                           "JSON/YAML/CSV/XML, validate and format, diff, test regexes, "
                           "hash, encode/decode, decode JWTs and transform text.\n\n"
                           "100% AI-built, open source, published on QuickOpen.\n"
                           "Nothing is ever uploaded anywhere.").pack(anchor="w")
            ttk.Label(frm, style="Sub.TLabel", justify="left", wraplength=400,
                      text="Licensed under Apache-2.0. Pure Python standard library "
                           "plus PyYAML.").pack(anchor="w", pady=(8, 4))
            link = ttk.Label(frm, text="Project page: quickopen.ai",
                             style="Sub.TLabel", cursor="hand2")
            link.pack(anchor="w", pady=(4, 10))
            link.bind("<Button-1>", lambda e: open_with_default_app(PROJECT_URL))
            ttk.Button(frm, text="Close", command=win.destroy).pack(anchor="e")
            win.transient(self)
            win.grab_set()

    return App


def main():
    """Entry point: build the root window and run.  Degrades on headless hosts.

    Importing this module does nothing; only this function creates a Tk root.
    With no display (e.g. a server), it prints a friendly note and returns 0
    instead of raising.
    """
    try:
        import tkinter as tk
    except Exception as exc:  # tkinter missing entirely
        print(f"{APP_NAME}: a graphical environment with tkinter is required "
              f"to run the GUI ({exc}).")
        return 0

    try:
        App = build_app()
        app = App()
    except tk.TclError as exc:
        print(f"{APP_NAME}: no graphical display available — cannot start the "
              f"GUI here ({exc}). This app is intended for the Windows desktop.")
        return 0
    except Exception as exc:
        print(f"{APP_NAME}: could not start the GUI ({exc}).")
        return 1

    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
