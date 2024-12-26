import datetime
import queue
import threading

class DataProcessing:
    def __init__(self, data_proc_queue, logger_queue, main_gui):
        # Поток обработки данных
        self.data_process_thread = None
        self.data_process_event = threading.Event()

        # Очереди
        self.data_proc_queue = data_proc_queue
        self.logger_queue = logger_queue

        # Интерфейс пользователя
        self.main_gui = main_gui

        # Паттерны ориона2
        # self.req_ack_pattern1 = "ff011f6c" + "6f6c"
        # self.req_ack_pattern2 = "ff021f48" + "6f1d"

        # Счетчики
        self.counter_custom = 0

        self.unparsed_encoding_data_size = 150
        self.timestamp = ""

    def start_data_processing(self):
        # Запускаем отдельный поток для обработки данных
        self.data_process_event.clear()
        self.data_process_thread = threading.Thread(target=self.encodings_handler, daemon=True)
        self.data_process_thread.start()

    def stop_data_processing(self):
        # Останавливаем обработку данных
        self.data_process_event.set()
        if self.data_process_thread and self.data_process_thread.is_alive():
            self.data_process_thread.join(timeout=1.0)
        # Очищаем ссылку на поток
        self.data_process_thread = None

    def encodings_handler(self):
        """Обработка кодировок данных."""
        while not self.data_process_event.is_set():
            try:
                current_buffer = self.data_proc_queue.get(timeout=1)
            except queue.Empty:
                continue  # Если нет данных, продолжаем ожидание
            self.timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")
            # Значение по умолчанию
            encoding = self.main_gui.encoding.get()
            if encoding == "O2":
                # Передаем данные напрямую в парсер
                self.orion2_parser(current_buffer)
            elif encoding == "HEX":
                decoded_data = current_buffer.hex()
                while decoded_data and not self.data_process_event.is_set():
                    if len(decoded_data) > self.unparsed_encoding_data_size:
                        # Берём данные фиксированной длины
                        packet = decoded_data[:self.unparsed_encoding_data_size]
                        decoded_data = decoded_data[self.unparsed_encoding_data_size:]
                        self.timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")
                    else:
                        try:
                            additional_buffer = self.data_proc_queue.get(timeout=1)
                            decoded_data += additional_buffer.hex()
                            self.timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")
                            continue
                        except queue.Empty:
                            continue
                    if packet:
                        try:
                            self.logger_queue.put(f"{self.timestamp}  {packet}  ")
                            # Обновляем GUI
                            self.main_gui.update_text_area(f"{self.timestamp}  {packet}  ")
                        except queue.Full:
                            self.main_gui.update_message_area(f"Очередь заполнена")
            elif encoding == "BIN":
                decoded_data = ''.join(format(byte, '08b') for byte in current_buffer)
                while decoded_data and not self.data_process_event.is_set():
                    if len(decoded_data) > self.unparsed_encoding_data_size:
                        # Берём данные фиксированной длины
                        packet = decoded_data[:self.unparsed_encoding_data_size]
                        decoded_data = decoded_data[self.unparsed_encoding_data_size:]
                        self.timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")
                    else:
                        try:
                            additional_buffer = self.data_proc_queue.get(timeout=1)
                            decoded_data += ''.join(format(byte, '08b') for byte in additional_buffer)
                            self.timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")
                            continue
                        except queue.Empty:
                            continue
                    if packet:
                        try:
                            self.logger_queue.put(f"{self.timestamp}  {packet}  ")
                            # Обновляем GUI
                            self.main_gui.update_text_area(f"{self.timestamp}  {packet}  ")
                        except queue.Full:
                            self.main_gui.update_message_area(f"Очередь заполнена")
            elif encoding == "ASCII":
                try:
                    decoded_data = current_buffer.decode("ascii", errors="ignore")
                    while decoded_data and not self.data_process_event.is_set():
                        end = decoded_data.find('\n', 0)
                        #self.main_gui.update_message_area(f"Данные на парсинг: {len(decoded_data)}, {decoded_data}, {end}")
                        if end == -1 or end == 0:
                            if len(decoded_data) > 200:
                                # Берём данные фиксированной длины
                                packet = decoded_data[:200]
                                decoded_data = decoded_data[200:]
                                self.timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")
                            else:
                                try:
                                    additional_buffer = self.data_proc_queue.get(timeout=1)
                                except queue.Empty:
                                    continue  # Если нет данных, продолжаем ожидание
                                decoded_data += additional_buffer.decode("ascii", errors="ignore")
                                self.timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")
                                continue
                        else:
                            # Берём данные до следующего маркера с исключением \n
                            packet = decoded_data[:end-1]
                            decoded_data = decoded_data[end+1:]
                        if packet:
                            try:
                                self.logger_queue.put(f"{self.timestamp}  {packet}  ")
                                # Обновляем GUI
                                self.main_gui.update_text_area(f"{self.timestamp}  {packet}  ")
                            except queue.Full:
                                self.main_gui.update_message_area(f"Очередь заполнена")
                except UnicodeDecodeError:
                    decoded_data = current_buffer.decode("latin-1", errors="ignore")

    def orion2_parser(self, data_bytes):
        """Парсер для кодировки Orion2."""
        while data_bytes and not self.data_process_event.is_set():
            decode = ""
            # Ищем 'ff'
            next_ff = data_bytes.find(b"\xFF", 2 if len(data_bytes) > 2 else 0)
            #self.main_gui.update_message_area(f"Данные на парсинг: {len(data)}, {data}, {next_ff}")
            if next_ff == -1 or next_ff == 0:
                try:
                    # Пытаемся получить данные из очереди
                    additional_buffer = self.data_proc_queue.get(timeout=1)
                except queue.Empty:
                    continue  # Если нет данных, продолжаем ожидание
                data_bytes += additional_buffer
                continue
            else:
                # Берём данные до следующего маркера
                packet = data_bytes[:next_ff].hex()
                data_bytes = data_bytes[next_ff:]
                self.timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")

            if self.main_gui.skip_requests and (len(packet) > 4) and packet.startswith('ff'):
                temp_packet = packet[4:]
                # Пакеты IN запросы для каждого адреса
                if temp_packet.startswith('1f'):
                    address = int(packet[2:4], 16) & 0x1F
                    # Ответы ACK если байт не NACK
                    if temp_packet.find('6f') != 4:
                        temp_packet = temp_packet[4:]
                        decode = "REQACK+"
                    else:
                        self.main_gui.req_ack_counters[int(address)] += 1
                        continue
                # Пакеты DATA0
                if temp_packet.startswith('2f'):
                    temp_packet = temp_packet[len(temp_packet)-4:]
                    if temp_packet.startswith('4f'):
                        packet = packet[6:len(packet)-4]
                        decode += "DATA0+ACK0"
                    else:
                        packet = temp_packet[6:]
                        decode += "DATA0+NACK"
                # Пакеты DATA1
                elif temp_packet.startswith('3f'):
                    temp_packet = temp_packet[len(temp_packet)-4:]
                    if temp_packet.startswith('5f'):
                        packet = packet[6:len(packet)-4]
                        decode += "DATA1+ACK1"
                    else:
                        packet = temp_packet[6:]
                        decode += "DATA1+NACK"
                # Пакеты SEARCH для каждого адреса
                elif temp_packet.startswith('8f'):
                    address = int(packet[2:4], 16) & 0x1F
                    self.main_gui.search_counters[int(address)] += 1
                    continue
                # Пакеты GETID для каждого адреса
                elif temp_packet.startswith('af'):
                    address = int(packet[2:4], 16) & 0x1F
                    if address < 33:
                        self.main_gui.get_id_counters[address] += 1
                    continue
                # Пакеты GIVEADDR
                if packet:
                    temp_packet = packet[2:]
                    if temp_packet.startswith('80') and temp_packet.find('9f') == 14:
                        address = int(packet[22:24])
                        self.main_gui.give_addr[address] = (temp_packet[12:14]+":"+temp_packet[10:12]+":"+temp_packet[8:10]
                              +":"+temp_packet[6:8]+":"+temp_packet[4:6]+":"+temp_packet[2:4])
                        continue

                custom_pattern = self.main_gui.custom_skip_pattern.get().lower()
                if custom_pattern: # and all(c in "0123456789abcdef"for c in custom_pattern):
                    try:
                        self.counter_custom += packet.count(custom_pattern)
                        packet = packet.replace(custom_pattern, "")
                    except Exception as e:
                        self.main_gui.update_message_area(f"Ошибка обработки пользовательского шаблона: {e}")
                # else:
                #     self.update_message_area("Некорректный пользовательский шаблон")

            if packet:
                try:
                    self.logger_queue.put(f"{self.timestamp}  {packet}  {decode}")
                    # Обновляем GUI
                    self.main_gui.update_text_area(f"{self.timestamp}  {packet}  {decode}")
                    #self.main_gui.update_message_area(f"Размер очереди2: {self.logger_queue.qsize()}")
                except queue.Full:
                    self.main_gui.update_message_area(f"Очередь заполнена")