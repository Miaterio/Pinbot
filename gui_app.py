import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, ttk
import threading
import os
import sys
import io
import logging

# Попытка импортировать функции из image_scraper
try:
    # Добавляем родительскую директорию в sys.path, если gui_app.py находится в подпапке
    # current_dir = os.path.dirname(os.path.abspath(__file__))
    # parent_dir = os.path.dirname(current_dir)
    # if parent_dir not in sys.path:
    #     sys.path.append(parent_dir)
    
    # Предполагаем, что image_scraper.py находится в той же директории
    import image_scraper 
except ImportError as e:
    messagebox.showerror("Ошибка импорта", f"Не удалось импортировать image_scraper.py: {e}\nУбедитесь, что файл находится в той же директории.")
    sys.exit(1)

# Класс GuiHandler теперь использует импортированный logging
class GuiHandler(logging.Handler):
    """Обработчик логов для вывода в Tkinter Text виджет."""
    def __init__(self, text_widget):
        logging.Handler.__init__(self)
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.configure(state='disabled')
            self.text_widget.yview(tk.END) # Автопрокрутка
        # Выполняем обновление виджета в главном потоке Tkinter
        self.text_widget.after(0, append)

class ImageScraperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Scraper")
        self.root.geometry("600x450")

        self.url_file_path = tk.StringVar()
        self.save_dir_path = tk.StringVar()
        self.urls = []

        # --- Фреймы для организации --- 
        top_frame = tk.Frame(root, padx=10, pady=5)
        top_frame.pack(fill=tk.X)

        middle_frame = tk.Frame(root, padx=10, pady=5)
        middle_frame.pack(fill=tk.BOTH, expand=True)

        bottom_frame = tk.Frame(root, padx=10, pady=5)
        bottom_frame.pack(fill=tk.X)

        # --- Выбор файла с URL --- 
        tk.Label(top_frame, text="Файл с URL:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        tk.Entry(top_frame, textvariable=self.url_file_path, width=50).grid(row=0, column=1, padx=5, pady=2)
        tk.Button(top_frame, text="Обзор...", command=self.select_url_file).grid(row=0, column=2, padx=5, pady=2)

        # --- Выбор папки для сохранения --- 
        tk.Label(top_frame, text="Папка сохранения:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        tk.Entry(top_frame, textvariable=self.save_dir_path, width=50).grid(row=1, column=1, padx=5, pady=2)
        tk.Button(top_frame, text="Обзор...", command=self.select_save_dir).grid(row=1, column=2, padx=5, pady=2)

        # --- Логи --- 
        tk.Label(middle_frame, text="Логи:").pack(anchor=tk.W)
        self.log_area = scrolledtext.ScrolledText(middle_frame, state='disabled', height=15, wrap=tk.WORD)
        self.log_area.pack(fill=tk.BOTH, expand=True, pady=5)

        # --- Прогресс --- 
        self.progress_bar = ttk.Progressbar(bottom_frame, orient='horizontal', mode='indeterminate') # Изменено на indeterminate
        self.progress_bar.pack(fill=tk.X, pady=5)

        # --- Кнопки управления --- 
        button_frame = tk.Frame(bottom_frame)
        button_frame.pack(pady=5)
        self.start_button = tk.Button(button_frame, text="Начать", command=self.start_scraping_thread)
        self.start_button.pack(side=tk.LEFT, padx=10)
        self.copy_log_button = tk.Button(button_frame, text="Копировать логи", command=self.copy_logs)
        self.copy_log_button.pack(side=tk.LEFT, padx=10)

        # Настройка логирования для вывода в GUI
        self.setup_logging()

    def setup_logging(self):
        """Настраивает стандартный модуль logging для вывода в GUI."""
        log_text_handler = GuiHandler(self.log_area)
        log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        log_text_handler.setFormatter(log_format)
        
        # Получаем корневой логгер и добавляем наш обработчик
        # Важно: нужно настроить логгер ДО того, как image_scraper начнет логировать
        logger = logging.getLogger() 
        logger.setLevel(logging.INFO) # Устанавливаем уровень логирования
        logger.addHandler(log_text_handler)

        # Перехватываем stdout и stderr
        sys.stdout = LoggerRedirector(self.log_area, "stdout")
        sys.stderr = LoggerRedirector(self.log_area, "stderr")

    def select_url_file(self):
        filepath = filedialog.askopenfilename(title="Выберите файл с URL", filetypes=(("Text/CSV files", "*.txt *.csv"), ("All files", "*.*")))
        if filepath:
            self.url_file_path.set(filepath)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    self.urls = [line.strip() for line in f if line.strip()]
                if not self.urls:
                    messagebox.showwarning("Пустой файл", "Выбранный файл не содержит URL.")
                else:
                    print(f"Загружено {len(self.urls)} URL из файла.") # Используем print для лога
            except Exception as e:
                messagebox.showerror("Ошибка чтения файла", f"Не удалось прочитать файл: {e}")
                self.urls = []

    def select_save_dir(self):
        dirpath = filedialog.askdirectory(title="Выберите папку для сохранения изображений")
        if dirpath:
            self.save_dir_path.set(dirpath)
            print(f"Папка для сохранения: {dirpath}") # Используем print для лога

    def copy_logs(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.log_area.get('1.0', tk.END))
        messagebox.showinfo("Скопировано", "Логи скопированы в буфер обмена.")

    def start_scraping_thread(self):
        if not self.urls:
            messagebox.showerror("Ошибка", "Сначала выберите файл с URL.")
            return
        if not self.save_dir_path.get():
            messagebox.showerror("Ошибка", "Сначала выберите папку для сохранения.")
            return

        self.start_button.config(state=tk.DISABLED)
        # self.progress_bar['value'] = 0 # Не нужно для indeterminate
        # self.progress_bar['maximum'] = len(self.urls) # Не нужно для indeterminate
        self.progress_bar.start(10) # Запускаем анимацию indeterminate
        print("--- Начало процесса --- ")

        # Запускаем парсинг в отдельном потоке
        thread = threading.Thread(target=self.run_scraping_task, daemon=True)
        thread.start()

    def run_scraping_task(self):
        save_dir = self.save_dir_path.get()
        urls_to_process = self.urls[:] # Копируем список URL

        try:
            # Вызываем единую функцию из image_scraper, передавая список URL и папку
            print("Передача управления в image_scraper.run_scraping...")
            image_scraper.run_scraping(urls_to_process, save_dir)

            # Сообщение об успешном завершении (выполняется после run_scraping)
            # Используем after для вызова в главном потоке Tkinter
            print("Процесс в image_scraper завершен. Показ сообщения...")
            self.root.after(0, lambda: messagebox.showinfo("Завершено", "Загрузка и склеивание изображений завершены."))

        except Exception as e:
            # Логируем ошибку и показываем сообщение
            print(f"Критическая ошибка во время выполнения: {e}")
            # Используем after для вызова в главном потоке Tkinter
            self.root.after(0, lambda: messagebox.showerror("Ошибка выполнения", f"Произошла ошибка: {e}"))
        finally:
            # Останавливаем прогресс-бар и активируем кнопку в главном потоке
            print("Остановка прогресс-бара и активация кнопки...")
            self.root.after(0, self.stop_progress_and_enable_button)

    # def update_progress(self, value): # Больше не используется с indeterminate
    #     pass # self.progress_bar['value'] = value

    def stop_progress_and_enable_button(self):
        """Останавливает прогресс-бар и активирует кнопку 'Начать'."""
        self.progress_bar.stop()
        # self.progress_bar['value'] = 0 # Сброс значения, если нужно
        self.start_button.config(state=tk.NORMAL)

# Класс для перенаправления stdout/stderr в текстовый виджет
class LoggerRedirector(io.TextIOBase):
    def __init__(self, widget, stream_type):
        self.widget = widget
        self.stream_type = stream_type # 'stdout' или 'stderr'

    def write(self, msg):
        def append():
            self.widget.configure(state='normal')
            # Можно добавить префикс, чтобы различать stdout и stderr
            # prefix = f"[{self.stream_type.upper()}] " if self.stream_type == 'stderr' else ""
            # self.widget.insert(tk.END, prefix + msg)
            self.widget.insert(tk.END, msg)
            self.widget.configure(state='disabled')
            self.widget.yview(tk.END)
        self.widget.after(0, append)

    def flush(self):
        # Tkinter Text виджет не требует flush в этом контексте
        pass

if __name__ == "__main__":
    # Настройка базового логирования (на случай, если scraper не настроит)
    # Это важно сделать до создания GuiHandler
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    root = tk.Tk()
    app = ImageScraperApp(root)
    root.mainloop()