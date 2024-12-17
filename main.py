import tkinter as tk
from tkinter import ttk
import serial
import threading
import datetime
import crcmod

class SerialMonitorGUI:
    def __init__(self, master):
        self.master = master
        master.title("COM Port Monitor")

        # Переменные для настроек COM-порта
        self.port = tk.StringVar(value="COM10")
        self.baudrate = tk.IntVar(value=115200)
        self.databits = tk.IntVar(value=8)
        self.parity = tk.StringVar(value="N")
        self.stopbits = tk.IntVar(value=1)
        self.encoding = tk.StringVar(value="HEX")

        # Создание элементов интерфейса
        self.create_widgets()

        # Serial port object
        self.ser = None
        self.serial_thread = None
        self.stop_event = threading.Event()

        # Буфер для данных
        self.data_buffer = ""
        self.data_coded = "ff021f486f1dff021f486f1dff011f6c6f6cff021f486f1dff011f6c6f6cff011f6c6f6cff021f486f1dff011f6c6f6cff021f486f1dff021f486f1dff011f6c6f6cff021f486f1dff011f6c6f6cff011f6c6f6cff021f486f1dff011f6c6f6cff021f486f1dff011f6c6f6cff021f486f1dff011f6c6f6cff011f6c6f6cff021f486f1dff011f6c6f6cff021f486f1dff021f486f1dff011f6c6f6cff021f486f1dff011f6c6f6cff011f6c6f6cff021f486f1dff011f6c6f6cff021f486f1dff021f486f1dff011f6c6f6cff021f486f1dff011f6c6f6cff011f6c6f6cff021f486f1dff011f6c6f6cff021f486f1dff021f486f1dff011f6c6f6cff021f486f1dff011f6c6f6cff021f486f1dff011f6c6f6cff8faf2a"


    def create_widgets(self):
         # Frame для настроек COM-порта
        settings_frame = ttk.LabelFrame(self.master, text="Настройки COM-порта")
        settings_frame.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        # Labels и Entry для параметров
        ttk.Label(settings_frame, text="Порт:").grid(row=0, column=0, sticky="w")
        ttk.Entry(settings_frame, textvariable=self.port, width=10).grid(row=0, column=1, padx=5)

        ttk.Label(settings_frame, text="Скорость:").grid(row=1, column=0, sticky="w")
        ttk.Entry(settings_frame, textvariable=self.baudrate, width=10).grid(row=1, column=1, padx=5)

        ttk.Label(settings_frame, text="Биты данных:").grid(row=2, column=0, sticky="w")
        ttk.Combobox(settings_frame, textvariable=self.databits, values=[5, 6, 7, 8], width=8).grid(row=2, column=1, padx=5)

        ttk.Label(settings_frame, text="Четность:").grid(row=3, column=0, sticky="w")
        ttk.Combobox(settings_frame, textvariable=self.parity, values=["N", "E", "O", "M", "S"], width=8).grid(row=3, column=1, padx=5)

        ttk.Label(settings_frame, text="Стоп-биты:").grid(row=4, column=0, sticky="w")
        ttk.Combobox(settings_frame, textvariable=self.stopbits, values=[1, 1.5, 2], width=8).grid(row=4, column=1, padx=5)

        # Add encoding settings
        encoding_frame = ttk.LabelFrame(self.master, text="Кодировка")
        encoding_frame.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        ttk.Radiobutton(encoding_frame, text="HEX", variable=self.encoding, value="HEX").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(encoding_frame, text="BIN", variable=self.encoding, value="BIN").grid(row=1, column=0, sticky="w")
        ttk.Radiobutton(encoding_frame, text="ASCII", variable=self.encoding, value="ASCII").grid(row=2, column=0, sticky="w")


        # Кнопка "Открыть порт"
        self.open_button = ttk.Button(settings_frame, text="Открыть порт", command=self.open_port)
        self.open_button.grid(row=5, column=0, columnspan=2, pady=(10, 0))

        # Text widget для вывода данных с полосой прокрутки
        text_frame = ttk.Frame(self.master)
        text_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="nsew")

        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_area = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set)
        self.text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar.config(command=self.text_area.yview)

        # Настройка динамического изменения размеров
        self.master.grid_rowconfigure(1, weight=1)
        self.master.grid_columnconfigure(0, weight=1)


    def open_port(self):
        try:
            # Закрываем порт, если он уже открыт
            if self.ser and self.ser.is_open:
                self.close_port()

            # Открываем порт с заданными параметрами
            self.ser = serial.Serial(
                port=self.port.get(),
                baudrate=self.baudrate.get(),
                bytesize=self.databits.get(),
                parity=self.parity.get(),
                stopbits=self.stopbits.get(),
                timeout=1  # Timeout для чтения данных (1 секунда)
            )

            self.open_button.config(text="Закрыть порт", command=self.close_port)
            self.start_reading()
        except serial.SerialException as e:
            self.text_area.insert(tk.END, f"Ошибка открытия порта: {e}\n")
            return
        self.text_area.insert(tk.END, self.data_coded + "\n")
        # data_mass = self.data_coded.encode(encoding = 'HEX')
        # input_data = bytes([0xFF, 0x44, 0x41, 0x54, 0x41, 0x08, 0x01, 0x02, 0x03, 0xFE, 0x01, 0xFE, 0x02, 0x12, 0x34])
        # input_data2 = bytes([0xff,0x02,0x1f,0x48,0x6f,0x1d])
        # data_decoded = self.parse_packet(input_data2)
        # self.text_area.insert(tk.END, data_decoded + "\n")


    def close_port(self):
        try:
            self.stop_event.set()  # Сигнализируем потоку о завершении
            if self.serial_thread:
                self.serial_thread.join()  # Дожидаемся завершения потока
            if self.ser and self.ser.is_open:  # Проверяем, открыт ли порт перед закрытием
                self.ser.close()
            self.open_button.config(text="Открыть порт", command=self.open_port)
            self.text_area.insert(tk.END, "Порт закрыт.\n")
        except Exception as e:
            self.text_area.insert(tk.END, f"Ошибка закрытия порта: {e}\n")

    def parse_packet(self, data):
        """
        Парсит входящий пакет данных согласно описанным требованиям.

        :param data: Входящий поток байтов (bytes).
        :return: Разобранные данные или сообщение об ошибке.
        """
        if not data:
            return "Нет данных для парсинга."

        # Этап 1: Замена последовательностей 0xFE, 0x01 -> 0xFF и 0xFE, 0x02 -> 0xFE
        parsed_data = bytearray()
        i = 0
        while i < len(data):
            if data[i] == 0xFE:
                if i + 1 < len(data):
                    if data[i + 1] == 0x01:
                        parsed_data.append(0xFF)
                        i += 2
                    elif data[i + 1] == 0x02:
                        parsed_data.append(0xFE)
                        i += 2
                    else:
                        parsed_data.append(data[i])
                        i += 1
                else:
                    parsed_data.append(data[i])
                    i += 1
            else:
                parsed_data.append(data[i])
                i += 1

        # Этап 2: Проверка стартового символа 0xFF
        if parsed_data[0] != 0xFF:
            return "Ошибка: отсутствует стартовый символ 0xFF."

        # Этап 3: Извлечение управляющего пакета (3 байта после стартового символа)
        if len(parsed_data) < 4:
            return "Ошибка: пакет слишком короткий для извлечения управляющего пакета."

        # Распознаем тип управляющего пакета
        if parsed_data[1] == 0x02:
            session_type = "Передача данных"
        elif parsed_data[1] == 0x01:  # "INQ" - запрос данных
            session_type = "Запрос данных"
        else:
            return f"Ошибка: неизвестный управляющий пакет {parsed_data[1]}."

        # Этап 4: Парсинг информационной телеграммы
        if session_type == "Передача данных":
            if len(parsed_data) < 5:
                return "Ошибка: отсутствует информационная телеграмма."

            # Поле длины Len (1 байт)
            len_field = parsed_data[2]
            if len_field > len(parsed_data) - 5:
                return f"Ошибка: длина телеграммы указана некорректно {parsed_data[2]}."

            # Заголовок и содержательная часть
            payload = parsed_data[5:5 + len_field - 3]  # Заголовок + содержательная часть
            header = payload[:-2]  # Исключаем CRC-16
            crc_received = int.from_bytes(payload[-2:], "big")  # Последние 2 байта - CRC-16

            # Этап 5: Проверка CRC-16
            crc_calculator = crcmod.predefined.Crc('crc-16-modbus')  # Используем стандартный CRC-16 Modbus
            crc_calculator.update(parsed_data[4:4 + len_field - 2])  # Вычисляем CRC-16
            crc_calculated = crc_calculator.crcValue

            if crc_calculated != crc_received:
                return f"Ошибка: неверная контрольная сумма. Ожидалось {crc_calculated}, получено {crc_received}."

            # Возвращаем разобранные данные
            return {
                "Тип сессии": session_type,
                "Длина телеграммы": len_field,
                "Заголовок": header,
                "Содержательная часть": payload[:-2],
                "CRC-16": crc_received
            }

        elif session_type == "Запрос данных":
            # Запрос данных не содержит телеграммы, возвращаем информацию о запросе
            return {
                "Тип сессии": session_type,
                "Управляющий пакет": control_packet
            }

        return "Ошибка: неизвестный тип сессии."

    def read_serial(self):
        while not self.stop_event.is_set():
            try:
                if self.ser.in_waiting > 0:
                    data = self.ser.read(self.ser.in_waiting)

                    if self.encoding.get() == "HEX":
                        decoded_data = data.hex()
                    elif self.encoding.get() == "BIN":
                        decoded_data = ''.join(format(byte, '08b') for byte in data)
                    else:  # ASCII
                        try:
                            decoded_data = data.decode("ascii", errors="ignore")
                        except UnicodeDecodeError:
                            decoded_data = data.decode("latin-1", errors="ignore")  # or other encoding if known

                    # self.data_buffer += decoded_data

                    # Разбиваем буфер на строки по 0xFF (255 в десятичном виде)
                    lines = []
                    start = 0
                    for i in range(len(decoded_data)):
                        if decoded_data[i:i+2].lower() == "ff":  # or if data_buffer[i:i+2] == "ff" if HEX mode
                            lines.append(decoded_data[start:i])
                            start = i + 1
                    lines.append(decoded_data[start:])  # Add last part
                    # self.data_buffer = ""  # Clear buffer

                    for line in lines:  # output each line with timestamp
                        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")
                        formatted_data = f"{timestamp}: {line}"
                        self.master.after(0, self.update_text_area, formatted_data)

            except serial.SerialException as e:
                self.master.after(0, self.update_text_area, f"Ошибка чтения данных: {e}\n")
                self.close_port()
                break


    def update_text_area(self, formatted_data):
        self.text_area.insert(tk.END, formatted_data + "\n")
        self.text_area.see(tk.END)  # Автоматическая прокрутка к концу


    def start_reading(self):
        self.stop_event.clear()  # Сбрасываем флаг остановки
        self.serial_thread = threading.Thread(target=self.read_serial, daemon=True)
        self.serial_thread.start()


