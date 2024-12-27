import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports
import queue

# Свои реализации
import serial_port
import file_logger
import data_processing

class SerialMonitorGUI:
    def __init__(self, gui, logger_queue, data_proc_queue):
        # Кнопки
        self.refresh_ports_button = None
        self.skip_button = None
        self.skip_requests = True
        self.clear_button = None
        self.open_button = None
        # Прочая
        self.counter_table = None
        self.port_combobox = None
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
        available_ports = self.get_available_ports()
        if available_ports:
            self.port.set(available_ports[0])

        # Присваиваем себе функционал ткинтера
        self.gui = gui
        self.gui.title("CUM_port ver.beta.1")
        self.gui.geometry("1280x768")
        self.gui.minsize(1280,768)
        # Очередь для элементов GUI
        self.gui_queue = queue.Queue()
        # Обновляем GUI по таймеру
        self.gui.after(200, self.process_gui_queue)

        # Пользовательский шаблон для парсера
        self.custom_skip_pattern = tk.StringVar(value="")

        # Размер таблицы на экране
        self.MAX_TABLE_SIZE = 50000

        # Создание элементов интерфейса
        self.create_widgets()

    # Создание графического окна
    def create_widgets(self):
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
        self.port_combobox['values'] = self.get_available_ports()  # Устанавливаем список портов
        self.port_combobox.state(['readonly'])  # Только выбор из списка

        # Кнопка обновить список портов
        self.refresh_ports_button = ttk.Button(settings_frame, text=u'\u21bb', command=self.refresh_ports, width=4)
        self.refresh_ports_button.grid(row=0, column=2, padx=5)

        ttk.Label(settings_frame, text="Скорость:").grid(row=1, column=0, sticky="w")
        ttk.Combobox(settings_frame, textvariable=self.baud_rate, values=["115200", "57600", "38400", "19200", "9600"], width=8).grid(row=1, column=1, padx=5)

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
        self.counter_table = ttk.Treeview(self.counter_frame, columns=("address", "req_ack", "search", "get_id", "give_addr"), show="headings", height=10)
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
        for i in range(33):
            self.counter_table.insert("", "end", values=(i, 0, 0, 0))

        # Добавим счетчик для пользовательского шаблона
        self.counter_label_custom = ttk.Label(self.counter_frame, text="Свой шаблон: не задан")
        self.counter_label_custom.grid(row=3, column=0, padx=5, pady=2, sticky="w")

        # Кнопка "Пропускать запросы"
        self.skip_button = ttk.Button(o2_frame, text="Включен пропуск запросов", command=self.toggle_skip_requests)
        self.skip_button.grid(row=6, column=0, columnspan=2, pady=(5, 0), sticky="nw")

        # Настройки кодировки
        encoding_frame = ttk.LabelFrame(fixed_frame, text="Кодировка")
        encoding_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nwe")

        # Кнопки выбора кодировок
        ttk.Radiobutton(encoding_frame, text="O2", variable=self.encoding, value="O2").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(encoding_frame, text="HEX", variable=self.encoding, value="HEX").grid(row=1, column=0, sticky="w")
        ttk.Radiobutton(encoding_frame, text="BIN", variable=self.encoding, value="BIN").grid(row=2, column=0, sticky="w")
        ttk.Radiobutton(encoding_frame, text="ASCII", variable=self.encoding, value="ASCII").grid(row=3, column=0, sticky="w")

        tree_frame = ttk.Frame(stretchable_frame)
        tree_frame.grid(row=0, column=0, rowspan=2, padx=10, pady=(0, 10), sticky="nsew")

        # Create Treeview
        self.tree = ttk.Treeview(tree_frame, columns=("time", "direction", "raw_data", "packet_type", "decoded_data"), show="headings")
        self.tree.heading("time", text="Время")
        self.tree.heading("direction", text="Направление")
        self.tree.heading("raw_data", text="Сырые данные")
        self.tree.heading("packet_type", text="Тип пакета")
        self.tree.heading("decoded_data", text="Расшифрованные данные")

        # Configure column widths
        self.tree.column("time", width=100, stretch=False, anchor="center")
        self.tree.column("direction", width=250, stretch=False, anchor="center")
        self.tree.column("raw_data", width=300)
        self.tree.column("packet_type", width=100, anchor="center")
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
        message_frame = ttk.Frame(stretchable_frame)
        message_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="sew")
        scrollbar_message = ttk.Scrollbar(message_frame)
        scrollbar_message.pack(side=tk.RIGHT, fill=tk.Y)
        self.message_area = tk.Text(message_frame, wrap=tk.WORD, height=5, yscrollcommand=scrollbar_message.set, state=tk.DISABLED)
        self.message_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_message.config(command=self.message_area.yview)

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

    def get_available_ports(self):
        """Возвращает список доступных COM-портов."""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def refresh_ports(self):
        """Обновляет список доступных COM-портов."""
        available_ports = self.get_available_ports()
        self.port_combobox['values'] = available_ports
        if available_ports:
            self.port_combobox.current(0)  # Устанавливаем первый порт как выбранный
        else:
            self.port.set("")  # Если портов нет, сбрасываем значение

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
        # Сбрасываем счетчики в списках (инициализируем заново)
        self.req_ack_counters = [0] * 32
        self.search_counters = [0] * 32
        self.get_id_counters = [0] * 32
        self.give_addr = [0] * 32
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
        parts = formatted_data.split('  ', 4)
        if len(parts) == 5:
            timestamp = parts[0]
            direction = parts[1]
            raw_data = parts[2]
            packet_type = parts[3]
            decoded_data = parts[4]
        elif len(parts) == 3:
            timestamp = parts[0]
            direction = ""
            raw_data = parts[1]
            packet_type = ""
            decoded_data = ""

        # Обновляем дерево (GUI) из главного потока
        self.tree.insert('', 'end', values=(timestamp, direction, raw_data, packet_type, decoded_data))
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
        if self.serial_port.ser and self.serial_port.ser.is_open:
            # Обновляем GUI с накопленными данными
            if accumulated_message_data:
                self._update_message_area("\n".join(accumulated_message_data))
            if accumulated_text_data:
                for text_data in accumulated_text_data:
                    self._update_text_area(text_data)
            #self._update_message_area(f"Размер очереди гуи: {self.data_queue.qsize()}")
            self.update_counters()
        # Повторный вызов через 100 мс
        self.gui.after(200, self.process_gui_queue)

    def calc_crc7(self, old_crc, in_byte):
        temp = 0
        in_byte ^= old_crc

        if in_byte & 0x01:
            temp ^= 0x49
        if in_byte & 0x02:
            temp ^= 0x25
        if in_byte & 0x04:
            temp ^= 0x4A
        if in_byte & 0x08:
            temp ^= 0x23
        if in_byte & 0x10:
            temp ^= 0x46
        if in_byte & 0x20:
            temp ^= 0x3B
        if in_byte & 0x40:
            temp ^= 0x76
        if in_byte & 0x80:
            temp ^= 0x5B

        return temp

    def calculate_crc7(self, data):
        crc7 = 0xFF
        for byte in data:
            crc7 = self.calc_crc7(crc7, byte)
        return crc7

# Очередь логера
log_queue = queue.Queue()
# Очередь данных последовательного порта
data_queue = queue.Queue()
# Создаем главное окно
main = tk.Tk()
# Создаем один экземпляр GUI
app = SerialMonitorGUI(main, logger_queue=log_queue, data_proc_queue=data_queue)
# data = [0x01, 0x1f]  # Пример массива данных
# crc7_result = app.calculate_crc7(data)
# print(f"CRC7: {crc7_result:#04x}")
# Запускаем главный цикл
main.mainloop()