import selectors
import socket
import threading
import queue

class UDPConnection:
    """Класс для работы с UDP соединением."""

    def __init__(self, data_queue: queue.Queue, on_error=None):
        """Инициализация объекта UDPConnection."""
        self._data_queue = data_queue  # Очередь для данных
        self._udp_thread = None  # Поток для чтения данных
        self._close_event = threading.Event()  # Событие для остановки потока
        self._on_error = on_error  # Callback для обработки ошибок

        # UDP сокет
        self._sock = None
        self._ip = None
        self._port = None
        #
        self.buffer_size = 1024

    def open_connection(self, ip: str, port: int):
        """
        Открывает UDP соединение с заданными параметрами.
        :param ip: IP-адрес для прослушивания
        :param port: Порт для прослушивания
        """
        # Закрываем соединение, если оно уже открыто
        self.close_connection()

        try:
            # Создаем UDP сокет
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.bind((ip, port))
            self._ip = ip
            self._port = port

            # Устанавливаем неблокирующий режим
            self._sock.setblocking(False)

            # Запускаем поток для чтения данных
            self._start_reading_thread()
        except Exception as e:
            self._handle_error(f"Ошибка открытия UDP соединения: {e}")
            raise

    def close_connection(self):
        """Закрывает UDP соединение и останавливает поток чтения."""
        self._close_event.set()  # Сигнализируем потоку о завершении

        if self._udp_thread and self._udp_thread.is_alive():
            self._udp_thread.join(timeout=1.0)  # Ждем завершения потока

        if self._sock:
            try:
                self._sock.close()  # Закрываем сокет
            except Exception as e:
                self._handle_error(f"Ошибка закрытия UDP соединения: {e}")
            finally:
                self._sock = None  # Освобождаем ресурс
                self._udp_thread = None
                self._ip = None
                self._port = None

    def is_open(self) -> bool:
        """
        Проверяет, открыто ли UDP соединение
        :return: True если соединение открыто, иначе False
        """
        return bool(self._sock is not None)

    def _start_reading_thread(self):
        """Запускает поток для чтения данных из UDP сокета."""
        self._close_event.clear()
        self._udp_thread = threading.Thread(target=self._read_udp, daemon=True)
        self._udp_thread.start()

    def _read_udp(self):
        """Читает данные из UDP сокета с помощью селектора."""
        selector = selectors.DefaultSelector()
        selector.register(self._sock, selectors.EVENT_READ)

        while not self._close_event.is_set():
            try:
                if self._sock is None or not self.is_open():  # Проверка состояния сокета
                    break
                events = selector.select(timeout=0.1)  # Ожидание данных с таймаутом
                for key, _ in events:
                    data, addr = key.fileobj.recvfrom(self.buffer_size)
                    if data:
                        try:
                            self._data_queue.put(data, timeout=0.1)
                        except queue.Full:
                            self._handle_error("Очередь данных переполнена. Данные потеряны.")
            except BlockingIOError:
                    # Нет доступных данных, продолжаем цикл
                continue
            except Exception as e:
                self._handle_error(f"Ошибка чтения UDP данных: {e}")
                self.close_connection()
                break

    def _handle_error(self, message: str):
        """Обрабатывает ошибку, вызывая callback или выводя сообщение в консоль."""
        if self._on_error:
            self._on_error(message)
        else:
            print(message)