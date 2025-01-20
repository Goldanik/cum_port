import datetime
import queue
import threading
from Crypto.Cipher import AES

"""
def calc_crc16(old_crc, in_byte):
    # Вычисляет CRC16 для одного байта данных, используя порождающий полином 0x1021.
    # XOR входного байта с младшим байтом текущего CRC
    crc = old_crc ^ in_byte
    # Выполняем 8 итераций (по количеству битов в байте)
    for _ in range(8):
        # Если старший бит установлен, применяем порождающий полином
        if crc & 0x0001:
            crc = (crc >> 1) ^ 0x8408  # Полином в обратном порядке (0x1021 -> 0x8408)
        else:
            crc >>= 1
    return crc

def calculate_crc16(data):
    # Вычисляет контрольную сумму CRC16 для массива данных.
    crc = 0xFFFF  # начальное значение CRC
    for byte in data:
        crc = calc_crc16(crc, byte)
    return crc

# Пример использования
hex_string = "2913f605666666bc1800676767bc180089d129fa44d81babe849ba37288b04f602cdb728fa9784"
expected_crc16 = "3343"
data = bytes.fromhex(hex_string)
crc16_result = calculate_crc16(data)
low_byte = crc16_result & 0xFF
high_byte = (crc16_result >> 8) & 0xFF
# Вывод результата
print(f"CRC16 (младший байт вперед): {low_byte:02X}{high_byte:02X}")
"""

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

        # Флаги данных в заголовке пакета
        self.packet_flags = ["SAF", "DAF", "Ackn", "PFirst", "PSyn", "WKey", "SMode", "Reserv"]
        # Счетчик мастер ключа СЧМК
        self.master_key_counter = [""] * 32
        # Флаг получения СЧМК, введен т.к. счетчик может быть 0, и его пустоту никак не проверить
        self.new_mkey_saved = False
        # Мастер ключ
        self.master_key = "A4955A7C0C51939E863C135FF468693D"
        # Рабочий ключ и его счетчик СЧРК для расшифровки исходящего пакета
        self.work_key_out_counter = [""] * 32
        self.work_key_out = [""] * 32
        # Рабочий ключ и его счетчик СЧРК для расшифровки входящего пакета
        self.work_key_in_counter = [""] * 32
        self.work_key_in = [""] * 32
        # Флаг получения СЧРК, введен т.к. счетчик может быть 0, и его пустоту никак не проверить
        self.new_wkey_saved = False
        # Мак-адрес GIVEADDR в литл-индиан как в пакете
        self.give_addr = [""] * 32
        # Список типов пакетов
        self.packet_types = {
            0: "ACK_SERV+",
            1: "DT_SERV",
            2: "ACK_DATA+",
            3: "DT_DATA"
        }
        # Список типов сервисных команд
        self.serv_cmd_types = {
            1: "(SCNumReq)+",
            2: "(SCNum)+",
            3: "(SCWorkKey)+",
            4: "(SCMasterKey)+",
            10: "(SCAbility)+"
        }
        # Список типов команд данных
        self.data_cmd_types = {
            3: "(Cmd)+",
            4: "(CmdResp)+",
            6: "(UMsg)+"
        }
        # Переменная для мак-адресов
        self.mac = ["00:00:00:00:00:00"] * 2
        # Счетчик для пользовательского фильтра
        self.counter_custom = 0

        # Длина в байтах обрезки не шифрованных кодировок (ASCII и HEX)
        self.unparsed_encoding_data_size = 100

        # Переменная для хранения отметки времени
        self.timestamp = ""

    def start_data_processing(self):
        """Запуск отдельного потока для обработки данных"""
        self.data_process_event.clear()
        encoding = self.main_gui.encoding.get()  # Получаем значение перед запуском потока
        if not self.data_process_thread or not self.data_process_thread.is_alive():
            self.data_process_thread = threading.Thread(
                target=self.encodings_handler, args=(encoding,), daemon=True
            )
            self.data_process_thread.start()

    def stop_data_processing(self):
        """Остановка потока обработки данных"""
        self.data_process_event.set()
        if self.data_process_thread and self.data_process_thread.is_alive():
            self.data_process_thread.join(timeout=1.0)
        # Очищаем ссылку на поток
        self.data_process_thread = None
        # Очищаем ключи, счетчики, ид
        # Очистка отключена т.к. удобнее пытаться восстановить ключ между сессиями открытия порта
        # self.new_mkey_saved = False
        # self.master_key_counter = [""] * 32
        # self.work_key_out_counter = [""] * 32
        # self.work_key_out = [""] * 32
        # self.work_key_in_counter = [""] * 32
        # self.work_key_in = [""] * 32
        # self.give_addr = [""] * 32

    def encodings_handler(self, encoding):
        """Обработка кодировок данных"""
        while not self.data_process_event.is_set():
            try:
                current_buffer = self.data_proc_queue.get(timeout=1)
            except queue.Empty:
                continue  # Если нет данных, продолжаем ожидание
            self.timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")
            # Значение по умолчанию
            if encoding == "O2":
                # Передаем данные напрямую в парсер
                self._orion2_parser(current_buffer)
            elif encoding == "HEX":
                while current_buffer and not self.data_process_event.is_set():
                    if len(current_buffer) > self.unparsed_encoding_data_size:
                        # Берём данные фиксированной длины
                        packet = current_buffer[:self.unparsed_encoding_data_size].hex()
                        current_buffer = current_buffer[self.unparsed_encoding_data_size:]
                    else:
                        try:
                            additional_buffer = self.data_proc_queue.get(timeout=1)
                        except queue.Empty:
                            continue
                        current_buffer += additional_buffer
                        continue
                    self.timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")
                    self.update_gui_and_log(packet, "", "", "", "", "")
            elif encoding == "ASCII":
                try:
                    while current_buffer and not self.data_process_event.is_set():
                        end = current_buffer.find(b"\x0a", 0)
                        #self.main_gui.update_message_area(f"Данные на парсинг: {len(decoded_data)}, {decoded_data}, {end}")
                        if end == -1 or end == 0:
                            if len(current_buffer) > self.unparsed_encoding_data_size:
                                # Берём данные фиксированной длины
                                packet = current_buffer[:self.unparsed_encoding_data_size].decode("ascii", errors="ignore")
                                current_buffer = current_buffer[self.unparsed_encoding_data_size:]
                            else:
                                try:
                                    additional_buffer = self.data_proc_queue.get(timeout=1)
                                except queue.Empty:
                                    continue  # Если нет данных, продолжаем ожидание
                                current_buffer += additional_buffer
                                continue
                        else:
                            # Берём данные до следующего маркера с исключением \n
                            packet = current_buffer[:end-1].decode("ascii", errors="ignore")
                            current_buffer = current_buffer[end+1:]
                        self.timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")
                        self.update_gui_and_log(packet,"","","","","")
                except UnicodeDecodeError:
                    self.main_gui.update_message_area(f"Некорректный символ")

    #@profile
    def _orion2_parser(self, data_bytes):
        """Парсер для кодировки Orion2."""
        while data_bytes and not self.data_process_event.is_set():
            # Ищем начало следующего пакета 'ff'
            next_ff = data_bytes.find(b"\xFF", 2)
            # Если не найдено или в нулевой позиции
            if next_ff == -1 or next_ff == 0:
                try:
                    # Пытаемся получить данные из очереди
                    additional_buffer = self.data_proc_queue.get(timeout=0.1)
                except queue.Empty:
                    # print("Очередь пуста")
                    # Если нет данных, продолжаем ожидание
                    continue
                # Получили новую порцию данных, добавляем ее к существующим данным
                data_bytes += additional_buffer
                continue
            # Нашли начало пакета
            else:
                # Формируем пакет из данных в буфере до следующего маркера
                packet = data_bytes[:next_ff]
                # Вырезаем пакет из буфера
                data_bytes = data_bytes[next_ff:]

            # Инициализируем переменные для вывода и обработки данных
            packet_len = ""
            packet_num = ""
            direction = ""
            decoded_flags = ""
            packet_type = ""
            decode = ""
            was_req = False
            data_encrypt = False
            encrypted_work_key = False
            dont_decode = False
            overall_len = 0

            # Если длина пакета больше 2 байт и пакет начинается на ff
            bytes_length = len(packet)
            bytes_first = bytes([packet[0]])
            if not ((bytes_length > 2) and (bytes_first == b"\xff")):
                decode = "Ошибка, пакет не целый"
                packet = packet.hex()
            else:
                # Заменяем в пакете подмененные при передаче байты
                packet = packet.replace(b'\xFE\x01', b'\xFF').replace(b'\xFE\x02', b'\xFE')
                packet = packet.hex()
                raw_packet = packet
                # packet_header_type = bytes([packet[2]])
                # packet_header_ack_type = bytes([packet[4]])

                # Парсинг заголовка пакета.
                # Получаем адрес абонента
                address = int(packet[2:4], 16) & 0x1F
                # Для парсинга заголовка отрезаем первые два байта
                temp_packet = packet[4:]
                # Пакеты IN запросы для каждого адреса
                if temp_packet.startswith('1f'):
                    # Ставим флаг, что пакет получен по запросу
                    was_req = True
                    # Ответы ACK если байт не NACK
                    if temp_packet[4:6] != '6f':
                        temp_packet = temp_packet[4:]
                        #packet_type = "REQ+"
                    else:
                        # Инкрементируем счетчик "холостых" запросов-ответов
                        self.main_gui.req_ack_counters[address] += 1
                        continue

                # Пакеты DATA0 и DATA1 могут приходить как самостоятельно так и по запросу после 1f
                if temp_packet.startswith('2f') or temp_packet.startswith('3f'):
                    ans_packet = temp_packet[len(temp_packet)-4:]
                    # Ищем в конце успешный ответ
                    if ((temp_packet.startswith('2f') and ans_packet.startswith('4f'))
                            or (temp_packet.startswith('3f') and ans_packet.startswith('5f'))):
                        if was_req:
                            # Обрезаем с полем len если ведомый-мастер
                            packet = packet[12:len(packet)-4]
                        else:
                            # Обрезаем меньше при пакете мастер-ведомый
                            packet = packet[8:len(packet) - 4]
                    else:
                        decode = f"Ошибка, потеря квитанции {temp_packet[:2]}, {ans_packet[:2]}"
                        if was_req:
                            # Обрезаем с полем len если ведомый-мастер
                            packet = packet[12:len(packet)-4]
                        else:
                            # Обрезаем меньше при пакете мастер-ведомый
                            packet = packet[8:len(packet) - 4]
                    if was_req:
                        direction = "s-m"
                    else:
                        direction = "m-s"

                # Пакеты SEARCH для каждого адреса
                elif temp_packet.startswith('8f'):
                    # Инкрементируем счетчик поисковых запросов
                    self.main_gui.search_counters[address] += 1
                    continue

                # Пакеты GETID для каждого адреса
                elif temp_packet.startswith('af'):
                    # Инкрементируем счетчик присвоения мак адреса (ид) к адресу абонента
                    self.main_gui.get_id_counters[address] += 1
                    continue

                else:
                    # Пакеты GIVEADDR
                    temp_packet = packet[2:]
                    if temp_packet.startswith('80') and temp_packet[14:16] == '9f':
                        # Получаем адрес прибора
                        address = int(packet[22:24], 16) & 0x1F
                        # Получаем мак прибора
                        self.give_addr[address] = temp_packet[2:14]
                        # Получаем мак мастера
                        self.give_addr[0] = temp_packet[22:34]
                        continue

                # Ставим отметку времени
                self.timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")
                # Парсинг заголовка команды
                try:
                    # Парсинг общей длины
                    len_byte = str(packet[:2])
                    if len_byte:
                        overall_len = int(len_byte, 16)
                        # Если фактическая длина пакета не совпадает с указанной в заголовке
                        if overall_len != len(packet)/2:
                            decode = "Ошибка, пакет не целый"
                            packet = raw_packet
                            dont_decode = True
                        else:
                            packet_len = overall_len
                            # Парсинг типа пакета
                            packet_type_byte = str(packet[3:4])
                            if packet_type_byte:
                                packet_type_int = int(packet_type_byte, 16)
                                packet_type = self.packet_types[packet_type_int]
                            # Парсинг номера пакета
                            packet_num_byte = str(packet[6:8])
                            if packet_num_byte:
                                packet_num = int(packet_num_byte, 16)
                            packet_flags = str(packet[4:6])
                            if packet_flags:
                                # Парсинг флагов содержимого пакета
                                decoded_flags = self._decode_flags(int(packet_flags, 16))
                            # Если присутствует флаг SMode значит пакет зашифрован
                            data_encrypt = "SMode" in decoded_flags
                            # Если присутствует флаг WKey значит пакет зашифрован рабочим ключом
                            encrypted_work_key = "WKey" in decoded_flags
                            # Если шифрован, но не рабочим ключом, вставляем флаг мастер ключа
                            if data_encrypt and not encrypted_work_key:
                                decoded_flags = decoded_flags[:len(decoded_flags)-6] + ":MKey:SMode"
                            # Обрезка основной части заголовка
                            packet = packet[8:]
                            # Парсинг и обрезка идентификаторов
                            count = 0
                            source = 0
                            destination = 0

                            for item in self.give_addr:
                                # Ищем в пакете мак адреса (ид) приборов, сохраненные из пакетов GIVEADDR в список give_addr
                                if item:
                                    start_index = packet.find(item)
                                    if start_index >= 0:
                                        if start_index == 0:
                                            self.mac[0] = item
                                            source = count
                                        else:
                                            self.mac[1] = item
                                            destination = count
                                    self.main_gui.mac_addr[count] = self._convert_mac(item)
                                count += 1
                            if self.mac[0] and self.mac[1]:
                                # Обрезаем идентификаторы из тела пакета
                                packet = packet[24:]
                                # packet = packet.replace(self.mac[0], "").replace(self.mac[1], "")
                                direction += "  " + self.main_gui.mac_addr[source] + "-" + self.main_gui.mac_addr[destination]
                            else:
                                # Обрезаем идентификаторы из тела пакета
                                packet = packet[24:]
                except Exception as e:
                    self.main_gui.update_message_area(f"Ошибка при парсинге заголовка: {e}")

                # Парсинг содержимого команды
                if not dont_decode:
                    try:
                        # Если данные не шифрованы
                        if not data_encrypt:
                            if packet_type == "DT_SERV":
                                serv_cmd_type_byte = str(packet[4:6])
                                if serv_cmd_type_byte:
                                    serv_cmd_type = int(serv_cmd_type_byte, 16)
                                    packet_type += self.serv_cmd_types[serv_cmd_type]
                                    if serv_cmd_type == 2:
                                        # Сохраняем значение счетчика мастер ключа
                                        self.master_key_counter[address] = packet[6:14]
                                        # Ставим флаг, что ключ получен
                                        self.new_mkey_saved = True
                            # Дополняем общую длину пакета длиной данных
                            not_encr_data_len_byte = str(packet[:2])
                            if not_encr_data_len_byte:
                                not_encr_data_len = int(not_encr_data_len_byte, 16)
                                packet_len = f"{overall_len}/{not_encr_data_len}"
                            if not decode:
                                decode = "Не шифрованные данные"
                        # Данные шифрованы
                        else:
                            # Начинаем расшифровку только если получен счетчик мастер ключа
                            if not self.new_mkey_saved:
                                decode = "Ошибка, не получен счетчик мастер-ключа"
                            else:
                                s_counter = packet[:2]
                                # Убираем значение счетчика, mac и crc из данных
                                packet = packet[2:len(packet) - 12]
                                # Если нет флага "Рабочий ключ"
                                if not encrypted_work_key:
                                    # Расшифровка мастер ключом
                                    decode_packet = self._decrypt_with_master_key(address, packet, s_counter)
                                else:
                                    # Если значения СЧРК пустые
                                    if not self.new_wkey_saved:
                                        decode = "Ошибка, не получен счетчик рабочего ключа"
                                        decode_packet = ""
                                    else:
                                        # Расшифровка рабочим ключом
                                        decode_packet = self._decrypt_with_work_key(address, packet, s_counter)
                                        # Уточняем тип пакета
                                        if packet_type == "DT_SERV":
                                            packet_subtype = decode_packet[2]
                                            if packet_subtype in self.serv_cmd_types:
                                                packet_type += self.serv_cmd_types[packet_subtype]
                                            else:
                                                packet_type += f"({str(packet_subtype)})+"
                                                # decode = "Ошибка, неизвестный подтип пакета"
                                            if packet_subtype == 2:
                                                # Сохраняем значение счетчика мастер ключа
                                                self.master_key_counter[address] = packet[6:14]
                                        elif packet_type == "DT_DATA":
                                            packet_subtype = decode_packet[1]
                                            if packet_subtype in self.data_cmd_types:
                                                packet_type += self.data_cmd_types[packet_subtype]
                                            else:
                                                packet_type += f"({str(packet_subtype)})+"
                                                # decode = "Ошибка, неизвестный подтип пакета"
                                if not decode:
                                    # Сохраняем расшифрованные данные
                                    decode = decode_packet
                                    # Дополняем общую длину пакета длиной данных
                                    data_len = decode_packet[0]
                                    packet_len = f"{overall_len}/{data_len}"
                    except Exception as e:
                        self.main_gui.update_message_area(f"Ошибка при парсинге данных: {e}")
            # Отправка данных на экран и в лог-файл
            self.update_gui_and_log(packet, packet_len, packet_num, direction, packet_type + decoded_flags, decode)

    def update_gui_and_log(self, packet, packet_len, packet_num, direction, packet_type_flags, decode):
        """Отправка данных на экран и в лог-файл"""
        try:
            # Отправка данных в лог
            if not decode:
                self.logger_queue.put(f"{self.timestamp}  {packet}")
            else:
                self.logger_queue.put(f"{self.timestamp}  {packet}  {packet_len}  {packet_num}  {direction}  "
                                    f"{packet_type_flags}  {decode}")
        except queue.Full:
            self.main_gui.update_message_area(f"Очередь лога заполнена")
        try:
            # Обновляем GUI
            if not decode:
                self.main_gui.update_data_area(f"{self.timestamp}@{packet}")
            else:
                self.main_gui.update_data_area(f"{self.timestamp}@{packet}@{packet_len}"
                                           f"@{packet_num}@{direction}@{packet_type_flags}@{decode}")
        except queue.Full:
            self.main_gui.update_message_area(f"Очередь гуи заполнена")

    def _decode_flags(self, flags):
        if flags:
            binary_str = format(flags, '08b')
            array_flags = [int(bit) for bit in binary_str]
            # Сравниваем биты со списком флагов и сохраняем те что 1
            true_flags = [flag for num, flag in zip(array_flags, self.packet_flags) if num != 0]
            decoded_flags = ":".join(true_flags)
            return decoded_flags
        return ""

    @staticmethod
    def _convert_and_increment(hex_little_endian):
        """Функция инкрементирования счетчиков ключей с конвертацией литл-индиан в биг-индиан и обратно"""
        # Преобразуем строку в байты
        little_endian_bytes = bytes.fromhex(hex_little_endian)
        # Преобразуем из little-endian в int
        int_value = int.from_bytes(little_endian_bytes, byteorder='little')
        # Увеличиваем значение на 1
        int_value += 1
        # Преобразуем обратно в байты в little-endian формате
        new_little_endian_bytes = int_value.to_bytes(4, byteorder='little')
        # Преобразуем байты обратно в строку hex
        return new_little_endian_bytes.hex()

    @staticmethod
    def _convert_mac(mac_little):
        """Конвертирует MAC-адрес из little-endian в big-endian формат."""
        if mac_little != "00:00:00:00:00:00":
            pairs = [mac_little[i:i + 2] for i in range(0, 12, 2)]
            mac_convert = ":".join(reversed(pairs))
            return mac_convert
        return mac_little

    def _decrypt_with_work_key(self, address, packet, s_counter):
        work_key = ""
        init_vector = ""

        # Инкрементируем значения счетчиков после получения пакета при этом сравниваем значение младшего байта
        if (self.mac[0] == self.give_addr[address]) and (s_counter != self.work_key_out_counter[address][:2]):
            self.work_key_out_counter[address] = self._convert_and_increment(self.work_key_out_counter[address])
            if s_counter != self.work_key_out_counter[address][:2]:
                self.work_key_out_counter[address] = s_counter + self.work_key_out_counter[address][2:]
                if s_counter == self.work_key_out_counter[address][:2]:
                    self.main_gui.update_message_area(f"Восстановление СЧРК исходящих, для прибора с адресом {address}. Проверьте корректность расшифровки")
        elif (self.mac[1] == self.give_addr[address]) and (s_counter != self.work_key_in_counter[address][:2]):
            self.work_key_in_counter[address] = self._convert_and_increment(self.work_key_in_counter[address])
            if s_counter != self.work_key_in_counter[address][:2]:
                self.work_key_in_counter[address] = s_counter + self.work_key_in_counter[address][2:]
                if s_counter == self.work_key_in_counter[address][:2]:
                    self.main_gui.update_message_area(f"Восстановление СЧРК входящих, для прибора с адресом {address}. Проверьте корректность расшифровки")

        if self.mac[0] == self.give_addr[address]:
            # Получаем начальный вектор расшифровки из saf+daf+SCNum
            init_vector = self.mac[0] + self.mac[1] + self.work_key_out_counter[address]
            work_key = self.work_key_out[address]
        elif self.mac[1] == self.give_addr[address]:
            # Получаем начальный вектор расшифровки из saf+daf+SCNum
            init_vector = self.mac[0] + self.mac[1] + self.work_key_in_counter[address]
            work_key = self.work_key_in[address]
        decode_packet = self._decrypt_aes(init_vector, work_key, packet)

        return decode_packet

    def _decrypt_with_master_key(self, address, packet, s_counter):
        if s_counter != self.master_key_counter[address][:2]: #and (self.work_key_out_counter[address] and self.work_key_in_counter[address]):
            self.master_key_counter[address] = self._convert_and_increment(self.master_key_counter[address])
            if s_counter != self.master_key_counter[address][:2]:
                self.master_key_counter[address] = s_counter + self.master_key_counter[address][2:]
                if s_counter == self.master_key_counter[address][:2]:
                    self.main_gui.update_message_area(f"Восстановление СЧМК для прибора с адресом {address}. Проверьте корректность расшифровки")
        # Получаем начальный вектор расшифровки из saf+daf+SCNum
        init_vector = self.mac[0] + self.mac[1] + self.master_key_counter[address]
        # Расшифровка пакета
        decode_packet = self._decrypt_aes(init_vector, self.master_key, packet)
        # Преобразуем список целых чисел в объект bytes
        byte_sequence = bytes(decode_packet)
        # Используем метод hex() для преобразования в шестнадцатеричную строку
        hex_string = byte_sequence.hex()
        # Забираем рабочий ключ для исходящих пакетов абонента
        work_key_shift = len(hex_string) - 32
        if self.mac[0] == self.give_addr[address]:
            self.work_key_in[address] = hex_string[work_key_shift:]
            self.work_key_in_counter[address] = hex_string[work_key_shift - 8:work_key_shift]
        # Забираем рабочий ключ для входящих пакетов абонента
        elif self.mac[1] == self.give_addr[address]:
            self.work_key_out[address] = hex_string[work_key_shift:]
            self.work_key_out_counter[address] = hex_string[work_key_shift - 8:work_key_shift]
        # Ставим флаг, что ключ получен
        self.new_wkey_saved = True
        return decode_packet

    def _decrypt_aes(self, init_vector_str, key_str, data_str):
        """Расшифровка AES для ориона2"""
        # Преобразуем строку в байты
        key = bytes.fromhex(key_str)
        init_vector = bytes.fromhex(init_vector_str)
        # Шифрование стартовой последовательности (ECB mode)
        cipher = AES.new(key, AES.MODE_ECB)
        encrypted_data = cipher.encrypt(init_vector)

        first_vector = True
        xor_result = ""
        old_data = ""
        decoded = []

        # Расшифровываем все данные в пакете
        while len(data_str) > 0:
            try:
                # Обрезаем по 16 байт (32 символа)
                data = bytes.fromhex(data_str[:32])
                data_str = data_str[32:]
                # После первого прохода начальные данные для расшифровки это предыдущие данные
                if not first_vector:
                    # Шифрование последовательности (ECB mode)
                    encrypted_data = cipher.encrypt(old_data)

                def xor_bytes(a, b):
                    """Функция для выполнения XOR между двумя байтовыми последовательностями"""
                    return bytes(x ^ y for x, y in zip(a, b))

                # Применение XOR к зашифрованным данным
                if len(encrypted_data) == 16:
                    xor_result = xor_bytes(encrypted_data[:16], data) + encrypted_data[16:]
                # Собираем расшифрованные данные
                decoded += xor_result
                # Запоминаем пакет 16 байт как стартовую последовательность для расшифровки последующих пакетов
                old_data = data
                # Сбрасываем флаг начальной последовательности
                first_vector = False
            except Exception as ex:
                self.main_gui.update_message_area(f"Произошла при расшифровке AES: {ex}")
        return decoded
