"""Pre-launch settings for the existing OpenSHSM user config."""
from pathlib import Path
import math
import os
import re
import stat
import tempfile
import tomllib

from launcher_locale import text


SIZES = ((960, 540), (1280, 720), (1600, 900), (1920, 1080), (2560, 1440))
DEFAULTS = {'graphics': {'window_width': 960, 'window_height': 540, 'fullscreen': False},
    'input': {'mouse_look_sensitivity': 1.0, 'gamepad_look_sensitivity': 1.0}}


def controller_icon_environment(user_dir, inherited=None):
    """Resolve optional owner icons; missing icons use the built-in runtime symbols."""
    inherited = os.environ if inherited is None else inherited
    selected = inherited.get('OPENSHSM_PS2_BUTTON_ICONS')
    try:
        candidate = Path(selected).expanduser() if selected else Path(user_dir) / 'controller-icons/ps2'
        if candidate.is_dir():
            return {'OPENSHSM_PS2_BUTTON_ICONS': str(candidate.resolve(strict=True))}
    except (OSError, ValueError, TypeError):
        pass
    return {}


def read_settings(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(text('Settings must be a regular config.toml file.',
            'Настройки должны быть обычным файлом config.toml.'))
    original = path.read_bytes()
    data = tomllib.loads(original.decode('utf-8'))
    values = {}
    for table, defaults in DEFAULTS.items():
        section = data.get(table, {})
        if not isinstance(section, dict):
            raise ValueError(text(f'[{table}] must be a TOML table.',
                f'Раздел [{table}] должен быть таблицей TOML.'))
        values[table] = {key: section.get(key, default) for key, default in defaults.items()}
    validate_values(values)
    return original, values


def validate_values(values):
    for key, low, high in [('window_width', 320, 8192), ('window_height', 240, 8192)]:
        value = values['graphics'][key]
        if type(value) is not int or not low <= value <= high:
            raise ValueError(text(f'{key}: expected an integer from {low} to {high}.',
                f'{key}: допустимо целое число от {low} до {high}.'))
    if type(values['graphics']['fullscreen']) is not bool:
        raise ValueError(text('fullscreen must be true or false.',
            'fullscreen должен быть true или false.'))
    for key in DEFAULTS['input']:
        value = values['input'][key]
        if type(value) not in (int, float) or not math.isfinite(value) or not 0.05 <= value <= 5:
            raise ValueError(text('Sensitivity must be between 0.05 and 5.',
                'Чувствительность должна быть от 0.05 до 5.'))


def updated_config(original, values):
    validate_values(values)
    text = original.decode('utf-8')
    expected = tomllib.loads(text)
    for table, fields in values.items():
        if table not in DEFAULTS or set(fields) != set(DEFAULTS[table]):
            raise ValueError(text('Unknown launcher settings.',
                'Неизвестные настройки лаунчера.'))
        section = expected.setdefault(table, {})
        if not isinstance(section, dict):
            raise ValueError(text(f'[{table}] must be a TOML table.',
                f'Раздел [{table}] должен быть таблицей TOML.'))
        section.update(fields)
        headers = list(re.finditer(r'^\s*\[[^\n]+\][ \t]*(?:#[^\n]*)?$', text, re.M))
        matching = [i for i, header in enumerate(headers)
            if re.fullmatch(r'\s*\[' + table + r'\][ \t]*(?:#[^\n]*)?', header.group())]
        if len(matching) > 1:
            raise ValueError(text('Duplicate settings section.',
                'Повторяющийся раздел настроек.'))
        if matching:
            index = matching[0]
            start = headers[index].end()
            end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        else:
            text = text.rstrip() + f'\n\n[{table}]\n'
            start = end = len(text)
        body = text[start:end]
        for key, value in fields.items():
            literal = str(value).lower() if type(value) is bool else str(value)
            line = f'{key} = {literal}'
            pattern = re.compile(r'^[ \t]*' + key + r'[ \t]*=[^\n]*$', re.M)
            if pattern.search(body):
                body = pattern.sub(line, body)
            else:
                body = body.rstrip() + '\n' + line + '\n'
        text = text[:start] + body + text[end:]
    if tomllib.loads(text) != expected:
        raise ValueError(text('Complex TOML layout: settings were not saved. Use regular [graphics] and [input] sections.',
            'Сложная запись TOML: настройки не сохранены. Используйте обычные [graphics] и [input].'))
    return text.encode('utf-8')


def save_settings(path, original, values):
    path = Path(path)
    content = updated_config(original, values)
    if path.is_symlink() or path.read_bytes() != original:
        raise ValueError(text('config.toml changed. Close and reopen settings.',
            'config.toml изменился. Закройте и откройте настройки заново.'))
    if content == original:
        return original
    mode = stat.S_IMODE(path.stat().st_mode)
    descriptor, temporary = tempfile.mkstemp(prefix='.openshsm-settings-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as output:
            if hasattr(os, 'fchmod'):
                os.fchmod(output.fileno(), mode)
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        if path.is_symlink() or path.read_bytes() != original:
            raise ValueError(text('config.toml changed while settings were being saved.',
                'config.toml изменился во время сохранения.'))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return content


def show_settings(path, settings_only=False):
    original, values = read_settings(path)
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except ImportError as error:
        raise RuntimeError(text('The settings window requires Python with Tk. For direct launch: --no-settings.',
            'Для окна настроек нужен Python с Tk. Для прямого запуска: --no-settings.')) from error
    try:
        root = tk.Tk()
    except tk.TclError as error:
        raise RuntimeError(text('Could not open settings. For direct launch: --no-settings.',
            'Не удалось открыть настройки. Для прямого запуска: --no-settings.')) from error
    root.title(text('OpenSHSM — launch settings', 'OpenSHSM — настройки запуска'))
    root.resizable(False, False)
    panel = ttk.Frame(root, padding=20)
    panel.grid()
    ttk.Label(panel, text=text('Display', 'Экран'), font=('', 14, 'bold')).grid(row=0, column=0, sticky='w', pady=(0, 10))
    current_size = (values['graphics']['window_width'], values['graphics']['window_height'])
    sizes = list(dict.fromkeys([current_size, *SIZES]))
    size = tk.StringVar(value=f'{current_size[0]} × {current_size[1]}')
    ttk.Label(panel, text=text('Window size', 'Размер окна')).grid(row=1, column=0, sticky='w')
    ttk.Combobox(panel, textvariable=size, state='readonly', width=20,
        values=[f'{width} × {height}' for width, height in sizes]).grid(row=1, column=1, padx=(20, 0))
    fullscreen = tk.BooleanVar(value=values['graphics']['fullscreen'])
    ttk.Checkbutton(panel, text=text('Fullscreen', 'Полный экран'), variable=fullscreen).grid(row=2, column=0, columnspan=2, sticky='w', pady=10)
    ttk.Label(panel, text=text('Fullscreen uses the desktop resolution.\nWindow size does not change the internal Wii resolution.',
        'Полный экран использует разрешение рабочего стола.\nРазмер окна не меняет внутреннее разрешение Wii.')).grid(row=3, column=0, columnspan=2, sticky='w')
    ttk.Separator(panel).grid(row=4, column=0, columnspan=2, sticky='ew', pady=14)
    sensitivity = {}
    for row, (key, label) in enumerate([('mouse_look_sensitivity', text('Mouse sensitivity', 'Чувствительность мыши')),
            ('gamepad_look_sensitivity', text('Stick sensitivity', 'Чувствительность стика'))], 5):
        ttk.Label(panel, text=label).grid(row=row, column=0, sticky='w', pady=4)
        sensitivity[key] = tk.StringVar(value=str(values['input'][key]))
        ttk.Spinbox(panel, textvariable=sensitivity[key], from_=0.05, to=5, increment=0.05,
            width=20).grid(row=row, column=1, padx=(20, 0))
    ttk.Label(panel, text=text('1 is the normal look speed; 0.5 is half speed.',
        '1 — обычная скорость обзора; 0.5 — вдвое медленнее.')).grid(row=7, column=0, columnspan=2, sticky='w', pady=(8, 14))
    result = False

    def apply(close):
        nonlocal original, result
        try:
            width, height = map(int, size.get().split(' × '))
            updated = {'graphics': {'window_width': width, 'window_height': height,
                'fullscreen': fullscreen.get()},
                'input': {key: float(value.get()) for key, value in sensitivity.items()}}
            original = save_settings(path, original, updated)
        except (OSError, ValueError) as error:
            messagebox.showerror(text('OpenSHSM — settings', 'OpenSHSM — настройки'), str(error), parent=root)
            return
        if close:
            result = True
            root.destroy()
        else:
            status.set(text('Settings saved.', 'Настройки сохранены.'))

    status = tk.StringVar()
    ttk.Label(panel, textvariable=status).grid(row=8, column=0, columnspan=2, sticky='w')
    buttons = ttk.Frame(panel)
    buttons.grid(row=9, column=0, columnspan=2, sticky='e', pady=(10, 0))
    ttk.Button(buttons, text=text('Cancel', 'Отмена'), command=root.destroy).grid(row=0, column=0, padx=4)
    ttk.Button(buttons, text=text('Save', 'Сохранить'), command=lambda: apply(False)).grid(row=0, column=1, padx=4)
    ttk.Button(buttons, text=text('Done', 'Готово') if settings_only else text('Play', 'Играть'),
        command=lambda: apply(True)).grid(row=0, column=2, padx=4)
    root.protocol('WM_DELETE_WINDOW', root.destroy)
    root.mainloop()
    return result
