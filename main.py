import tkinter as tk
from tkinter import ttk
import serial
import threading
import datetime

class SerialMonitorGUI:
    def __init__(self, master):
        self.master = master
        master.title("COM Port Monitor")

        # Переменные для настроек COM-порта
        self.port = tk.StringVar(value="COM1")
        self.baudrate = tk.IntVar(value=9600)
        self.databits = tk.IntVar(value=8)
        self.parity = tk.StringVar(value="N")
        self.stopbits = tk.IntVar(value=1)
        self.encoding = tk.StringVar(value="ASCII")

        # Создание элементов интерфейса
        self.create_widgets()

        # Serial port object
        self.ser = None
        self.serial_thread = None
        self.stop_event = threading.Event()

        # Буфер для данных
        self.data_buffer = ""


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


    def read_serial(self):
        while not self.stop_event.is_set():
            try:
                if self.ser.in_waiting > 0:
                    data = self.ser.read(self.ser.in_waiting)  # Чтение всех доступных данных

                    if self.encoding.get() == "HEX":
                        decoded_data = data.hex()
                    elif self.encoding.get() == "BIN":
                        decoded_data = ''.join(format(byte, '08b') for byte in data)
                    else:  # ASCII
                        decoded_data = data.decode("ascii", errors="ignore")

                    self.data_buffer += decoded_data  # Добавление в буфер
                    timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")
                    formatted_data = f"{timestamp}: {self.data_buffer}"
                    self.data_buffer = ""  # Очистка буфера после вывода
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