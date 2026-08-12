#!/usr/bin/env python3
r"""Text & Data Toolkit -- an Aura (QuickOpen design system) GUI over ``textkit``.

A single Aura window: the sidebar lists the tools (Convert, Validate/Format,
Diff, Regex tester, Hash, Encode/Decode, JWT, Text transforms, About) and the
main panel swaps to the selected tool.  Every operation calls the tested core
library (never re-implements logic); file hashing runs on a background thread
so the UI stays responsive.  Results appear in an output area with Copy/Save
buttons, and any :class:`TextKitError` is shown in the Aura status bar (never
as a traceback).

Design goals baked in here (mirrors the QuickOpen house style):
  * built on the vendored ``textkit/aura.py`` design system, which layers the
    quickopen.ai look (deep space + light) over CustomTkinter.  Runtime deps:
    ``customtkinter`` (+ ``darkdetect``) -- declared in requirements.txt; the
    PyInstaller build adds ``--collect-all customtkinter``.
  * Importing this module does nothing.  Only :func:`main` builds a root
    window, and it degrades gracefully (prints a message, returns 0) with no
    display or with customtkinter missing.
  * Frozen-exe safe: bundled assets are resolved via ``sys._MEIPASS`` / the
    exe directory when ``sys.frozen`` is set -- never ``__file__``.

100% AI-built, open source, published on QuickOpen (quickopen.ai).
"""

from __future__ import annotations

import os
import sys
import threading

# NOTE: tkinter/customtkinter are imported lazily inside main()/build_app so
# that merely importing this module (e.g. during packaging or on a headless CI
# box) never fails.

APP_NAME = "Text & Data Toolkit"
APP_VERSION = "1.0.0"
WINDOW_TITLE = "Text & Data Toolkit — by QuickOpen (quickopen.ai)"
PROJECT_URL = "https://quickopen.ai"
ACCENT = "#2f5fe0"      # publish/specs/text-data-toolkit.json "accent": [47, 95, 224]

