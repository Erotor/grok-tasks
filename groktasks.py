# tasks.py
# Основной файл для приложения Tasks - планировщик задач
# Версия: 1.1 (с Firebase клиентской интеграцией)
# Автор: Grok 4 (на основе плана пользователя)
# Дата создания: 31.01.2026 → обновлено 16.02.2026
# Описание: GUI с Tkinter + облачное хранение задач в Firebase Realtime Database
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import datetime
import threading
import time
import os
import winsound
import pygame
try:
    from plyer import notification
except ImportError:
    notification = None
import re
import pyrebase
import requests
# ────────────────────────────────────────────────
# Firebase конфигурация (твоя)
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
        pygame.mixer.init()  # Инициализируем здесь, чтобы избежать проблем позже
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.FONT_SMALL = ('Helvetica', 10)
        self.FONT_MEDIUM = ('Helvetica', 12)
        self.FONT_LARGE = ('Helvetica', 14)
        self.BG_COLOR = '#2E2E2E'
        self.TEXT_COLOR = '#FFFFFF'
        self.BUTTON_COLOR = '#6A1B9A'
        self.ACTIVE_BUTTON_COLOR = '#AB47BC'
        self.BORDER_COLOR = '#424242'
        self.GREEN_BUTTON = '#4CAF50'
        self.sidebar_frame = tk.Frame(
            self.root,
            bg=self.BG_COLOR,
            width=200,
            bd=2,
            relief='solid',
            highlightbackground=self.BORDER_COLOR,
            highlightthickness=2
        )
        self.sidebar_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.content_frame = tk.Frame(self.root, bg=self.BG_COLOR)
        self.content_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.current_section = tk.StringVar(value="Login")
        self.theme_var = tk.StringVar(value="Тёмная")
        self.text_size_var = tk.StringVar(value="Средний")
        self.lang_var = tk.StringVar(value="Русский")
        self.user = None
        self.user_token = None
        self.tasks = []
        self.next_task_id = 1
        self.custom_types = ["Основная", "Дополнительная", "Необязательная"]
        self.bin = []
        # Для обновлений (ДОБАВЛЕНО, чтобы избежать ошибки)
        self.version = "1.1"
        self.update_url = "https://raw.githubusercontent.com/your-repo/version.txt"  # ← Замените на реальный URL
        self.exe_url = "https://raw.githubusercontent.com/your-repo/download/{new_version}.exe"  # ← Замените на реальный URL
        self.configure_styles()
        self.show_login()
        self.reminder_thread = threading.Thread(target=self.check_reminders_loop, daemon=True)
        self.reminder_thread.start()
        print("→ Инициализация приложения завершена")

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
        print("→ Показ экрана логина")
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
        print("→ Метод login вызван")
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
            threading.Thread(target=self.check_for_update, daemon=True).start()
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

    def load_data_from_db(self):
        if not self.user:
            print("Нет пользователя")
            return
        uid = self.user['localId']
        token = self.user_token
        try:
            print(f"Загрузка для uid: {uid}")
            print("Токен:", token[:20] + "...")
            # custom_types
            types_data = db.child("users").child(uid).child("custom_types").get(token).val()
            print("custom_types из DB:", types_data)
            self.custom_types = types_data if types_data else ["Основная", "Дополнительная", "Необязательная"]
            # tasks
            tasks_data = db.child("users").child(uid).child("tasks").get(token).val()
            print("tasks_data из DB:", tasks_data)
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
                    print(f"Обрабатываем задачу {str_id}:", task)
                    try:
                        task["id"] = int(str_id) if str_id.isdigit() else task.get("id", max_id + 1)
                        if "created" in task and isinstance(task["created"], str):
                            date_str = task["created"].split('.')[0].replace('T', ' ')
                            task["created"] = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        if "last_trigger" in task and task.get("last_trigger") and isinstance(task["last_trigger"], str):
                            date_str = task["last_trigger"].split('.')[0].replace('T', ' ')
                            task["last_trigger"] = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        self.tasks.append(task)
                        max_id = max(max_id, task["id"])
                    except Exception as inner_e:
                        print(f"Ошибка парсинга задачи {str_id}: {inner_e}")
            # bin
            bin_data = db.child("users").child(uid).child("bin").get(token).val()
            print("bin_data из DB:", bin_data)
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
                        if "last_trigger" in task and task.get("last_trigger") and isinstance(task["last_trigger"], str):
                            date_str = task["last_trigger"].split('.')[0].replace('T', ' ')
                            task["last_trigger"] = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        self.bin.append(task)
                    except Exception as inner_e:
                        print(f"Ошибка парсинга bin {str_id}: {inner_e}")
            # next_task_id
            next_id = db.child("users").child(uid).child("next_task_id").get(token).val()
            self.next_task_id = next_id if next_id is not None else max_id + 1
            # settings — загружаем и применяем
            settings_data = db.child("users").child(uid).child("settings").get(token).val()
            print("settings_data из DB:", settings_data)
            if settings_data:
                if "theme" in settings_data:
                    self.theme_var.set(settings_data["theme"])
                if "text_size" in settings_data:
                    self.text_size_var.set(settings_data["text_size"])
                if "language" in settings_data:
                    self.lang_var.set(settings_data["language"])
        except Exception as e:
            messagebox.showerror("Ошибка загрузки", str(e))
            print("Ошибка загрузки:", str(e))

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
            # Сохранение настроек
            settings = {
                "theme": self.theme_var.get(),
                "text_size": self.text_size_var.get(),
                "language": self.lang_var.get()
            }
            db.child("users").child(uid).child("settings").set(settings, token)
            print("Сохранены настройки:", settings)
        except Exception as e:
            messagebox.showerror("Ошибка сохранения", str(e))
            print("Ошибка сохранения:", str(e))

    def create_sidebar(self):
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

    def clear_content(self):
        """Очистка основного контента перед переключением раздела"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def show_welcome(self):
        """Отображение первого экрана Welcome"""
        print("→ show_welcome() вызван") # Для отладки
   
        self.clear_content()
        self.current_section.set("Welcome")
   
        print("→ clear_content выполнен, current_section =", self.current_section.get()) # Отладка
   
        welcome_label = ttk.Label(
            self.content_frame,
            text="Добро пожаловать в Tasks!",
            style='TLabel',
            font=self.FONT_LARGE,
            wraplength=500
        )
        welcome_label.pack(pady=40)
   
        sections_btn = ttk.Button(
            self.content_frame,
            text="Разделы",
            style='Sidebar.TButton',
            command=self.show_tasks
        )
        sections_btn.pack(pady=20)
   
        print("→ welcome-экран отрисован") # Отладка
        self.root.update() # Принудительно обнови окно

    def show_tasks(self):
        self.clear_content()
        self.current_section.set("Задачи")
        # Верхняя панель с кнопкой добавления
        top_frame = tk.Frame(self.content_frame, bg=self.BG_COLOR)
        top_frame.pack(fill=tk.X, padx=20, pady=(20, 10))
        add_btn = ttk.Button(
            top_frame,
            text="+ Добавить задачу",
            style='Add.TButton',
            command=self.open_add_task_form
        )
        add_btn.pack(side=tk.LEFT)
        # Таблица задач
        columns = ("№", "Название", "Описание", "Тип", "Дата", "Статус")
        self.tasks_tree = ttk.Treeview(
            self.content_frame,
            columns=columns,
            show='headings',
            style='Treeview',
            selectmode='extended'
        )
        headings = ["№", "Название", "Описание", "Тип", "Дата создания", "Статус"]
        widths = [50, 180, 220, 120, 160, 100]
        for col, text, w in zip(columns, headings, widths):
            self.tasks_tree.heading(col, text=text)
            self.tasks_tree.column(col, width=w, anchor='w' if col != "№" else 'center')
        self.tasks_tree.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        self.tasks_tree.bind("<Double-1>", self.on_double_click_task)
        # Нижняя панель с действиями
        bottom_frame = tk.Frame(self.content_frame, bg=self.BG_COLOR)
        bottom_frame.pack(fill=tk.X, padx=20, pady=10)
        delete_btn = ttk.Button(bottom_frame, text="Удалить выбранное", command=self.delete_selected_tasks)
        delete_btn.pack(side=tk.LEFT, padx=(0, 10))
        toggle_btn = ttk.Button(
            bottom_frame,
            text="Переключить статус (выполнено ↔ не выполнено)",
            command=self.toggle_selected_status
        )
        toggle_btn.pack(side=tk.LEFT, padx=10)
        self.refresh_tasks_table()

    def refresh_tasks_table(self):
        if not hasattr(self, 'tasks_tree') or not self.tasks_tree or not self.tasks_tree.winfo_exists():
            return
        for item in self.tasks_tree.get_children():
            self.tasks_tree.delete(item)
        for i, task in enumerate(self.tasks, 1):
            status = "✅" if task.get("done", False) else "❌"
            values = (
                i,
                task["name"][:45] + "..." if len(task["name"]) > 45 else task["name"],
                task["desc"][:60] + "..." if len(task["desc"]) > 60 else task["desc"],
                task["type"],
                task["created"].strftime("%H:%M %d.%m.%Y"),
                status
            )
            self.tasks_tree.insert("", tk.END, iid=str(task["id"]), values=values)

    def open_add_task_form(self, task_to_edit=None):
        form = tk.Toplevel(self.root)
        form.title("Добавить задачу" if not task_to_edit else "Редактировать задачу")
        form.geometry("480x380")
        form.configure(bg=self.BG_COLOR)
        form.resizable(True, True)
        padx = 20
        pady = 8
        tk.Label(form, text="Название:", bg=self.BG_COLOR, fg=self.TEXT_COLOR, font=self.FONT_MEDIUM).pack(anchor='w', padx=padx, pady=(20, pady))
        name_entry = ttk.Entry(form, font=self.FONT_MEDIUM, width=50)
        name_entry.pack(padx=padx, fill=tk.X)
        tk.Label(form, text="Описание:", bg=self.BG_COLOR, fg=self.TEXT_COLOR, font=self.FONT_MEDIUM).pack(anchor='w', padx=padx, pady=(12, pady))
        desc_text = tk.Text(form, height=6, font=self.FONT_SMALL, bg='#3C3C3C', fg=self.TEXT_COLOR, insertbackground=self.TEXT_COLOR)
        desc_text.pack(padx=padx, fill=tk.BOTH, expand=False)
        tk.Label(form, text="Тип задачи:", bg=self.BG_COLOR, fg=self.TEXT_COLOR, font=self.FONT_MEDIUM).pack(anchor='w', padx=padx, pady=(12, pady))
        type_frame = tk.Frame(form, bg=self.BG_COLOR)
        type_frame.pack(fill=tk.X, padx=padx)
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
                self.save_data_to_db() # Сохраняем новые типы
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
                name_entry.focus()
                return
            created = datetime.datetime.now()
            if task_to_edit:
                task_to_edit["name"] = name
                task_to_edit["desc"] = desc
                task_to_edit["type"] = typ
            else:
                task = {
                    "id": self.next_task_id,
                    "name": name,
                    "desc": desc,
                    "type": typ,
                    "created": created,
                    "done": False
                }
                self.tasks.append(task)
                self.next_task_id += 1
            self.refresh_tasks_table()
            form.destroy()
            self.save_data_to_db() # Сохранение после добавления/редактирования
        ttk.Button(btn_frame, text="Сохранить", style='Add.TButton', command=save_and_close).pack(side=tk.LEFT, padx=15)
        ttk.Button(btn_frame, text="Отмена", command=form.destroy).pack(side=tk.LEFT)
        name_entry.focus()

    def on_double_click_task(self, event):
        item = self.tasks_tree.identify_row(event.y)
        if not item:
            return
        task_id = int(item)
        task = next((t for t in self.tasks if t["id"] == task_id), None)
        if task:
            self.open_add_task_form(task_to_edit=task)

    def delete_selected_tasks(self):
        selected = self.tasks_tree.selection()
        if not selected:
            return
        ids_to_remove = [int(iid) for iid in selected]
        count = len(ids_to_remove)
        if count == 0:
            return
        if messagebox.askyesno("Подтверждение удаления", f"Переместить {count} задач(у) в корзину?"):
            to_bin = [task for task in self.tasks if task["id"] in ids_to_remove]
            self.tasks = [task for task in self.tasks if task["id"] not in ids_to_remove]
            self.bin.extend(to_bin)
            self.refresh_tasks_table()
            messagebox.showinfo("Готово", f"{count} задач перемещено в корзину.")
            self.save_data_to_db() # Сохранение после удаления/перемещения

    def toggle_selected_status(self):
        if self.current_section.get() != "Задачи":
            return
        selected = self.tasks_tree.selection()
        if not selected:
            messagebox.showwarning("Нет выбора", "Выберите хотя бы одну задачу.")
            return
        ids_selected = [int(iid) for iid in selected]
        done_count = sum(1 for t in self.tasks if t["id"] in ids_selected and t.get("done", False))
        total_selected = len(ids_selected)
        not_done_count = total_selected - done_count
        new_status = not_done_count >= done_count
        if not messagebox.askyesno(
            "Подтверждение",
            f"Переключить статус для {total_selected} задач?\n"
            f"Сейчас: {done_count} выполнено, {not_done_count} не выполнено\n"
            f"Будет: {'выполнено' if new_status else 'не выполнено'}"
        ):
            return
        for task in self.tasks:
            if task["id"] in ids_selected:
                task["done"] = new_status
        self.refresh_tasks_table()
        messagebox.showinfo("Готово", f"Статус изменён для {total_selected} задач.")
        self.save_data_to_db() # Сохранение после изменения статуса

    def show_bin(self):
        self.clear_content()
        self.current_section.set("Корзина")
        title_label = ttk.Label(self.content_frame, text="Корзина", style='TLabel', font=self.FONT_LARGE)
        title_label.pack(pady=20)
        columns = ("№", "Название", "Описание", "Тип", "Дата создания", "Статус")
        self.bin_tree = ttk.Treeview(
            self.content_frame,
            columns=columns,
            show='headings',
            style='Treeview',
            selectmode='extended'
        )
        headings = ["№", "Название", "Описание", "Тип", "Дата создания", "Статус"]
        widths = [50, 180, 220, 120, 160, 100]
        for col, text, w in zip(columns, headings, widths):
            self.bin_tree.heading(col, text=text)
            self.bin_tree.column(col, width=w, anchor='w' if col != "№" else 'center')
        self.bin_tree.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        bottom_frame = tk.Frame(self.content_frame, bg=self.BG_COLOR)
        bottom_frame.pack(fill=tk.X, padx=20, pady=10)
        restore_btn = ttk.Button(bottom_frame, text="Восстановить", style='Add.TButton', command=self.restore_from_bin)
        restore_btn.pack(side=tk.LEFT, padx=(0, 10))
        delete_perm_btn = ttk.Button(bottom_frame, text="Удалить навсегда", command=self.delete_permanently_from_bin)
        delete_perm_btn.pack(side=tk.LEFT, padx=5)
        self.refresh_bin_table()

    def refresh_bin_table(self):
        if not hasattr(self, 'bin_tree') or not self.bin_tree or not self.bin_tree.winfo_exists():
            return
        for item in self.bin_tree.get_children():
            self.bin_tree.delete(item)
        for i, task in enumerate(self.bin, 1):
            status = "✅" if task.get("done", False) else "❌"
            values = (
                i,
                task["name"][:45] + "..." if len(task["name"]) > 45 else task["name"],
                task["desc"][:60] + "..." if len(task["desc"]) > 60 else task["desc"],
                task["type"],
                task["created"].strftime("%H:%M %d.%m.%Y"),
                status
            )
            self.bin_tree.insert("", tk.END, iid=str(task["id"]), values=values)

    def restore_from_bin(self):
        selected = self.bin_tree.selection()
        if not selected:
            return
        ids_to_restore = [int(iid) for iid in selected]
        if messagebox.askyesno("Восстановление", f"Восстановить {len(ids_to_restore)} задач?"):
            to_restore = []
            remaining_bin = []
            for task in self.bin:
                if task["id"] in ids_to_restore:
                    to_restore.append(task)
                else:
                    remaining_bin.append(task)
            self.bin = remaining_bin
            self.tasks.extend(to_restore)
            self.refresh_bin_table()
            if self.current_section.get() == "Задачи":
                self.refresh_tasks_table()
            messagebox.showinfo("Готово", f"{len(to_restore)} задач восстановлено.")
            self.save_data_to_db() # Сохранение после восстановления

    def delete_permanently_from_bin(self):
        selected = self.bin_tree.selection()
        if not selected:
            return
        ids_to_delete = [int(iid) for iid in selected]
        if messagebox.askyesno("Удаление навсегда", f"Удалить {len(ids_to_delete)} задач БЕЗ ВОЗМОЖНОСТИ восстановления?"):
            self.bin = [t for t in self.bin if t["id"] not in ids_to_delete]
            self.refresh_bin_table()
            messagebox.showinfo("Готово", "Задачи удалены навсегда.")
            self.save_data_to_db() # Сохранение после удаления

    def show_reminders(self):
        self.clear_content()
        self.current_section.set("Напоминания")
        title_label = ttk.Label(self.content_frame, text="Напоминания", style='TLabel', font=self.FONT_LARGE)
        title_label.pack(pady=20)
        top_frame = tk.Frame(self.content_frame, bg=self.BG_COLOR)
        top_frame.pack(fill=tk.X, padx=20, pady=(10, 10))
        add_reminder_btn = ttk.Button(
            top_frame,
            text="Поставить / Изменить напоминание",
            style='Add.TButton',
            command=self.open_reminder_form
        )
        add_reminder_btn.pack(side=tk.LEFT)
        columns = ("№", "Название", "Тип", "Дата создания", "Напоминание", "Статус")
        self.reminders_tree = ttk.Treeview(
            self.content_frame,
            columns=columns,
            show='headings',
            style='Treeview',
            selectmode='extended'
        )
        headings = ["№", "Название", "Тип", "Дата создания", "Напоминание", "Статус"]
        widths = [50, 220, 120, 160, 180, 100]
        for col, text, w in zip(columns, headings, widths):
            self.reminders_tree.heading(col, text=text)
            self.reminders_tree.column(col, width=w, anchor='center' if col == "№" else 'w')
        self.reminders_tree.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        self.reminders_tree.bind("<Double-1>", self.on_double_click_reminder)
        bottom_frame = tk.Frame(self.content_frame, bg=self.BG_COLOR)
        bottom_frame.pack(fill=tk.X, padx=20, pady=10)
        delete_reminder_btn = ttk.Button(
            bottom_frame,
            text="Удалить напоминание у выбранных",
            command=self.delete_selected_reminders
        )
        delete_reminder_btn.pack(side=tk.LEFT, padx=10)
        self.refresh_reminders_table()

    def refresh_reminders_table(self):
        if not hasattr(self, 'reminders_tree') or not self.reminders_tree or not self.reminders_tree.winfo_exists():
            return
        for item in self.reminders_tree.get_children():
            self.reminders_tree.delete(item)
        for i, task in enumerate(self.tasks, 1):
            reminder_str = "—"
            if task.get("reminder_date") and task.get("reminder_time"):
                reminder_str = f"{task['reminder_date']} {task['reminder_time']}"
            status = "✅" if task.get("done", False) else "❌"
            values = (
                i,
                task["name"][:55] + "…" if len(task["name"]) > 55 else task["name"],
                task["type"],
                task["created"].strftime("%H:%M %d.%m.%Y"),
                reminder_str,
                status
            )
            self.reminders_tree.insert("", tk.END, iid=str(task["id"]), values=values)

    def open_reminder_form(self, task_to_edit=None):
        if task_to_edit is None:
            selected = self.reminders_tree.selection()
            if not selected:
                messagebox.showwarning("Выбор", "Выберите задачу для установки напоминания.")
                return
            task_id = int(selected[0])
            task_to_edit = next((t for t in self.tasks if t["id"] == task_id), None)
            if not task_to_edit:
                return
        form = tk.Toplevel(self.root)
        form.title("Напоминание")
        form.geometry("500x520")
        form.configure(bg=self.BG_COLOR)
        form.transient(self.root)
        form.grab_set()
        form.resizable(True, True)
        padx = 30
        # Заголовок задачи
        ttk.Label(
            form,
            text=f"Задача: {task_to_edit['name']}",
            style='TLabel',
            font=self.FONT_MEDIUM
        ).pack(anchor='w', padx=padx, pady=(25, 10))
        # ───────────── Дата ─────────────
        tk.Label(
            form,
            text="Дата (ддммгггг или дд.мм.гггг):",
            bg=self.BG_COLOR, fg=self.TEXT_COLOR,
            font=self.FONT_MEDIUM
        ).pack(anchor='w', padx=padx, pady=(5, 2))
        date_entry = ttk.Entry(form, font=self.FONT_MEDIUM)
        date_entry.pack(padx=padx, fill=tk.X, ipady=4)
        today_str = datetime.date.today().strftime("%d.%m.%Y")
        date_entry.insert(0, task_to_edit.get("reminder_date", today_str))
        # ───────────── Время (с секундами опционально) ─────────────
        tk.Label(
            form,
            text="Время (ччмм или ччммсс):",
            bg=self.BG_COLOR, fg=self.TEXT_COLOR,
            font=self.FONT_MEDIUM
        ).pack(anchor='w', padx=padx, pady=(20, 2))
        time_entry = ttk.Entry(form, font=self.FONT_MEDIUM, width=12)
        time_entry.pack(padx=padx, fill=tk.X, ipady=4)
        placeholder = "ччммсс"
        time_entry.insert(0, placeholder)
        time_entry.config(foreground='grey')
        def on_time_focus_in(e):
            if time_entry.get() == placeholder:
                time_entry.delete(0, tk.END)
                time_entry.config(foreground=self.TEXT_COLOR)
        def on_time_focus_out(e):
            if not time_entry.get().strip():
                time_entry.insert(0, placeholder)
                time_entry.config(foreground='grey')
        time_entry.bind("<FocusIn>", on_time_focus_in)
        time_entry.bind("<FocusOut>", on_time_focus_out)
        saved_time = task_to_edit.get("reminder_time", "")
        if saved_time:
            time_entry.delete(0, tk.END)
            time_entry.insert(0, saved_time.replace(":", ""))
            time_entry.config(foreground=self.TEXT_COLOR)
        # ───────────── Звук ─────────────
        tk.Label(
            form,
            text="Звук напоминания:",
            bg=self.BG_COLOR, fg=self.TEXT_COLOR,
            font=self.FONT_MEDIUM
        ).pack(anchor='w', padx=padx, pady=(25, 5))
        sound_var = tk.StringVar(value=task_to_edit.get("reminder_sound", "По умолчанию"))
        sound_combo = ttk.Combobox(
            form,
            textvariable=sound_var,
            values=["По умолчанию", "Системный", "Пользовательский"],
            font=self.FONT_MEDIUM,
            state="readonly",
            width=25
        )
        sound_combo.pack(padx=padx, fill=tk.X, ipady=3)
        # Пользовательский звук
        custom_frame = tk.Frame(form, bg=self.BG_COLOR)
        custom_path_entry = ttk.Entry(custom_frame, font=self.FONT_SMALL)
        custom_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        choose_btn = ttk.Button(
            custom_frame,
            text="Выбрать файл",
            command=lambda: self.choose_sound_file(custom_path_entry)
        )
        choose_btn.pack(side=tk.RIGHT)
        def on_sound_change(*args):
            if sound_var.get() == "Пользовательский":
                custom_frame.pack(fill=tk.X, padx=padx, pady=(10, 0))
                custom_path_entry.delete(0, tk.END)
                custom_path_entry.insert(0, task_to_edit.get("custom_sound_path", ""))
            else:
                custom_frame.pack_forget()
        sound_var.trace("w", on_sound_change)
        on_sound_change() # инициализация
        # ───────────── Кнопки ─────────────
        btn_frame = tk.Frame(form, bg=self.BG_COLOR)
        btn_frame.pack(pady=35)
        def normalize_date(s: str) -> str:
            s = ''.join(c for c in s if c.isdigit())
            if len(s) == 6:
                s = s[:4] + "20" + s[4:] # 010225 → 01022025
            if len(s) == 8:
                return f"{s[:2]}.{s[2:4]}.{s[4:]}"
            return s # оставляем как есть, если не 6/8 цифр
        def normalize_time(s: str) -> str:
            s = ''.join(c for c in s if c.isdigit())
            if len(s) == 3:
                s = "0" + s + "00"
            elif len(s) == 4:
                s += "00"
            elif len(s) == 5:
                s = s[:4] + "0" + s[4]
            if len(s) == 6:
                return f"{s[:2]}:{s[2:4]}:{s[4:]}"
            return ""
        def save_reminder():
            date_raw = date_entry.get().strip()
            time_raw = time_entry.get().strip()
            if not date_raw or not time_raw or time_raw in (placeholder, "ччммсс", ""):
                messagebox.showwarning("Ошибка", "Укажите дату и время напоминания.")
                return
            # Нормализация
            date_norm = normalize_date(date_raw)
            time_norm = normalize_time(time_raw)
            if not time_norm:
                messagebox.showerror("Неверный формат", "Время должно быть 4 или 6 цифр (ччмм или ччммсс)")
                return
            # Проверка формата после нормализации
            if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", date_norm):
                messagebox.showerror("Неверный формат", "Дата должна быть в формате дд.мм.гггг")
                return
            if not re.match(r"^\d{2}:\d{2}:\d{2}$", time_norm):
                messagebox.showerror("Неверный формат", "Время должно быть в формате чч:мм:сс")
                return
            # Проверка валидности даты и времени
            try:
                dt = datetime.datetime.strptime(f"{date_norm} {time_norm}", "%d.%m.%Y %H:%M:%S")
                if dt < datetime.datetime.now():
                    if not messagebox.askyesno("Прошлое время", "Напоминание установлено в прошлом.\nСохранить всё равно?"):
                        return
            except ValueError:
                messagebox.showerror("Ошибка", "Некорректная дата или время (например, 31.04 или 25:00)")
                return
            # Сохраняем нормализованные значения
            task_to_edit["reminder_date"] = date_norm
            task_to_edit["reminder_time"] = time_norm
            task_to_edit["reminder_sound"] = sound_var.get()
            if sound_var.get() == "Пользовательский":
                path = custom_path_entry.get().strip()
                if not path or not os.path.exists(path):
                    messagebox.showwarning("Звук", "Укажите существующий звуковой файл.")
                    return
                task_to_edit["custom_sound_path"] = path
            else:
                task_to_edit.pop("custom_sound_path", None)
            task_to_edit.pop("last_trigger", None) # сбрасываем при установке
            self.refresh_reminders_table()
            form.destroy()
            messagebox.showinfo("Готово", "Напоминание сохранено.")
            self.save_data_to_db() # Сохранение после установки напоминания
   
    def choose_sound_file(self, entry):
        file = filedialog.askopenfilename(
            title="Выберите звуковой файл",
            filetypes=[("Аудио файлы", "*.wav *.mp3 *.ogg *.flac"), ("Все файлы", "*.*")]
        )
        if file:
            entry.delete(0, tk.END)
            entry.insert(0, file)

    def delete_selected_reminders(self):
        selected = self.reminders_tree.selection()
        if not selected:
            messagebox.showwarning("Выбор", "Выберите хотя бы одну задачу.")
            return
        ids = [int(iid) for iid in selected]
        count = len(ids)
        if not messagebox.askyesno("Подтверждение", f"Удалить напоминания у {count} задач?"):
            return
        for task in self.tasks:
            if task["id"] in ids:
                task.pop("reminder_date", None)
                task.pop("reminder_time", None)
                task.pop("reminder_sound", None)
                task.pop("custom_sound_path", None)
                task.pop("last_trigger", None)
        self.refresh_reminders_table()
        messagebox.showinfo("Готово", f"Напоминания удалены у {count} задач.")
        self.save_data_to_db() # Сохранение после удаления напоминаний

    def on_double_click_reminder(self, event):
        item = self.reminders_tree.identify_row(event.y)
        if not item:
            return
        task_id = int(item)
        task = next((t for t in self.tasks if t["id"] == task_id), None)
        if task:
            self.open_reminder_form(task_to_edit=task)

    def _trigger_reminder(self, task):
        msg = f"НАПОМИНАНИЕ\n\n{task['name']}\n{task.get('desc', '')[:120]}..."
        self.root.after(0, lambda m=msg: messagebox.showinfo("Напоминание", m))
        # Системное уведомление (если plyer есть)
        if notification is not None:
            try:
                notification.notify(
                    title="Напоминание Tasks",
                    message=msg,
                    app_name="Tasks App",
                    timeout=12
                )
            except Exception as e:
                print("Ошибка системного уведомления:", e)
        # Звук
        sound_type = task.get("reminder_sound", "По умолчанию")
        try:
            if sound_type == "По умолчанию":
                winsound.MessageBeep()
            elif sound_type == "Системный":
                winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS)
            elif sound_type == "Пользовательский":
                path = task.get("custom_sound_path")
                if path and os.path.exists(path):
                    pygame.mixer.music.load(path)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.08)
        except Exception as e:
            print("Ошибка воспроизведения звука:", e)
        self.save_data_to_db() # Сохранение после срабатывания

    def check_reminders_loop(self):
        while True:
            try:
                now = datetime.datetime.now()
                for task in self.tasks:
                    r_date = task.get("reminder_date")
                    r_time = task.get("reminder_time")
                    if r_date and r_time and not task.get("done", False):
                        r_dt_str = f"{r_date} {r_time}"
                        r_dt = datetime.datetime.strptime(r_dt_str, "%d.%m.%Y %H:%M:%S")
                        if now >= r_dt:
                            last_trigger = task.get("last_trigger")
                            if last_trigger is None or (now - last_trigger).total_seconds() > 10:
                                self._trigger_reminder(task)
                                task["last_trigger"] = now
            except Exception as e:
                print("Ошибка в check_reminders_loop:", e)
            time.sleep(1) # проверяем каждую секунду для точности

    def check_for_update(self):
        try:
            response = requests.get(self.update_url)
            latest_version = response.text.strip()
            if latest_version != self.version:
                if messagebox.askyesno("Обновление", f"Доступна версия {latest_version}. Обновить?"):
                    self.download_update(latest_version)
        except Exception as e:
            print("Ошибка проверки обновлений:", e)

    def download_update(self, version):
        try:
            url = self.exe_url.replace("{new_version}", version)
            response = requests.get(url)
            new_exe = "new_groktasks.exe"
            with open(new_exe, "wb") as f:
                f.write(response.content)
            # Замена текущего exe (только для Windows)
            import subprocess
            subprocess.call(['cmd', '/c', 'ping', 'localhost', '-n', '1', '>', 'nul']) # Задержка
            subprocess.call(['cmd', '/c', 'move', new_exe, 'groktasks.exe'])
            subprocess.call(['groktasks.exe']) # Перезапуск
            self.root.quit()
        except Exception as e:
            messagebox.showerror("Ошибка обновления", str(e))

    def show_settings(self):
        self.clear_content()
        self.current_section.set("Настройки")
        title_label = ttk.Label(self.content_frame, text="Настройки", style='TLabel', font=self.FONT_LARGE)
        title_label.pack(pady=30)
        content_frame = tk.Frame(self.content_frame, bg=self.BG_COLOR)
        content_frame.pack(padx=40, pady=20, fill=tk.BOTH, expand=True)
        # Раздел "Размер текста"
        text_size_frame = tk.Frame(content_frame, bg=self.BG_COLOR)
        text_size_frame.pack(fill=tk.X, pady=15)
        ttk.Label(text_size_frame, text="Размер текста:", style='TLabel').pack(side=tk.LEFT, padx=10)
        text_size_combo = ttk.Combobox(
            text_size_frame,
            textvariable=self.text_size_var,
            values=["Маленький", "Средний", "Большой"],
            state="readonly",
            font=self.FONT_MEDIUM,
            width=15
        )
        text_size_combo.pack(side=tk.LEFT, padx=10)
        text_size_combo.bind("<<ComboboxSelected>>", self.apply_text_size)
        # Раздел "Тема"
        theme_frame = tk.Frame(content_frame, bg=self.BG_COLOR)
        theme_frame.pack(fill=tk.X, pady=15)
        ttk.Label(theme_frame, text="Тема:", style='TLabel').pack(side=tk.LEFT, padx=10)
        theme_combo = ttk.Combobox(
            theme_frame,
            textvariable=self.theme_var,
            values=["Тёмная", "Светлая"],
            state="readonly",
            font=self.FONT_MEDIUM,
            width=15
        )
        theme_combo.pack(side=tk.LEFT, padx=10)
        theme_combo.bind("<<ComboboxSelected>>", self.apply_theme)
        # Раздел "Звук по умолчанию"
        sound_frame = tk.Frame(content_frame, bg=self.BG_COLOR)
        sound_frame.pack(fill=tk.X, pady=15)
        ttk.Label(sound_frame, text="Звук по умолчанию:", style='TLabel').pack(side=tk.LEFT, padx=10)
        self.default_sound_var = tk.StringVar(value="По умолчанию")
        sound_combo = ttk.Combobox(
            sound_frame,
            textvariable=self.default_sound_var,
            values=["По умолчанию", "Системный", "Пользовательский"],
            state="readonly",
            font=self.FONT_MEDIUM,
            width=20
        )
        sound_combo.pack(side=tk.LEFT, padx=10)
        self.custom_default_sound_frame = tk.Frame(sound_frame, bg=self.BG_COLOR)
        self.custom_default_path = ttk.Entry(self.custom_default_sound_frame, font=self.FONT_SMALL, width=40)
        self.custom_default_path.pack(side=tk.LEFT, padx=5)
        ttk.Button(self.custom_default_sound_frame, text="Выбрать", command=self.choose_default_sound).pack(side=tk.LEFT)
        def toggle_custom_sound(*args):
            if self.default_sound_var.get() == "Пользовательский":
                self.custom_default_sound_frame.pack(fill=tk.X, pady=5)
            else:
                self.custom_default_sound_frame.pack_forget()
        self.default_sound_var.trace("w", toggle_custom_sound)
        toggle_custom_sound()
        # Раздел "Язык"
        lang_frame = tk.Frame(content_frame, bg=self.BG_COLOR)
        lang_frame.pack(fill=tk.X, pady=15)
        ttk.Label(lang_frame, text="Язык:", style='TLabel').pack(side=tk.LEFT, padx=10)
        lang_combo = ttk.Combobox(
            lang_frame,
            textvariable=self.lang_var,
            values=["Русский", "Қазақша", "English"],
            state="readonly",
            font=self.FONT_MEDIUM,
            width=15
        )
        lang_combo.pack(side=tk.LEFT, padx=10)
        lang_combo.bind("<<ComboboxSelected>>", self.apply_language)
        # Кнопка сохранения
        save_btn = ttk.Button(content_frame, text="Сохранить настройки", style='Add.TButton', command=self.save_settings)
        save_btn.pack(pady=40)

    def choose_default_sound(self):
        file = filedialog.askopenfilename(
            title="Выберите звуковой файл по умолчанию",
            filetypes=[("Аудио файлы", "*.wav *.mp3 *.ogg *.flac"), ("Все файлы", "*.*")]
        )
        if file:
            self.custom_default_path.delete(0, tk.END)
            self.custom_default_path.insert(0, file)

    def apply_text_size(self, event=None):
        size = self.text_size_var.get()
        if size == "Маленький":
            self.FONT_SMALL = ('Helvetica', 9)
            self.FONT_MEDIUM = ('Helvetica', 10)
            self.FONT_LARGE = ('Helvetica', 11)
        elif size == "Большой":
            self.FONT_SMALL = ('Helvetica', 12)
            self.FONT_MEDIUM = ('Helvetica', 14)
            self.FONT_LARGE = ('Helvetica', 16)
        else: # Средний
            self.FONT_SMALL = ('Helvetica', 10)
            self.FONT_MEDIUM = ('Helvetica', 12)
            self.FONT_LARGE = ('Helvetica', 14)
        self.configure_styles()
        # Перерисовываем текущий раздел, чтобы изменения применились
        current = self.current_section.get()
        if current == "Настройки":
            self.show_settings()
        elif current == "Задачи":
            self.show_tasks()
        elif current == "Корзина":
            self.show_bin()
        elif current == "Напоминания":
            self.show_reminders()
        elif current == "О программе":
            self.show_about()
        self.save_data_to_db() # Сохранение после изменения

    def apply_theme(self, event=None):
        print("→ apply_theme вызван") # для отладки, потом можно убрать
        theme = self.theme_var.get()
        if theme == "Светлая":
            self.BG_COLOR = '#F5F5F5'
            self.TEXT_COLOR = '#000000'
            self.BUTTON_COLOR = '#FFD700'
            self.ACTIVE_BUTTON_COLOR = '#FFA500'
            self.BORDER_COLOR = '#D3D3D3'
            self.GREEN_BUTTON = '#32CD32'
        else: # Тёмная
            self.BG_COLOR = '#2E2E2E'
            self.TEXT_COLOR = '#FFFFFF'
            self.BUTTON_COLOR = '#6A1B9A'
            self.ACTIVE_BUTTON_COLOR = '#AB47BC'
            self.BORDER_COLOR = '#424242'
            self.GREEN_BUTTON = '#4CAF50'
       
        self.root.configure(bg=self.BG_COLOR)
        self.sidebar_frame.configure(bg=self.BG_COLOR, highlightbackground=self.BORDER_COLOR)
        self.content_frame.configure(bg=self.BG_COLOR)
        self.configure_styles()
       
        # Перерисовываем текущий экран
        current = self.current_section.get()
        if current == "Настройки":
            self.show_settings()
        elif current == "Задачи":
            self.show_tasks()
        elif current == "Корзина":
            self.show_bin()
        elif current == "Напоминания":
            self.show_reminders()
        elif current == "О программе":
            self.show_about()
       
        # self.save_data_to_db() # можно закомментировать, если сохраняет слишком часто

    def apply_language(self, event=None):
        lang = self.lang_var.get()
        messagebox.showinfo("Язык", f"Язык изменён на {lang}. Для полного применения перезапустите приложение.")
        self.save_data_to_db() # Сохранение после изменения

    def save_settings(self):
        messagebox.showinfo("Настройки", "Настройки сохранены.\nИзменения размера текста и темы применяются сразу.")
        self.save_data_to_db() # Сохранение после кнопки

    def show_about(self):
        """Отображение раздела 'О программе'"""
        self.clear_content()
        self.current_section.set("О программе")
      
        title_label = ttk.Label(self.content_frame, text="О программе", style='TLabel', font=self.FONT_LARGE)
        title_label.pack(pady=20)
      
        desc_text = (
            "Tasks - это удобный планировщик задач для повседневного использования.\n"
            "Версия: 1.1\n"
            "Подпись: @Temirlan\n and Создано с помощью Grok от xAI"
            "Приложение позволяет управлять задачами, устанавливать напоминания и многое другое."
        )
        desc_label = ttk.Label(self.content_frame, text=desc_text, style='TLabel', justify=tk.CENTER, wraplength=500)
        desc_label.pack(pady=20)

if __name__ == "__main__":
    root = tk.Tk()
    app = TasksApp(root)
    root.mainloop()