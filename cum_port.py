import datetime
import tkinter as tk
import webbrowser
from tkinter import ttk, filedialog
import queue
from abc import ABC, abstractmethod

# Свои реализации
import serial_port
import file_logger
import data_processing
import udp_connection

class GUIManager(ABC):
    """Абстрактный класс для управления GUI."""

    @abstractmethod
    def update_message_area(self, message: str):
        """Обновляет область сообщений."""
        pass

    @abstractmethod
    def update_data_area(self, formatted_data: str):
        """Обновляет область данных."""
        pass

    @abstractmethod
    def update_counters(self):
        """Обновляет счетчики."""
        pass

    @abstractmethod
    def get_encoding(self) -> str:
        """Возвращает текущую кодировку."""
        pass

    @abstractmethod
    def get_port_settings(self) -> dict:
        """Возвращает настройки порта."""
        pass

    @abstractmethod
    def open_port_button_callback(self, callback):
        """Устанавливает callback для кнопки открытия порта."""
        pass

    @abstractmethod
    def close_port_button_callback(self, callback):
        """Устанавливает callback для кнопки закрытия порта."""
        pass

    @abstractmethod
    def refresh_ports_callback(self, callback):
        """Устанавливает callback для кнопки обновления портов."""
        pass

    @abstractmethod
    def open_file_callback(self, callback):
        """Устанавливает callback для кнопки открытия файла."""
        pass

    @abstractmethod
    def clear_screen_callback(self, callback):
        """Устанавливает callback для кнопки очистки экрана."""
        pass

    @abstractmethod
    def toggle_column_visibility_callback(self, callback):
        """Устанавливает callback для переключения видимости столбцов."""
        pass

    @abstractmethod
    def hide_columns_on_encoding_callback(self, callback):
        """Устанавливает callback для скрытия столбцов при смене кодировки."""
        pass

    @abstractmethod
    def copy_selection_callback(self, callback):
        """Устанавливает callback для копирования выделенных данных."""
        pass

    @abstractmethod
    def start_gui(self):
        """Запускает GUI."""
        pass

__version__ = "1.10"
__app_name__ = "CUM-port"