root = tk.Tk()
app = SerialMonitorGUI(root)
root.mainloop()

# Основные изменения и дополнения:

# Обработка ошибок: Добавлены блоки try-except для обработки ошибок открытия/закрытия порта и чтения данных.
# Декодирование: Добавлена декодировка decode('utf-8', errors='replace') для преобразования байтов в строку. errors='replace' заменяет некорректные символы, предотвращая ошибки.
# Закрытие порта: Реализована функция close_port() для корректного закрытия порта и остановки потока чтения.
# Поток чтения: Чтение данных из COM-порта происходит в отдельном потоке (threading), чтобы не блокировать графический интерфейс. Используется daemon=True, чтобы поток завершался при закрытии основного приложения.
# Обновление интерфейса: self.master.after(0, self.update_text_area, data) используется для обновления text_area в главном потоке, что необходимо для корректной работы Tkinter.
# Автопрокрутка: self.text_area.see(tk.END) добавлена для автоматической прокрутки к последней строке в text_area.
# Флаг остановки: threading.Event() используется для корректной остановки потока чтения при закрытии порта.
#Импорт datetime: Добавлен импорт модуля datetime для работы с временем.
#Получение метки времени: Внутри цикла read_serial, перед выводом данных, добавлена строка: timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#Эта строка получает текущее время и форматирует его в виде строки "ГГГГ-ММ-ДД ЧЧ:ММ:СС". Вы можете изменить формат, если нужно.
#Форматирование вывода: Данные и метка времени объединяются в одну строку: formatted_data = f"{timestamp}: {data}"
#Теперь formatted_data содержит строку с меткой времени и данными, разделенными двоеточием и пробелом.