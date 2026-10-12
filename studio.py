"""Interfaz de HTML APK Studio. Funciona con Tkinter estándar de Python."""
from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

import studio_core as core

BG = '#080E1D'
PANEL = '#121D31'
PANEL2 = '#19263D'
TEXT = '#E7F0FF'
MUTED = '#94A7C4'
CYAN = '#42E7CF'
PURPLE = '#9A82FF'


class Studio:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title('HTML APK Studio  |  Professional 0.7')
        root.geometry('1100x800')
        root.minsize(860, 650)
        root.configure(bg=BG)
        self.events = queue.Queue()
        self.current = None
        self.busy = False
        self.auto_build_on_import = tk.BooleanVar(value=False)
        self.preview_server = None
        self.preview_thread = None
        self.source_var = tk.StringVar(value='Ningún proyecto seleccionado')
        self.name = tk.StringVar(value='Mi aplicación')
        self.package = tk.StringVar(value='com.misapps.demo')
        self.orientation = tk.StringVar(value='unspecified')
        self.internet = tk.BooleanVar(value=False)
        self.icon = tk.StringVar()
        self.version_code = tk.StringVar(value='1')
        self.version_name = tk.StringVar(value='1.0')
        self.mode = tk.StringVar(value='debug')
        self.keystore = tk.StringVar()
        self.alias = tk.StringVar()
        self.store_pass = tk.StringVar()
        self.key_pass = tk.StringVar()
        self.status = tk.StringVar(value='LISTO · Importa un HTML, ZIP o carpeta')
        self.editor_file = None
        self.editor_dirty = False
        self._create_styles()
        self._layout()
        self._load_library()
        self._refresh_history()
        self._diagnose()
        self.root.after(120, self._drain_events)
        self.root.protocol('WM_DELETE_WINDOW', self._close)
        self._log('HTML APK Studio 0.7 preparado. El APK no se considera validado hasta compilarlo.')

    def _create_styles(self):
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('Studio.TNotebook', background=BG, borderwidth=0)
        style.configure('Studio.TNotebook.Tab', background=PANEL, foreground=MUTED, padding=(22, 11), borderwidth=0, font=('Segoe UI', 10, 'bold'))
        style.map('Studio.TNotebook.Tab', background=[('selected', PANEL2)], foreground=[('selected', CYAN)])
        style.configure('Studio.TCombobox', fieldbackground=PANEL2, background=PANEL2, foreground=TEXT)
        style.map('Studio.TCombobox', fieldbackground=[('readonly', PANEL2)], foreground=[('readonly', TEXT)])
        style.configure('Studio.Treeview', background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=29, borderwidth=0, font=('Segoe UI', 10))
        style.configure('Studio.Treeview.Heading', background=PANEL2, foreground=CYAN, relief='flat', font=('Segoe UI', 10, 'bold'))
        style.map('Studio.Treeview', background=[('selected', '#274F68')])
        style.configure('Studio.Horizontal.TProgressbar', troughcolor=PANEL2, background=CYAN, borderwidth=0)

    def _button(self, parent, label, command, accent=False, **pack):
        btn = tk.Button(parent, text=label, command=command, bg=CYAN if accent else PANEL2,
                        fg=BG if accent else TEXT, activebackground=PURPLE, activeforeground=BG,
                        font=('Segoe UI', 10, 'bold'), relief='flat', padx=15, pady=9,
                        cursor='hand2', bd=0)
        btn.pack(**pack)
        return btn

    def _label(self, parent, text, color=MUTED, size=10, bold=False, **pack):
        label = tk.Label(parent, text=text, bg=parent.cget('bg'), fg=color,
                         font=('Segoe UI', size, 'bold' if bold else 'normal'), anchor='w')
        label.pack(**pack)
        return label

    def _entry(self, parent, variable, secret=False):
        entry = tk.Entry(parent, textvariable=variable, bg=PANEL2, fg=TEXT, insertbackground=CYAN,
                         font=('Segoe UI', 11), relief='flat', bd=0, show='•' if secret else '')
        entry.pack(fill='x', ipady=9, pady=(4, 12))
        return entry

    def _layout(self):
        header = tk.Frame(self.root, bg=BG, height=95)
        header.pack(fill='x', padx=26, pady=(14, 0))
        tk.Label(header, text='⬡', bg=BG, fg=CYAN, font=('Segoe UI', 32, 'bold')).pack(side='left', padx=(0, 12))
        brand = tk.Frame(header, bg=BG)
        brand.pack(side='left')
        self._label(brand, 'HTML  APK  STUDIO', color=TEXT, size=23, bold=True)
        self._label(brand, 'PROFESSIONAL  /  LOCAL-FIRST  /  v0.7', color=CYAN, size=9, bold=True)
        tk.Label(header, text='●  SISTEMA PREPARADO', bg=BG, fg=CYAN,
                 font=('Consolas', 10, 'bold')).pack(side='right')

        main = tk.Frame(self.root, bg=BG)
        main.pack(fill='both', expand=True, padx=24, pady=(8, 0))
        self.tabs = ttk.Notebook(main, style='Studio.TNotebook')
        self.tabs.pack(fill='both', expand=True)
        self.project_tab = tk.Frame(self.tabs, bg=BG)
        self.editor_tab = tk.Frame(self.tabs, bg=BG)
        self.library_tab = tk.Frame(self.tabs, bg=BG)
        self.system_tab = tk.Frame(self.tabs, bg=BG)
        self.log_tab = tk.Frame(self.tabs, bg=BG)
        for frame, title in [(self.project_tab, 'INICIO'), (self.editor_tab, 'EDITOR'),
                             (self.library_tab, 'PROYECTOS'), (self.system_tab, 'SISTEMA'),
                             (self.log_tab, 'REGISTRO')]:
            self.tabs.add(frame, text=title)
        self._project_ui()
        self._editor_ui()
        self._library_ui()
        self._system_ui()

        self.console = tk.Text(self.log_tab, bg='#060B16', fg='#B3C8E3', insertbackground=CYAN,
                               relief='flat', padx=16, pady=15, font=('Consolas', 10), wrap='word')
        self.console.pack(fill='both', expand=True, pady=12)
        self.console.configure(state='disabled')
        foot = tk.Frame(self.root, bg=BG)
        foot.pack(fill='x', padx=24, pady=(7, 14))
        top = tk.Frame(foot, bg=BG)
        top.pack(fill='x')
        tk.Label(top, textvariable=self.status, bg=BG, fg=CYAN, font=('Consolas', 10)).pack(side='left')
        self.progress = ttk.Progressbar(top, style='Studio.Horizontal.TProgressbar', mode='indeterminate', length=170)
        self.progress.pack(side='right')

    def _project_ui(self):
        """Flujo simple primero; opciones técnicas disponibles bajo demanda."""
        outer = tk.Frame(self.project_tab, bg=BG)
        outer.pack(fill='both', expand=True, padx=12, pady=14)

        hero = tk.Frame(outer, bg=BG)
        hero.pack(fill='x', pady=(0, 18))
        self._label(hero, 'Crear aplicación', color=TEXT, size=21, bold=True, fill='x')
        self._label(hero, 'Importa tu web, personaliza lo esencial y genera tu APK.', fill='x', pady=(4, 0))

        card = tk.Frame(outer, bg=PANEL, padx=24, pady=20)
        card.pack(fill='both', expand=True)
        self._label(card, '1  TU PROYECTO', color=CYAN, bold=True, fill='x')
        self._label(card, 'HTML, ZIP o carpeta. Se crea una copia; el original no se modifica.',
                    size=9, fill='x', pady=(6, 10))
        pick = tk.Frame(card, bg=PANEL)
        pick.pack(fill='x', pady=(0, 8))
        self._button(pick, '+ ELEGIR HTML O ZIP', self._pick_file, side='left', padx=(0, 9))
        self._button(pick, '+ ELEGIR CARPETA', self._pick_folder, side='left')
        self._label(card, 'Archivo seleccionado', size=9, fill='x')
        source = tk.Label(card, textvariable=self.source_var, bg=PANEL2, fg=TEXT,
                          font=('Segoe UI', 10), anchor='w', padx=12, pady=10)
        source.pack(fill='x', pady=(4, 18))

        self._label(card, '2  PERSONALIZA', color=CYAN, bold=True, fill='x', pady=(0, 9))
        self._label(card, 'Nombre de tu aplicación', color=TEXT, fill='x')
        self._entry(card, self.name)
        icon_row = tk.Frame(card, bg=PANEL)
        icon_row.pack(fill='x', pady=(0, 12))
        self._button(icon_row, 'ELEGIR ÍCONO (OPCIONAL)', self._pick_icon, side='left')
        tk.Label(icon_row, textvariable=self.icon, bg=PANEL, fg=MUTED,
                 font=('Segoe UI', 9), anchor='w').pack(side='left', fill='x', expand=True, padx=12)

        self.advanced_visible = tk.BooleanVar(value=False)
        self.advanced = tk.Frame(card, bg=PANEL2, padx=16, pady=12)
        def toggle_advanced():
            if self.advanced_visible.get():
                self.advanced.pack(fill='x', pady=(0, 12), before=actions)
            else:
                self.advanced.pack_forget()
        self._button(card, '⚙  OPCIONES AVANZADAS  ▾', lambda: (
            self.advanced_visible.set(not self.advanced_visible.get()), toggle_advanced()
        ), fill='x', pady=(0, 12))

        self._label(self.advanced, 'Identificador Android (paquete)', color=TEXT, fill='x')
        self._entry(self.advanced, self.package)
        settings = tk.Frame(self.advanced, bg=PANEL2)
        settings.pack(fill='x')
        a = tk.Frame(settings, bg=PANEL2)
        b = tk.Frame(settings, bg=PANEL2)
        a.pack(side='left', fill='both', expand=True, padx=(0, 10))
        b.pack(side='left', fill='both', expand=True)
        self._label(a, 'Orientación', fill='x')
        ttk.Combobox(a, textvariable=self.orientation, values=('unspecified', 'portrait', 'landscape'),
                     state='readonly', style='Studio.TCombobox').pack(fill='x', pady=(4, 12))
        self._label(b, 'Tipo de compilación', fill='x')
        ttk.Combobox(b, textvariable=self.mode, values=('debug', 'release'),
                     state='readonly', style='Studio.TCombobox').pack(fill='x', pady=(4, 12))
        self._label(a, 'Versión visible', fill='x')
        self._entry(a, self.version_name)
        self._label(b, 'Código de versión', fill='x')
        self._entry(b, self.version_code)
        tk.Checkbutton(self.advanced, text='Permitir acceso a Internet', variable=self.internet,
                       bg=PANEL2, fg=TEXT, selectcolor=PANEL, activebackground=PANEL2,
                       activeforeground=CYAN).pack(anchor='w', pady=(0, 12))
        self._label(self.advanced, 'Firma de publicación (solo modo release)',
                    color=PURPLE, bold=True, fill='x', pady=(4, 9))
        for title, var, secret in [('Ruta del keystore (.jks)', self.keystore, False),
                                   ('Alias de la clave', self.alias, False),
                                   ('Contraseña del keystore', self.store_pass, True),
                                   ('Contraseña de la clave', self.key_pass, True)]:
            self._label(self.advanced, title, fill='x')
            self._entry(self.advanced, var, secret)
        self._button(self.advanced, 'BUSCAR KEYSTORE', self._pick_keystore, fill='x')
        self._label(self.advanced, 'Las contraseñas no se guardan. Conserva tu clave para actualizar la app.',
                    size=9, fill='x', pady=(10, 0))

        actions = tk.Frame(card, bg=PANEL)
        actions.pack(fill='x', pady=(5, 0))
        self._label(actions, '3  GENERA TU APK', color=CYAN, bold=True, fill='x', pady=(0, 10))
        self._button(actions, '⚡ GENERAR APK', self._start_build, accent=True, fill='x', pady=(0, 10))
        tools = tk.Frame(actions, bg=PANEL)
        tools.pack(fill='x')
        self._button(tools, 'VISTA PREVIA', self._preview, side='left', padx=(0, 8))
        self._button(tools, 'VALIDAR', self._validate, side='left', padx=(0, 8))
        self._button(tools, 'GUARDAR AJUSTES', self._save_config, side='left')

    def _editor_ui(self):
        top = tk.Frame(self.editor_tab, bg=BG)
        top.pack(fill='x', pady=(14, 8))
        self._label(top, 'EDITOR HTML · index.html', color=CYAN, size=13, bold=True, side='left')
        self._button(top, 'GUARDAR HTML', self._save_editor, side='right', padx=(8, 0), accent=True)
        self._button(top, 'VISTA PREVIA', self._preview, side='right', padx=(8, 0))
        self._button(top, 'RECARGAR', self._load_editor, side='right')
        self.editor = tk.Text(self.editor_tab, undo=True, bg='#07101E', fg='#DBEAFF',
                              insertbackground=CYAN, selectbackground='#345A76', relief='flat',
                              font=('Consolas', 11), padx=15, pady=15, wrap='none')
        self.editor.pack(fill='both', expand=True, pady=(0, 9))
        self.editor.bind('<<Modified>>', self._on_editor_change)
        self.editor.bind('<Control-s>', lambda e: (self._save_editor(), 'break')[1])
        self._label(self.editor_tab, 'Edita la copia de trabajo. Guarda antes de compilar. Ctrl+S para guardar.', fill='x', pady=(0, 10))

    def _library_ui(self):
        top = tk.Frame(self.library_tab, bg=BG)
        top.pack(fill='x', pady=(14, 8))
        self._label(top, 'MIS PROYECTOS', color=CYAN, size=13, bold=True, side='left')
        self._button(top, 'ABRIR SELECCIÓN', self._open_library_selection, side='right', accent=True)
        self._button(top, 'ACTUALIZAR', self._load_library, side='right', padx=(0, 9))
        self.project_tree = ttk.Treeview(self.library_tab, columns=('name','package','created'),
                                         show='headings', style='Studio.Treeview', height=9)
        for key, title, width in [('name','Proyecto',220),('package','Paquete',310),('created','Importado',160)]:
            self.project_tree.heading(key, text=title)
            self.project_tree.column(key, width=width)
        self.project_tree.pack(fill='both', expand=True)
        self.project_tree.bind('<Double-1>', lambda _: self._open_library_selection())
        self._label(self.library_tab, 'HISTORIAL DE COMPILACIONES', color=CYAN, size=12, bold=True, fill='x', pady=(17, 6))
        self.history_tree = ttk.Treeview(self.library_tab, columns=('date','name','mode','apk'),
                                         show='headings', style='Studio.Treeview', height=6)
        for key, title, width in [('date','Fecha',150),('name','Nombre',180),('mode','Tipo',85),('apk','Archivo APK',400)]:
            self.history_tree.heading(key, text=title)
            self.history_tree.column(key, width=width)
        self.history_tree.pack(fill='both', expand=True, pady=(0, 8))
        self.history_tree.bind('<Double-1>', lambda _: self._open_history_apk())
        self._button(self.library_tab, 'ABRIR CARPETA DEL APK SELECCIONADO', self._open_history_apk, side='bottom', pady=(0, 8))

    def _system_ui(self):
        top = tk.Frame(self.system_tab, bg=BG)
        top.pack(fill='x', pady=(14, 8))
        self._label(top, 'DIAGNÓSTICO DE COMPILACIÓN', color=CYAN, size=13, bold=True, side='left')
        self._button(top, 'REVISAR ENTORNO', self._diagnose, side='right', accent=True)
        self.diagnostic_text = tk.Text(self.system_tab, bg=PANEL, fg=TEXT, relief='flat',
                                       font=('Consolas', 11), padx=18, pady=16, wrap='word')
        self.diagnostic_text.pack(fill='both', expand=True, pady=(0, 12))
        self._label(self.system_tab, 'Se necesita Java, Android SDK API 35, Build Tools y Gradle 8.9. No se instalan automáticamente sin tu autorización.', fill='x')

    def _log(self, msg):
        self.console.configure(state='normal')
        self.console.insert('end', str(msg) + '\n')
        self.console.see('end')
        self.console.configure(state='disabled')

    def _drain_events(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'log':
                    self._log(value)
                elif kind == 'imported':
                    self._set_project(value['project'])
                    self._log(f"Importado: {value['report']['files']} archivos. Advertencias: {len(value['report']['warnings'])}")
                    self._load_library()
                    if self.auto_build_on_import.get():
                        self.root.after(200, self._start_build)
                elif kind == 'validated':
                    self._log(f"VALIDACIÓN: {value['files']} archivos, {value['bytes']} bytes")
                    for w in value['warnings']:
                        self._log('AVISO: ' + w)
                    messagebox.showinfo('Validación', f"Archivos: {value['files']}\nTamaño: {value['bytes']} bytes\nAdvertencias: {len(value['warnings'])}")
                elif kind == 'increment':
                    pid, new_code = value
                    if self.current and self.current['id'] == pid:
                        self.version_code.set(str(new_code))
                        self.current['config']['version_code'] = new_code
                elif kind == 'built':
                    self._log('RESULTADO: ' + str(value))
                    self._refresh_history()
                    messagebox.showinfo('APK generado', 'Archivo: ' + str(value) + '\n\nFalta probarlo en Android.')
                elif kind == 'error':
                    self._log('ERROR: ' + str(value))
                    messagebox.showerror('HTML APK Studio', str(value))
                elif kind == 'done':
                    self.busy = False
                    self.progress.stop()
                    self.status.set('LISTO · Esperando acciones')
        except queue.Empty:
            pass
        self.root.after(120, self._drain_events)

    def _background(self, label, fn):
        if self.busy:
            messagebox.showwarning('Operación en curso', 'Espera a que termine la tarea actual.')
            return
        self.busy = True
        self.status.set(label)
        self.progress.start(12)
        def run():
            try:
                fn()
            except Exception as exc:
                self.events.put(('error', str(exc)))
            finally:
                self.events.put(('done', None))
        threading.Thread(target=run, daemon=True).start()

    def _pick_file(self):
        path = filedialog.askopenfilename(filetypes=[('Proyecto web','*.html *.htm *.zip')])
        if path:
            self._import(path)

    def _pick_folder(self):
        path = filedialog.askdirectory()
        if path:
            self._import(path)

    def _import(self, path):
        if self.editor_dirty and not self._save_editor():
            return
        self._background('IMPORTANDO PROYECTO...', lambda: self.events.put(('imported', core.import_project(path))))

    def _pick_icon(self):
        path = filedialog.askopenfilename(filetypes=[('Ícono PNG','*.png')])
        if path:
            self.icon.set(path)

    def _pick_keystore(self):
        path = filedialog.askopenfilename(filetypes=[('Keystore','*.jks *.keystore'),('Todos','*.*')])
        if path:
            self.keystore.set(path)

    def _set_project(self, info):
        self.current = info
        cfg = info['config']
        self.source_var.set(info['source'])
        for key, variable in [('name',self.name),('package',self.package),('orientation',self.orientation),
                               ('internet',self.internet),('icon',self.icon),('version_code',self.version_code),
                               ('version_name',self.version_name),('mode',self.mode)]:
            variable.set(cfg.get(key, variable.get()))
        self._load_editor()
        self.status.set('PROYECTO CARGADO · ' + cfg['name'])
        self.tabs.select(self.project_tab)

    def _collect_config(self):
        cfg = {'name':self.name.get().strip(), 'package':self.package.get().strip(),
               'orientation':self.orientation.get(), 'internet':self.internet.get(),
               'icon':self.icon.get().strip(), 'version_code':int(self.version_code.get()),
               'version_name':self.version_name.get().strip(), 'mode':self.mode.get()}
        core.validate_config(cfg['name'],cfg['package'],cfg['orientation'],cfg['internet'],cfg['version_code'],cfg['version_name'])
        if cfg['mode'] not in ('debug','release'):
            raise ValueError('Modo inválido')
        return cfg

    def _save_config(self):
        if not self.current:
            messagebox.showwarning('Sin proyecto', 'Importa primero un proyecto.')
            return False
        try:
            self.current['config'] = self._collect_config()
            core.save_project(self.current)
            self._log('Configuración guardada. No se guardan contraseñas.')
            self._load_library()
            return True
        except Exception as e:
            messagebox.showerror('Configuración', str(e))
            return False

    def _on_editor_change(self, event):
        if self.editor.edit_modified():
            self.editor_dirty = True
            self.editor.edit_modified(False)

    def _load_editor(self):
        if not self.current:
            return
        if self.editor_dirty and not messagebox.askyesno('Cambios sin guardar', '¿Descartar los cambios del editor?'):
            return
        path = core.project_dir(self.current['id']) / 'web/index.html'
        try:
            content = path.read_text(encoding='utf-8-sig')
        except UnicodeDecodeError:
            messagebox.showerror('Editor', 'El archivo no es UTF-8. Conviértelo antes de editar.')
            return
        self.editor.delete('1.0', 'end')
        self.editor.insert('1.0', content)
        self.editor.edit_modified(False)
        self.editor_dirty = False
        self.editor_file = path

    def _save_editor(self):
        if not self.editor_file:
            messagebox.showwarning('Editor', 'Importa un proyecto para editarlo.')
            return False
        try:
            text = self.editor.get('1.0', 'end-1c')
            self.editor_file.write_text(text, encoding='utf-8')
            self.editor_dirty = False
            self.editor.edit_modified(False)
            self._log('HTML guardado: ' + str(self.editor_file))
            return True
        except OSError as e:
            messagebox.showerror('Editor', str(e))
            return False

    def _validate(self):
        if not self.current:
            messagebox.showwarning('Validación', 'Importa un proyecto primero.')
            return
        if self.editor_dirty and not self._save_editor():
            return
        folder = core.project_dir(self.current['id']) / 'web'
        self._background('VALIDANDO PROYECTO...', lambda: self.events.put(('validated', core.analyze_web(folder))))

    def _preview(self):
        if not self.current:
            messagebox.showwarning('Vista previa', 'Importa un proyecto primero.')
            return
        if self.editor_dirty and not self._save_editor():
            return
        folder = core.project_dir(self.current['id']) / 'web'
        self._stop_preview()
        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(folder), **kwargs)
            def log_message(self, fmt, *args):
                pass
            def list_directory(self, path):
                self.send_error(403, 'Directorio no disponible')
                return None
        try:
            self.preview_server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            self.preview_server.daemon_threads = True
            self.preview_thread = threading.Thread(target=self.preview_server.serve_forever, daemon=True)
            self.preview_thread.start()
            url = f'http://127.0.0.1:{self.preview_server.server_port}/index.html'
            webbrowser.open(url)
            self._log('Vista previa local: ' + url + ' (navegador de Windows, no emulador Android)')
        except OSError as e:
            messagebox.showerror('Vista previa', str(e))

    def _stop_preview(self):
        if self.preview_server:
            self.preview_server.shutdown()
            self.preview_server.server_close()
            self.preview_server = None

    def _start_build(self):
        if not self.current:
            messagebox.showwarning('Compilación', 'Importa primero un proyecto.')
            return
        if self.editor_dirty and not self._save_editor():
            return
        if not self._save_config():
            return
        cfg = self.current['config'].copy()
        if cfg['mode'] == 'release' and not all((self.keystore.get(), self.alias.get(), self.store_pass.get(), self.key_pass.get())):
            messagebox.showerror('Firma', 'Release necesita keystore, alias y dos contraseñas.')
            return
        pid = self.current['id']
        web = core.project_dir(pid) / 'web'
        kwargs = dict(name=cfg['name'], package=cfg['package'], orientation=cfg['orientation'],
                      internet=cfg['internet'], icon=cfg['icon'] or None,
                      version_code=cfg['version_code'], version_name=cfg['version_name'], mode=cfg['mode'],
                      keystore=self.keystore.get() or None, key_alias=self.alias.get() or None,
                      store_password=self.store_pass.get() or None, key_password=self.key_pass.get() or None)
        def work():
            apk = core.build(web, log=lambda msg: self.events.put(('log', msg)), **kwargs)
            self.events.put(('built', apk))
            # Solo incrementa después de una compilación exitosa, sin tocar secretos.
            info = core.load_project(pid)
            info['config']['version_code'] = cfg['version_code'] + 1
            core.save_project(info)
            self.events.put(('log', f"Próximo versionCode: {cfg['version_code']+1} (guardado en proyecto)"))
            self.events.put(('increment', (pid, cfg['version_code'] + 1)))
        self._background('COMPILANDO APK...', work)

    def _load_library(self):
        if not hasattr(self, 'project_tree'):
            return
        self.project_tree.delete(*self.project_tree.get_children())
        for p in core.list_projects():
            self.project_tree.insert('', 'end', iid=p['id'], values=(p['config']['name'],p['config']['package'],p['created']))

    def _open_library_selection(self):
        sel = self.project_tree.selection()
        if not sel:
            return
        if self.editor_dirty and not messagebox.askyesno('Editor', 'Descartar cambios sin guardar del proyecto actual?'):
            return
        try:
            self.editor_dirty = False
            self._set_project(core.load_project(sel[0]))
        except Exception as e:
            messagebox.showerror('Proyectos', str(e))

    def _refresh_history(self):
        if not hasattr(self, 'history_tree'):
            return
        self.history_tree.delete(*self.history_tree.get_children())
        data = core.read_json(core.data_dir() / 'history.json', [])
        if isinstance(data, list):
            for i, h in enumerate(data[:50]):
                self.history_tree.insert('', 'end', iid=str(i), values=(h.get('date'),h.get('name'),h.get('mode'),h.get('apk')))

    def _open_history_apk(self):
        sel = self.history_tree.selection()
        if not sel:
            messagebox.showinfo('Historial', 'Selecciona primero un APK del historial.')
            return
        record = core.read_json(core.data_dir() / 'history.json', [])
        try:
            apk = Path(record[int(sel[0])]['apk'])
            if not apk.is_file():
                raise FileNotFoundError('El APK ya no existe: ' + str(apk))
            if sys.platform == 'win32':
                os.startfile(str(apk.parent))
            else:
                messagebox.showinfo('APK', str(apk))
        except (IndexError, ValueError, KeyError, OSError) as exc:
            messagebox.showerror('Historial', str(exc))

    def _diagnose(self):
        if not hasattr(self, 'diagnostic_text'):
            return
        report = core.diagnostic_report()
        lines = ['HTML APK STUDIO  /  DIAGNÓSTICO\n', 'Python: ' + report['python'],
                 'Java: ' + str(report['java'] or 'NO DETECTADO'),
                 'JDK: ' + (f"OK (Java {report['java_major']})" if report['java_compatible'] else 'REQUIERE JDK 17-22'),
                 'Gradle: ' + str(report['gradle'] or 'NO DETECTADO'),
                 'Android SDK: ' + str(report['sdk'] or 'NO DETECTADO'),
                 'Plataforma API 35: ' + ('OK' if report['api35'] else 'FALTA'),
                 'Build Tools: ' + ('OK' if report['build_tools'] else 'FALTAN'),
                 'apksigner: ' + str(report['apksigner'] or 'NO DETECTADO'),
                 '\nEstado: ' + ('LISTO PARA INTENTAR COMPILAR' if report['ready_to_try'] else 'DEPENDENCIAS INCOMPLETAS'),
                 '\n' + report['note'],
                 '\nConsulta README.md y setup_windows.ps1 para preparar Windows.']
        self.diagnostic_text.delete('1.0','end')
        self.diagnostic_text.insert('1.0','\n'.join(lines))

    def _close(self):
        if self.busy and not messagebox.askyesno('Cerrar', 'Hay una tarea en curso. ¿Cerrar igualmente?'):
            return
        if self.editor_dirty and not messagebox.askyesno('Cambios sin guardar', '¿Cerrar sin guardar el HTML?'):
            return
        self._stop_preview()
        self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    Studio(root)
    root.mainloop()
