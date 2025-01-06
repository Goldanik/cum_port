import tkinter as tk
from tkinter import ttk, filedialog
import queue

# Свои реализации
import serial_port
import file_logger
import data_processing

class SerialMonitorGUI:
    def __init__(self, gui, logger_queue, data_proc_queue):
        # Кнопки
        self.file_open = False
        self.refresh_ports_button = None
        self.skip_button = None
        self.skip_requests = True
        self.clear_button = None
        self.open_button = None
        # Прочая
        self.counter_table = None
        self.port_combobox = None
        self.raw_file_frame = None
        self.counter_label_custom = None
        self.custom_pattern_entry = None
        self.custom_pattern_frame = None
        self.counter_frame = None
        self.message_area = None
        self.tree = None
        self.encoding = None

        # Инициализация массивов счетчиков
        self.req_ack_counters = [0] * 32  # Счетчики REQ/ACK для каждого адреса
        self.search_counters = [0] * 32  # Счетчики SEARCH для каждого адреса
        self.get_id_counters = [0] * 32  # Счетчики GETID для каждого адреса
        self.give_addr = [""] * 32  # Мак-адрес GIVEADDR для каждого адреса

        # Присваиваем себе экземпляр очереди
        self.log_queue = logger_queue
        self.data_queue = data_proc_queue
        # Передаем тот же экземпляр GUI в другие компоненты
        self.serial_port = serial_port.SerialPort(data_proc_queue=data_queue, main_gui=self)
        self.data_proc = data_processing.DataProcessing(data_proc_queue=data_queue, logger_queue=log_queue, main_gui=self)
        self.file_logger = file_logger.FileLogger(log_queue=log_queue, main_gui=self)

        # Переменные для настроек COM-порта
        self.port = tk.StringVar()
        self.baud_rate = tk.IntVar(value=115200)
        self.databits = tk.IntVar(value=8)
        self.parity = tk.StringVar(value="N")
        self.stop_bits = tk.IntVar(value=1)
        self.encoding = tk.StringVar(value="O2")

        # Устанавливаем первый порт как текущий
        available_ports = self.serial_port.get_available_ports()
        if available_ports:
            self.port.set(available_ports[0])

        # Присваиваем себе функционал ткинтера
        self.gui = gui
        self.gui.title("CUM-port")
        self.gui.geometry("1270x750")
        self.gui.minsize(1270,750)
        # Очередь для элементов GUI
        self.gui_queue = queue.Queue()
        # Обновляем GUI по таймеру
        self.gui.after(200, self.process_gui_queue)

        # Пользовательский шаблон для парсера
        self.custom_skip_pattern = tk.StringVar(value="")

        # Размер таблицы на экране
        self.MAX_TABLE_SIZE = 50000

        # Переменные для состояния галочек видимости столбцов
        self.column_visibility = {}

        # Список столбцов таблицы
        self.columns = [
            #colimn_id          column_name                 column_width
            ("time",            "Время",                    100),
            ("raw_data",        "Сырые данные",             100),
            ("len",             "Длина",                    50),
            ("pnum",            "Pnum",                     50),
            ("direction",       "Направление",              220),
            ("packet_type",     "Заголовок",                150),
            ("decoded_data",    "Расшифрованные данные",    200)
        ]

        # Создание соответствия между идентификаторами столбцов и их названиями
        self.column_names = {col[0]: col[1] for col in self.columns}

        # Создание соответствия между идентификаторами столбцов и их шириной
        self.column_widths = {col[0]: col[2] for col in self.columns}

        # Создание элементов интерфейса
        self.create_widgets()

    def create_widgets(self):
        """Создание графического окна"""
        # Создаем два фрейма: для фиксированного и растягивающегося содержимого
        fixed_frame = tk.Frame(self.gui, bg="gray")
        fixed_frame.grid_columnconfigure(0, minsize=350)

        fixed_frame.grid(row=0, column=0, sticky="nsew")
        stretchable_frame = tk.Frame(self.gui, bg="white")
        stretchable_frame.grid(row=0, column=1, sticky="nsew")

        # Рамка для настроек COM-порта
        settings_frame = ttk.LabelFrame(fixed_frame, text="Настройки COM-порта")
        settings_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nwe")

        # Имена и поля ввода для параметров
        ttk.Label(settings_frame, text="Порт:").grid(row=0, column=0, sticky="w")
        self.port_combobox = ttk.Combobox(settings_frame, textvariable=self.port, width=8)
        self.port_combobox.grid(row=0, column=1, padx=5)
        # Устанавливаем список портов
        self.port_combobox['values'] = self.serial_port.get_available_ports()
        # Только выбор из списка
        self.port_combobox.state(['readonly'])

        # Кнопка обновить список портов
        self.refresh_ports_button = ttk.Button(settings_frame, text=u'\u21bb', command=self.refresh_ports, width=4)
        self.refresh_ports_button.grid(row=0, column=2, padx=5)

        ttk.Label(settings_frame, text="Скорость:").grid(row=1, column=0, sticky="w")
        ttk.Combobox(settings_frame, textvariable=self.baud_rate, values=["115200", "57600", "38400", "19200", "9600"],
                     width=8).grid(row=1, column=1, padx=5)

        ttk.Label(settings_frame, text="Биты данных:").grid(row=2, column=0, sticky="w")
        ttk.Combobox(settings_frame, textvariable=self.databits, values=["5", "6", "7", "8"], width=8).grid(row=2, column=1, padx=5)

        ttk.Label(settings_frame, text="Четность:").grid(row=3, column=0, sticky="w")
        ttk.Combobox(settings_frame, textvariable=self.parity, values=["N", "E", "O", "M", "S"], width=8).grid(row=3, column=1, padx=5)

        ttk.Label(settings_frame, text="Стоп-биты:").grid(row=4, column=0, sticky="w")
        ttk.Combobox(settings_frame, textvariable=self.stop_bits, values=["1", "1.5", "2"], width=8).grid(row=4, column=1, padx=5)

        # Кнопка "Открыть порт"
        self.open_button = ttk.Button(settings_frame, text="Открыть порт", command=self.attempt_open_port)
        self.open_button.grid(row=5, column=0, columnspan=3, pady=5, sticky="we")

        # Кнопка "Очистить экран"
        self.clear_button = ttk.Button(settings_frame, text="Очистить экран", command=self.clear_screen)
        self.clear_button.grid(row=6, column=0, columnspan=3, pady=5, sticky="we")

        # Рамка
        self.raw_file_frame = ttk.LabelFrame(settings_frame, text="Парсинг сырых данных из файла:")
        self.raw_file_frame.grid(row=7, column=0, pady=5, columnspan=3, sticky="nwe")

        # Добавляем кнопку "Открыть файл"
        ttk.Button(self.raw_file_frame, text="Открыть файл", command=self.open_file).grid(row=8, column=0, columnspan=3,
                                                                                     pady=5, sticky="we")

        # Рамка "Функции Орион 2"
        o2_frame = ttk.LabelFrame(fixed_frame, text="Функции Орион 2")
        o2_frame.grid(row=2, column=0, padx=10, pady=10, sticky="nwe")

        # Рамка "Счетчики пропущенных запросов"
        self.counter_frame = ttk.LabelFrame(o2_frame, text="Счетчики пропущенных запросов")
        self.counter_frame.grid(row=7, column=0, pady=5, sticky="nwe")

        # Поле для пользовательского шаблона
        self.custom_pattern_frame = ttk.Frame(self.counter_frame)
        self.custom_pattern_frame.grid(row=4, column=0, padx=5, pady=2, sticky="w")

        ttk.Label(self.custom_pattern_frame, text="Свой шаблон:").grid(row=0, column=0, padx=(0, 5))
        self.custom_pattern_entry = ttk.Entry(self.custom_pattern_frame, textvariable=self.custom_skip_pattern, width=20)
        self.custom_pattern_entry.grid(row=0, column=1)

        # Создаем таблицу для отображения данных
        self.counter_table = ttk.Treeview(self.counter_frame, columns=("address", "req_ack", "search", "get_id", "give_addr"),
                                          show="headings", height=10)
        self.counter_table.heading("address", text="№")
        self.counter_table.heading("req_ack", text="IN/NACK")
        self.counter_table.heading("search", text="SEARCH")
        self.counter_table.heading("get_id", text="GETID")
        self.counter_table.heading("give_addr", text="GIVEADDR")

        # Устанавливаем ширину колонок
        self.counter_table.column("address", width=30, anchor="center")
        self.counter_table.column("req_ack", width=60, anchor="center")
        self.counter_table.column("search", width=60, anchor="center")
        self.counter_table.column("get_id", width=60, anchor="center")
        self.counter_table.column("give_addr", width=100, anchor="center")

        # Добавляем вертикальный скроллбар
        scrollbar = ttk.Scrollbar(self.counter_frame, orient="vertical", command=self.counter_table.yview)
        self.counter_table.configure(yscrollcommand=scrollbar.set)
        self.counter_table.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Инициализируем данные таблицы
        for i in range(32):
            self.counter_table.insert("", "end", values=(i, 0, 0, 0))

        # Добавим счетчик для пользовательского шаблона
        self.counter_label_custom = ttk.Label(self.counter_frame, text="Свой шаблон фильтрации данных: не задан")
        self.counter_label_custom.grid(row=3, column=0, padx=5, pady=2, sticky="w")

        # Кнопка "Пропускать запросы"
        self.skip_button = ttk.Button(o2_frame, text="Включен пропуск запросов", command=self.toggle_skip_requests)
        self.skip_button.grid(row=6, column=0, columnspan=2, pady=(5, 0), sticky="nw")

        # Настройки кодировки
        encoding_frame = ttk.LabelFrame(fixed_frame, text="Кодировка")
        encoding_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nwe")

        # Кнопки выбора кодировок
        ttk.Radiobutton(encoding_frame, text="O2", variable=self.encoding, value="O2",
                        command=self.update_columns_on_encoding).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(encoding_frame, text="HEX", variable=self.encoding, value="HEX",
                        command=self.update_columns_on_encoding).grid(row=1, column=0, sticky="w")
        ttk.Radiobutton(encoding_frame, text="ASCII", variable=self.encoding, value="ASCII",
                        command=self.update_columns_on_encoding).grid(row=3, column=0, sticky="w")

        tree_frame = ttk.Frame(stretchable_frame)
        tree_frame.grid(row=0, column=0, rowspan=2, padx=10, pady=(0, 10), sticky="nsew")

        # Добавляем фрейм для галочек над таблицей
        column_options_frame = ttk.Frame(tree_frame)
        column_options_frame.grid(row=0, column=0, columnspan=2, pady=(0, 5), sticky="w")

        # Заголовок для строки с галочками
        ttk.Label(column_options_frame, text="Отображать столбцы:").pack(side=tk.LEFT, padx=(0, 10))

        # Заполняем заголовки галочек видимости
        for column_id, column_name, column_width in self.columns:
            # По умолчанию все столбцы видимы
            var = tk.BooleanVar(value=True)
            cb = ttk.Checkbutton(column_options_frame, text=column_name, variable=var,
                                 command=lambda col=column_id: self.toggle_column_visibility(col))
            cb.pack(side=tk.LEFT, padx=5)
            self.column_visibility[column_id] = var

        # Таблица вывода данных
        self.tree = ttk.Treeview(tree_frame, columns=[col[0] for col in self.columns], show="headings")
        # Заполняем заголовки и ширину столбцов
        for column_id, column_name, column_width in self.columns:
            self.tree.heading(column_id, text=column_name)
            self.tree.column(column_id, width=column_width, stretch=False)

        # Вертикальный скроллбар
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        # Сетка таблицы вывода данных
        self.tree.grid(row=1, column=0, sticky="nsew")
        vsb.grid(row=1, column=1, sticky="ns")

        # Веса сетки таблицы вывода данных
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(1, weight=1)

        # Создание функционала копирования данных из таблицы по хоткею
        self.tree.bind('<Control-c>', self.copy_selection)

        # Текстовая строка для вывода сообщений
        message_frame = ttk.Frame(stretchable_frame)
        message_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="sew")
        scrollbar_message = ttk.Scrollbar(message_frame)
        scrollbar_message.pack(side=tk.RIGHT, fill=tk.Y)
        self.message_area = tk.Text(message_frame, wrap=tk.WORD, height=5,
                                    yscrollcommand=scrollbar_message.set, state=tk.DISABLED)
        self.message_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_message.config(command=self.message_area.yview)

        # Информационная строка
        info_label = ttk.Label(stretchable_frame, text="Версия:1.0    tg:@danyagolovanov", anchor="e")
        info_label.grid(row=3, column=0, padx=10, pady=5, sticky="we")

        # Фиксируем строки внутри фиксированного фрейма
        fixed_frame.grid_rowconfigure(0, weight=0)  # Строка 0 фиксирована
        fixed_frame.grid_rowconfigure(1, weight=0)  # Строка 1 фиксирована
        fixed_frame.grid_rowconfigure(2, weight=0)  # Строка 2 фиксирована
        fixed_frame.grid_columnconfigure(0, weight=0)  # Колонка фиксирована

        # Настраиваем строки внутри растягивающегося фрейма
        stretchable_frame.grid_rowconfigure(0, weight=1)  # Строка 0 растягивается
        stretchable_frame.grid_rowconfigure(1, weight=1)  # Строка 1 растягивается
        stretchable_frame.grid_columnconfigure(0, weight=1)  # Колонка растягивается

        # Настройка динамического изменения размеров
        self.gui.grid_rowconfigure(0, weight=1)
        self.gui.grid_columnconfigure(0, weight=0)
        self.gui.grid_columnconfigure(1, weight=1)

    def open_file(self):
        """Открывает текстовый файл, читает его содержимое и отправляет данные в очередь."""
        try:
            # Открываем диалог выбора файла
            file_path = filedialog.askopenfilename(
                title="Открыть файл",
                filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
            )
            if not file_path:
                return  # Если файл не выбран, ничего не делать

            # Читаем файл построчно
            with open(file_path, "r", encoding="utf-8") as file:
                for line in file:
                    # Удаляем символы новой строки и пробелы
                    stripped_line = line.strip()
                    if stripped_line:
                        # Преобразуем строку в байты (если строка содержит HEX-представление данных)
                        try:
                            byte_data = bytes.fromhex(stripped_line)
                            self.data_queue.put(byte_data)
                        except ValueError:
                            self.update_message_area(f"Ошибка преобразования строки в байты: {stripped_line}")
            self.file_open = True
            # Запускаем поток обработки данных, если он еще не работает
            self.data_proc.start_data_processing()

            # Обновляем сообщение в GUI
            self.update_message_area(f"Файл {file_path} успешно прочитан и данные добавлены в очередь.")
        except Exception as e:
            self.update_message_area(f"Ошибка при чтении файла: {e}")

    def toggle_column_visibility(self, column_id):
        """Переключает видимость столбца в зависимости от состояния галочки."""
        # Если галочка установлена
        if self.column_visibility[column_id].get():
            # Восстанавливаем заголовок столбца из словаря column_names
            self.tree.heading(column_id, text=self.column_names[column_id])
            # Восстанавливаем ширину столбца из словаря column_widths
            self.tree.column(column_id, width=self.column_widths[column_id], stretch=False)
        # Если галочка снята
        else:
            self.tree.column(column_id, width=0)  # Скрыть столбец
            self.tree.heading(column_id, text="")  # Очистить заголовок столбца
            self.tree.column(column_id, stretch=False)  # Убедитесь, что столбец не растягивается

    def update_columns_on_encoding(self):
        """Отключает столбцы и меняет их ширину в таблице данных в зависимости от выбранной кодировки."""
        if self.encoding.get() == "O2":
            # В кодировке о2 включаем все столбцы со стандартной заданной шириной
            for column_id, column_name, column_width in self.columns:
                self.tree.column(column_id, width=column_width, stretch=False)
                self.column_visibility[column_id].set(True)
                self.toggle_column_visibility(column_id)
        else:
            # Для кодировок ASCI и HEX выключаем все столбцы кроме времени и сырых данных
            self.tree.column("time", width=100, stretch=False, anchor="center")
            self.tree.column("raw_data", width=600)
            for column_id, column_name, column_width in self.columns[2:]:
                self.column_visibility[column_id].set(False)
                self.toggle_column_visibility(column_id)

    def attempt_open_port(self):
        """Открытие последовательного порта"""
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
        except Exception as e:
            self.update_message_area(f"Ошибка открытия порта: {e}")
            return

    def attempt_close_port(self):
        """Закрытие последовательного порта"""
        try:
            self.serial_port.close_port()
            self.data_proc.stop_data_processing()
            self.file_logger.stop_logger()
            self.open_button.config(text="Открыть порт", command=self.attempt_open_port)
            self.update_message_area("Порт закрыт.")
        except Exception as e:
            self.update_message_area(f"Ошибка закрытия порта: {e}")

    def refresh_ports(self):
        """Обновляет список доступных COM-портов."""
        available_ports = self.serial_port.get_available_ports()
        self.port_combobox['values'] = available_ports
        if available_ports:
            self.port_combobox.current(0)  # Устанавливаем первый порт как выбранный
        else:
            self.port.set("")  # Если портов нет, сбрасываем значение

    def copy_selection(self, event):
        """Функционал копирования строк из окна вывода"""
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

    def clear_screen(self):
        """Кнопка очистки окна вывода"""
        # Сбрасываем счетчики в списках (инициализируем заново)
        self.req_ack_counters = [0] * 32
        self.search_counters = [0] * 32
        self.get_id_counters = [0] * 32
        self.give_addr = [0] * 32
        self.data_proc.counter_custom = 0
        self.update_counters()
        for item in self.tree.get_children():
            self.tree.delete(item)

    def toggle_skip_requests(self):
        """Переключатель пропуска пакетов"""
        self.skip_requests = not self.skip_requests
        if self.skip_requests:
            self.skip_button.config(text="Включен пропуск запросов")
        else:
            self.skip_button.config(text="Пропускать запросы")

    def update_counters(self):
        """Обновление данных в таблице счетчиков."""
        # Обновляем данные в строках таблицы
        for i in range(32):
            # Получаем текущие значения счетчиков для каждого адреса
            req_ack_count = self.req_ack_counters[i]  # Массив счетчиков REQ/ACK
            search_count = self.search_counters[i]  # Массив счетчиков SEARCH
            getid_count = str(self.get_id_counters[i])  # Массив счетчиков GETID
            # Массив мак-адресов GETID преобразуем в читаемый вид
            if self.give_addr[i]:
                give_addr = self.give_addr[i]
                pairs = [give_addr[i:i + 2] for i in range(0, 12, 2)]
                give_addr = ":".join(reversed(pairs))
            else:
                give_addr = ""

            # Обновляем соответствующую строку в таблице
            self.counter_table.item(self.counter_table.get_children()[i], values=(i, req_ack_count, search_count, getid_count, give_addr))

    def update_message_area(self, message):
        """Запись в очередь гуи для информационной строки"""
        self.gui_queue.put(('message', message))

    def _update_message_area(self, message):
        """Обновление информационной строки"""
        # Разрешаем редактирование
        self.message_area.config(state=tk.NORMAL)
        # Добавляем сообщение
        self.message_area.insert(tk.END, message + "\n")
        # Прокручиваем к последнему сообщению
        self.message_area.see(tk.END)
        # Запрещаем редактирование
        self.message_area.config(state=tk.DISABLED)

    def update_data_area(self, formatted_data):
        """Запись в очередь гуи для окна вывода"""
        self.gui_queue.put(('text', formatted_data))

    def _update_data_area(self, formatted_data):
        """Обновление данных в окне вывода"""
        timestamp = ""
        raw_data = ""
        data_len = ""
        pnum = ""
        direction = ""
        packet_type = ""
        decoded_data = ""
        # Разделяем данные на время и содержимое
        parts = formatted_data.split('@', 6)
        if len(parts) == 7:
            timestamp = parts[0]
            raw_data = parts[1]
            data_len = parts[2]
            pnum = parts[3]
            direction = parts[4]
            packet_type = parts[5]
            decoded_data = parts[6]
        elif len(parts) == 3:
            timestamp = parts[0]
            raw_data = parts[1]

        # Обновляем дерево (GUI) из главного потока
        self.tree.insert('', 'end', values=(timestamp, raw_data, data_len, pnum, direction, packet_type, decoded_data))
        # Опускаем скроллбар вниз
        self.tree.yview_moveto(1)
        # Ограничиваем количество строк в дереве удаляя старые
        if len(self.tree.get_children()) > self.MAX_TABLE_SIZE:
            self.tree.delete(self.tree.get_children()[0])

    def process_gui_queue(self):
        """Обработчик очереди гуи и отрисовка данных"""
        # Добавляем временный буфер для накопления данных
        accumulated_text_data = []
        accumulated_message_data = []

        while not self.gui_queue.empty():
            msg_type, data = self.gui_queue.get()
            if msg_type == 'message':
                accumulated_message_data.append(data)
            elif msg_type == 'text':
                accumulated_text_data.append(data)
        if (self.serial_port.ser and self.serial_port.ser.is_open) or self.file_open:
            # Обновляем GUI с накопленными данными
            if accumulated_message_data:
                self._update_message_area("\n".join(accumulated_message_data))
            if accumulated_text_data:
                for text_data in accumulated_text_data:
                    self._update_data_area(text_data)
            #self._update_message_area(f"Размер очереди гуи: {self.data_queue.qsize()}")
            self.update_counters()
        if self.file_open:
            # Стираем флаг обновления гуи после открытия файла
            if self.data_queue.qsize() == 0:
                self._update_message_area("Расшифровка файла завершена")
                self.file_open = False
        # Повторный вызов через 200 мс
        self.gui.after(200, self.process_gui_queue)

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

# Сборка
# pyinstaller --onefile -w cum_port.py
