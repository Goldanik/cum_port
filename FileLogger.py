import queue
import threading

class FileLogger:
    def __init__(self, filename="log.txt"):
        self.log_file = filename
        self.log_queue = queue.Queue()
        self.log_thread = None
        self.log_stop_event = threading.Event()

    def start_log_thread(self):
        """Запускаем поток для записи лога"""
        self.log_stop_event.clear()
        self.log_thread = threading.Thread(target=self.log_data_to_file, daemon=True)
        self.log_thread.start()

    def stop_log_thread(self):
        """Останавливаем поток записи лога"""
        self.log_stop_event.set()
        if self.log_thread and self.log_thread.is_alive():
            self.log_thread.join(timeout=1.0)

    def log_data_to_file(self):
        """Фоновый поток для записи лога"""
        while not self.log_stop_event.is_set():
            try:
                # Пытаемся получить данные из очереди
                try:
                    data = self.log_queue.get(timeout=1)  # Ждем максимум 1 секунду
                except queue.Empty:
                    continue  # Если нет данных, продолжаем ожидание

                # Пишем данные в файл
                with open(self.log_file, "a", encoding="utf-8", buffering=1) as log_file:
                    log_file.write(data + "\n")
            except Exception as e:
                self.update_message_area(f"Ошибка при записи лога: {e}")
