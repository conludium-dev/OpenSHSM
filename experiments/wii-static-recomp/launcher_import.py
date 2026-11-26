"""First-run UI for the existing verified Wii importer; no game data registry."""
from pathlib import Path
import json
import os
import queue
import shutil
import sys
import threading
import uuid

from prepare_wii_us_copy import prepare, prepare_image
from verify_wii_us_copy import audit_copy


def default_user_dir():
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/OpenSHSM'
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'OpenSHSM'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'OpenSHSM'


def find_dolphin_tool():
    for name in ('DolphinTool', 'dolphin-tool'):
        found = shutil.which(name)
        if found:
            return found
    candidate = Path('/Applications/Dolphin.app/Contents/MacOS/DolphinTool')
    return str(candidate) if candidate.is_file() else ''


def import_game(source, user_dir, dolphin_tool=None, *, extracted=False):
    user_dir = Path(user_dir).expanduser().absolute()
    if user_dir.is_symlink():
        raise ValueError('Каталог пользователя не должен быть ссылкой.')
    target = user_dir / 'wii-import'
    if target.exists() or target.is_symlink():
        raise ValueError('Данные уже существуют: ' + str(target))
    user_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    partial = user_dir / ('wii-import.partial-' + uuid.uuid4().hex)
    if extracted:
        report = prepare(source, partial)
    else:
        if not dolphin_tool:
            raise ValueError('Выберите исполняемый DolphinTool с командой extract.')
        report = prepare_image(source, dolphin_tool, partial)
    report['destination'] = str(target / 'DATA')
    (partial / 'import.json').write_text(json.dumps(report, indent=2) + '\n')
    if target.exists() or target.is_symlink():
        raise RuntimeError('Другой импорт уже создал ' + str(target))
    partial.rename(target)
    return target / 'DATA'


def show_import(user_dir):
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
        root = tk.Tk()
    except Exception as error:
        raise RuntimeError('Для первого запуска нужен Python 3.11+ с Tk и рабочим дисплеем. '
            'Можно использовать --import-only --no-settings --import-image IMAGE '
            '--dolphin-tool TOOL.') from error
    root.title('OpenSHSM — подготовка Wii-копии')
    root.resizable(True, False)
    frame = ttk.Frame(root, padding=18)
    frame.grid(sticky='nsew')
    frame.columnconfigure(1, weight=1)
    root.columnconfigure(0, weight=1)
    ttk.Label(frame, text='Выберите собственную Wii US R5WEA4, revision 0.\n'
        'Данные будут извлечены и проверены перед запуском.\n'
        'PS2-копия не требуется. DolphinTool устанавливается отдельно.').grid(
        row=0, column=0, columnspan=3, sticky='w', pady=(0, 12))
    source = tk.StringVar()
    tool = tk.StringVar(value=find_dolphin_tool())
    extracted = tk.BooleanVar(value=False)
    status = tk.StringVar(value='Данные: ' + str(Path(user_dir) / 'wii-import'))
    events = queue.Queue()
    running = False
    result = None

    def choose_source():
        chosen = filedialog.askdirectory(parent=root, title='Извлечённая Wii DATA') if extracted.get() else \
            filedialog.askopenfilename(parent=root, title='Собственный Wii-образ',
                filetypes=[('Wii images', '*.iso *.rvz *.wbfs *.wia *.gcz'), ('All files', '*')])
        if chosen:
            source.set(chosen)

    def choose_tool():
        chosen = filedialog.askopenfilename(parent=root, title='DolphinTool / dolphin-tool')
        if chosen:
            tool.set(chosen)

    def close():
        if running:
            messagebox.showinfo('OpenSHSM', 'Дождитесь завершения извлечения и проверки.', parent=root)
        else:
            root.destroy()

    def start():
        nonlocal running
        if not source.get().strip() or (not extracted.get() and not tool.get().strip()):
            messagebox.showerror('OpenSHSM', 'Выберите источник и DolphinTool для образа.', parent=root)
            return
        selected, selected_tool, is_extracted = source.get(), tool.get(), extracted.get()
        running = True
        for widget in controls:
            widget.configure(state='disabled')
        progress.start()
        status.set('Извлечение и SHA-256 проверка файлов. Это может занять несколько минут…')

        def worker():
            try:
                events.put((True, import_game(selected, user_dir, selected_tool, extracted=is_extracted)))
            except Exception as error:
                events.put((False, str(error)))
        threading.Thread(target=worker, daemon=True).start()
        root.after(100, poll)

    def poll():
        nonlocal running, result
        try:
            success, value = events.get_nowait()
        except queue.Empty:
            root.after(100, poll)
            return
        running = False
        progress.stop()
        if success:
            result = value
            root.destroy()
        else:
            for widget in controls:
                widget.configure(state='normal')
            status.set('Импорт не завершён. Частичные данные сохранены для диагностики.')
            messagebox.showerror('OpenSHSM — ошибка импорта', value, parent=root)

    controls = []
    for row, label, variable, command in [(1, 'Wii-образ / DATA', source, choose_source),
            (2, 'DolphinTool', tool, choose_tool)]:
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky='w', padx=(0, 8))
        entry = ttk.Entry(frame, textvariable=variable, width=54)
        entry.grid(row=row, column=1, sticky='ew', pady=4)
        button = ttk.Button(frame, text='Обзор…', command=command)
        button.grid(row=row, column=2, padx=(8, 0))
        controls.extend([entry, button])
    mode = ttk.Checkbutton(frame, text='Уже извлечённая DATA (без DolphinTool)', variable=extracted)
    mode.grid(row=3, column=0, columnspan=3, sticky='w', pady=8)
    controls.append(mode)
    progress = ttk.Progressbar(frame, mode='indeterminate')
    progress.grid(row=4, column=0, columnspan=3, sticky='ew')
    ttk.Label(frame, textvariable=status, wraplength=640).grid(
        row=5, column=0, columnspan=3, sticky='w', pady=8)
    button = ttk.Button(frame, text='Подготовить данные', command=start)
    button.grid(row=6, column=1, sticky='e')
    cancel = ttk.Button(frame, text='Отмена', command=close)
    cancel.grid(row=6, column=2, padx=(8, 0))
    controls.extend([button, cancel])
    root.protocol('WM_DELETE_WINDOW', close)
    root.mainloop()
    return result


def resolve_game_data(game_data, user_dir, *, interactive=True, image=None, dolphin_tool=None):
    if game_data is not None:
        if image is not None:
            raise ValueError('--game-data и --import-image несовместимы.')
        return Path(audit_copy(game_data)['source'])
    user_dir = Path(user_dir).expanduser()
    if user_dir.is_symlink():
        raise ValueError('Каталог пользователя не должен быть ссылкой.')
    managed = user_dir / 'wii-import'
    if managed.exists() or managed.is_symlink():
        if image is not None:
            raise ValueError('Импорт уже существует: ' + str(managed))
        if managed.is_symlink() or not (managed / 'import.json').is_file():
            raise ValueError('Незавершённый или неверный импорт: ' + str(managed))
        return Path(audit_copy(managed)['source'])
    if image is not None:
        return import_game(image, user_dir, dolphin_tool)
    if not interactive:
        raise ValueError('Нет Wii DATA. Укажите --game-data или выполните первый запуск с импортом.')
    return show_import(user_dir)
