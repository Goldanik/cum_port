import os
import queue
import threading
import datetime

class FileLogger:
    """
    Класс для управления файловым логированием.
    Отвечает за создание лог-файлов, буферизированную запись данных
    и управление потоком логирования.
    """

    def __init__(self, data_queue: queue.Queue, on_error=None, on_file_size_exceeded=None):
        """Инициализация объекта FileLogger."""
        # Основные компоненты
        self._data_queue = data_queue
        # Callback для уведомления об ошибках
        self._on_error = on_error
        # Callback для уведомления о превышении размера файла
        self._on_file_size_exceeded = on_file_size_exceeded
        # Максимальный размер файла лога
        self._file_size_limit = 5 * 1024 * 1024  # 5 MB в байтах

        # Управление потоком
        self._log_thread = None
        self._stop_event = threading.Event()

        # Настройки буфера
        self._buffer = []
        self._buffer_size = 10

        # Параметры файла лога
        self._folder_path = 'logs'
        self._file_prefix = 'log_'
        self._file_extension = '.txt'
        self._timestamp = ''
        self._current_log_path = ''

        # Таймер для проверки размера файла
        self._size_check_timer = None

        # Создаем директорию для логов при инициализации
        self._ensure_log_directory()

    def _ensure_log_directory(self):
        """Создает директорию для логов, если она не существует."""
        if not os.path.exists(self._folder_path):
            os.makedirs(self._folder_path)

    @property
    def is_running(self) -> bool:
        """Проверяет, активен ли поток логирования."""
        return bool(self._log_thread and self._log_thread.is_alive())

    def start(self):
        """Запускает поток логирования."""
        # Проверяем, не запущен ли уже поток
        if self.is_running:
            self._handle_error("Поток логирования уже запущен.")
            return

        # Создаем метку времени и путь к файлу
        self._timestamp = datetime.datetime.now().strftime("%H_%M_%S")
        self._current_log_path = os.path.join(
            self._folder_path,
            f"{self._file_prefix}{self._timestamp}{self._file_extension}"
        )

        try:
            # Проверяем возможность записи в файл
            with open(self._current_log_path, "a", encoding="utf-8"):
                pass
            self._handle_error(f"Создан файл лога: {self._current_log_path}")
        except IOError as e:
            self._handle_error(f"Ошибка создания файла лога: {e}")
            raise

        # Запускаем поток логирования
        self._stop_event.clear()
        self._log_thread = threading.Thread(target=self._logging_worker, daemon=True)
        self._log_thread.start()

        # Запускаем таймер для проверки размера файла
        self._start_size_check_timer()

    def stop(self):
        """Останавливает поток логирования и сбрасывает оставшийся буфер."""
        self._stop_event.set()

        # Останавливаем таймер
        if self._size_check_timer:
            self._size_check_timer.cancel()

        # Ждем завершения потока
        if self._log_thread and self._log_thread.is_alive():
            self._log_thread.join(timeout=1.0)

        # Записываем оставшиеся данные
        self._flush_buffer()
        self._data_queue.queue.clear()

    def _start_size_check_timer(self):
        """Запускает таймер для проверки размера файла."""
        self._size_check_timer = threading.Timer(1.0, self._check_file_size)
        self._size_check_timer.start()

    def _check_file_size(self):
        """Проверяет размер файла и вызывает callback, если он превышает 5 МБ."""
        if os.path.exists(self._current_log_path):
            file_size = os.path.getsize(self._current_log_path)
            if file_size > self._file_size_limit:  # 5 МБ
                if self._on_file_size_exceeded:
                    self._on_file_size_exceeded()
        # Перезапускаем таймер
        self._start_size_check_timer()

    def _logging_worker(self):
        """Фоновый поток для обработки и записи данных лога."""
        while not self._stop_event.is_set():
            try:
                # Получаем данные из очереди
                data = self._data_queue.get(timeout=1)
                self._buffer.append(data + "\n")

                # Проверяем необходимость сброса буфера
                if len(self._buffer) >= self._buffer_size:
                    self._flush_buffer()

            except queue.Empty:
                continue

    def _flush_buffer(self):
        """Записывает буферизированные данные в файл лога."""
        if not self._buffer:
            return

        try:
            # Записываем данные из буфера в файл
            with open(self._current_log_path, "a", encoding="utf-8", buffering=1) as log_file:
                log_file.writelines(self._buffer)
            self._buffer.clear()
        except IOError as e:
            self._handle_error(f"Ошибка записи в файл лога: {e}")

    def _handle_error(self, message: str):
        """Обрабатывает статусные сообщения через callback или выводит в консоль."""
        if self._on_error:
            self._on_error(message)
        else:
            print(message)