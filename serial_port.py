import queue
import threading
import serial

class SerialPort:
    def __init__(self, data_proc_queue, main_gui):
        # Переменные для настроек COM-порта
        self.port = None
        self.baud_rate = None
        self.databits = None
        self.parity = None
        self.stop_bits = None
        self.encoding = None

        # Очереди
        self.data_queue = data_proc_queue

        # Объекты последовательного порта
        self.ser = None
        self.serial_thread = None
        self.close_port_event = threading.Event()

        # Интерфейс пользователя
        self.main_gui = main_gui

    # Открытие последовательного порта
    def open_port(self,port,baudrate,bytesize,parity,stopbits,timeout):
        try:
            # Закрываем старый порт если он есть
            if self.ser and self.ser.is_open:
                self.ser.close()
            # Открываем порт с заданными параметрами
            self.ser = serial.Serial(port,baudrate,bytesize,parity,stopbits,timeout)
            # Запуск потока чтения из последовательного порта
            self.close_port_event.clear()  # Сбрасываем флаг остановки
            self.serial_thread = threading.Thread(target=self.read_serial, daemon=True)
            self.serial_thread.start()
        except serial.SerialException as e:
            self.main_gui.update_message_area(f"Ошибка открытия порта: {e}")
            return

    # Закрытие последовательного порта
    def close_port(self):
        try:
            # Сигнализируем потоку о завершении
            self.close_port_event.set()

            if self.serial_thread and self.serial_thread.is_alive():
                self.serial_thread.join(timeout=1.0)

            if self.ser and self.ser.is_open:
                # Очищаем буферы порта перед закрытием
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                self.data_queue.queue.clear()
                self.ser.close()
        except Exception as e:
            self.main_gui.update_message_area(f"Ошибка закрытия порта: {e}")
        finally:
            # Очищаем ссылку на поток
            self.serial_thread = None

    # Чтение данных из последовательного порта
    def read_serial(self):
        """Чтение данных из порта."""
        while not self.close_port_event.is_set():
            try:
                try:
                    # Получение всех байтов из очереди входящих и складывание в очередь данных
                    data = self.ser.read(self.ser.in_waiting or 1)
                    try:
                        self.data_queue.put(data)
                    except queue.Full:
                        self.main_gui.update_message_area("Очередь порта переполнена. Данные потеряны.")
                    #self.main_gui.update_message_area(f"Размер очереди1: {self.data_queue.qsize()}")
                except serial.SerialException as e:
                    # Выходим из цикла чтения, если порт еще не закрыт
                    if not self.close_port_event.is_set():
                        self.main_gui.update_message_area(f"Ошибка чтения данных: {e}")
                        self.close_port()
                        break
            # Общий обработчик ошибок
            except Exception as e:
                if not self.close_port_event.is_set():
                    self.main_gui.update_message_area(f"Критическая ошибка: {e}")
                    self.close_port()
                    break