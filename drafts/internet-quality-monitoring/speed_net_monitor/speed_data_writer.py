import csv
import os
from datetime import datetime


class SpeedDataWriter:
    def __init__(self, filename):
        """
        Инициализация модуля записи данных.
        
        :param filename: Имя файла или путь для сохранения результатов
        """
        self.filename = os.path.abspath(filename)
        self._ensure_dir_exists()
        self._init_file()

    def _ensure_dir_exists(self):
        """Создает все необходимые директории, если они не существуют."""
        directory = os.path.dirname(self.filename)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory)
                print(f'Создана директория: {directory}')
            except OSError as e:
                raise OSError(f'Не удалось создать директорию {directory}: {e}')

    def _init_file(self):
        """Инициализирует файл с заголовками столбцов."""
        if os.path.exists(self.filename):
            return
            
        try:
            with open(self.filename, 'x', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([
                    'timestamp',
                    'ping',
                    'jitter',
                    'download',
                    'upload',
                    'packet_loss',
                    'connection_lost',
                    'connection_recovered',
                    'connection_error',
                    'server_id',
                    'server_name',
                    'server_city',
                    'server_sponsor',
                    'server_host',
                    'server_distance',
                ])
            print(f'Создан файл для записи: {self.filename}')
        except PermissionError:
            raise PermissionError(f'Нет прав на запись в файл {self.filename}')
        except OSError as e:
            raise OSError(f'Ошибка при создании файла {self.filename}: {e}')

    def write_data(self, data):
        """
        Записывает данные измерения в файл.
        
        :param data: Словарь с данными измерения
        """
        try:
            with open(self.filename, 'a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([
                    data['timestamp'],
                    data['ping'],
                    data['jitter'],
                    data['download'],
                    data['upload'],
                    data['packet_loss'],
                    data['connection_lost'],
                    data['connection_recovered'],
                    data.get('connection_error', ''),
                    data.get('server_id', ''),
                    data.get('server_name', ''),
                    data.get('server_city', ''),
                    data.get('server_sponsor', ''),
                    data.get('server_host', ''),
                    data.get('server_distance', ''),
                ])
        except PermissionError:
            print(f'Ошибка: Нет прав на запись в файл {self.filename}')
        except OSError as e:
            print(f'Ошибка записи в файл {self.filename}: {e}')

    def close(self):
        """Закрывает ресурсы записи (если используются)."""
        pass