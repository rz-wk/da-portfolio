_conf = {}

# Интервал между замерами, секунд
_conf['speed_monitor_interval'] = 60
# Файл для сохранения результатов
_conf['speed_data_filename'] = 'data/internet_speed.csv'
# Формат метки времени данных
_conf['ts_data_format'] = '%Y-%m-%d %H:%M:%S'
# Сервер для мониторинга метрик (id, словарь или URL)
_conf['server'] = {
    'id': '5681', 
    'name': 'Ekaterinburg', 
    'city': 'Ekaterinburg', 
    'sponsor': 'MOTIV',
    'host': 'speedtest.motivtelecom.ru:8080'
}
# Поиск серверов в указанных городах
_conf['server_preferred_cities'] = ['Ekaterinburg', 'Екатеринбург', 'Yekaterinburg'] #'Nizhny Tagil', 'Pervouralsk', 'Ozersk', 'Chelyabinsk'
# Вывод результатов измерений (0-ошибки, 1-время, скорость, сервер и статус, 2-полный лог со всеми значеними измерений)
_conf['log_measure_result'] = 1
# Формат метки времени логов. Краткий формат для 1, полный для 2
_conf['log_ts_short_format'] = '%H:%M:%S'
_conf['log_ts_full_format'] = '%Y-%m-%d %H:%M:%S'