TEXT_TYPES = [
    ("Text/data files", "*.json *.yaml *.yml *.xml *.csv *.txt"),
    ("All files", "*.*"),
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
# The app (built lazily; tkinter/customtkinter imported only inside build_app)
# ---------------------------------------------------------------------------
def build_app():
    """Construct and return the App class bound to live GUI imports.

    Kept inside a function so this module imports cleanly without a display
    (and without customtkinter installed).
    """
    import tkinter as tk
    from tkinter import ttk, filedialog
    import customtkinter as ctk

    from . import aura, guiconfig
    from .errors import TextKitError
    # Import functions directly: ``from . import convert`` would resolve to the
    # re-exported *function* of that name rather than the submodule (textkit's
    # __init__ rebinds those package attributes).
    from .convert import convert as kit_convert
    from .validate import validate as kit_validate, pretty as kit_pretty, \
        minify as kit_minify
    from . import diff as diff_mod
    from . import regex_util
    from . import hashing
    from . import encoding
    from . import textops

    MONO = "Consolas"   # falls back gracefully off-Windows, as before

    # -- small reusable widgets ------------------------------------------
    def make_scrolled_text(app, master, height=10, mono=True):
        """A framed tk.Text with scrollbars, registered for Aura theme flips."""
        frame = ctk.CTkFrame(master, fg_color="transparent")
        txt = tk.Text(frame, height=height, wrap="none", undo=True,
                      font=((MONO, 10) if mono else aura.font()),
                      borderwidth=0)
        sb = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
        hb = ttk.Scrollbar(frame, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=sb.set, xscrollcommand=hb.set)
        sb.pack(side="right", fill="y")
        hb.pack(side="bottom", fill="x")
        txt.pack(side="left", fill="both", expand=True)
        aura.track(txt, "text")
        return frame, txt

    def get_text(widget):
        return widget.get("1.0", "end-1c")

    def set_text(widget, value):
        widget.delete("1.0", "end")
        widget.insert("1.0", value)

    # -- the main window --------------------------------------------------
    class App(aura.AuraApp):
        def __init__(self):
            super().__init__(
                title=WINDOW_TITLE, app_name=APP_NAME, accent=ACCENT,
                theme=guiconfig.get_theme(),
                icon_png=asset_path("text-data-toolkit.png"),
                version=APP_VERSION, tagline="offline text & data tools",
                on_theme_change=guiconfig.set_theme,
                size=(1080, 700), min_size=(900, 560))

            self._busy = False
            # NOTE: AuraApp.__init__ already created self._img_refs and put
            # the sidebar brand PhotoImage in it — never reassign it, or the
            # image is garbage-collected and the brand icon goes blank.
            self._img_refs_gui = []
            self._hl_texts = []     # tk.Text widgets carrying the "hl" tag

            self._set_icon()
            self._build_menu()
            self.add_section("convert", "Convert", "⇄", self._panel_convert)
            self.add_section("format", "Validate / Format", "▤",
                             self._panel_format)
            self.add_section("diff", "Diff", "⇅", self._panel_diff)
            self.add_section("regex", "Regex tester", "⚲", self._panel_regex)
            self.add_section("hash", "Hash / Checksum", "▦", self._panel_hash)
            self.add_section("encode", "Encode / Decode", "◈",
                             self._panel_encode)
            self.add_section("jwt", "JWT decoder", "⊚", self._panel_jwt)
            self.add_section("text", "Text transforms", "✎", self._panel_text)
            self.add_section("about", "About", "ℹ", self._panel_about)
            self.show("convert")
            self.set_status("Ready")
            self.protocol("WM_DELETE_WINDOW", self.destroy)

        # ---- assets / icon
        def _set_icon(self):
            try:
                ico = asset_path("text-data-toolkit.ico")
                if ico and os.name == "nt":
                    self.iconbitmap(ico)
                    return
            except Exception:
                pass
            try:
                png = asset_path("text-data-toolkit.png")
                if png:
                    img = tk.PhotoImage(file=png)
                    self._img_refs_gui.append(img)
                    self.iconphoto(True, img)
            except Exception:
                pass  # icon is cosmetic; never block launch

        # ---- theme: re-tint the regex highlight tag after a flip
        def set_theme(self, theme):
            super().set_theme(theme)
            self._retag_highlights()

        def _retag_highlights(self):
            for txt in list(self._hl_texts):
                try:
                    txt.tag_configure("hl",
                                      background=aura.P("accent_soft"),
                                      foreground=aura.P("text"))
                except Exception:
                    pass

        # ---- menu (native menus stay; theme lives in the sidebar toggle too)
        def _build_menu(self):
            bar = tk.Menu(self)
            filem = tk.Menu(bar, tearoff=0)
            filem.add_command(label="Open into current tool…",
                              accelerator="Ctrl+O",
                              command=self._open_into_current)
            self._recent_menu = tk.Menu(filem, tearoff=0)
            filem.add_cascade(label="Open Recent", menu=self._recent_menu)
            self._fill_recent_menu()
            filem.add_separator()
            filem.add_command(label="Exit", command=self.destroy)
            bar.add_cascade(label="File", menu=filem)

            viewm = tk.Menu(bar, tearoff=0)
            viewm.add_command(
                label="Toggle dark mode",
                command=lambda: self.set_theme(
                    "light" if self.theme == "dark" else "dark"))
            bar.add_cascade(label="View", menu=viewm)

            helpm = tk.Menu(bar, tearoff=0)
            helpm.add_command(label="About",
                              command=lambda: self.show("about"))
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
            self._recent_menu.add_command(label="Clear list",
                                          command=self._clear_recent)

        def _clear_recent(self):
            guiconfig.clear_recent()
            self._fill_recent_menu()

        def remember_input(self, path):
            if path:
                guiconfig.add_recent(path)
                self._fill_recent_menu()

        # ---- background operation runner
        def _bg(self, work, on_ok, button=None, busy="Working…"):
            """Run ``work()`` off the UI thread; call ``on_ok(result)`` back on it."""
            if self._busy:
                self.set_error("Please wait — an operation is already running.")
                return
            self._busy = True
            if button is not None:
                try:
                    button.state(["disabled"])
                except Exception:
                    pass
            self.set_status(busy, kind="working")

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
                    self.set_error(err)
                    return
                try:
                    on_ok(res)
                except Exception as ex:
                    self.set_error(f"Post-processing error: {ex}")

            threading.Thread(target=run, daemon=True).start()

        # ---- status helpers (kept as thin wrappers over the Aura status bar)
        def _show_error(self, message):
            self.set_error(message)

        def report_success(self, message):
            self.set_success(message)

        # ---- shared small helpers
        def _copy(self, text):
            try:
                self.clipboard_clear()
                self.clipboard_append(text)
                self.report_success("Copied output to clipboard.")
            except Exception as exc:
                self._show_error(f"Could not copy: {exc}")

        def _open_file_text(self):
            path = filedialog.askopenfilename(title="Open file",
                                              filetypes=TEXT_TYPES)
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
        def _describe(self, parent, tool_id):
            """The tool's one-line description, under the header."""
            aura.Caption(parent, TOOL_DESCRIPTIONS.get(tool_id, ""),
                         wraplength=820, justify="left", anchor="w").pack(
                anchor="w", pady=(0, 10))

        def _io_buttons(self, parent, get_input_widget, get_output_text,
                        default_ext=".txt"):
            """A row of Open / Save-output / Copy buttons shared by most panels."""
            row = ctk.CTkFrame(parent, fg_color="transparent")
            aura.AuraButton(row, "Open file…", kind="secondary",
                            command=lambda: self._panel_open(
                                get_input_widget())).pack(side="left")
            aura.AuraButton(row, "Save output…", kind="secondary",
                            command=lambda: self._save_text(
                                get_output_text(), default_ext)).pack(
                side="left", padx=8)
            aura.AuraButton(row, "Copy output", kind="secondary",
                            command=lambda: self._copy(
                                get_output_text())).pack(side="left")
            return row

        def _panel_open(self, widget):
            content = self._open_file_text()
            if content is not None and widget is not None:
                set_text(widget, content)

        # ---------- Convert ----------
        def _panel_convert(self, parent):
            self._describe(parent, "convert")
            opts = ctk.CTkFrame(parent, fg_color="transparent")
            opts.pack(fill="x")
            ctk.CTkLabel(opts, text="From", font=aura.font()).pack(side="left")
            from_var = tk.StringVar(value="json")
            aura.AuraCombo(opts, variable=from_var, values=FORMATS, width=110,
                           state="readonly").pack(side="left", padx=(6, 14))
            ctk.CTkLabel(opts, text="To", font=aura.font()).pack(side="left")
            to_var = tk.StringVar(value="yaml")
            aura.AuraCombo(opts, variable=to_var, values=FORMATS, width=110,
                           state="readonly").pack(side="left", padx=(6, 14))
            run = aura.AuraButton(opts, "Convert →")
            run.pack(side="left")

            in_frame, in_txt = make_scrolled_text(self, parent, height=10)
            out_frame, out_txt = make_scrolled_text(self, parent, height=10)
            self._register_input(in_txt)
            set_text(in_txt, '{\n  "name": "Ada",\n  "langs": ["python", "c"]\n}')

            # bottom action row is packed FIRST (side="bottom") so the
            # expanding text areas can never squeeze it out of the window
            self._io_buttons(parent, lambda: in_txt,
                             lambda: get_text(out_txt)).pack(
                side="bottom", fill="x", pady=(8, 0))

            aura.SectionLabel(parent, "Input").pack(anchor="w", pady=(12, 2))
            in_frame.pack(fill="both", expand=True, pady=(0, 8))
            aura.SectionLabel(parent, "Output").pack(anchor="w", pady=(0, 2))
            out_frame.pack(fill="both", expand=True)

            def go():
                src, dst = from_var.get(), to_var.get()
                try:
                    out = kit_convert(get_text(in_txt), src, dst)
                except TextKitError as exc:
                    self._show_error(str(exc))
                    return
                set_text(out_txt, out)
                self.report_success(f"Converted {src} → {dst}.")

            run.configure(command=go)

        # ---------- Validate / Format ----------
        def _panel_format(self, parent):
            self._describe(parent, "format")
            opts = ctk.CTkFrame(parent, fg_color="transparent")
            opts.pack(fill="x")
            ctk.CTkLabel(opts, text="Kind", font=aura.font()).pack(side="left")
            kind_var = tk.StringVar(value="json")
            aura.AuraCombo(opts, variable=kind_var, values=FORMATS, width=110,
                           state="readonly").pack(side="left", padx=(6, 14))
            ctk.CTkLabel(opts, text="Indent", font=aura.font()).pack(side="left")
            indent_var = tk.StringVar(value="2")
            ttk.Spinbox(opts, from_=0, to=8, width=4,
                        textvariable=indent_var).pack(side="left", padx=(6, 14))

            in_frame, in_txt = make_scrolled_text(self, parent, height=10)
            out_frame, out_txt = make_scrolled_text(self, parent, height=10)
            self._register_input(in_txt)
            set_text(in_txt, '{"b":2,"a":1,"list":[1,2,3]}')

            self._io_buttons(parent, lambda: in_txt,
                             lambda: get_text(out_txt)).pack(
                side="bottom", fill="x", pady=(8, 0))

            aura.SectionLabel(parent, "Input").pack(anchor="w", pady=(12, 2))
            in_frame.pack(fill="both", expand=True, pady=(0, 8))

            btns = ctk.CTkFrame(parent, fg_color="transparent")
            btns.pack(fill="x", pady=(0, 8))
            b_val = aura.AuraButton(btns, "Validate")
            b_val.pack(side="left")
            b_pretty = aura.AuraButton(btns, "Pretty-print", kind="secondary")
            b_pretty.pack(side="left", padx=8)
            b_min = aura.AuraButton(btns, "Minify", kind="secondary")
            b_min.pack(side="left")

            aura.SectionLabel(parent, "Output").pack(anchor="w", pady=(0, 2))
            out_frame.pack(fill="both", expand=True)

            def _indent():
                try:
                    return max(0, int(indent_var.get()))
                except ValueError:
                    return 2

            def on_validate():
                ok, err = kit_validate(get_text(in_txt), kind_var.get())
                if ok:
                    self.report_success(f"Valid {kind_var.get()}.")
                    set_text(out_txt, f"✓ valid {kind_var.get()}")
                else:
                    self._show_error(f"Invalid {kind_var.get()}: {err}")
                    set_text(out_txt, f"✕ invalid {kind_var.get()}: {err}")

            def on_pretty():
                try:
                    out = kit_pretty(get_text(in_txt), kind_var.get(), _indent())
                except TextKitError as exc:
                    self._show_error(str(exc))
                    return
                set_text(out_txt, out)
                self.report_success("Formatted.")

            def on_minify():
                try:
                    out = kit_minify(get_text(in_txt), kind_var.get())
                except TextKitError as exc:
                    self._show_error(str(exc))
                    return
                set_text(out_txt, out)
                self.report_success("Minified.")

            b_val.configure(command=on_validate)
            b_pretty.configure(command=on_pretty)
            b_min.configure(command=on_minify)

        # ---------- Diff ----------
        def _panel_diff(self, parent):
            self._describe(parent, "diff")
            opts = ctk.CTkFrame(parent, fg_color="transparent")
            opts.pack(fill="x")
            mode_seg = aura.SegmentedControl(
                opts, values=["Unified text diff", "Structural JSON diff"])
            mode_seg.set("Unified text diff")
            mode_seg.pack(side="left")
            run = aura.AuraButton(opts, "Compare")
            run.pack(side="left", padx=14)

            pair = ctk.CTkFrame(parent, fg_color="transparent")
            pair.pack(fill="both", expand=True, pady=(12, 8))
            left = ctk.CTkFrame(pair, fg_color="transparent")
            left.pack(side="left", fill="both", expand=True, padx=(0, 6))
            right = ctk.CTkFrame(pair, fg_color="transparent")
            right.pack(side="left", fill="both", expand=True, padx=(6, 0))
            aura.SectionLabel(left, "A").pack(anchor="w", pady=(0, 2))
            a_frame, a_txt = make_scrolled_text(self, left, height=10)
            a_frame.pack(fill="both", expand=True)
            aura.SectionLabel(right, "B").pack(anchor="w", pady=(0, 2))
            b_frame, b_txt = make_scrolled_text(self, right, height=10)
            b_frame.pack(fill="both", expand=True)
            self._register_input(a_txt)
            set_text(a_txt, "one\ntwo\nthree\n")
            set_text(b_txt, "one\ntwo\nTHREE\nfour\n")

            out_frame, out_txt = make_scrolled_text(self, parent, height=10)
            aura.AuraButton(parent, "Copy result", kind="secondary",
                            command=lambda: self._copy(
                                get_text(out_txt))).pack(
                side="bottom", anchor="w", pady=(8, 0))
            aura.SectionLabel(parent, "Result").pack(anchor="w", pady=(0, 2))
            out_frame.pack(fill="both", expand=True)

            def go():
                a, b = get_text(a_txt), get_text(b_txt)
                try:
                    if mode_seg.get() == "Structural JSON diff":
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
            self._describe(parent, "regex")
            top = ctk.CTkFrame(parent, fg_color="transparent")
            top.pack(fill="x")
            ctk.CTkLabel(top, text="Pattern", font=aura.font()).pack(side="left")
            pat_var = tk.StringVar(value=r"\b(\w+)@(\w+)\b")
            aura.AuraEntry(top, textvariable=pat_var).pack(
                side="left", fill="x", expand=True, padx=(8, 0))

            flags = ctk.CTkFrame(parent, fg_color="transparent")
            flags.pack(fill="x", pady=(8, 0))
            fi = tk.BooleanVar()
            fm = tk.BooleanVar()
            fs = tk.BooleanVar()
            ctk.CTkCheckBox(flags, text="ignorecase (i)", variable=fi,
                            font=aura.font()).pack(side="left")
            ctk.CTkCheckBox(flags, text="multiline (m)", variable=fm,
                            font=aura.font()).pack(side="left", padx=10)
            ctk.CTkCheckBox(flags, text="dotall (s)", variable=fs,
                            font=aura.font()).pack(side="left")

            aura.SectionLabel(parent, "Test text").pack(anchor="w", pady=(12, 2))
            in_frame, in_txt = make_scrolled_text(self, parent, height=8)
            in_frame.pack(fill="both", expand=True, pady=(0, 8))
            self._register_input(in_txt)
            set_text(in_txt, "contact ada@lovelace and grace@hopper today")
            self._hl_texts.append(in_txt)
            self._retag_highlights()

            repl_row = ctk.CTkFrame(parent, fg_color="transparent")
            repl_row.pack(fill="x", pady=(0, 8))
            ctk.CTkLabel(repl_row, text="Replace with",
                         font=aura.font()).pack(side="left")
            repl_entry = aura.AuraEntry(
                repl_row, placeholder="Replacement (may use \\1 groups)")
            repl_entry.pack(side="left", fill="x", expand=True, padx=8)
            aura.AuraButton(repl_row, "Replace", kind="secondary",
                            command=lambda: do_replace()).pack(side="left")

            out_frame, out_txt = make_scrolled_text(self, parent, height=8)
            aura.AuraButton(parent, "Copy output", kind="secondary",
                            command=lambda: self._copy(
                                get_text(out_txt))).pack(
                side="bottom", anchor="w", pady=(8, 0))
            aura.SectionLabel(parent, "Matches / output").pack(
                anchor="w", pady=(0, 2))
            out_frame.pack(fill="both", expand=True)

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
                    matches = regex_util.test_regex(pat_var.get(),
                                                    get_text(in_txt),
                                                    flags=_flags())
                except TextKitError as exc:
                    self._show_error(str(exc))
                    return
                for m in matches:
                    in_txt.tag_add("hl", f"1.0+{m['start']}c",
                                   f"1.0+{m['end']}c")
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
                    out = regex_util.replace(pat_var.get(), repl_entry.get(),
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
            self._describe(parent, "hash")
            opts = ctk.CTkFrame(parent, fg_color="transparent")
            opts.pack(fill="x")
            ctk.CTkLabel(opts, text="Algorithm", font=aura.font()).pack(side="left")
            algo_var = tk.StringVar(value="sha256")
            aura.AuraCombo(opts, variable=algo_var, values=HASH_ALGOS,
                           width=120, state="readonly").pack(
                side="left", padx=(6, 14))
            b_text = aura.AuraButton(opts, "Hash text")
            b_text.pack(side="left")
            b_file = aura.AuraButton(opts, "Hash file…", kind="secondary")
            b_file.pack(side="left", padx=8)

            aura.SectionLabel(parent, "Text to hash").pack(
                anchor="w", pady=(12, 2))
            in_frame, in_txt = make_scrolled_text(self, parent, height=10)
            in_frame.pack(fill="both", expand=True, pady=(0, 8))
            self._register_input(in_txt)
            set_text(in_txt, "abc")

            out_frame, out_txt = make_scrolled_text(self, parent, height=6)
            aura.AuraButton(parent, "Copy digest", kind="secondary",
                            command=lambda: self._copy(
                                get_text(out_txt))).pack(
                side="bottom", anchor="w", pady=(8, 0))
            aura.SectionLabel(parent, "Digest").pack(anchor="w", pady=(0, 2))
            out_frame.pack(fill="both", expand=True)

            def hash_text():
                try:
                    digest = hashing.hash_text(get_text(in_txt),
                                               algo=algo_var.get())
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
                                    self.report_success(
                                        f"{algo_var.get()} of file.")),
                    button=b_file, busy="Hashing…")

            b_text.configure(command=hash_text)
            b_file.configure(command=hash_file)

        # ---------- Encode / Decode ----------
        def _panel_encode(self, parent):
            self._describe(parent, "encode")
            opts = ctk.CTkFrame(parent, fg_color="transparent")
            opts.pack(fill="x")
            ctk.CTkLabel(opts, text="Codec", font=aura.font()).pack(side="left")
            codec_var = tk.StringVar(value="base64")
            aura.AuraCombo(opts, variable=codec_var, values=CODECS, width=120,
                           state="readonly").pack(side="left", padx=(6, 14))
            b_enc = aura.AuraButton(opts, "Encode →")
            b_enc.pack(side="left")
            b_dec = aura.AuraButton(opts, "Decode →", kind="secondary")
            b_dec.pack(side="left", padx=8)

            in_frame, in_txt = make_scrolled_text(self, parent, height=10)
            out_frame, out_txt = make_scrolled_text(self, parent, height=10)
            self._register_input(in_txt)
            set_text(in_txt, "Hello, Text & Data Toolkit!")

            self._io_buttons(parent, lambda: in_txt,
                             lambda: get_text(out_txt)).pack(
                side="bottom", fill="x", pady=(8, 0))

            aura.SectionLabel(parent, "Input").pack(anchor="w", pady=(12, 2))
            in_frame.pack(fill="both", expand=True, pady=(0, 8))
            aura.SectionLabel(parent, "Output").pack(anchor="w", pady=(0, 2))
            out_frame.pack(fill="both", expand=True)

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
            self._describe(parent, "jwt")
            aura.SectionLabel(
                parent, "Paste a JWT (header.payload.signature)").pack(
                anchor="w", pady=(0, 2))
            in_frame, in_txt = make_scrolled_text(self, parent, height=6)
            in_frame.pack(fill="both", expand=True, pady=(0, 8))
            self._register_input(in_txt)
            set_text(in_txt,
                     "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
                     "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ."
                     "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c")

            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=(0, 8))
            run = aura.AuraButton(row, "Decode")
            run.pack(side="left")
            aura.Caption(row,
                         "Decode only — the signature is NOT verified.").pack(
                side="left", padx=(10, 0))

            out_frame, out_txt = make_scrolled_text(self, parent, height=12)
            aura.AuraButton(parent, "Copy output", kind="secondary",
                            command=lambda: self._copy(
                                get_text(out_txt))).pack(
                side="bottom", anchor="w", pady=(8, 0))
            aura.SectionLabel(parent, "Decoded").pack(anchor="w", pady=(0, 2))
            out_frame.pack(fill="both", expand=True)

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
            self._describe(parent, "text")
            opts = ctk.CTkFrame(parent, fg_color="transparent")
            opts.pack(fill="x")
            ctk.CTkLabel(opts, text="Transform", font=aura.font()).pack(side="left")
            op_var = tk.StringVar(value="snake")
            aura.AuraCombo(opts, variable=op_var, values=TEXT_OPS, width=150,
                           state="readonly").pack(side="left", padx=(6, 14))
            rev = tk.BooleanVar()
            ctk.CTkCheckBox(opts, text="reverse (sort)", variable=rev,
                            font=aura.font()).pack(side="left")
            ctk.CTkLabel(opts, text="wrap width", font=aura.font()).pack(
                side="left", padx=(14, 4))
            width_var = tk.StringVar(value="80")
            ttk.Spinbox(opts, from_=1, to=200, width=5,
                        textvariable=width_var).pack(side="left")
            run = aura.AuraButton(opts, "Apply")
            run.pack(side="left", padx=14)

            in_frame, in_txt = make_scrolled_text(self, parent, height=10,
                                                  mono=False)
            out_frame, out_txt = make_scrolled_text(self, parent, height=10,
                                                    mono=False)
            self._register_input(in_txt)
            set_text(in_txt, "Hello World Example")

            self._io_buttons(parent, lambda: in_txt,
                             lambda: get_text(out_txt)).pack(
                side="bottom", fill="x", pady=(6, 0))
            info = aura.Caption(parent, "")
            info.pack(side="bottom", anchor="w", pady=(8, 0))

            aura.SectionLabel(parent, "Input").pack(anchor="w", pady=(12, 2))
            in_frame.pack(fill="both", expand=True, pady=(0, 8))
            aura.SectionLabel(parent, "Output").pack(anchor="w", pady=(0, 2))
            out_frame.pack(fill="both", expand=True)

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
                info.configure(text=(f"in: {stats['lines']} lines · "
                                     f"{stats['words']} words · "
                                     f"{stats['chars']} chars"))
                self.report_success(f"Applied '{op}'.")

            run.configure(command=go)

        # ---------- About ----------
        def _panel_about(self, parent):
            card = aura.Card(parent, title="About Text & Data Toolkit")
            card.pack(fill="x")
            aura.Heading(card.body, APP_NAME).pack(anchor="w")
            aura.Caption(card.body, f"Version {APP_VERSION}").pack(
                anchor="w", pady=(0, 10))
            ctk.CTkLabel(
                card.body, font=aura.font(), justify="left", anchor="w",
                wraplength=520,
                text="A fast, fully-offline toolkit for text and data: convert "
                     "JSON/YAML/CSV/XML, validate and format, diff, test "
                     "regexes, hash, encode/decode, decode JWTs and transform "
                     "text.\n\n"
                     "100% AI-built, open source, published on QuickOpen. "
                     "Nothing is ever uploaded anywhere.").pack(anchor="w")
            aura.Caption(card.body,
                         "Licensed under Apache-2.0. Pure Python standard "
                         "library plus PyYAML and CustomTkinter (MIT).").pack(
                anchor="w", pady=(10, 4))
            aura.AuraButton(card.body, "Project page: quickopen.ai",
                            kind="ghost",
                            command=lambda: open_with_default_app(
                                PROJECT_URL)).pack(anchor="w", pady=(6, 0))

    return App


def main():
    """Entry point: build the root window and run.  Degrades on headless hosts.

    Importing this module does nothing; only this function creates a Tk root.
    With no display (e.g. a server) or without customtkinter installed, it
    prints a friendly note and returns 0 instead of raising.
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
    except ImportError as exc:
        print(f"{APP_NAME}: the GUI needs the 'customtkinter' package "
              f"({exc}). Install it with:  pip install customtkinter")
        return 0
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
