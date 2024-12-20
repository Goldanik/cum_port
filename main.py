import FileLogger
import tkinter as tk
from tkinter import ttk
import serial
import threading
import datetime
import queue

class SerialMonitorGUI:
    def __init__(self, master):
        self.master = master
        master.title("O2 Monitor")
        # Создаем очередь
        self.log_queue = queue.Queue()
        # Делимся очередью с логером
        self.logger = FileLogger.FileLogger(log_queue=self.log_queue)
        # Переменные для настроек COM-порта
        self.port = tk.StringVar(value="COM10")
        self.baud_rate = tk.IntVar(value=115200)
        self.databits = tk.IntVar(value=8)
        self.parity = tk.StringVar(value="N")
        self.stop_bits = tk.IntVar(value=1)
        self.encoding = tk.StringVar(value="O2")
        self.skip_requests = True
        # Паттерны ориона2
        self.req_pattern1 = "ff011f6c"
        self.req_pattern2 = "ff021f48"
        self.ack_pattern1 = "6f6c"
        self.ack_pattern2 = "6f1d"
        self.custom_skip_pattern = tk.StringVar(value="")  # Для пользовательского шаблона
        # Счетчики
        self.counter_req = 0
        self.counter_ack = 0
        self.counter_search = 0
        self.counter_custom = 0
        # Буфер для накопления данных
        self.data_buffer = ""
        self.MAX_BUFFER_SIZE = 1024 * 1024  # 1 MB
        self.MAX_TABLE_SIZE = 10000
        # Создание элементов интерфейса
        self.create_widgets()
        # Объекты последовательного порта
        self.ser = None
        self.serial_thread = None
        self.stop_event = threading.Event()
        # Поток обработки данных
        self.data_process = None
        self.data_process_thread = None
        self.data_process_event = threading.Event()

    # Создание графического окна
    def create_widgets(self):
         # Frame для настроек COM-порта
        settings_frame = ttk.LabelFrame(self.master, text="Настройки COM-порта")
        settings_frame.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        # Labels и Entry для параметров
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
        self.open_button = ttk.Button(settings_frame, text="Открыть порт", command=self.open_port)
        self.open_button.grid(row=5, column=0, pady=(5, 0))

        # Clear Screen button
        self.clear_button = ttk.Button(settings_frame, text="Очистить экран", command=self.clear_screen)
        self.clear_button.grid(row=6, column=0, pady=(5, 0))

        # Add O2 settings
        o2_frame = ttk.LabelFrame(self.master, text="Функции Орион 2")
        o2_frame.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        # Сounters display
        self.counter_frame = ttk.LabelFrame(o2_frame, text="Счетчики пропущенных запросов")
        self.counter_frame.grid(row=7, column=0, pady=(5, 0), sticky="w")

        # В counter_frame добавим поле для пользовательского шаблона
        self.custom_pattern_frame = ttk.Frame(self.counter_frame)
        self.custom_pattern_frame.grid(row=4, column=0, padx=5, pady=2, sticky="w")

        ttk.Label(self.custom_pattern_frame, text="Свой шаблон:").grid(row=0, column=0, padx=(0, 5))
        self.custom_pattern_entry = ttk.Entry(self.custom_pattern_frame, textvariable=self.custom_skip_pattern, width=10)
        self.custom_pattern_entry.grid(row=0, column=1)

        self.counter_label1 = ttk.Label(self.counter_frame, text="IN: 0")
        self.counter_label1.grid(row=0, column=0, padx=5, pady=2, sticky="w")

        self.counter_label2 = ttk.Label(self.counter_frame, text="ACK: 0")
        self.counter_label2.grid(row=1, column=0, padx=5, pady=2, sticky="w")

        self.counter_label3 = ttk.Label(self.counter_frame, text="SEARCH: 0")
        self.counter_label3.grid(row=2, column=0, padx=5, pady=2, sticky="w")

        # Добавим счетчик для пользовательского шаблона
        self.counter_label_custom = ttk.Label(self.counter_frame, text="Свой шаблон: 0")
        self.counter_label_custom.grid(row=3, column=0, padx=5, pady=2, sticky="w")

        ttk.Radiobutton(o2_frame, text="O2", variable=self.encoding, value="O2").grid(row=0, column=0,
                                                                                             sticky="w")
        # Кнопка "Пропускать запросы"
        self.skip_button = ttk.Button(o2_frame, text="Включен пропуск запросов", command=self.toggle_skip_requests)
        self.skip_button.grid(row=6, column=0, columnspan=2, pady=(5, 0))

        # Настройки кодировки
        encoding_frame = ttk.LabelFrame(self.master, text="Кодировка")
        encoding_frame.grid(row=0, column=2, padx=10, pady=10, sticky="w")

        ttk.Radiobutton(encoding_frame, text="HEX", variable=self.encoding, value="HEX").grid(row=1, column=0, sticky="w")
        ttk.Radiobutton(encoding_frame, text="BIN", variable=self.encoding, value="BIN").grid(row=2, column=0, sticky="w")
        ttk.Radiobutton(encoding_frame, text="ASCII", variable=self.encoding, value="ASCII").grid(row=3, column=0, sticky="w")

        tree_frame = ttk.Frame(self.master)
        tree_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="nsew")

        # Create Treeview
        self.tree = ttk.Treeview(tree_frame, columns=("time", "raw_data", "decoded_data"), show="headings")
        self.tree.heading("time", text="Время")
        self.tree.heading("raw_data", text="Сырые данные")
        self.tree.heading("decoded_data", text="Расшифрованные данные")

        # Configure column widths
        self.tree.column("time", width=100)
        self.tree.column("raw_data", width=300)
        self.tree.column("decoded_data", width=300)

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
        message_frame = ttk.Frame(self.master)
        message_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="nsew")
        scrollbar_message = ttk.Scrollbar(message_frame)
        scrollbar_message.pack(side=tk.RIGHT, fill=tk.Y)
        self.message_area = tk.Text(message_frame, wrap=tk.WORD, height=5, yscrollcommand=scrollbar_message.set, state=tk.DISABLED)
        self.message_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_message.config(command=self.message_area.yview)

        # Настройка динамического изменения размеров
        self.master.grid_rowconfigure(1, weight=1)
        self.master.grid_columnconfigure(0, weight=1)

    # Открытие последовательного порта
    def open_port(self):
        try:
            # Закрываем порт, если он уже открыт
            if self.ser and self.ser.is_open:
                self.close_port()

            # Открываем порт с заданными параметрами
            self.ser = serial.Serial(
                port=self.port.get(),
                baudrate=self.baud_rate.get(),
                bytesize=self.databits.get(),
                parity=self.parity.get(),
                stopbits=self.stop_bits.get(),
                timeout=0.01  # Timeout для чтения данных (1 секунда)
            )

            self.open_button.config(text="Закрыть порт", command=self.close_port)
            self.start_reading()
            # Запускаем поток логгера
            self.logger.start_log_thread()
            self.master.after(0, self.update_message_area, f"Порт {self.port.get()} открыт.")
        except serial.SerialException as e:
            self.master.after(0, self.update_message_area, f"Ошибка открытия порта: {e}")
            return

    # Закрытие последовательного порта
    def close_port(self):
        try:
            # Сигнализируем потоку о завершении
            self.stop_event.set()
            # Добавляем очистку буфера
            self.data_buffer = ""

            if self.serial_thread and self.serial_thread.is_alive():
                self.serial_thread.join(timeout=1.0)

            if self.ser and self.ser.is_open:
                # Очищаем буферы порта перед закрытием
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                self.ser.close()

            self.open_button.config(text="Открыть порт", command=self.open_port)
            self.master.after(0, self.update_message_area, "Порт закрыт.")
            # Останавливаем поток логгера
            self.logger.stop_log_thread()
        except Exception as e:
            self.master.after(0, self.update_message_area, f"Ошибка закрытия порта: {e}")
        finally:
            # Очищаем ссылку на поток
            self.serial_thread = None

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
        self.master.clipboard_clear()
        self.master.clipboard_append(copied_string)

    # Кнопка очистки окна вывода
    def clear_screen(self):
        self.counter_req = 0
        self.counter_ack = 0
        self.counter_search = 0
        self.counter_custom = 0
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
        self.counter_label1.config(text=f"IN: {self.counter_req}")
        self.counter_label2.config(text=f"ACK: {self.counter_ack}")
        self.counter_label3.config(text=f"SEARCH: {self.counter_search}")
        custom_pattern = self.custom_skip_pattern.get()
        if custom_pattern:
            self.counter_label_custom.config(text=f"Свой шаблон ({custom_pattern}): {self.counter_custom}")
        else:
            self.counter_label_custom.config(text="Свой шаблон: 0")

    # Обновление информационной строки
    def update_message_area(self, message):
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
        """Обновление данных в дереве и отправка их в очередь для записи в лог"""
        # Разделяем данные на время и содержимое
        parts = formatted_data.split('^ ', 1)
        if len(parts) == 2:
            timestamp = parts[0]
            raw_data = parts[1].strip()

            # Здесь можно добавить декодированные данные
            decoded_data = ""  # Оставляем пустым для примера

            # Обновляем дерево (GUI) из главного потока
            self.master.after(0, lambda: self.tree.insert('', 0, values=(timestamp, raw_data, decoded_data)))

            # Ограничиваем количество строк в дереве
            if len(self.tree.get_children()) > self.MAX_TABLE_SIZE:
                self.tree.delete(self.tree.get_children()[-1])

            # Отправляем данные в очередь для записи в лог через self.log_queue
            try:
                self.log_queue.put_nowait(f"{timestamp}\t{raw_data}\t{decoded_data}")
            except queue.Full:
                self.master.after(0, self.update_message_area, "Очередь логов переполнена. Данные потеряны.")

    # Интерпретатор данных в соответствии с кодировкой
    def encodings_handler(self):
        """Обработка кодировок данных."""
        # Значение по умолчанию
        decoded_data = ""
        while self.data_process_event.is_set():
            if self.encoding.get() == "O2":
                # Передаем данные напрямую в парсер
                self.orion2_parser(self.data_buffer.encode('utf-8').hex())
            elif self.encoding.get() == "HEX":
                decoded_data = self.data_buffer.encode('utf-8').hex()
            elif self.encoding.get() == "BIN":
                decoded_data = ''.join(format(byte, '08b') for byte in self.data_buffer)
            elif self.encoding.get() == "ASCII":
                try:
                    decoded_data = self.data_buffer.encode("ascii", errors="ignore")
                except UnicodeDecodeError:
                    decoded_data = self.data_buffer.encode("latin-1", errors="ignore")
            if self.encoding.get() != "O2":
                timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")
                self.master.after(0, self.update_text_area, f"{timestamp}^ {decoded_data}")

    # Парсер пакетов для орион2
    def orion2_parser(self, data):
        """Парсер для кодировки Orion2."""
        processed_data = ""  # Строка для хранения обработанных данных

        while 'ff' in self.data_buffer:
            # Ищем 'ff', начиная со 2 символа, если буфер достаточно длинный
            next_ff = self.data_buffer.find('ff', 2 if len(self.data_buffer) > 2 else 0)

            if next_ff == -1:
                # Если больше нет маркеров, берём весь оставшийся буфер
                packet = self.data_buffer
                self.data_buffer = ""
            elif next_ff % 2 != 0:
                # Если длина в битах нечетная, вероятно пакет разбит не правильно (например из-за F на конце пакета)
                # в этом случае дополняем пакет до четного размера и парсинг следующего начинаем со следующего элемента
                packet = self.data_buffer[:next_ff + 1]
                self.data_buffer = self.data_buffer[next_ff + 1:]
            else:
                # Берём данные до следующего маркера
                packet = self.data_buffer[:next_ff]
                self.data_buffer = self.data_buffer[next_ff:]

            if self.skip_requests:
                # Подсчёт и удаление шаблонов из целого пакета
                self.counter_req += packet.count(self.req_pattern1) + packet.count(self.req_pattern2)
                self.counter_ack += packet.count(self.ack_pattern1) + packet.count(self.ack_pattern2)
                # Временный функционал подсчета пакетов SEARCH известной длины
                if next_ff == 14:
                    self.counter_search += 1

                custom_pattern = self.custom_skip_pattern.get().lower()

                if custom_pattern: # and all(c in "0123456789abcdef"for c in custom_pattern):
                    try:
                        self.counter_custom += packet.count(custom_pattern)
                        packet = packet.replace(custom_pattern, "")
                    except Exception as e:
                        self.master.after(0, self.update_message_area, f"Ошибка обработки пользовательского шаблона: {e}")
                # else:
                #     self.update_message_area("Некорректный пользовательский шаблон")

                packet = packet.replace(self.req_pattern1, "")
                packet = packet.replace(self.ack_pattern1, "")
                packet = packet.replace(self.req_pattern2, "")
                packet = packet.replace(self.ack_pattern2, "")
                # Временный функционал отрезки пакетов SEARCH известной длины
                if next_ff == 14:
                    packet = ""

                self.master.after(0, self.update_counters)

            if packet.strip():
                timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")
                formatted_data = f"{timestamp}^ {packet}"
                processed_data += formatted_data + "\n"  # Добавляем обработанные данные к строке

        if processed_data:
            self.master.after(0, self.update_text_area, processed_data)  # Обновляем text area один раз с всеми данными

    # Запуск потока чтения из последовательного порта
    def start_reading(self):
        self.stop_event.clear()  # Сбрасываем флаг остановки
        self.serial_thread = threading.Thread(target=self.read_serial, daemon=True)
        self.serial_thread.start()

    # Чтение данных из последовательного порта
    def read_serial(self):
        """Чтение данных из порта."""
        while not self.stop_event.is_set():
            try:
                # Если поток чтения запущен и порт не закрыт
                if self.ser.in_waiting > 0 and not self.stop_event.is_set():
                    try:
                        # Получение всех байтов из очереди входящих
                        data = self.ser.read(self.ser.in_waiting)
                        # Складываем данные в буфер
                        self.data_buffer += data
                    except serial.SerialException as e:
                        # Выходим из цикла чтения, если порт закрыт
                        if not self.stop_event.is_set():
                            self.master.after(0, self.update_message_area, f"Ошибка чтения данных: {e}")
                            self.close_port()
                            break
                    # Сигнализируем что пора начать обработку
                    self.data_process_event.set()
                    # Проверка размера буфера
                    if len(self.data_buffer) > self.MAX_BUFFER_SIZE:
                        processed_data = self.data_buffer[:self.MAX_BUFFER_SIZE]
                        self.data_buffer = self.data_buffer[self.MAX_BUFFER_SIZE:]
                        self.master.after(0, self.update_message_area, "Предупреждение: буфер данных был очищен из-за превышения размера")
            # Общий обработчик ошибок
            except Exception as e:
                if not self.stop_event.is_set():
                    self.master.after(0, self.update_message_area, f"Критическая ошибка: {e}")
                    self.close_port()
                    break

root = tk.Tk()
app = SerialMonitorGUI(root)
root.mainloop()