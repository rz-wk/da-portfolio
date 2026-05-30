import speedtest
import time
import requests
from datetime import datetime
from threading import Thread
from speed_data_writer import SpeedDataWriter
from conf import _conf


class SpeedNetMonitor:
    def __init__(self, interval=_conf['speed_monitor_interval'], filename=_conf['speed_data_filename'], server=_conf['server']):
        """
        Инициализация монитора скорости интернета.
        
        :param interval: Интервал между замерами в секундах
        :param filename: Имя файла для сохранения результатов
        :param server: Опционально. Сервер для тестирования (ID, словарь или URL)
        """
        self.interval = interval
        self.data_writer = SpeedDataWriter(filename)
        self._running = False
        self._thread = None
        self._last_measurement_success = True
        self.server = server
        self.server_info = {}

        self.get_server()

    def _measure_speed(self):
        """Выполняет замер скорости интернета и возвращает результаты."""
        # Время бага модуля speedtest
        current_minute = datetime.now().minute
        is_bug_time = current_minute % 30 == 0  # 00 или 30 минут

        data = {
            'timestamp': datetime.now().strftime(_conf['ts_data_format']),
            'ping': None,
            'jitter': None,
            'download': None,
            'upload': None,
            'packet_loss': 0,
            'connection_lost': False,
            'connection_recovered': False,
            'connection_error': 'Ok',
            'server_id': self.server_info.get('id', ''),
            'server_name': self.server_info.get('name', ''),
            'server_city': self.server_info.get('city', ''),
            'server_host': self.server_info.get('host', ''),
            'server_sponsor': self.server_info.get('sponsor', ''),
            'server_distance': self.server_info.get('distance', ''),
        }

        try:
            st = speedtest.Speedtest(secure=True)
            
            # Если "баговое" время - делаем паузу
            if is_bug_time:
                time.sleep(60)  # Ждем минуту
                return self._measure_speed()  # Повторяем измерение

            st.get_servers([self.server_info['id']])

            # Измеряем ping и jitter (для jitter делаем несколько измерений)
            try:
                ping_results = []
                for _ in range(5):
                    st.get_best_server()
                    ping_results.append(st.results.ping)
                    time.sleep(0.5)

                data.update({
                    'ping': round(sum(ping_results) / len(ping_results), 2),
                    'jitter': round(max(ping_results) - min(ping_results), 2)
                })
            except speedtest.SpeedtestBestServerFailure as e:
                if is_bug_time:
                    time.sleep(60) # Ждем минуту
                    return self._measure_speed() # Повторяем измерение
                raise

            # Измеряем скорости
            data.update({
                'download': round(st.download() / 1_000_000, 2), # Мбит/с
                'upload': round(st.upload() / 1_000_000, 2) # Мбит/с
            })
            
            # Проверяем потерю соединения (если ping None или скорости 0)
            connection_lost = (data['ping'] is None) or (data['download'] == 0) or (data['upload'] == 0)
            
            # Если было восстановление соединения после обрыва
            recovery_flag = not self._last_measurement_success and not connection_lost

            self._last_measurement_success = not connection_lost

            data.update({
                'connection_lost': connection_lost,
                'connection_recovered': recovery_flag,
                'packet_loss': 100 if connection_lost else 0
            })
            
        except speedtest.SpeedtestHTTPError as e:
            raise ValueError(f'Base HTTP exception for this module. {str(e)}')

        except speedtest.SpeedtestConfigError as e:
            raise ValueError(f'Configuration XML is invalid. {str(e)}')

        except speedtest.SpeedtestServersError as e:
            raise ValueError(f'Servers XML is invalid. {str(e)}')

        except speedtest.ServersRetrievalError as e:
            raise ValueError(f'Could not retrieve speedtest-servers.php. {str(e)}')

        except speedtest.InvalidServerIDType as e:
            raise ValueError(f'Server ID used for filtering was not an integer. {str(e)}')

        except speedtest.NoMatchedServers as e:
            raise ValueError(f'No servers matched when filtering. {str(e)}')

        except speedtest.SpeedtestMiniConnectFailure as e:
            raise ValueError(f'Could not connect to the provided speedtest mini server. {str(e)}')

        except speedtest.InvalidSpeedtestMiniServer as e:
            raise ValueError(f'Server provided as a speedtest mini server does not actually appear to be a speedtest mini server. {str(e)}')

        except speedtest.ShareResultsConnectFailure as e:
            raise ValueError(f'Could not connect to speedtest.net API to POST results. {str(e)}')

        except speedtest.ShareResultsSubmitFailure as e:
            raise ValueError(f'Unable to successfully POST results to speedtest.net API after connection. {str(e)}')

        except speedtest.SpeedtestUploadTimeout as e:
            raise ValueError(f'testlength configuration reached during upload.Used to ensure the upload halts when no additional data should be sent. {str(e)}')

        except speedtest.SpeedtestMissingBestServer as e:
            raise ValueError(f'get_best_server not called or not able to determine best server. {str(e)}')

        except speedtest.SpeedtestBestServerFailure as e:
            if 'Unable to connect to servers to test latency' in str(e):
                time.sleep(60)
                return self._measure_speed()
            else:
                raise ValueError(f'Unable to determine best server. {str(e)}')
            raise
        
        except Exception as e:
            self._log(f'Ошибка измерения. {str(e)}')
            self._last_measurement_success = False
            data.update({
                'connection_lost': True,
                'packet_loss': 100,
                'connection_error': str(e) or 'Unknown'
            })

        return data

    def _monitor_loop(self):
        """Основной цикл мониторинга (с защитой от сюрпризов* и багов** модуля speedtest)
            Особенности:
            1. Если меняется список серверов, запускается поиск и проверка подходящего, после этого измерение повторяется.
            2. При обнаружении "багового" времени (00 или 30 минут):
                - Делается пауза 60 секунд
                - Измерение повторяется автоматически
            3. Если ошибка все же возникает:
                - Она перехватывается и обрабатывается
                - Измерение повторяется через 60 секунд
            
            *— [!] `Speedtest` периодически меняет список доступных серверов, что приводит к ошибке измерения. 
            **— [!] Ошибка `Unable to connect to servers to test latency` возникает, если время измерения n:30 или n:00 [https://community.ipfire.org/t/speedtest-cli-error-unable-to-connect-to-servers-to-test-latency-when-run-from-fcrontab/13315/21?page=2](ссылка)
        """
        while self._running:
            try:
                data = self._measure_speed()

                # Проверяем, что измерение прошло успешно (не было пропущено из-за бага или смены сервера)
                if data.get('ping') is not None:
                    # Запись данных
                    self.data_writer.write_data(data)
                    # Логирование результатов
                    self._log_measurement(data)

                # Время ожидания
                wait_time = self.interval
                if datetime.now().minute % 30 == 0:
                    wait_time = max(wait_time, 60) # Минимум 60 сек, если время бага
                
                # Ждем указанный интервал
                for _ in range(wait_time):
                    if not self._running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                # if type(e).__name__.startswith('ValueError: Base HTTP exception for this module'):
                #     self._log(self._log_timestamp(f'Критическая ошибка в цикле мониторинга: {type(e).__name__}'))
                #     time.sleep(60)
                #     self.get_server()
                # else:
                self._log(f'Критическая ошибка в цикле мониторинга: {type(e).__name__}: {e}') #str(e)
                time.sleep(60)
                # Меняем сервер
                self.get_server()
                    

    def _log_ts(self, lg, ts=_conf['log_ts_short_format'], dt=''):
        tm = datetime.strptime(dt, _conf['log_ts_full_format']) if dt else datetime.now()
        return f'[{tm.strftime(ts)}] {lg}'

    def _log_measurement(self, data):
        """
        Логирует результаты измерения в консоль в удобочитаемом формате.
        :param data: Словарь с данными измерения
        :example:
        [14:30:45] 5681 MegaFon, Ekaterinburg - OK
        
        [2023-12-15 14:30:45] 5681 MegaFon, Ekaterinburg - OK | Ping: 24.56 ms | Jitter: 2.34 ms | Download: 78.34 Mbps | Upload: 36.78 Mbps | Packet loss: 0% 
        
        [2023-12-15 14:31:45] - ОБРЫВ | Ping: -- ms | Jitter: -- ms | Download: -- Mbps | Upload: -- Mbps | Packet loss: 100% | Ошибка: Unable to connect to servers
        """

        server_info = f'{data['server_id']} {data['server_sponsor']}, {data['server_name']}' if data.get('server_name') else ''
        
        status = 'ОБРЫВ' if data.get('connection_lost') else 'OK'
 
        log_message = ''
        if _conf['log_measure_result'] > 0:
            log_message += (
                f'↓{data['download'] or '--'} Mbps '
                f'↑{data['upload'] or '--'} Mbps '
                f'⇋{data['ping'] or '--'} ms | '
                f'{server_info} - {status}'
            )
            # log_message += self._log_timestamp(f'{server_info} - {status}', dt=data['timestamp'])
            # log_message += f'[{data['timestamp'].strftime('%H:%M:%S')}]{server_info} - {status}'
        
        if _conf['log_measure_result'] == 2:
            # log_message += self._log_timestamp(f'{server_info} - {status}', tm='%Y-%m-%d %H:%M:%S', dt=data['timestamp'])
            log_message += (
                f' | '
                f'Ping: {data['ping'] or '--'} ms | '
                f'Jitter: {data['jitter'] or '--'} ms | '
                f'Download: {data['download'] or '--'} Mbps | '
                f'Upload: {data['upload'] or '--'} Mbps | '
                f'Packet loss: {data.get('packet_loss', 0)}%'
            )
        
        if data.get('connection_error') and data.get('connection_error') != 'Ok':
            log_message += f' | Ошибка: {data['connection_error']}'
        
        self._log(log_message, ts=(_conf['log_ts_full_format'] if _conf['log_measure_result'] == 2 else _conf['log_ts_short_format']), dt=data['timestamp'])

        """Логирование в файл"""
        # console_log = '...'
        # print(console_log)
        
        # Дополнительное логирование в файл
        # log_file = "speedtest_monitor.log"
        # try:
        #     with open(log_file, 'a') as f:
        #         f.write(f"{console_log}\n")
        # except IOError as e:
        #     self._log(f'Ошибка записи в лог-файл: {e}')

    def _log(self, lg, ts='', dt=''):
        lg = self._log_ts(lg, ts, dt) if ts else lg
        print(lg)

    def get_server(self, preferred_cities=_conf['server_preferred_cities']):
        """
        Находит и возвращает подходящий сервер для тестирования:
        1. Проверяет доступность указанного в параметрах или настройках сервера (см. _conf['server']).
        2. Если не указан, пытается найти сервер в указанном городе (см. _conf['server_preferred_cities']).
        3. Если не находит, использует автоматический выбор лучшего сервера.
        Возвращает словарь с параметрами сервера
        """

        st = speedtest.Speedtest(secure=True)
        
        def _get_server_params(server={}):
            return {
                'id': server.get('id', 0),
                'name': server.get('name', 'Unknown'),
                'host': server.get('host', 'Unknown'),
                'city': server.get('name', 'Unknown'), #.split('-')[0].strip(),
                'country': server.get('country', 'Unknown'),
                'sponsor': server.get('sponsor', 'Unknown'),
                'distance': server.get('d', 0),
            }
        
        def _get_specific_server(self):
            if not self.server:
                return None
            
            self._log(f'Поиск заданного сервера...') 

            try:
                if isinstance(self.server, (dict, int)):
                    # Для словаря и ID сервера
                    server_id = self.server['id'] if isinstance(self.server, dict) else self.server
                    servers = st.get_servers([server_id])
                    
                    if not servers:
                        raise ValueError(f'Сервер {server_id} не найден')
                    
                    # Поиск полной информации о сервере
                    server_data = None
                    for _, server_list in servers.items():
                        for s in server_list:
                            if s['id'] == server_id:
                                server_data = _get_server_params(s)
                                break
                        if server_data:
                            break
                    
                    if server_data:
                        return server_data
                    
                    raise ValueError(f'Информация о сервере {server_id} отсутствует') 

                elif isinstance(self.server, str):
                    # Для URL сервера
                    response = requests.head(self.server, timeout=5)

                    if response.status_code == 200:
                        return _get_server_params({'host': self.server})
                    
                    raise ValueError(f'Сервер {self.server} недоступен')

            except Exception as e:
                if type(e).__name__ == 'NoMatchedServers':
                    self._log(f'Сервер не найден в списке')
                else:
                    self._log(f'Ошибка валидации сервера: {type(e).__name__}: {e}')

                return None

        def _get_preferred_servers(preferred_cities):
            self._log(f'Поиск серверов в городах: {', '.join(preferred_cities)}...')

            try:
                servers = st.get_servers()
                server_data = None
                for _, server_list in servers.items():
                    for s in server_list:
                        if s.get('name', '') in preferred_cities:
                            server_data = _get_server_params(s)
                    if server_data:
                        break

                if server_data:
                    return server_data

                raise ValueError(f'Сервера на найдены') 
                
            except Exception as e:
                self._log(f'Ошибка поиска серверов: {str(e)}')
            
                return None
        
        def _get_best_server():
            self._log('Автоматический подбор лучшего сервера...')
            
            try:
                best_server = st.get_best_server()

                if best_server:
                    return _get_server_params(best_server)
            
                raise ValueError(f'Сервер не найден')
            
            except Exception as e:
                self._log(f'Ошибка автоматического выбора сервера: {str(e)}')
                
                return None
        
        self.server_info = (
            # 1. Валидация заданного сервера
            # _get_specific_server(self) or

            # 2. Пытаемся найти сервер в указанном городе
            # _get_preferred_servers(preferred_cities) or
            
            # 3. Если не нашли сервер в нужном городе - используем автоматический выбор
            _get_best_server() or
            
            # Нулевой сервер
            _get_server_params()
        )

        self._log(
            f'Найден сервер: {self.server_info['id']} {self.server_info['sponsor']}, {self.server_info['name']}' if self.server_info.get('id') else 'Сервер не найден' 
        )

        return self.server_info

    def start(self):
        """Запускает мониторинг скорости в фоновом режиме."""
        if not self._running:
            self._running = True
            self._thread = Thread(target=self._monitor_loop)
            self._thread.start()
            self._log(f'Мониторинг запущен: {self.server_info.get('id', 'Unknown')} {self.server_info.get('sponsor', 'Unknown')}, {self.server_info.get('name', 'Default')} – интервал {self.interval} секунд')

    def stop(self):
        """Останавливает мониторинг скорости."""
        if self._running:
            self._running = False
            self._thread.join()
            self.data_writer.close()
            self._log('Мониторинг остановлен')


if __name__ == '__main__':
    opts = {
        'interval': 300, # Проверка каждые 5 минут
        # 'server': [25330, 28672]
        'server': 25330
        # 'server': 5681 # Мотив, Екатеринбург
    }

    monitor = SpeedNetMonitor(**opts)
    
    try:
        monitor.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        monitor.stop()