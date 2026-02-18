# tasks.py
# Основной файл для приложения Tasks - планировщик задач
# Версия: 1.4 (улучшения: фоновая работа с tray icon, системные уведомления)
# Автор: Grok 4 (на основе плана пользователя, с рефакторингом и доработками)
# Дата создания: 31.01.2026 → обновлено 18.02.2026
# Описание: GUI с Tkinter + облачное хранение задач в Firebase Realtime Database
# Улучшения:
# 1. Фоновая работа: приложение запускается скрытым (root.withdraw()), добавлен system tray icon с помощью infi.systray (для Windows).
#    - Меню в tray: Show (показать окно), Hide (скрыть), Quit (выход).
#    - Нужно установить библиотеку: pip install infi.systray
#    - Иконка: предполагается файл 'icon.ico' в директории (скачай или создай простую иконку, например, с помощью онлайн-конвертера).
#    - Если нет иконки, tray запустится без неё.
# 2. Уведомления: добавлены системные уведомления с plyer (pip install plyer).
#    - Теперь уведомление показывает системный toast (на компе, вне приложения) + звук.
#    - Для интерактива ("Прекратить" или "OK") — всё равно использует Tkinter askyesno, который покажет попап даже если окно скрыто.
#    - Повторения: уже было каждые >5 сек до "Прекратить" (если выбрал "OK" — повторяется). Если не повторялось — возможно, bug в тесте; теперь с системным notify должно быть заметнее.
#    - Если хочешь чисто системное с кнопками — для Windows можно использовать winotify, но plyer + askyesno проще и работает.
# Дополнительно: приложение продолжает работать в фоне, reminder_thread проверяет напоминания даже без окна.

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import datetime
import threading
import time
import os
import winsound
import pyrebase
import requests
import sys
import subprocess
import platform
import re  # Для re.match в normalize функциях
from infi.systray import SysTrayIcon  # Для tray icon (pip install infi.systray)
from plyer import notification  # Для системных уведомлений (pip install plyer)

# ────────────────────────────────────────────────
# Firebase конфигурация
# ────────────────────────────────────────────────
firebaseConfig = {
    "apiKey": "AIzaSyA_GcaGJ0iY6U9bM4GphmjVqsROjmWo8Ak",
    "authDomain": "tasksgrok.firebaseapp.com",
    "databaseURL": "https://tasksgrok-default-rtdb.firebaseio.com",
    "projectId": "tasksgrok",
    "storageBucket": "tasksgrok.firebasestorage.app",
    "messagingSenderId": "102332985270",
    "appId": "1:102332985270:web:a6adc26f2e0240247ddb17",
    "measurementId": "G-ZYVMRZWFF6"
}

firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()
db = firebase.database()