class SerialMonitorGUI:
    def __init__(self, gui, logger_queue, data_proc_queue):
        # Кнопки
        self.open_button = None
        # Прочая
        self.counter_table = None
        self.port_combobox = None
        self.message_area = None
        self.tree = None
        self.encoding = None
        self.autoscroll_enabled = None
        self.file_open = False
        self.highlight_enabled = False

        # Инициализация массивов счетчиков
        self.req_ack_counters = [0] * 32  # Счетчики REQ/ACK для каждого адреса
        self.search_counters = [0] * 32  # Счетчики SEARCH для каждого адреса
        self.get_id_counters = [0] * 32  # Счетчики GETID для каждого адреса
        self.mac_addr = [""] * 32  # Мак-адрес GIVEADDR для каждого адреса

        # Присваиваем себе экземпляр очереди
        self.log_queue = logger_queue
        self.data_queue = data_proc_queue
        # Передаем тот же экземпляр GUI в другие компоненты
        self.serial_port = serial_port.SerialPort(data_queue, on_error=self.update_message_area)
        self.udp_connection = udp_connection.UDPConnection(data_queue, on_error=self.update_message_area)
        self.data_proc = data_processing.DataProcessing(data_proc_queue=data_queue, logger_queue=log_queue, main_gui=self)
        self.file_logger = file_logger.FileLogger(log_queue, on_error=self.update_message_area, on_file_size_exceeded=self._restart_logger)

        # Логическое состояние соединений
        self.com_port_open = False
        self.udp_port_open = False

        # Вкладка/интерфейс по умолчанию
        self.selected_tab = "COM-порт"
        # Переключатель раскраски строк в таблице
        self.flip_flop = False

        # Переменные для настроек COM-порта
        self.port = tk.StringVar()
        self.baud_rate = tk.IntVar(value=115200)
        self.baud_rate_list = ["115200", "57600", "38400", "19200", "9600"]
        self.databits = tk.IntVar(value=8)
        self.databits_list = ["5", "6", "7", "8"]
        self.parity = tk.StringVar(value="N")
        self.parity_list = ["N", "E", "O", "M", "S"]
        self.stop_bits = tk.IntVar(value=1)
        self.stop_bits_list = ["1", "2"]
        self.encoding = tk.StringVar(value="O2")

        # Устанавливаем первый порт как текущий
        available_ports = self.serial_port.get_available_ports()
        if available_ports:
            self.port.set(available_ports[0])

        # Присваиваем себе функционал ткинтера
        self.gui = gui
        self.gui.title(__app_name__)
        self.gui.geometry("1260x600")
        self.gui.minsize(1260,600)

        # Очередь для элементов GUI
        self.gui_queue = queue.Queue()
        # GUI по таймер
        self.gui_update_timeout = 200
        # Обновляем GUI по таймеру
        self.gui.after(self.gui_update_timeout, self._process_gui_queue)

        # Пользовательский шаблон для парсера
        self.custom_skip_pattern = tk.StringVar(value="")

        # Размер таблицы на экране
        self.MAX_TABLE_SIZE = 1000

        # Переменные для состояния галочек видимости столбцов
        self.column_visibility = {}

        # Список столбцов таблицы данных
        self.data_columns = [
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
        self.column_names = {col[0]: col[1] for col in self.data_columns}

        # Создание соответствия между идентификаторами столбцов и их шириной
        self.column_widths = {col[0]: col[2] for col in self.data_columns}

        # Создание элементов интерфейса
        self._create_widgets()

    def _create_widgets(self):
        """Создание графического окна"""
        # Создаем два фрейма: для фиксированного и растягивающегося содержимого
        fixed_frame = tk.Frame(self.gui, bg="gray")
        fixed_frame.grid_columnconfigure(0, minsize=350)

        fixed_frame.grid(row=0, column=0, sticky="nsew")
        stretchable_frame = tk.Frame(self.gui, bg="white")
        stretchable_frame.grid(row=0, column=1, sticky="nsew")

        # Рамка настройки интерфейса
        interface_frame = ttk.LabelFrame(fixed_frame, text="Настройки интерфейса:")
        interface_frame.grid(row=0, column=0, padx=10, pady=5, sticky="nwe")

        # Создаем панель вкладок Notebook
        self.notebook = ttk.Notebook(interface_frame)
        self.notebook.grid(row=0, column=0, padx=5, pady=5, sticky="nwe")

        # Первая вкладка: Настройки COM-порта
        com_settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(com_settings_frame, text="COM-порт")

        # Вторая вкладка: UDP
        udp_frame = ttk.Frame(self.notebook)
        self.notebook.add(udp_frame, text="UDP")

        # Третья вкладка: Файл
        file_frame = ttk.Frame(self.notebook)
        self.notebook.add(file_frame, text="Файл")

        # Четвертая вкладка: Bluetooth
        bluetooth_frame = ttk.Frame(self.notebook)
        self.notebook.add(bluetooth_frame, text="In progress")

        # Привязываем обработчик изменения вкладки
        self.notebook.bind("<<NotebookTabChanged>>", self._check_tabs)

        # Имена и поля ввода для параметров COM-порта
        ttk.Label(com_settings_frame, text="Порт:").grid(row=0, column=0, sticky="w")
        self.port_combobox = ttk.Combobox(com_settings_frame, textvariable=self.port, width=8)
        self.port_combobox.grid(row=0, column=1, padx=5)
        # Устанавливаем список портов
        self.port_combobox['values'] = self.serial_port.get_available_ports()
        # Только выбор из списка
        self.port_combobox.state(['readonly'])

        # Кнопка обновить список портов
        refresh_ports_button = ttk.Button(com_settings_frame, text=u'\u21bb', command=self._refresh_ports, width=4)
        refresh_ports_button.grid(row=0, column=2, padx=5)

        ttk.Label(com_settings_frame, text="Скорость:").grid(row=1, column=0, sticky="w")
        ttk.Combobox(com_settings_frame, textvariable=self.baud_rate, values=self.baud_rate_list,
                     width=8).grid(row=1, column=1, padx=5)

        ttk.Label(com_settings_frame, text="Биты данных:").grid(row=2, column=0, sticky="w")
        ttk.Combobox(com_settings_frame, textvariable=self.databits, values=self.databits_list, width=8).grid(row=2,
                                                                                                              column=1,
                                                                                                              padx=5)

        ttk.Label(com_settings_frame, text="Четность:").grid(row=3, column=0, sticky="w")
        ttk.Combobox(com_settings_frame, textvariable=self.parity, values=self.parity_list, width=8).grid(row=3,
                                                                                                          column=1,
                                                                                                          padx=5)

        ttk.Label(com_settings_frame, text="Стоп-биты:").grid(row=4, column=0, sticky="w")
        ttk.Combobox(com_settings_frame, textvariable=self.stop_bits, values=self.stop_bits_list, width=8).grid(row=4,
                                                                                                                column=1,
                                                                                                                padx=5)

        # Кнопка "Открыть порт"
        self.open_button = ttk.Button(com_settings_frame, text="Открыть порт", command=self._open_com_port, width=20)
        self.open_button.grid(row=5, column=0, columnspan=2, pady=5, sticky="we")

        # Переменные для хранения значений UDP
        self.udp_ip_var = tk.StringVar(value="192.168.66.1")
        self.udp_port_var = tk.StringVar(value="40001")

        # Добавляем элементы для настройки UDP
        ttk.Label(udp_frame, text="IP-адрес:").grid(row=0, column=0, sticky="w")
        self.udp_ip_entry = ttk.Entry(udp_frame, textvariable=self.udp_ip_var, width=15)
        self.udp_ip_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(udp_frame, text="Порт:").grid(row=1, column=0, sticky="w")
        self.udp_port_entry = ttk.Entry(udp_frame, textvariable=self.udp_port_var, width=15)
        self.udp_port_entry.grid(row=1, column=1, padx=5, pady=5)

        # Кнопка для UDP
        self.udp_button = ttk.Button(udp_frame, text="Подключиться", command=self._connect_udp, width=20)
        self.udp_button.grid(row=2, column=0, columnspan=2, pady=5, sticky="we")

        # Добавляем элементы для настройки Bluetooth
        ttk.Label(bluetooth_frame, text="Устройство:").grid(row=0, column=0, sticky="w")
        self.bluetooth_device_entry = ttk.Entry(bluetooth_frame, width=15)
        self.bluetooth_device_entry.grid(row=0, column=1, padx=5, pady=5)

        # Кнопка для Bluetooth
        self.bluetooth_button = ttk.Button(bluetooth_frame, text="In progress", #command=self._connect_bluetooth,
                                           width=20)
        self.bluetooth_button.grid(row=1, column=0, columnspan=2, pady=5, sticky="we")

        # Рамка настроек в две колонки
        double_column_frame = ttk.LabelFrame(fixed_frame, text="Настройки:")
        double_column_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nwe")

        # Инфо по работе с файлом
        ttk.Label(file_frame, text="Парсинг сырых данных из файла.\nДанные можно записать из интерфейса\nвыбрав кодировку HEX.").grid(row=0, column=0, sticky="w")

        # Добавляем кнопку "Открыть файл"
        clear_button = ttk.Button(file_frame, text="Открыть файл", command=self._open_file, width=20)
        clear_button.grid(row=1, column=0, padx=5, pady=5, sticky="we")

        # Рамка "Настройки окна вывода"
        screen_frame = ttk.LabelFrame(double_column_frame, text="Настройки окна вывода:")
        screen_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nwe")

        # Настройки кодировки
        encoding_frame = ttk.LabelFrame(double_column_frame, text="Кодировка")
        encoding_frame.grid(row=0, column=1, padx=10, pady=5, sticky="nwe")

        # Кнопки выбора кодировок
        ttk.Radiobutton(encoding_frame, text="O2", variable=self.encoding, value="O2",
                        command=self._check_encoding).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(encoding_frame, text="HEX", variable=self.encoding, value="HEX",
                        command=self._check_encoding).grid(row=1, column=0, sticky="w")
        ttk.Radiobutton(encoding_frame, text="ASCII", variable=self.encoding, value="ASCII",
                        command=self._check_encoding).grid(row=3, column=0, sticky="w")

        # Кнопка "Очистить экран"
        clear_button = ttk.Button(screen_frame, text="Очистить экран", command=self._clear_screen, width=20)
        clear_button.grid(row=0, column=0, padx=5, pady=5, sticky="we")

        # Добавляем фрейм для галочки автопрокрутки
        scroll_control_frame = ttk.Frame(screen_frame)
        scroll_control_frame.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

        # Переменная для отслеживания состояния галочки автопрокрутки
        self.autoscroll_enabled = tk.BooleanVar(value=True)

        # Галочка для автопрокрутки
        autoscroll_checkbox = ttk.Checkbutton(scroll_control_frame, text="Автопрокрутка", variable=self.autoscroll_enabled)
        autoscroll_checkbox.pack(side=tk.LEFT)

        # Рамка "Счетчики сервисных запросов О2"
        counter_frame = ttk.LabelFrame(fixed_frame, text="Счетчики сервисных запросов О2")
        counter_frame.grid(row=4, column=0, padx=10, pady=5, sticky="nwe")

        # Создаем таблицу для отображения данных
        self.counter_table = ttk.Treeview(counter_frame, columns=("address", "req_ack", "search", "get_id", "give_addr"),
                                          show="headings", height=10)
        self.counter_table.heading("address", text="ADDR")
        self.counter_table.heading("req_ack", text="IN/NACK")
        self.counter_table.heading("search", text="SEARCH")
        self.counter_table.heading("get_id", text="GETID")
        self.counter_table.heading("give_addr", text="GIVEADDR")

        # Устанавливаем ширину колонок
        self.counter_table.column("address", width=40, anchor="center")
        self.counter_table.column("req_ack", width=60, anchor="center")
        self.counter_table.column("search", width=60, anchor="center")
        self.counter_table.column("get_id", width=40, anchor="center")
        self.counter_table.column("give_addr", width=100, anchor="center")

        # Добавляем вертикальный скроллбар
        scrollbar = ttk.Scrollbar(counter_frame, orient="vertical", command=self.counter_table.yview)
        self.counter_table.configure(yscrollcommand=scrollbar.set)
        self.counter_table.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Инициализируем данные таблицы
        for i in range(32):
            self.counter_table.insert("", "end", values=(i, 0, 0, 0))

        # Рамка вывода данных
        tree_frame = ttk.Frame(stretchable_frame)
        tree_frame.grid(row=0, column=0, rowspan=2, padx=5, pady=5, sticky="nsew")

        # Таблица вывода данных
        self.tree = ttk.Treeview(tree_frame, columns=[col[0] for col in self.data_columns], show="headings")

        # Настраиваем чередующиеся цвета строк
        self.tree.tag_configure('oddrow', background='#EEEEEE')
        self.tree.tag_configure('evenrow', background='#FFFFFF')

        # Заполняем заголовки и ширину столбцов
        for column_id, column_name, column_width in self.data_columns:
            self.tree.heading(column_id, text=column_name)
            self.tree.column(column_id, width=column_width, stretch=False)

        # Вертикальный скроллбар
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        # Добавляем фрейм для поиска и подсветки
        highlight_frame = ttk.Frame(tree_frame)
        highlight_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="w")

        ttk.Label(highlight_frame, text="Подсветка строк:").pack(side=tk.LEFT, padx=(0, 5))

        # Добавляем поле ввода для поиска
        self.search_entry = ttk.Entry(highlight_frame, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=5)

        # Добавляем кнопку подсветки
        self.highlight_button = ttk.Button(highlight_frame, text="Включить подсветку", command=self._toggle_highlight)
        self.highlight_button.pack(side=tk.LEFT, padx=5)

        # Добавляем фрейм для галочек над таблицей
        column_options_frame = ttk.Frame(tree_frame)
        column_options_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="w")

        # Заголовок для строки с галочками
        ttk.Label(column_options_frame, text="Отображать столбцы:").pack(side=tk.LEFT, padx=(0, 10))

        # Заполняем заголовки галочек видимости
        for column_id, column_name, column_width in self.data_columns:
            # По умолчанию все столбцы видимы
            var = tk.BooleanVar(value=True)
            cb = ttk.Checkbutton(column_options_frame, text=column_name, variable=var,
                                 command=lambda col=column_id: self._toggle_column_visibility(col))
            cb.pack(side=tk.LEFT, padx=5)
            self.column_visibility[column_id] = var

        # Сетка таблицы вывода данных
        self.tree.grid(row=2, column=0, sticky="nsew")
        vsb.grid(row=2, column=1, sticky="ns")

        # Веса сетки таблицы вывода данных
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(1, weight=1)

        # Создание функционала копирования данных из таблицы по хоткею
        self.tree.bind('<Control-c>', self._copy_selection)

        # Привязка события прокрутки к дереву
        self.tree.bind('<MouseWheel>', self._on_scroll)

        # Обработчик закрытия окна
        self.gui.protocol("WM_DELETE_WINDOW", self._on_app_closing)

        # Текстовая строка для вывода сообщений
        message_frame = ttk.Frame(stretchable_frame)
        message_frame.grid(row=2, column=0, padx=5, pady=5, sticky="sew")
        scrollbar_message = ttk.Scrollbar(message_frame)
        scrollbar_message.pack(side=tk.RIGHT, fill=tk.Y)
        self.message_area = tk.Text(message_frame, wrap=tk.WORD, height=5,
                                    yscrollcommand=scrollbar_message.set, state=tk.DISABLED)
        self.message_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_message.config(command=self.message_area.yview)

        # Информационная строка
        info_frame = ttk.Frame(stretchable_frame)
        info_frame.grid(row=3, column=0, padx=10, pady=5, sticky="we")

        # Создаем label-ссылку для телеграма
        telegram_label = ttk.Label(info_frame, text="tg:@danyagolovanov", cursor="hand2")
        telegram_label.pack(side=tk.RIGHT)

        # Создаем label для версии
        version_label = ttk.Label(info_frame, text=f"Версия: {__version__}    ")
        version_label.pack(side=tk.RIGHT)

        # Добавляем обработчик клика только для телеграм-ссылки
        telegram_label.bind("<Button-1>", lambda e: webbrowser.open("https://t.me/danyagolovanov"))

        # Фиксируем строки внутри фиксированного фрейма
        fixed_frame.grid_rowconfigure(0, weight=0)  # Строка 0 фиксирована
        fixed_frame.grid_rowconfigure(1, weight=0)  # Строка 1 фиксирована
        fixed_frame.grid_rowconfigure(2, weight=0)  # Строка 2 фиксирована
        fixed_frame.grid_columnconfigure(0, weight=0)  # Колонка фиксирована

        # Настраиваем веса строк в tree_frame
        tree_frame.grid_rowconfigure(0, weight=0)  # фрейм поиска - фиксированный
        tree_frame.grid_rowconfigure(1, weight=0)  # фрейм галочек - фиксированный
        tree_frame.grid_rowconfigure(2, weight=1)  # таблица - растягивается
        tree_frame.grid_columnconfigure(0, weight=1)  # колонка с таблицей - растягивается

        # Настраиваем строки внутри растягивающегося фрейма
        stretchable_frame.grid_rowconfigure(0, weight=1)  # Строка 0 растягивается
        stretchable_frame.grid_rowconfigure(1, weight=1)  # Строка 1 растягивается
        stretchable_frame.grid_columnconfigure(0, weight=1)  # Колонка растягивается

        # Настройка динамического изменения размеров
        self.gui.grid_rowconfigure(0, weight=1)
        self.gui.grid_columnconfigure(0, weight=0)
        self.gui.grid_columnconfigure(1, weight=1)

    def _on_app_closing(self):
        """Обработчик закрытия окна"""
        # Останавливаем все активные потоки
        if self.com_port_open:
            self._close_com_port()
        if self.udp_port_open:
            self._disconnect_udp()

        # Останавливаем логгер
        self.file_logger.stop()

        # Очищаем очереди
        self.log_queue.queue.clear()
        self.data_queue.queue.clear()

        # Закрываем главное окно
        self.gui.destroy()

    def _toggle_highlight(self):
        """Переключение режима подсветки"""
        if not self.search_entry.get().strip():
            self.update_message_area("Подсветка не включена. Введите текст для поиска.")
        else:
            self.highlight_enabled = not self.highlight_enabled
            if self.highlight_enabled:
                self.highlight_button.config(text="Выключить подсветку")
                # Блокируем строку ввода
                self.search_entry.config(state='readonly')
                self._apply_highlight_to_visible()
            else:
                self.highlight_button.config(text="Включить подсветку")
                # Разблокируем строку ввода
                self.search_entry.config(state='normal')
                self._restore_row_colors()

    def _restore_row_colors(self):
        """Восстановление чередующихся цветов строк"""
        local_flip_flop = False
        for idx, item in enumerate(self.tree.get_children()):
            if local_flip_flop:
                self.tree.item(item, tags=('evenrow',))
            else:
                self.tree.item(item, tags=('oddrow',))
            local_flip_flop = not local_flip_flop

    def _apply_highlight_to_visible(self):
        """Применение подсветки к видимым строкам"""
        if not self.highlight_enabled:
            return

        search_text = self.search_entry.get().strip().lower()
        if not search_text:
            return

        # Получаем информацию о видимой области
        first_visible = self.tree.yview()[0]
        last_visible = self.tree.yview()[1]
        total_rows = len(self.tree.get_children())

        # Вычисляем индексы видимых строк
        first_idx = int(first_visible * total_rows)
        last_idx = int(last_visible * total_rows) + 1

        # Получаем все элементы
        all_items = self.tree.get_children()

        # Создаем/обновляем тег для подсветки
        self.tree.tag_configure('highlight', background='#ADD8E6')  # Светло-синий цвет

        # Проходим только по видимым строкам
        for idx, item in enumerate(all_items):
            if first_idx <= idx <= last_idx:
                values = [str(value).lower() for value in self.tree.item(item)['values']]
                row_text = ' '.join(values)
                if search_text in row_text:
                    self.tree.item(item, tags=('highlight',))

    def _on_scroll(self, event):
        """Обработчик прокрутки таблицы"""
        self._apply_highlight_to_visible()

    def _check_tabs(self, event):
        """Обработчик изменения вкладки"""
        self.selected_tab = self.notebook.tab(self.notebook.select(), "text")
        self._check_encoding()

    def _open_file(self):
        """Открывает текстовый файл, читает его содержимое и отправляет данные в очередь."""
        if self.com_port_open or self.udp_port_open or self.mac_addr[0]:
            self.update_message_area(f"Для открытия файла, закройте соединение если работали с портом, если работали с файлом очистите экран.")
        else:
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
                    buffer = []
                    for line in file:
                        # Удаляем символы новой строки и пробелы
                        stripped_line = line.strip()
                        if stripped_line:
                            # Обрезка времени если данные сняты этой прогой через хекс
                            if stripped_line[2:3] == ':':
                                stripped_line = stripped_line[17:]
                            # Преобразуем строку в байты (если строка содержит HEX-представление данных)
                            try:
                                buffer.append(bytes.fromhex(stripped_line))
                            except ValueError:
                                self.update_message_area(f"Ошибка преобразования строки в байты: {stripped_line}")
                    # Добавляем все данные в очередь блоками
                    for chunk in buffer:
                        self.data_queue.put(chunk)
                self.file_open = True

                # Обновляем сообщение в GUI
                self.update_message_area(f"Файл {file_path} успешно прочитан и данные добавлены в очередь.")
                # Чистим экран перед открытием нового файла
                self._clear_screen()
                # Запускаем поток обработки данных, если он еще не работает
                self.data_proc.start_data_processing()
            except Exception as e:
                self.update_message_area(f"Ошибка при чтении файла: {e}")

    def _restart_logger(self):
        """Перезапускает логгер с созданием нового файла."""
        self.file_logger.stop()
        self.file_logger.start()
        self._clear_screen()
        self.update_message_area("Размер лог-файла превысил 5 МБ. Очищены счетчики и создан новый файл.")

    def _toggle_column_visibility(self, column_id):
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

    def _check_encoding(self):
        """Отключает столбцы и меняет их ширину в таблице данных в зависимости от выбранной кодировки."""
        if self.com_port_open or self.udp_port_open:
            self.update_message_area(f"Для смены кодировки, закройте соединение если работали с портом, если работали с файлом очистите экран.")
        else:
            # Проверка открытой вкладки на запрещенные кодировки
            if ((self.encoding.get() == "O2" and self.selected_tab == "UDP")
                    or (self.encoding.get() == "O2" and self.udp_port_open)):
                self.encoding.set("ASCII")
                self.update_message_area(f"Для UDP соединения кодировка О2 не поддерживается.")
            if self.encoding.get() == "O2":
                    # В кодировке о2 включаем все столбцы со стандартной заданной шириной
                    for column_id, column_name, column_width in self.data_columns:
                        self.tree.column(column_id, width=column_width, stretch=False)
                        self.column_visibility[column_id].set(True)
                        self._toggle_column_visibility(column_id)
            else:
                # Для кодировок ASCI и HEX выключаем все столбцы кроме времени и сырых данных
                self.tree.column("time", width=100, stretch=False, anchor="center")
                self.tree.column("raw_data", width=600)
                for column_id, column_name, column_width in self.data_columns[2:]:
                    self.column_visibility[column_id].set(False)
                    self._toggle_column_visibility(column_id)

    def _connect_udp(self):
        """Подключение к UDP"""
        if self.com_port_open:
            self.update_message_area(f"Закройте COM-порт для работы с UDP.")
        else:
            # Получаем IP и порт из полей ввода
            ip = self.udp_ip_entry.get()
            try:
                port = int(self.udp_port_entry.get())
            except ValueError:
                self.update_message_area("Некорректный порт")
                return
            # Очистка счетчиков
            self._clear_screen()
            try:
                # Открываем UDP соединение
                self.udp_connection.open_connection(ip, port)
                if self.udp_connection.is_open():
                    self.udp_port_open = True
                    self.udp_button.config(text="Отключить", command=self._disconnect_udp)
                    # Запускаем поток обработчика
                    self.data_proc.start_data_processing()
                    # Запускаем поток логера
                    self.file_logger.start()
                    self.update_message_area(f"UDP подключен {ip}:{port}")
            except Exception as e:
                self.update_message_area(f"Ошибка подключения UDP: {e}")

    def _disconnect_udp(self):
        """Отключение от UDP"""
        self.udp_port_open = False
        self.udp_connection.close_connection()
        self.data_proc.stop_data_processing()
        self.file_logger.stop()
        self.udp_button.config(text="Подключиться", command=self._connect_udp)
        self.update_message_area("UDP отключен")

    def _open_com_port(self):
        """Открытие последовательного порта"""
        if self.udp_port_open:
            self.update_message_area(f"Закройте UDP-соединение для работы с COM-портом.")
        else:
            # Очистка счетчиков, если не первая попытка открыть порт
            self._clear_screen()
            # Открываем порт с заданными параметрами
            self.serial_port.open_port(
                port=self.port.get(),
                baudrate=self.baud_rate.get(),
                bytesize=self.databits.get(),
                parity=self.parity.get(),
                stopbits=self.stop_bits.get(),
                timeout=0.1
            )
            if self.serial_port.is_open:
                self.com_port_open = True
                self.open_button.config(text="Закрыть порт", command=self._close_com_port)
                # Запускаем поток обработчика
                self.data_proc.start_data_processing()
                # Запускаем поток логера
                self.file_logger.start()
                self.update_message_area(f"Порт {self.port.get()} открыт.")
            return

    def _close_com_port(self):
        """Закрытие последовательного порта"""
        self.com_port_open = False
        self.serial_port.close_port()
        self.data_proc.stop_data_processing()
        self.file_logger.stop()
        self.open_button.config(text="Открыть порт", command=self._open_com_port)
        self.update_message_area("Порт закрыт.")

    def _refresh_ports(self):
        """Обновляет список доступных COM-портов."""
        available_ports = self.serial_port.get_available_ports()
        self.port_combobox['values'] = available_ports
        if available_ports:
            self.port_combobox.current(0)  # Устанавливаем первый порт как выбранный
        else:
            self.port.set("")  # Если портов нет, сбрасываем значение

    def _copy_selection(self, event):
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

    def _clear_screen(self):
        """Кнопка очистки окна вывода"""
        # Сбрасываем счетчики в списках (инициализируем заново)
        self.req_ack_counters = [0] * 32
        self.search_counters = [0] * 32
        self.get_id_counters = [0] * 32
        self.data_proc.counter_custom = 0
        self._update_counters()
        # Если закрыли-открыли порт (мак адреса не пустые с прошлого раза) сообщаем об очистке
        if self.mac_addr[0]:
            self.update_message_area("Экран очищен.")
        # Сброс мак-адресов
        self.mac_addr = [""] * 32
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _update_counters(self):
        """Обновление данных в таблице счетчиков."""
        # Обновляем данные в строках таблицы
        for i in range(32):
            # Получаем текущие значения счетчиков для каждого адреса
            req_ack_count = self.req_ack_counters[i]  # Массив счетчиков REQ/ACK
            search_count = self.search_counters[i]  # Массив счетчиков SEARCH
            get_id_count = str(self.get_id_counters[i])  # Массив счетчиков GETID
            mac_addr = self.mac_addr[i] # Массив мак-адресов GETID
            # Обновляем соответствующую строку в таблице
            self.counter_table.item(self.counter_table.get_children()[i], values=(i, req_ack_count, search_count, get_id_count, mac_addr))

    def update_message_area(self, message):
        """Запись в очередь гуи для информационной строки"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.gui_queue.put(('message', f"{timestamp} {message}"))

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
        """Обновляет таблицу вывода данными."""
        # Разделяем данные по формату
        parts = formatted_data.split('@', 6)
        if len(parts) == 7:
            values = (
                parts[0],  # Время
                parts[1],  # Сырые данные
                parts[2],  # Длина
                parts[3],  # Номер пакета
                parts[4],  # Направление
                parts[5],  # Тип пакета
                parts[6]  # Расшифрованные данные
            )
        elif len(parts) == 2:
            values = (parts[0], parts[1], "", "", "", "", "")
        else:
            values = ("", "", "", "", "", "", "")

        # Добавляем строку в таблицу
        item = self.tree.insert('', 'end', values=values)

        # Применяем чередование строк
        if self.flip_flop:
            self.tree.item(item, tags=('evenrow',))
        else:
            self.tree.item(item, tags=('oddrow',))
        self.flip_flop = not self.flip_flop

        # Применяем подсветку сразу при добавлении, если она включена
        if self.highlight_enabled:
            search_text = self.search_entry.get().strip().lower()
            if search_text:
                row_text = ' '.join(str(v).lower() for v in values)
                if search_text in row_text:
                    self.tree.item(item, tags=('highlight',))

        # Выполняем автопрокрутку, только если галочка включена
        if self.autoscroll_enabled.get():
            self.tree.yview_moveto(1.0)  # Прокрутка в самый низ

        # Удаляем старые строки, если превышен лимит
        if len(self.tree.get_children()) > self.MAX_TABLE_SIZE:
            self.tree.delete(self.tree.get_children()[0])
            # Если автопрокрутка отключена, сдвигаем вверх по мере удаления строк, чтобы зафиксировать экран
            if not self.autoscroll_enabled.get():
                self.tree.yview_scroll(number=-1, what="units")

    def _process_gui_queue(self):
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
        if self.serial_port.is_open or self.file_open:
            # Обновляем GUI с накопленными данными
            if accumulated_message_data:
                self._update_message_area("\n".join(accumulated_message_data))
            if accumulated_text_data:
                for text_data in accumulated_text_data:
                    self._update_data_area(text_data)
            self._update_counters()
        if self.file_open:
            # Стираем флаг обновления гуи после открытия файла
            if self.data_queue.empty() and self.gui_queue.empty():
                self.update_message_area("Расшифровка файла завершена")
                self.file_open = False
                # Останавливаем поток после расшифровки файла
                self.data_proc.stop_data_processing()
        # Повторный вызов отрисовки
        self.gui.after(self.gui_update_timeout, self._process_gui_queue)

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

# Отладка
# py -m cProfile -o profile_output.prof cum_port.py
# snakeviz profile_output.prof

# kernprof -l cum_port.py
# py -m line_profiler cum_port.py.lprof
