import queue
import threading
import datetime

class FileLogger:
    def __init__(self, log_queue, main_gui):
        self.log_file_name = "log_"
        self.log_file_format= ".txt"
        # Поток логера
        self.log_queue = log_queue
        self.log_thread = None
        self.log_stop_event = threading.Event()

        # Интерфейс пользователя
        self.main_gui = main_gui

        self.buffer = []
        self.buffer_size = 10

        self.timestamp = ""

    def start_logger(self):
        """Запускаем поток для записи лога"""
        self.timestamp = datetime.datetime.now().strftime("%H_%M_%S")
        # Проверяем что файл можно открыть
        try:
            with open(self.log_file_name+self.timestamp+self.log_file_format, "a", encoding="utf-8", buffering=1):
                pass  # Проверяем, что файл доступен для записи
        except Exception as e:
            self.main_gui.update_message_area(f"Ошибка открытия файла лога: {e}")
            return
        # Проверяем что поток был остановлен перед повторным открытием
        if self.log_thread and self.log_thread.is_alive():
            self.main_gui.update_message_area("Поток записи уже запущен.")
            return

        self.log_stop_event.clear()
        self.log_thread = threading.Thread(target=self.log_data_to_file, daemon=True)
        self.log_thread.start()

    def stop_logger(self):
        """Останавливаем поток записи лога"""
        self.log_stop_event.set()

        if self.log_thread and self.log_thread.is_alive():
            self.log_thread.join(timeout=1.0)

        self.log_queue.queue.clear()

    def log_data_to_file(self):
        """Фоновый поток для записи лога"""
        while not self.log_stop_event.is_set():
            try:
                # Пытаемся получить данные из очереди
                data = self.log_queue.get(timeout=1)
                # Добавляем данные в буфер
                self.buffer.append(data + "\n")
                # Проверяем размер буфера
                if len(self.buffer) >= self.buffer_size:
                    # Если буфер заполнен, записываем все в файл
                    try:
                        with open(self.log_file_name+self.timestamp+self.log_file_format, "a", encoding="utf-8") as log_file:
                            log_file.writelines(self.buffer)
                            self.buffer = []
                    except Exception as e:
                        self.main_gui.update_message_area(f"Ошибка записи лога: {e}")
            except queue.Empty:
                # Если нет данных, продолжаем ожидание
                continue
        # Записываем оставшиеся данные из буфера после остановки потока
        if self.buffer:
            try:
                with open(self.log_file_name+self.timestamp+self.log_file_format, "a", encoding="utf-8") as log_file:
                     log_file.writelines(self.buffer)
            except Exception as e:
                self.main_gui.update_message_area(f"Ошибка записи лога: {e}")


