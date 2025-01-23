import subprocess
import sys
import os

def get_version():
    # Из основного скрипта
    import cum_port
    return cum_port.__version__

def get_app_name():
    # Из основного скрипта
    import cum_port
    return cum_port.__app_name__

def build_executable(name, version):
    # Формируем имя файла с версией
    exe_name = f"{name}_{version}"

    # Опции PyInstaller
    options = [
        '--onefile',  # Собрать в один файл
        f'--name={exe_name}',  # Имя файла
        '--icon=icon.ico',  # Иконка
        '--windowed',  # Без консоли
        'cum_port.py'  # Ваш основной скрипт
    ]

    # Формируем команду
    command = ['pyinstaller'] + options

    print(f"Запуск PyInstaller с командой: {' '.join(command)}")

    # Выполняем команду
    result = subprocess.run(command)

    if result.returncode == 0:
        print("Сборка успешно завершена.")
        # Переименование файла, если необходимо
        dist_path = os.path.join('dist', f"{exe_name}.exe")
        if not os.path.exists(dist_path):
            print(f"Не удалось найти файл {dist_path}")
        else:
            print(f"Файл находится здесь: {dist_path}")
    else:
        print("Сборка завершилась с ошибкой.")
        sys.exit(result.returncode)


def main():
    version = get_version()
    name = get_app_name()
    print(f"Текущее наименование: {name}_{version}")
    build_executable(name,version)


if __name__ == "__main__":
    main()