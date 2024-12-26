import tkinter as tk
from tkinter import ttk
import serial
import queue
# Свои реализации
import serial_port
import file_logger
import data_processing

class SerialMonitorGUI:
    def __init__(self, gui, logger_queue, data_proc_queue):
        # Кнопки
        self.skip_button = None
        self.skip_requests = True
        self.clear_button = None
        self.open_button = None
        # Прочая
        self.custom_pattern_entry = None
        self.custom_pattern_frame = None
        self.counter_frame = None
        self.message_area = None
        self.tree = None
        self.encoding = None

        # Присваиваем себе экземпляр очереди
        self.log_queue = logger_queue
        self.data_queue = data_proc_queue
        # Передаем тот же экземпляр GUI в другие компоненты
        self.serial_port = serial_port.SerialPort(data_proc_queue=data_queue, main_gui=self)
        self.data_proc = data_processing.DataProcessing(data_proc_queue=data_queue, logger_queue=log_queue, main_gui=self)
        self.file_logger = file_logger.FileLogger(log_queue=log_queue, main_gui=self)

        # Переменные для настроек COM-порта
        self.port = tk.StringVar(value="COM10")
        self.baud_rate = tk.IntVar(value=115200)
        self.databits = tk.IntVar(value=8)
        self.parity = tk.StringVar(value="N")
        self.stop_bits = tk.IntVar(value=1)
        self.encoding = tk.StringVar(value="O2")

        # Присваиваем себе функционал ткинтера
        self.gui = gui
        gui.title("O2 Monitor")
        gui.geometry("800x600")
        # Очередь для элементов GUI
        self.gui_queue = queue.Queue()
        # Обновляем GUI по таймеру
        self.gui.after(100, self.process_gui_queue)

        # Пользовательский шаблон для парсера
        self.custom_skip_pattern = tk.StringVar(value="")

        # Размер таблицы на экране
        self.MAX_TABLE_SIZE = 50000

        # Создание элементов интерфейса
        self.create_widgets()

    # Создание графического окна
    def create_widgets(self):
        main_frame = ttk.Frame(self.gui)
         # Рамка для настроек COM-порта
        settings_frame = ttk.LabelFrame(main_frame, text="Настройки COM-порта")
        settings_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nw")
        main_frame.pack()



        # Имена и поля ввода для параметров
        ttk.Label(settings_frame, text="Порт:").grid(row=0, column=0, sticky="w")
        ttk.Entry(settings_frame, textvariable=self.port, width=10).grid(row=0, column=1, padx=5)

        ttk.Label(settings_frame, text="Скорость:").grid(row=1, column=0, sticky="w")
        ttk.Entry(settings_frame, textvariable=self.baud_rate, width=10).grid(row=1, column=1, padx=5)

        ttk.Label(settings_frame, text="Биты данных:").grid(row=2, column=0, sticky="w")
        ttk.Combobox(settings_frame, textvariable=self.databits, values=["5", "6", "7", "8"], width=8).grid(row=2, column=1, padx=5)

        ttk.Label(settings_frame, text="Четность:").grid(row=3, column=0, sticky="w")
        ttk.Combobox(settings_frame, textvariable=self.parity, values=["N", "E", "O", "M", "S"], width=8).grid(row=3, column=1, padx=5)

        ttk.Label(settings_frame, text="Стоп-биты:").grid(row=4, column=0, sticky="w")
        ttk.Combobox(settings_frame, textvariable=self.stop_bits, values=["1", "1.5", "2"], width=8).grid(row=4, column=1, padx=5)

        # Кнопка "Открыть порт"
        self.open_button = ttk.Button(settings_frame, text="Открыть порт", command=self.attempt_open_port)
        self.open_button.grid(row=5, column=0, pady=(5, 0))

        # Кнопка "Очистить экран"
        self.clear_button = ttk.Button(settings_frame, text="Очистить экран", command=self.clear_screen)
        self.clear_button.grid(row=6, column=0, pady=(5, 0))

        # Рамка "Функции Орион 2"
        o2_frame = ttk.LabelFrame(main_frame, text="Функции Орион 2")
        o2_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nw")

        # Рамка "Счетчики пропущенных запросов"
        self.counter_frame = ttk.LabelFrame(o2_frame, text="Счетчики пропущенных запросов")
        self.counter_frame.grid(row=7, column=0, pady=(5, 0), sticky="w")

        # Поле для пользовательского шаблона
        self.custom_pattern_frame = ttk.Frame(self.counter_frame)
        self.custom_pattern_frame.grid(row=4, column=0, padx=5, pady=2, sticky="w")

        ttk.Label(self.custom_pattern_frame, text="Свой шаблон:").grid(row=0, column=0, padx=(0, 5))
        self.custom_pattern_entry = ttk.Entry(self.custom_pattern_frame, textvariable=self.custom_skip_pattern, width=20)
        self.custom_pattern_entry.grid(row=0, column=1)

        self.counter_label1 = ttk.Label(self.counter_frame, text="REQ/ACK 1: 0")
        self.counter_label1.grid(row=0, column=0, padx=5, pady=2, sticky="w")

        self.counter_label2 = ttk.Label(self.counter_frame, text="REQ/ACK 2: 0")
        self.counter_label2.grid(row=1, column=0, padx=5, pady=2, sticky="w")

        self.counter_label3 = ttk.Label(self.counter_frame, text="SEARCH: 0")
        self.counter_label3.grid(row=2, column=0, padx=5, pady=2, sticky="w")

        # Добавим счетчик для пользовательского шаблона
        self.counter_label_custom = ttk.Label(self.counter_frame, text="Свой шаблон: не задан")
        self.counter_label_custom.grid(row=3, column=0, padx=5, pady=2, sticky="w")

         # Кнопка "Кодировка О2"
        ttk.Radiobutton(o2_frame, text="O2", variable=self.encoding, value="O2").grid(row=0, column=0, sticky="w")

        # Кнопка "Пропускать запросы"
        self.skip_button = ttk.Button(o2_frame, text="Включен пропуск запросов", command=self.toggle_skip_requests)
        self.skip_button.grid(row=6, column=0, columnspan=2, pady=(5, 0),sticky="nw")

        # Настройки кодировки
        encoding_frame = ttk.LabelFrame(main_frame, text="Кодировка")
        encoding_frame.grid(row=0, column=2, padx=10, pady=10, sticky="nw")

        # Кнопки выбора кодировок
        ttk.Radiobutton(encoding_frame, text="HEX", variable=self.encoding, value="HEX").grid(row=1, column=0, sticky="w")
        ttk.Radiobutton(encoding_frame, text="BIN", variable=self.encoding, value="BIN").grid(row=2, column=0, sticky="w")
        ttk.Radiobutton(encoding_frame, text="ASCII", variable=self.encoding, value="ASCII").grid(row=3, column=0, sticky="w")

        tree_frame = ttk.Frame(main_frame)
        tree_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="nsew")

        # Create Treeview
        self.tree = ttk.Treeview(tree_frame, columns=("time", "raw_data", "decoded_data"), show="headings")
        self.tree.heading("time", text="Время")
        self.tree.heading("raw_data", text="Сырые данные")
        self.tree.heading("decoded_data", text="Расшифрованные данные")

        # Configure column widths
        self.tree.column("time", width=100, stretch=False)
        self.tree.column("raw_data", width=300)
        self.tree.column("decoded_data", width=100)

        # Add vertical scrollbar
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        # Grid layout
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        # Configure grid weights
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)

        # Add copy functionality
        self.tree.bind('<Control-c>', self.copy_selection)

        # Text widget для вывода строковых сообщений
        message_frame = ttk.Frame(main_frame)
        message_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="nsew")
        scrollbar_message = ttk.Scrollbar(message_frame)
        scrollbar_message.pack(side=tk.RIGHT, fill=tk.Y)
        self.message_area = tk.Text(message_frame, wrap=tk.WORD, height=5, yscrollcommand=scrollbar_message.set, state=tk.DISABLED)
        self.message_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_message.config(command=self.message_area.yview)

        # Настройка динамического изменения размеров
        self.gui.grid_rowconfigure(1, weight=1)
        self.gui.grid_columnconfigure(0, weight=1)

    # Открытие последовательного порта
    def attempt_open_port(self):
        try:
            # Закрываем порт, если он уже открыт
            if self.serial_port.ser and self.serial_port.ser.is_open:
                self.serial_port.close_port()
                self.data_proc.stop_data_processing()
                self.file_logger.stop_logger()
            # Открываем порт с заданными параметрами
            self.serial_port.open_port(
                port=self.port.get(),
                baudrate=self.baud_rate.get(),
                bytesize=self.databits.get(),
                parity=self.parity.get(),
                stopbits=self.stop_bits.get(),
                timeout=0.01  # Timeout для чтения данных (1 секунда)
            )

            if self.serial_port.ser.is_open:
                self.open_button.config(text="Закрыть порт", command=self.attempt_close_port)
                # Запускаем поток обработчика
                self.data_proc.start_data_processing()
                # Запускаем поток логера
                self.file_logger.start_logger()
                self.update_message_area(f"Порт {self.port.get()} открыт.")
            # while self.serial_port.ser.is_open:
            #     # Читаем данные из файла
            #     try:
            #         with open(self.file_logger.log_file, "rt", encoding="utf-8") as log_file:
            #             data = log_file.readline()
            #             self.update_text_area(data)
            #     except Exception as e:
            #         self.update_message_area(f"Ошибка чтения лога: {e}")
        except serial.SerialException as e:
            self.update_message_area(f"Ошибка открытия порта: {e}")
            return

    # Закрытие последовательного порта
    def attempt_close_port(self):
        try:
            self.serial_port.close_port()
            self.data_proc.stop_data_processing()
            self.file_logger.stop_logger()
            self.open_button.config(text="Открыть порт", command=self.attempt_open_port)
            self.update_message_area("Порт закрыт.")
        except Exception as e:
            self.update_message_area(f"Ошибка закрытия порта: {e}")

    # Функционал копирования строк из окна вывода
    def copy_selection(self, event):
        selected_items = self.tree.selection()
        if not selected_items:
            return

        copied_data = []
        for item in selected_items:
            values = self.tree.item(item)['values']
            copied_data.append('\t'.join(str(v) for v in values))

        copied_string = '\n'.join(copied_data)
        self.gui.clipboard_clear()
        self.gui.clipboard_append(copied_string)

    # Кнопка очистки окна вывода
    def clear_screen(self):
        self.data_proc.counter_req = 0
        self.data_proc.counter_ack = 0
        self.data_proc.counter_search = 0
        self.data_proc.counter_custom = 0
        self.update_counters()
        for item in self.tree.get_children():
            self.tree.delete(item)

    # Переключатель пропуска пакетов
    def toggle_skip_requests(self):
        self.skip_requests = not self.skip_requests
        if self.skip_requests:
            self.skip_button.config(text="Включен пропуск запросов")
        else:
            self.skip_button.config(text="Пропускать запросы")

    # Обновление счетчиков для пропускаемых пакетов
    def update_counters(self):
        self.counter_label1.config(text=f"REQ/ACK 1: {self.data_proc.counter_req_ack1}")
        self.counter_label2.config(text=f"REQ/ACK 2: {self.data_proc.counter_req_ack2}")
        self.counter_label3.config(text=f"SEARCH: {self.data_proc.counter_search}")
        custom_pattern = self.custom_skip_pattern.get()
        if custom_pattern:
            self.counter_label_custom.config(text=f"Свой шаблон ({custom_pattern}): {self.data_proc.counter_custom}")
        else:
            self.counter_label_custom.config(text="Свой шаблон: 0")

    # Обновление информационной строки
    def update_message_area(self, message):
        self.gui_queue.put(('message', message))

    def _update_message_area(self, message):
        # Разрешаем редактирование
        self.message_area.config(state=tk.NORMAL)
        # Добавляем сообщение
        self.message_area.insert(tk.END, message + "\n")
        # Прокручиваем к последнему сообщению
        self.message_area.see(tk.END)
        # Запрещаем редактирование
        self.message_area.config(state=tk.DISABLED)

    # Обновление окна вывода
    def update_text_area(self, formatted_data):
        self.gui_queue.put(('text', formatted_data))

    def _update_text_area(self, formatted_data):
        """Обновление данных в дереве и отправка их в очередь для записи в лог"""
        # Разделяем данные на время и содержимое
        parts = formatted_data.split('  ', 1)
        if len(parts) == 2:
            timestamp = parts[0]
            raw_data = parts[1]

            # Здесь можно добавить декодированные данные
            decoded_data = ""  # Оставляем пустым для примера

            # Обновляем дерево (GUI) из главного потока
            self.tree.insert('', 'end', values=(timestamp, raw_data, decoded_data))
            # Опускаем скроллбар вниз
            self.tree.yview_moveto(1)
            # Ограничиваем количество строк в дереве удаляя старые
            if len(self.tree.get_children()) > self.MAX_TABLE_SIZE:
                self.tree.delete(self.tree.get_children()[0])

    def process_gui_queue(self):
        # Добавляем временный буфер для накопления данных
        accumulated_text_data = []
        accumulated_message_data = []

        while not self.gui_queue.empty():
            type, data = self.gui_queue.get()
            if type == 'message':
                accumulated_message_data.append(data)
            elif type == 'text':
                accumulated_text_data.append(data)

        # Обновляем GUI с накопленными данными
        if accumulated_message_data:
            self._update_message_area("\n".join(accumulated_message_data))
        if accumulated_text_data:
            for text_data in accumulated_text_data:
                self._update_text_area(text_data)

        # Повторный вызов через 100 мс
        self.gui.after(100, self.process_gui_queue)

# Очередь логера
log_queue = queue.Queue()
# Очередь данных последовательного порта
data_queue = queue.Queue()
# Создаем главное окно
main = tk.Tk()
# Создаем один экземпляр GUI
app = SerialMonitorGUI(main, logger_queue=log_queue, data_proc_queue=data_queue)
# Запускаем главный цикл
main.mainloop()