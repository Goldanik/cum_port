import datetime
import queue
import threading
from Crypto.Cipher import AES

"""
def calc_crc7(self, old_crc, in_byte):
        temp = 0
        in_byte ^= old_crc

        if in_byte & 0x01:
            temp ^= 0x49
        if in_byte & 0x02:
            temp ^= 0x25
        if in_byte & 0x04:
            temp ^= 0x4A
        if in_byte & 0x08:
            temp ^= 0x23
        if in_byte & 0x10:
            temp ^= 0x46
        if in_byte & 0x20:
            temp ^= 0x3B
        if in_byte & 0x40:
            temp ^= 0x76
        if in_byte & 0x80:
            temp ^= 0x5B

        return temp

def calculate_crc7(self, data):
        crc7 = 0xFF
        for byte in data:
            crc7 = self.calc_crc7(crc7, byte)
        return crc7

data = [0x01, 0x1f]  # Пример массива данных
crc7_result = calculate_crc7(data)
print(f"CRC7: {crc7_result:#04x}")
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
        self.packet_header = ["SAF", "DAF", "Ackn", "PFirst", "PSyn", "SKeyN", "SMode", "Reserv"]
        # Начальный вектор для расшифровки AES
        self.init_vector = ""
        # Счетчик мастер ключа
        self.master_key_counter = [""] * 32
        # Мастер ключ
        self.master_key = "A4955A7C0C51939E863C135FF468693D"
        # Рабочий ключ и его счетчик для расшифровки исходящего пакета
        self.work_key_out_counter = [""] * 32
        self.work_key_out = [""] * 32
        # Рабочий ключ и его счетчик для расшифровки входящего пакета
        self.work_key_in_counter = [""] * 32
        self.work_key_in = [""] * 32

        # Счетчик для пользовательского фильтра
        self.counter_custom = 0

        # Длина обрезки строк без парсинга (ASCII и HEX)
        self.unparsed_encoding_data_size = 150

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
                            self.main_gui.update_data_area(f"{self.timestamp}  {packet}  ")
                        except queue.Full:
                            self.main_gui.update_message_area(f"Очередь заполнена")
            elif encoding == "ASCII":
                try:
                    while current_buffer and not self.data_process_event.is_set():
                        end = current_buffer.find(b"\x0a", 0)
                        #self.main_gui.update_message_area(f"Данные на парсинг: {len(decoded_data)}, {decoded_data}, {end}")
                        if end == -1 or end == 0:
                            if len(current_buffer) > 200:
                                # Берём данные фиксированной длины
                                packet = current_buffer[:200].decode("ascii", errors="ignore")
                                current_buffer = current_buffer[200:]
                                self.timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")
                            else:
                                try:
                                    additional_buffer = self.data_proc_queue.get(timeout=1)
                                except queue.Empty:
                                    continue  # Если нет данных, продолжаем ожидание
                                current_buffer += additional_buffer
                                self.timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")
                                continue
                        else:
                            # Берём данные до следующего маркера с исключением \n
                            packet = current_buffer[:end-1].decode("ascii", errors="ignore")
                            current_buffer = current_buffer[end+1:]
                        if packet:
                            try:
                                self.logger_queue.put(f"{self.timestamp}  {packet}  ")
                                # Обновляем GUI
                                self.main_gui.update_data_area(f"{self.timestamp}  {packet}  ")
                            except queue.Full:
                                self.main_gui.update_message_area(f"Очередь заполнена")
                except UnicodeDecodeError:
                    self.main_gui.update_message_area(f"Некорректный символ")

    def orion2_parser(self, data_bytes):
        """Парсер для кодировки Orion2."""
        while data_bytes and not self.data_process_event.is_set():
            # Ищем начало пакета 'ff'
            next_ff = data_bytes.find(b"\xFF", 2 if len(data_bytes) > 2 else 0)
            # Если не найдено или в нулевой позиции
            if next_ff == -1 or next_ff == 0:
                try:
                    # Пытаемся получить данные из очереди
                    additional_buffer = self.data_proc_queue.get(timeout=1)
                except queue.Empty:
                    # Если нет данных, продолжаем ожидание
                    continue
                # Получили новую порцию данных, добавляем ее к существующим данным
                data_bytes += additional_buffer
                continue
            # Нашли начало пакета
            else:
                # Формируем пакет из данных в буфере до следующего маркера
                packet = data_bytes[:next_ff].hex()
                # Вырезаем пакет из буфера
                data_bytes = data_bytes[next_ff:]
                # Ставим отметку вермени
                self.timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")

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
            overall_len = 0
            mac = ["00:00:00:00:00:00"] * 2

            # Если включен пропуск запросов, длина пакета больше 4 и пакет начинается на ff
            if self.main_gui.skip_requests and (len(packet) > 4) and packet.startswith('ff'):
                # Заменяем в пакете подмененные при передаче байты
                packet = packet.replace("fe01", "ff")
                packet = packet.replace("fe02", "fe")
                # Получаем адрес абонента
                address = int(packet[2:4], 16) & 0x1F
                # raw_packet = packet
                # Для парсинга заголовка отрезаем первые два байта
                temp_packet = packet[4:]

                # Пакеты IN запросы для каждого адреса
                if temp_packet.startswith('1f'):
                    # Ставим флаг, что пакет получен по запросу
                    was_req = True
                    # Ответы ACK если байт не NACK
                    if temp_packet.find('6f') != 4:
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
                            direction = "s-m"
                        else:
                            # Обрезаем меньше при пакете мастер-ведомый
                            packet = packet[8:len(packet) - 4]
                            direction = "m-s"
                    else:
                        decode = f"Потеря квитанции {temp_packet[:2]}, {ans_packet[:2]}"
                        if was_req:
                            # Обрезаем с полем len если ведомый-мастер
                            packet = packet[12:len(packet)-4]
                            direction = "s-m"
                        else:
                            # Обрезаем меньше при пакете мастер-ведомый
                            packet = packet[8:len(packet) - 4]
                            direction = "m-s"
                        # not_parsed = True

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
                    if temp_packet.startswith('80') and temp_packet.find('9f') == 14:
                        # Получаем адрес прибора
                        address = int(packet[22:24], 16) & 0x1F
                        # Получаем мак прибора
                        self.main_gui.give_addr[address] = temp_packet[2:14]
                        # Получаем мак мастера
                        self.main_gui.give_addr[0] = temp_packet[22:34]
                        continue

                # Проверка пользовательского фильтра
                custom_pattern = self.main_gui.custom_skip_pattern.get().lower()
                if custom_pattern: # and all(c in "0123456789abcdef"for c in custom_pattern):
                    try:
                        self.counter_custom += packet.count(custom_pattern)
                        packet = packet.replace(custom_pattern, "")
                    except Exception as e:
                        self.main_gui.update_message_area(f"Ошибка обработки пользовательского шаблона: {e}")
                # else:
                #     self.update_message_area("Некорректный пользовательский шаблон")

                # Парсинг заголовка пакета
                try:
                    # Парсинг общей длины
                    len_byte = str(packet[:2])
                    if len_byte:
                        overall_len = int(len_byte, 16)
                        packet_len = overall_len
                    # Парсинг типа пакета
                    packet_type_byte = str(packet[3:4])
                    if packet_type_byte:
                        packet_type_int = int(packet_type_byte, 16)
                        if packet_type_int == 0:
                            packet_type = "ACK_SERV"
                        elif packet_type_int == 1:
                            packet_type = "DT_SERV"
                        elif packet_type_int == 2:
                            packet_type = "ACK_DATA"
                        elif packet_type_int == 3:
                            packet_type = "DT_DATA"
                    # Парсинг номера пакета
                    packet_num_byte = str(packet[6:8])
                    if packet_num_byte:
                        packet_num = int(packet_num_byte, 16)
                    # Парсинг флагов содержимого пакета
                    flags = str(packet[4:6])
                    if flags:
                        to_int = int(flags, 16)
                        binary_str = format(to_int, '08b')
                        array_flags = [int(bit) for bit in binary_str]
                         # Сравниваем биты со списком флагов и сохраняем те что 1
                        for num, string in zip(array_flags, self.packet_header):
                            if num != 0:
                                # Если присутствует флаг SKeyN значит пакет зашифрован рабочим ключом
                                if string == "SKeyN":
                                    encrypted_work_key = True
                                else:
                                    decoded_flags += string + ":"
                                # Если присутствует флаг SMode значит пакет зашифрован
                                if string == "SMode":
                                    data_encrypt = True
                                    if encrypted_work_key:
                                        decoded_flags += "WKey"
                                    else:
                                        decoded_flags += "MKey"
                    # Обрезка основной части заголовка
                    packet = packet[8:]
                    # Парсинг и обрезка идентификаторов
                    for item in self.main_gui.give_addr:
                        # Ищем в пакете мак адреса (ид) приборов сохраненные из пакетов GIVEADDR в список give_addr
                        if item:
                            start_index = packet.find(item)
                            if start_index >= 0:
                                if start_index == 0:
                                    mac[0] = item
                                else:
                                    mac[1] = item
                    # Удаляем найденное из тела пакета
                    packet = packet.replace(mac[0], "")
                    packet = packet.replace(mac[1], "")
                    # Конвертируем маки в читаемый вид литл-индиан в биг-индиан
                    mac_convert0 = mac[0]
                    mac_convert1 = mac[1]
                    if mac_convert0 != "00:00:00:00:00:00":
                        pairs = [mac_convert0[i:i + 2] for i in range(0, 12, 2)]
                        mac_convert0 = ":".join(reversed(pairs))
                    if mac_convert1 != "00:00:00:00:00:00":
                        pairs = [mac_convert1[i:i + 2] for i in range(0, 12, 2)]
                        mac_convert1 = ":".join(reversed(pairs))
                    direction += "  " + mac_convert0 + "-" + mac_convert1
                except Exception as e:
                    self.main_gui.update_message_area(f"Ошибка при парсинге заголовка: {e}")

                # Парсинг данных пакета
                try:
                    # Если данные не шифрованы
                    if not data_encrypt:
                        if packet_type == "DT_SERV":
                            serv_cmd_type_byte = str(packet[4:6])
                            if serv_cmd_type_byte:
                                serv_cmd_type = int(serv_cmd_type_byte, 16)
                                if serv_cmd_type == 1:
                                    packet_type += "(SCNumReq)+"
                                elif serv_cmd_type == 2:
                                    packet_type += "(SCNum)+"
                                    # Сохраняем значение счетчика
                                    self.master_key_counter[address] = packet[6:14]
                                elif serv_cmd_type == 3:
                                    packet_type += "(SCWorkKey)+"
                                elif serv_cmd_type == 4:
                                    packet_type += "(SCMasterKey)+"
                        # Дополняем общую длину пакета длиной данных
                        not_encr_data_len_byte = str(packet[:2])
                        if not_encr_data_len_byte:
                            not_encr_data_len = int(not_encr_data_len_byte, 16)
                            packet_len = f"{overall_len}+{not_encr_data_len}"
                        if not decode:
                            decode = "Не шифрованные данные"
                    # Данные шифрованы
                    else:

                        def decrypt_aes(init_vector_str, key_str, data_str):
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
                                    print(f"Произошла при расшифровке: {ex}")
                            return decoded

                        # Начинаем расшифровку только если получен счетчик мастер ключа
                        if self.master_key_counter[address]:
                            # Расшифровка мастер ключом
                            if not encrypted_work_key:
                                # Получаем начальный вектор расшифровки из saf+daf+SCNum
                                self.init_vector = mac[0] + mac[1] + self.master_key_counter[address]
                                # Убираем значение счетчика, mac и crc из данных
                                packet = packet[2:66]
                                # Расшифровка пакета
                                decode_packet = decrypt_aes(self.init_vector, self.master_key, packet)
                                # Получение и сохранение длины дешифрованных данных
                                decoded_data_len = decode_packet[0]
                                packet_len = f"{overall_len}+{decoded_data_len}"
                                # Преобразуем список целых чисел в объект bytes
                                byte_sequence = bytes(decode_packet)
                                # Используем метод hex() для преобразования в шестнадцатеричную строку
                                hex_string = byte_sequence.hex()
                                # Берем свежее значение счетчика мастер ключа
                                # self.master_key_counter[address] = hex_string[8:16]
                                # Забираем рабочий ключ для исходящих пакетов абонента
                                if mac[0] == self.main_gui.give_addr[address]:
                                    self.work_key_in[address] = hex_string[len(hex_string) - 32:]
                                    self.work_key_in_counter[address] = hex_string[24:32]
                                # Забираем рабочий ключ для входящих пакетов абонента
                                elif mac[1] == self.main_gui.give_addr[address]:
                                    self.work_key_out[address] = hex_string[len(hex_string) - 32:]
                                    self.work_key_out_counter[address] = hex_string[24:32]
                                # Сохраняем расшифрованные данные
                                decode = decode_packet
                                # Уточняем тип пакета
                                if packet_type == "DT_SERV":
                                    serv_cmd_type = decode_packet[2]
                                    if serv_cmd_type == 1:
                                        packet_type += "(SCNumReq)+"
                                    elif serv_cmd_type == 2:
                                        packet_type += "(SCNum)+"
                                        # Сохраняем значение счетчика
                                        self.master_key_counter[address] = packet[6:14]
                                    elif serv_cmd_type == 3:
                                        packet_type += "(SCWorkKey)+"
                                    elif serv_cmd_type == 4:
                                        packet_type += "(SCMasterKey)+"
                                # Дополняем общую длину пакета длиной данных
                                data_len = decode_packet[0]
                                packet_len = f"{overall_len}+{data_len}"
                            # Расшифровка рабочим ключом
                            else:
                                work_key = ""
                                if mac[0] == self.main_gui.give_addr[address]:
                                    # Получаем начальный вектор расшифровки из saf+daf+SCNum
                                    self.init_vector = mac[0] + mac[1] + self.work_key_out_counter[address]
                                    work_key = self.work_key_out[address]
                                elif mac[1] == self.main_gui.give_addr[address]:
                                    # Получаем начальный вектор расшифровки из saf+daf+SCNum
                                    self.init_vector = mac[0] + mac[1] + self.work_key_in_counter[address]
                                    work_key = self.work_key_in[address]
                                packet = packet[2:len(packet)-12]
                                decode_packet = decrypt_aes(self.init_vector, work_key, packet)

                                def convert_and_increment(hex_little_endian):
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

                                # Инкрементируем значения счетчиков после получения пакета
                                if mac[0] == self.main_gui.give_addr[address]:
                                    self.work_key_out_counter[address] = convert_and_increment(self.work_key_out_counter[address])
                                elif mac[1] == self.main_gui.give_addr[address]:
                                    self.work_key_in_counter[address] = convert_and_increment(self.work_key_in_counter[address])

                                # Уточняем тип пакета
                                if packet_type == "DT_SERV":
                                    serv_cmd_type = decode_packet[2]
                                    if serv_cmd_type == 1:
                                        packet_type += "(SCNumReq)+"
                                    elif serv_cmd_type == 2:
                                        packet_type += "(SCNum)+"
                                        # Сохраняем значение счетчика
                                        self.master_key_counter[address] = packet[6:14]
                                    elif serv_cmd_type == 3:
                                        packet_type += "(SCWorkKey)+"
                                    elif serv_cmd_type == 4:
                                        packet_type += "(SCMasterKey)+"
                                    elif serv_cmd_type == 10:
                                        packet_type += "(SCAbility)+"
                                elif packet_type == "DT_DATA":
                                    data_cmd_type = decode_packet[1]
                                    if data_cmd_type == 3:
                                        packet_type += "(Cmd)+"
                                    elif data_cmd_type == 4:
                                        packet_type += "(CmdResp)+"
                                    elif data_cmd_type == 6:
                                        packet_type += "(UMsg)+"
                                elif packet_type == "ACK_SERV":
                                    packet_type = "ACK_SERV+"
                                elif packet_type == "ACK_DATA":
                                    packet_type = "ACK_DATA+"
                                # Получение и сохранение длины дешифрованных данных
                                decoded_data_len = decode_packet[0]
                                packet_len = f"{overall_len}+{decoded_data_len}"
                                # Сохраняем расшифрованные данные
                                decode = decode_packet
                        else:
                            decode = "Данные не могут быть расшифрованы, не получен мастер-ключ"
                except Exception as e:
                    self.main_gui.update_message_area(f"Ошибка при парсинге данных: {e}")

            # Отправка данных на экран и в лог-файл
            if packet:
                try:
                    # Отправка данных в лог
                    self.logger_queue.put(f"{self.timestamp}  {decode}  {packet_len}  {packet_num}  "
                                          f"{direction}  {packet_type+decoded_flags}  {packet}")
                except queue.Full:
                    self.main_gui.update_message_area(f"Очередь лога заполнена")
                try:
                    # Обновляем GUI
                    self.main_gui.update_data_area(f"{self.timestamp}@{packet}@{packet_len}"
                                                   f"@{packet_num}@{direction}@{packet_type+decoded_flags}@{decode}")
                except queue.Full:
                    self.main_gui.update_message_area(f"Очередь гуи заполнена")
