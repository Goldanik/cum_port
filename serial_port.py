import queue
import threading
import serial
import serial.tools.list_ports

class SerialPort:
    """
    Класс для работы с COM-портами.
    Отвечает за открытие, закрытие, чтение данных и управление последовательным портом.
    """

    def __init__(self, data_queue: queue.Queue, on_error=None):
        """Инициализация объекта SerialPort."""
        self._data_queue = data_queue  # Очередь для данных
        self._serial_thread = None  # Поток для чтения данных
        self._close_event = threading.Event()  # Событие для остановки потока
        self._on_error = on_error  # Callback для обработки ошибок

        # Объект последовательного порта
        self._ser = None

    @staticmethod
    def get_available_ports() -> list:
        """Возвращает список доступных COM-портов."""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def open_port(self, port: str, baudrate: int, bytesize: int, parity: str, stopbits: int, timeout: float = 1.0):
        """
        Открывает последовательный порт с заданными параметрами.
        :param port: Имя порта (например, "COM1").
        :param baudrate: Скорость передачи данных.
        :param bytesize: Количество бит в байте.
        :param parity: Тип проверки четности ('N', 'E', 'O', 'M', 'S').
        :param stopbits: Количество стоп-битов (1 или 2).
        :param timeout: Таймаут ожидания данных в секундах.
        :raises serial.SerialException: Если порт не удается открыть.
        """
        # Закрываем порт, если он уже открыт
        self.close_port()

        try:
            # Настраиваем и открываем порт
            self._ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                timeout=timeout,
            )
            # Запускаем поток для чтения данных
            self._start_reading_thread()
        except serial.SerialException as e:
            self._handle_error(f"Ошибка открытия порта: {e}")
            raise

    def close_port(self):
        """Закрывает последовательный порт и останавливает поток чтения."""
        # Сигнализируем о завершении чтения
        self._close_event.set()

        if self._serial_thread and self._serial_thread.is_alive():
            self._serial_thread.join(timeout=1.0)

        if self._ser and self._ser.is_open:
            try:
                self._ser.reset_input_buffer()
                self._ser.reset_output_buffer()
                self._ser.close()
            except serial.SerialException as e:
                self._handle_error(f"Ошибка закрытия порта: {e}")
            finally:
                self._serial_thread = None
                self._ser = None

    def is_open(self) -> bool:
        """
        Проверяет, открыт ли порт
        bool: True если порт открыт, иначе False
        """
        return bool(self._ser and self._ser.is_open)

    def _start_reading_thread(self):
        """Запускает поток для чтения данных из последовательного порта."""
        self._close_event.clear()
        self._serial_thread = threading.Thread(target=self._read_serial, daemon=True)
        self._serial_thread.start()

    def _read_serial(self):
        """Читает данные из последовательного порта и добавляет их в очередь."""
        while not self._close_event.is_set():
            try:
                # Читаем доступные данные из порта
                if self._ser and self._ser.is_open:
                    data = self._ser.read(self._ser.in_waiting or 1)
                    if data:
                        try:
                            self._data_queue.put(data, timeout=0.1)
                        except queue.Full:
                            self._handle_error("Очередь данных переполнена. Данные потеряны.")
            except serial.SerialException as e:
                self._handle_error(f"Ошибка чтения данных: {e}")
                self.close_port()
                break
            except Exception as e:
                self._handle_error(f"Неизвестная ошибка: {e}")
                self.close_port()
                break

    def _handle_error(self, message: str):
        """Обрабатывает ошибку, вызывая callback или выводя сообщение в консоль."""
        if self._on_error:
            self._on_error(message)
        else:
            print(message)