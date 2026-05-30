import logging
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s:     %(asctime)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

"""
формат вывода:
INFO:     2026-05-31 12:34:56 - [main.py:25] - Сервер запущен
ERROR:    2026-05-31 12:34:57 - [bots.py:42] - Ошибка подключения к БД
"""