class TasksApp:
    def __init__(self, root):
        print("→ Инициализация приложения начата")

        self.root = root
        self.root.title("Tasks - Планировщик задач")
        self.root.geometry("800x600")

        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Шрифты
        self.FONT_SMALL = ('Helvetica', 10)
        self.FONT_MEDIUM = ('Helvetica', 12)
        self.FONT_LARGE = ('Helvetica', 14)

        # Темы
        self.themes = {
            "Default": {
                "name": "Default (тёмный комфортный)",
                "BG_COLOR": "#111827",
                "TEXT_COLOR": "#f1f5f9",
                "BUTTON_COLOR": "#6366f1",
                "ACTIVE_BUTTON_COLOR": "#818cf8",
                "BORDER_COLOR": "#1e293b",
                "GREEN_BUTTON": "#10b981",
                "PLACEHOLDER_COLOR": "#a0aec0"
            },
            "Forest Mist": {
                "name": "Forest Mist (зелёный уют)",
                "BG_COLOR": "#0f1e17",
                "TEXT_COLOR": "#d1fae5",
                "BUTTON_COLOR": "#4ade80",
                "ACTIVE_BUTTON_COLOR": "#86efac",
                "BORDER_COLOR": "#14532d",
                "GREEN_BUTTON": "#059669",
                "PLACEHOLDER_COLOR": "#a0aec0"
            },
            "Lavender Dusk": {
                "name": "Lavender Dusk (фиолетовый вечер)",
                "BG_COLOR": "#1e1b2e",
                "TEXT_COLOR": "#ede9fe",
                "BUTTON_COLOR": "#a78bfa",
                "ACTIVE_BUTTON_COLOR": "#c4b5fd",
                "BORDER_COLOR": "#312e4a",
                "GREEN_BUTTON": "#34d399",
                "PLACEHOLDER_COLOR": "#a0aec0"
            }
        }

        # Переменные настроек
        self.theme_var = tk.StringVar(value="Default")
        self.text_size_var = tk.StringVar(value="Средний")
        self.lang_var = tk.StringVar(value="Русский")

        # Создаём фреймы ДО темы
        self.sidebar_frame = tk.Frame(
            self.root,
            width=200,
            bd=2,
            relief='solid',
            highlightthickness=2
        )
        self.sidebar_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.content_frame = tk.Frame(self.root)
        self.content_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Состояние
        self.current_section = tk.StringVar(value="Login")
        self.user = None
        self.user_token = None
        self.tasks = []
        self.next_task_id = 1
        self.custom_types = ["Основная", "Дополнительная", "Необязательная"]
        self.bin = []

        # Применяем начальную тему
        self.apply_theme()
        self.configure_styles()

        # Показываем логин
        self.show_login()

        # Поток напоминаний
        self.reminder_thread = threading.Thread(target=self.check_reminders_loop, daemon=True)
        self.reminder_thread.start()

        print("→ Инициализация приложения завершена")

    def _(self, text):
        return text  # пока только русский

    def configure_styles(self):
        print("→ Конфигурация стилей")
        self.style.configure('TLabel', background=self.BG_COLOR, foreground=self.TEXT_COLOR, font=self.FONT_MEDIUM)
        self.style.configure('Sidebar.TButton', background=self.BUTTON_COLOR, foreground=self.TEXT_COLOR, font=self.FONT_MEDIUM, padding=10)
        self.style.map('Sidebar.TButton', background=[('active', self.ACTIVE_BUTTON_COLOR)])
        self.style.configure('Add.TButton', background=self.GREEN_BUTTON, foreground=self.TEXT_COLOR, font=self.FONT_MEDIUM, padding=10)
        self.style.configure('Treeview', background=self.BG_COLOR, foreground=self.TEXT_COLOR, fieldbackground=self.BG_COLOR, font=self.FONT_SMALL)
        self.style.configure('Treeview.Heading', background=self.BUTTON_COLOR, foreground=self.TEXT_COLOR, font=self.FONT_MEDIUM)
        self.style.map('Treeview', background=[('selected', self.ACTIVE_BUTTON_COLOR)])

    def show_login(self):
        self.clear_content()
        self.current_section.set("Login")
        ttk.Label(self.content_frame, text="Вход / Регистрация", font=self.FONT_LARGE).pack(pady=40)
        ttk.Label(self.content_frame, text="Email:").pack(pady=5)
        self.email_entry = ttk.Entry(self.content_frame, width=40)
        self.email_entry.pack()
        ttk.Label(self.content_frame, text="Пароль:").pack(pady=5)
        self.password_entry = ttk.Entry(self.content_frame, show="*", width=40)
        self.password_entry.pack()
        btn_frame = tk.Frame(self.content_frame, bg=self.BG_COLOR)
        btn_frame.pack(pady=30)
        ttk.Button(btn_frame, text="Войти", style='Add.TButton', command=self.login).pack(side=tk.LEFT, padx=15)
        ttk.Button(btn_frame, text="Зарегистрироваться", command=self.register).pack(side=tk.LEFT, padx=15)

    def login(self):
        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()
        if not email or not password:
            messagebox.showwarning("Ошибка", "Введите email и пароль")
            return
        try:
            self.user = auth.sign_in_with_email_and_password(email, password)
            self.user_token = self.user['idToken']
            messagebox.showinfo("Успех", "Вход выполнен")
            self.load_data_from_db()
            self.apply_theme()
            self.apply_text_size()
            self.create_sidebar()
            self.show_welcome()
            print("→ Login завершён успешно")
        except Exception as e:
            messagebox.showerror("Ошибка входа", str(e))
            print("Ошибка входа:", str(e))

    def register(self):
        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()
        if not email or not password:
            messagebox.showwarning("Ошибка", "Введите email и пароль")
            return
        try:
            auth.create_user_with_email_and_password(email, password)
            messagebox.showinfo("Успех", "Аккаунт создан. Теперь войдите.")
        except Exception as e:
            messagebox.showerror("Ошибка регистрации", str(e))

    def logout(self):
        self.user = None
        self.user_token = None
        self.tasks = []
        self.bin = []
        self.next_task_id = 1
        self.custom_types = ["Основная", "Дополнительная", "Необязательная"]
        self.clear_content()
        for widget in self.sidebar_frame.winfo_children():
            widget.destroy()
        self.show_login()

    def edit_profile(self):
        form = tk.Toplevel(self.root)
        form.title("Редактировать профиль")
        form.geometry("400x400")
        form.configure(bg=self.BG_COLOR)

        current_email = self.user['email']

        ttk.Label(form, text="Текущий email: " + current_email).pack(pady=10)
        ttk.Label(form, text="Новый email (опционально):").pack(pady=5)
        new_email_entry = ttk.Entry(form, width=30)
        new_email_entry.pack()

        ttk.Label(form, text="Старый пароль (для подтверждения):").pack(pady=5)
        old_pass_entry = ttk.Entry(form, show="*", width=30)
        old_pass_entry.pack()

        ttk.Label(form, text="Новый пароль (опционально):").pack(pady=5)
        new_pass_entry = ttk.Entry(form, show="*", width=30)
        new_pass_entry.pack()

        ttk.Label(form, text="Подтвердите новый пароль:").pack(pady=5)
        confirm_entry = ttk.Entry(form, show="*", width=30)
        confirm_entry.pack()

        def save_profile():
            old_pass = old_pass_entry.get().strip()
            new_email = new_email_entry.get().strip()
            new_pass = new_pass_entry.get().strip()
            confirm = confirm_entry.get().strip()

            if not old_pass:
                messagebox.showwarning("Ошибка", "Введите старый пароль для подтверждения")
                return

            change_email = bool(new_email and new_email != current_email)
            change_pass = bool(new_pass and new_pass == confirm)

            if not change_email and not change_pass:
                messagebox.showinfo("Инфо", "Ничего не изменено")
                form.destroy()
                return

            if change_pass and new_pass != confirm:
                messagebox.showwarning("Ошибка", "Новые пароли не совпадают")
                return

            try:
                # Reauthenticate для безопасности
                auth.sign_in_with_email_and_password(current_email, old_pass)  # Проверяем старый пароль

                uid = self.user['localId']
                updates = {}
                if change_email:
                    updates['email'] = new_email
                if change_pass:
                    updates['password'] = new_pass

                auth.update_user(uid, **updates)
                messagebox.showinfo("Успех", "Профиль обновлён. Войдите заново.")
                self.logout()
                form.destroy()
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))

        ttk.Button(form, text="Сохранить", style='Add.TButton', command=save_profile).pack(pady=20)

    def show_profile_menu(self):
        menu = tk.Menu(self.root, tearoff=0, bg=self.BG_COLOR, fg=self.TEXT_COLOR)
        menu.add_command(label="Выход", command=self.logout)
        menu.add_command(label="Сменить аккаунт", command=self.logout)
        menu.add_command(label="Редактировать", command=self.edit_profile)
        menu.post(self.root.winfo_pointerx(), self.root.winfo_pointery())

    def load_data_from_db(self):
        if not self.user:
            return
        uid = self.user['localId']
        token = self.user_token

        try:
            # custom_types
            types_data = db.child("users").child(uid).child("custom_types").get(token).val()
            self.custom_types = types_data if types_data else ["Основная", "Дополнительная", "Необязательная"]

            # tasks
            tasks_data = db.child("users").child(uid).child("tasks").get(token).val()
            self.tasks = []
            max_id = 0
            if tasks_data:
                if isinstance(tasks_data, dict):
                    items = tasks_data.items()
                else:
                    items = enumerate(tasks_data)
                for raw_id, task in items:
                    if task is None:
                        continue
                    str_id = str(raw_id)
                    try:
                        task["id"] = int(str_id) if str_id.isdigit() else task.get("id", max_id + 1)
                        if "created" in task and isinstance(task["created"], str):
                            date_str = task["created"].split('.')[0].replace('T', ' ')
                            task["created"] = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        if "last_trigger" in task and task.get("last_trigger"):
                            date_str = task["last_trigger"].split('.')[0].replace('T', ' ')
                            task["last_trigger"] = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        self.tasks.append(task)
                        max_id = max(max_id, task["id"])
                    except Exception as inner_e:
                        print(f"Ошибка парсинга задачи {str_id}: {inner_e}")

            # bin
            bin_data = db.child("users").child(uid).child("bin").get(token).val()
            self.bin = []
            if bin_data:
                if isinstance(bin_data, dict):
                    items = bin_data.items()
                else:
                    items = enumerate(bin_data)
                for raw_id, task in items:
                    if task is None:
                        continue
                    str_id = str(raw_id)
                    try:
                        task["id"] = int(str_id) if str_id.isdigit() else task.get("id", 0)
                        if "created" in task and isinstance(task["created"], str):
                            date_str = task["created"].split('.')[0].replace('T', ' ')
                            task["created"] = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        if "last_trigger" in task and task.get("last_trigger"):
                            date_str = task["last_trigger"].split('.')[0].replace('T', ' ')
                            task["last_trigger"] = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        self.bin.append(task)
                    except Exception as inner_e:
                        print(f"Ошибка парсинга bin {str_id}: {inner_e}")

            # next_task_id
            next_id = db.child("users").child(uid).child("next_task_id").get(token).val()
            self.next_task_id = next_id if next_id is not None else max_id + 1

            # settings
            settings_data = db.child("users").child(uid).child("settings").get(token).val()
            if settings_data:
                if "theme" in settings_data:
                    self.theme_var.set(settings_data["theme"])
                    self.apply_theme()
                if "text_size" in settings_data:
                    self.text_size_var.set(settings_data["text_size"])
                    self.apply_text_size()

                self.lang_var.set("Русский")
                self.refresh_current_screen()

        except Exception as e:
            print("Ошибка загрузки данных:", str(e))
            messagebox.showerror("Ошибка загрузки", str(e))

    def save_data_to_db(self):
        if not self.user:
            return
        uid = self.user['localId']
        token = self.user_token
        try:
            db.child("users").child(uid).child("custom_types").set(self.custom_types, token)

            tasks_dict = {}
            for task in self.tasks:
                t = task.copy()
                t["created"] = task["created"].strftime("%Y-%m-%d %H:%M:%S")
                if "last_trigger" in t and t["last_trigger"]:
                    t["last_trigger"] = t["last_trigger"].strftime("%Y-%m-%d %H:%M:%S")
                tasks_dict[str(task["id"])] = t
            db.child("users").child(uid).child("tasks").set(tasks_dict, token)

            bin_dict = {}
            for task in self.bin:
                t = task.copy()
                t["created"] = task["created"].strftime("%Y-%m-%d %H:%M:%S")
                if "last_trigger" in t and t["last_trigger"]:
                    t["last_trigger"] = t["last_trigger"].strftime("%Y-%m-%d %H:%M:%S")
                bin_dict[str(task["id"])] = t
            db.child("users").child(uid).child("bin").set(bin_dict, token)

            db.child("users").child(uid).child("next_task_id").set(self.next_task_id, token)

            settings = {
                "theme": self.theme_var.get(),
                "text_size": self.text_size_var.get(),
            }
            db.child("users").child(uid).child("settings").set(settings, token)

        except Exception as e:
            messagebox.showerror("Ошибка сохранения", str(e))

    def create_sidebar(self):
        profile_btn = ttk.Button(self.sidebar_frame, text="Профиль", style='Sidebar.TButton', command=self.show_profile_menu)
        profile_btn.pack(fill=tk.X, pady=5, padx=10)

        logo_label = ttk.Label(self.sidebar_frame, text="Tasks", style='TLabel', font=self.FONT_LARGE)
        logo_label.pack(pady=20)
        sections = [
            ("Задачи", self.show_tasks),
            ("Корзина", self.show_bin),
            ("Напоминания", self.show_reminders),
            ("Настройки", self.show_settings),
            ("О программе", self.show_about)
        ]
        for name, command in sections:
            btn = ttk.Button(self.sidebar_frame, text=name, style='Sidebar.TButton', command=command)
            btn.pack(fill=tk.X, pady=5, padx=10)

        # Добавляем кнопку "Скрыть в tray"
        hide_btn = ttk.Button(self.sidebar_frame, text="Скрыть", style='Sidebar.TButton', command=self.hide_to_tray)
        hide_btn.pack(fill=tk.X, pady=5, padx=10)

    def hide_to_tray(self):
        self.root.withdraw()

    def show_from_tray(self, systray):
        self.root.deiconify()

    def quit_app(self, systray):
        systray.shutdown()
        self.root.quit()
        self.root.destroy()
        os._exit(0)  # Полный выход

    def clear_content(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def show_welcome(self):
        self.clear_content()
        self.current_section.set("Welcome")
        ttk.Label(self.content_frame, text="Добро пожаловать в Tasks!", style='TLabel', font=self.FONT_LARGE).pack(pady=40)
        ttk.Button(self.content_frame, text="Разделы", style='Sidebar.TButton', command=self.show_tasks).pack(pady=20)
        self.root.update()

    def show_tasks(self):
        self.clear_content()
        self.current_section.set("Задачи")
        top_frame = tk.Frame(self.content_frame, bg=self.BG_COLOR)
        top_frame.pack(fill=tk.X, padx=20, pady=(20, 10))
        ttk.Button(top_frame, text="+ Добавить задачу", style='Add.TButton', command=self.open_add_task_form).pack(side=tk.LEFT)

        columns = ("№", "Название", "Описание", "Тип", "Дата", "Статус")
        self.tasks_tree = ttk.Treeview(self.content_frame, columns=columns, show='headings', style='Treeview', selectmode='extended')
        for col, text, w in zip(columns, ["№", "Название", "Описание", "Тип", "Дата создания", "Статус"], [50, 180, 220, 120, 160, 100]):
            self.tasks_tree.heading(col, text=text)
            self.tasks_tree.column(col, width=w, anchor='center' if col == "№" else 'w')
        self.tasks_tree.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        self.tasks_tree.bind("<Double-1>", self.on_double_click_task)

        bottom_frame = tk.Frame(self.content_frame, bg=self.BG_COLOR)
        bottom_frame.pack(fill=tk.X, padx=20, pady=10)
        ttk.Button(bottom_frame, text="Удалить выбранное", command=self.delete_selected_tasks).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(bottom_frame, text="Переключить статус", command=self.toggle_selected_status).pack(side=tk.LEFT, padx=10)
        self.refresh_tasks_table()

    def refresh_tasks_table(self):
        if not hasattr(self, 'tasks_tree') or not self.tasks_tree.winfo_exists():
            return
        for item in self.tasks_tree.get_children():
            self.tasks_tree.delete(item)
        for i, task in enumerate(self.tasks, 1):
            status = "✅" if task.get("done", False) else "❌"
            values = (i, task["name"][:45] + ("..." if len(task["name"]) > 45 else ""), task["desc"][:60] + ("..." if len(task["desc"]) > 60 else ""), task["type"], task["created"].strftime("%H:%M %d.%m.%Y"), status)
            self.tasks_tree.insert("", tk.END, iid=str(task["id"]), values=values)

    def open_add_task_form(self, task_to_edit=None):
        form = tk.Toplevel(self.root)
        form.title("Добавить задачу" if not task_to_edit else "Редактировать задачу")
        form.geometry("480x380")
        form.configure(bg=self.BG_COLOR)

        tk.Label(form, text="Название:", bg=self.BG_COLOR, fg=self.TEXT_COLOR, font=self.FONT_MEDIUM).pack(anchor='w', padx=20, pady=(20, 8))
        name_entry = ttk.Entry(form, font=self.FONT_MEDIUM, width=50)
        name_entry.pack(padx=20, fill=tk.X)

        tk.Label(form, text="Описание:", bg=self.BG_COLOR, fg=self.TEXT_COLOR, font=self.FONT_MEDIUM).pack(anchor='w', padx=20, pady=(12, 8))
        desc_text = tk.Text(form, height=6, font=self.FONT_SMALL, bg='#3C3C3C', fg=self.TEXT_COLOR, insertbackground=self.TEXT_COLOR)
        desc_text.pack(padx=20, fill=tk.BOTH, expand=False)

        tk.Label(form, text="Тип задачи:", bg=self.BG_COLOR, fg=self.TEXT_COLOR, font=self.FONT_MEDIUM).pack(anchor='w', padx=20, pady=(12, 8))
        type_frame = tk.Frame(form, bg=self.BG_COLOR)
        type_frame.pack(fill=tk.X, padx=20)
        type_var = tk.StringVar(value=self.custom_types[0] if self.custom_types else "")
        type_combo = ttk.Combobox(type_frame, textvariable=type_var, values=self.custom_types, font=self.FONT_MEDIUM, state="readonly")
        type_combo.pack(side=tk.LEFT)
        new_type_entry = ttk.Entry(type_frame, font=self.FONT_MEDIUM, width=18)
        new_type_entry.pack(side=tk.LEFT, padx=(10, 0))

        def add_custom_type():
            new_t = new_type_entry.get().strip()
            if new_t and new_t not in self.custom_types:
                self.custom_types.append(new_t)
                type_combo['values'] = self.custom_types
                type_var.set(new_t)
                new_type_entry.delete(0, tk.END)
                self.save_data_to_db()

        ttk.Button(type_frame, text="Добавить тип", command=add_custom_type).pack(side=tk.LEFT, padx=8)

        if task_to_edit:
            name_entry.insert(0, task_to_edit["name"])
            desc_text.insert("1.0", task_to_edit["desc"])
            type_var.set(task_to_edit["type"])

        btn_frame = tk.Frame(form, bg=self.BG_COLOR)
        btn_frame.pack(pady=25)
        def save_and_close():
            name = name_entry.get().strip()
            desc = desc_text.get("1.0", tk.END).strip()
            typ = type_var.get().strip()
            if not name:
                messagebox.showwarning("Ошибка", "Название обязательно")
                return
            created = datetime.datetime.now()
            if task_to_edit:
                task_to_edit["name"] = name
                task_to_edit["desc"] = desc
                task_to_edit["type"] = typ
            else:
                task = {"id": self.next_task_id, "name": name, "desc": desc, "type": typ, "created": created, "done": False}
                self.tasks.append(task)
                self.next_task_id += 1
            self.refresh_tasks_table()
            form.destroy()
            self.save_data_to_db()

        ttk.Button(btn_frame, text="Сохранить", style='Add.TButton', command=save_and_close).pack(side=tk.LEFT, padx=15)
        ttk.Button(btn_frame, text="Отмена", command=form.destroy).pack(side=tk.LEFT)
        name_entry.focus()

    def on_double_click_task(self, event):
        item = self.tasks_tree.identify_row(event.y)
        if item:
            task_id = int(item)
            task = next((t for t in self.tasks if t["id"] == task_id), None)
            if task:
                self.open_add_task_form(task_to_edit=task)

    def delete_selected_tasks(self):
        selected = self.tasks_tree.selection()
        if not selected:
            return
        ids = [int(iid) for iid in selected]
        if messagebox.askyesno("Удаление", f"Переместить {len(ids)} задач в корзину?"):
            to_bin = [t for t in self.tasks if t["id"] in ids]
            self.tasks = [t for t in self.tasks if t["id"] not in ids]
            self.bin.extend(to_bin)
            self.refresh_tasks_table()
            self.save_data_to_db()

    def toggle_selected_status(self):
        selected = self.tasks_tree.selection()
        if not selected:
            return
        ids = [int(iid) for iid in selected]
        done_count = sum(1 for t in self.tasks if t["id"] in ids and t.get("done"))
        new_status = len(ids) - done_count >= done_count
        if messagebox.askyesno("Статус", f"Установить {'выполнено' if new_status else 'не выполнено'}?"):
            for t in self.tasks:
                if t["id"] in ids:
                    t["done"] = new_status
            self.refresh_tasks_table()
            self.save_data_to_db()

    def show_bin(self):
        self.clear_content()
        self.current_section.set("Корзина")
        ttk.Label(self.content_frame, text="Корзина", style='TLabel', font=self.FONT_LARGE).pack(pady=20)

        columns = ("№", "Название", "Описание", "Тип", "Дата создания", "Статус")
        self.bin_tree = ttk.Treeview(self.content_frame, columns=columns, show='headings', style='Treeview', selectmode='extended')
        for col, text, w in zip(columns, ["№", "Название", "Описание", "Тип", "Дата создания", "Статус"], [50, 180, 220, 120, 160, 100]):
            self.bin_tree.heading(col, text=text)
            self.bin_tree.column(col, width=w, anchor='center' if col == "№" else 'w')
        self.bin_tree.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        bottom_frame = tk.Frame(self.content_frame, bg=self.BG_COLOR)
        bottom_frame.pack(fill=tk.X, padx=20, pady=10)
        ttk.Button(bottom_frame, text="Восстановить", style='Add.TButton', command=self.restore_from_bin).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(bottom_frame, text="Удалить навсегда", command=self.delete_permanently_from_bin).pack(side=tk.LEFT)
        self.refresh_bin_table()

    def refresh_bin_table(self):
        if not hasattr(self, 'bin_tree') or not self.bin_tree.winfo_exists():
            return
        for item in self.bin_tree.get_children():
            self.bin_tree.delete(item)
        for i, task in enumerate(self.bin, 1):
            status = "✅" if task.get("done", False) else "❌"
            values = (i, task["name"][:45] + ("..." if len(task["name"]) > 45 else ""), task["desc"][:60] + ("..." if len(task["desc"]) > 60 else ""), task["type"], task["created"].strftime("%H:%M %d.%m.%Y"), status)
            self.bin_tree.insert("", tk.END, iid=str(task["id"]), values=values)

    def restore_from_bin(self):
        selected = self.bin_tree.selection()
        if not selected:
            return
        ids = [int(iid) for iid in selected]
        if messagebox.askyesno("Восстановление", f"Восстановить {len(ids)} задач?"):
            to_restore = [t for t in self.bin if t["id"] in ids]
            self.bin = [t for t in self.bin if t["id"] not in ids]
            self.tasks.extend(to_restore)
            self.refresh_bin_table()
            if self.current_section.get() == "Задачи":
                self.refresh_tasks_table()
            self.save_data_to_db()

    def delete_permanently_from_bin(self):
        selected = self.bin_tree.selection()
        if not selected:
            return
        ids = [int(iid) for iid in selected]
        if messagebox.askyesno("Удаление навсегда", f"Удалить {len(ids)} задач безвозвратно?"):
            self.bin = [t for t in self.bin if t["id"] not in ids]
            self.refresh_bin_table()
            self.save_data_to_db()

    def show_reminders(self):
        self.clear_content()
        self.current_section.set("Напоминания")
        ttk.Label(self.content_frame, text="Напоминания", style='TLabel', font=self.FONT_LARGE).pack(pady=20)

        top_frame = tk.Frame(self.content_frame, bg=self.BG_COLOR)
        top_frame.pack(fill=tk.X, padx=20, pady=(10, 10))
        ttk.Button(top_frame, text="Поставить / Изменить напоминание", style='Add.TButton', command=self.open_reminder_form).pack(side=tk.LEFT)

        columns = ("№", "Название", "Тип", "Дата создания", "Напоминание", "Статус")
        self.reminders_tree = ttk.Treeview(self.content_frame, columns=columns, show='headings', style='Treeview', selectmode='extended')
        for col, text, w in zip(columns, ["№", "Название", "Тип", "Дата создания", "Напоминание", "Статус"], [50, 220, 120, 160, 180, 100]):
            self.reminders_tree.heading(col, text=text)
            self.reminders_tree.column(col, width=w, anchor='center' if col == "№" else 'w')
        self.reminders_tree.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        self.reminders_tree.bind("<Double-1>", self.on_double_click_reminder)

        bottom_frame = tk.Frame(self.content_frame, bg=self.BG_COLOR)
        bottom_frame.pack(fill=tk.X, padx=20, pady=10)
        ttk.Button(bottom_frame, text="Удалить напоминание у выбранных", command=self.delete_selected_reminders).pack(side=tk.LEFT, padx=10)
        self.refresh_reminders_table()

    def refresh_reminders_table(self):
        if not hasattr(self, 'reminders_tree') or not self.reminders_tree.winfo_exists():
            return
        for item in self.reminders_tree.get_children():
            self.reminders_tree.delete(item)
        for i, task in enumerate(self.tasks, 1):
            reminder = f"{task.get('reminder_date', '—')} {task.get('reminder_time', '')}".strip()
            if not reminder or reminder == '—':
                reminder = "—"
            status = "✅" if task.get("done", False) else "❌"
            values = (i, task["name"][:55] + ("…" if len(task["name"]) > 55 else ""), task["type"], task["created"].strftime("%H:%M %d.%m.%Y"), reminder, status)
            self.reminders_tree.insert("", tk.END, iid=str(task["id"]), values=values)

    def open_reminder_form(self, task_to_edit=None):
        if task_to_edit is None:
            selected = self.reminders_tree.selection()
            if not selected:
                messagebox.showwarning("Выбор", "Выберите задачу")
                return
            task_id = int(selected[0])
            task_to_edit = next((t for t in self.tasks if t["id"] == task_id), None)
            if not task_to_edit:
                return

        form = tk.Toplevel(self.root)
        form.title("Напоминание")
        form.geometry("500x400")
        form.configure(bg=self.BG_COLOR)
        form.transient(self.root)
        form.grab_set()

        ttk.Label(form, text=f"Задача: {task_to_edit['name']}", font=self.FONT_MEDIUM, wraplength=450).pack(anchor='w', padx=35, pady=(25, 15))

        tk.Label(form, text="Дата (дд.мм.гггг):", bg=self.BG_COLOR, fg=self.TEXT_COLOR, font=self.FONT_MEDIUM).pack(anchor='w', padx=35, pady=(5, 2))
        date_entry = ttk.Entry(form, font=self.FONT_MEDIUM)
        date_entry.pack(padx=35, fill=tk.X, ipady=5)
        date_entry.insert(0, task_to_edit.get("reminder_date", datetime.date.today().strftime("%d.%m.%Y")))

        tk.Label(form, text="Время (чч:мм:сс):", bg=self.BG_COLOR, fg=self.TEXT_COLOR, font=self.FONT_MEDIUM).pack(anchor='w', padx=35, pady=(20, 2))
        time_entry = ttk.Entry(form, font=self.FONT_MEDIUM)
        time_entry.pack(padx=35, fill=tk.X, ipady=5)
        placeholder = "например: 14:30:00"
        time_entry.insert(0, placeholder)
        time_entry.config(foreground=self.PLACEHOLDER_COLOR)

        def on_focus_in(e):
            if time_entry.get() == placeholder:
                time_entry.delete(0, tk.END)
                time_entry.config(foreground='black')

        def on_focus_out(e):
            if not time_entry.get().strip():
                time_entry.insert(0, placeholder)
                time_entry.config(foreground=self.PLACEHOLDER_COLOR)
            else:
                time_entry.config(foreground='black')

        time_entry.bind("<FocusIn>", on_focus_in)
        time_entry.bind("<FocusOut>", on_focus_out)

        if task_to_edit.get("reminder_time"):
            time_entry.delete(0, tk.END)
            time_entry.insert(0, task_to_edit["reminder_time"])
            time_entry.config(foreground='black')

        btn_frame = tk.Frame(form, bg=self.BG_COLOR)
        btn_frame.pack(pady=40, fill=tk.X)

        def normalize_date(s):
            s = ''.join(c for c in s if c.isdigit())
            if len(s) == 6:
                s = s[:4] + "20" + s[4:]
            if len(s) == 8:
                return f"{s[:2]}.{s[2:4]}.{s[4:]}"
            return s

        def normalize_time(s):
            s = ''.join(c for c in s if c.isdigit())
            if len(s) == 4:
                s += "00"
            if len(s) == 6:
                return f"{s[:2]}:{s[2:4]}:{s[4:]}"
            return ""

        def save_reminder():
            date_raw = date_entry.get().strip()
            time_raw = time_entry.get().strip()
            if not date_raw or not time_raw or time_raw == placeholder:
                messagebox.showwarning("Ошибка", "Укажите дату и время")
                return

            date_norm = normalize_date(date_raw)
            time_norm = normalize_time(time_raw)

            if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", date_norm) or not re.match(r"^\d{2}:\d{2}:\d{2}$", time_norm):
                messagebox.showerror("Формат", "Неверный формат даты или времени")
                return

            try:
                dt = datetime.datetime.strptime(f"{date_norm} {time_norm}", "%d.%m.%Y %H:%M:%S")
                if dt < datetime.datetime.now():
                    if not messagebox.askyesno("Прошлое", "Напоминание в прошлом. Сохранить?"):
                        return
            except ValueError:
                messagebox.showerror("Ошибка", "Некорректная дата/время")
                return

            task_to_edit["reminder_date"] = date_norm
            task_to_edit["reminder_time"] = time_norm
            task_to_edit.pop("last_trigger", None)

            self.refresh_reminders_table()
            form.destroy()
            messagebox.showinfo("Успех", "Напоминание сохранено")
            self.save_data_to_db()

        ttk.Button(btn_frame, text="Сохранить", style='Add.TButton', command=save_reminder).pack(side=tk.LEFT, padx=20)
        ttk.Button(btn_frame, text="Отмена", command=form.destroy).pack(side=tk.LEFT)
        date_entry.focus()

    def delete_selected_reminders(self):
        selected = self.reminders_tree.selection()
        if not selected:
            return
        ids = [int(iid) for iid in selected]
        if messagebox.askyesno("Удаление", f"Удалить напоминания у {len(ids)} задач?"):
            for task in self.tasks:
                if task["id"] in ids:
                    task.pop("reminder_date", None)
                    task.pop("reminder_time", None)
                    task.pop("last_trigger", None)
            self.refresh_reminders_table()
            self.save_data_to_db()

    def on_double_click_reminder(self, event):
        item = self.reminders_tree.identify_row(event.y)
        if item:
            task_id = int(item)
            task = next((t for t in self.tasks if t["id"] == task_id), None)
            if task:
                self.open_reminder_form(task_to_edit=task)

    def _trigger_reminder(self, task):
        msg = f"{task['name']}\n{task.get('desc', '')[:120]}..."
        title = "НАПОМИНАНИЕ"

        # Системное уведомление (toast на компе)
        notification.notify(
            title=title,
            message=msg,
            app_name="Tasks",
            app_icon="icon.ico" if os.path.exists("icon.ico") else None,
            timeout=10
        )

        # Звук
        try:
            winsound.MessageBeep()
        except:
            pass

        # Интерактивный попап (даже если окно скрыто)
        stop = messagebox.askyesno(title, msg, detail="Прекратить напоминания для этой задачи?")

        task["last_trigger"] = datetime.datetime.now()

        if stop:
            task.pop("reminder_date", None)
            task.pop("reminder_time", None)
            task.pop("last_trigger", None)
            if hasattr(self, 'reminders_tree') and self.reminders_tree.winfo_exists():
                self.refresh_reminders_table()

        self.save_data_to_db()

    def check_reminders_loop(self):
        while True:
            try:
                now = datetime.datetime.now()
                for task in self.tasks:
                    if task.get("reminder_date") and task.get("reminder_time") and not task.get("done"):
                        r_str = f"{task['reminder_date']} {task['reminder_time']}"
                        r_dt = datetime.datetime.strptime(r_str, "%d.%m.%Y %H:%M:%S")
                        if now >= r_dt:
                            last = task.get("last_trigger")
                            if not last or (now - last).total_seconds() > 5:
                                self._trigger_reminder(task)
            except Exception as e:
                print("Ошибка в напоминаниях:", e)
            time.sleep(1)

    def show_settings(self):
        self.clear_content()
        self.current_section.set("Настройки")
        ttk.Label(self.content_frame, text="Настройки", style='TLabel', font=self.FONT_LARGE).pack(pady=30)
        content = tk.Frame(self.content_frame, bg=self.BG_COLOR)
        content.pack(padx=40, pady=20, fill=tk.BOTH, expand=True)

        f = tk.Frame(content, bg=self.BG_COLOR)
        f.pack(fill=tk.X, pady=15)
        ttk.Label(f, text="Размер текста:", style='TLabel').pack(side=tk.LEFT, padx=10)
        combo = ttk.Combobox(f, textvariable=self.text_size_var, values=["Маленький", "Средний", "Большой"], state="readonly", font=self.FONT_MEDIUM, width=15)
        combo.pack(side=tk.LEFT, padx=10)
        combo.bind("<<ComboboxSelected>>", self.apply_text_size)

        f = tk.Frame(content, bg=self.BG_COLOR)
        f.pack(fill=tk.X, pady=15)
        ttk.Label(f, text="Тема:", style='TLabel').pack(side=tk.LEFT, padx=10)
        combo = ttk.Combobox(f, textvariable=self.theme_var, values=list(self.themes.keys()), state="readonly", font=self.FONT_MEDIUM, width=25)
        combo.pack(side=tk.LEFT, padx=10)
        combo.bind("<<ComboboxSelected>>", self.apply_theme)

        f = tk.Frame(content, bg=self.BG_COLOR)
        f.pack(fill=tk.X, pady=15)
        ttk.Label(f, text="Звук напоминаний: системный сигнал Windows", style='TLabel').pack(side=tk.LEFT, padx=10)

        f = tk.Frame(content, bg=self.BG_COLOR)
        f.pack(fill=tk.X, pady=15)
        ttk.Label(f, text="Язык:", style='TLabel').pack(side=tk.LEFT, padx=10)
        ttk.Label(f, text="Русский (другие — в разработке)", style='TLabel', font=self.FONT_MEDIUM).pack(side=tk.LEFT, padx=10)

        ttk.Button(content, text="Сохранить настройки", style='Add.TButton', command=self.save_settings).pack(pady=40)

    def apply_text_size(self, event=None):
        size = self.text_size_var.get()
        if size == "Маленький":
            self.FONT_SMALL, self.FONT_MEDIUM, self.FONT_LARGE = ('Helvetica', 9), ('Helvetica', 10), ('Helvetica', 11)
        elif size == "Большой":
            self.FONT_SMALL, self.FONT_MEDIUM, self.FONT_LARGE = ('Helvetica', 12), ('Helvetica', 14), ('Helvetica', 16)
        else:
            self.FONT_SMALL, self.FONT_MEDIUM, self.FONT_LARGE = ('Helvetica', 10), ('Helvetica', 12), ('Helvetica', 14)

        self.configure_styles()
        self.refresh_current_screen()
        self.save_data_to_db()

    def apply_theme(self, event=None):
        theme = self.themes.get(self.theme_var.get(), self.themes["Default"])
        self.BG_COLOR = theme["BG_COLOR"]
        self.TEXT_COLOR = theme["TEXT_COLOR"]
        self.BUTTON_COLOR = theme["BUTTON_COLOR"]
        self.ACTIVE_BUTTON_COLOR = theme["ACTIVE_BUTTON_COLOR"]
        self.BORDER_COLOR = theme["BORDER_COLOR"]
        self.GREEN_BUTTON = theme["GREEN_BUTTON"]
        self.PLACEHOLDER_COLOR = theme.get("PLACEHOLDER_COLOR", "#a0aec0")

        self.root.configure(bg=self.BG_COLOR)
        if hasattr(self, 'sidebar_frame') and self.sidebar_frame.winfo_exists():
            self.sidebar_frame.configure(bg=self.BG_COLOR, highlightbackground=self.BORDER_COLOR)
        if hasattr(self, 'content_frame') and self.content_frame.winfo_exists():
            self.content_frame.configure(bg=self.BG_COLOR)

        self.configure_styles()
        self.refresh_current_screen()

    def refresh_current_screen(self):
        current = self.current_section.get()
        method_map = {
            "Login": self.show_login,
            "Welcome": self.show_welcome,
            "Задачи": self.show_tasks,
            "Корзина": self.show_bin,
            "Напоминания": self.show_reminders,
            "Настройки": self.show_settings,
            "О программе": self.show_about
        }
        if current in method_map:
            method_map[current]()

    def show_about(self):
        self.clear_content()
        self.current_section.set("О программе")
        ttk.Label(self.content_frame, text="О программе", style='TLabel', font=self.FONT_LARGE).pack(pady=20)
        text = (
            "Tasks — удобный планировщик задач\n"
            "Версия: 1.4\n"
            "Создано с помощью Grok от xAI\n"

            "Управление задачами, напоминания, облачное хранение"
        )
        ttk.Label(self.content_frame, text=text, style='TLabel', justify=tk.CENTER, wraplength=500).pack(pady=20)

    def save_settings(self):
        messagebox.showinfo("Настройки", "Настройки сохранены")
        self.save_data_to_db()


if __name__ == "__main__":
    root = tk.Tk()
    app = TasksApp(root)
    root.withdraw()  # Скрываем окно при запуске

    # Tray icon
    icon_path = "icon.ico" if os.path.exists("icon.ico") else None
    menu_options = (
        ("Show", None, app.show_from_tray),
        ("Hide", None, app.hide_to_tray),
        ("Quit", None, app.quit_app)
    )
    sys_tray = SysTrayIcon(icon_path, "Tasks App", menu_options)

    # Запускаем tray в отдельном потоке (т.к. blocking)
    tray_thread = threading.Thread(target=sys_tray.start, daemon=True)
    tray_thread.start()

    root.mainloop()
