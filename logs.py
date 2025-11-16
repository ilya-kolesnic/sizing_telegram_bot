import logging
import datetime
import configs


def setup_logs() -> None:
    """
    Настраивает систему логирования для приложения.
    Создаёт логи в файл и выводит в консоль с форматированием.
    :return: None
    """
    logs_format = '[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s'

    logging.basicConfig(
        level=logging.INFO,
        format=logs_format,
        handlers=[
            logging.FileHandler(
                f'{configs.logs_folder_path}/{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}.log'
            ),
            logging.StreamHandler()
        ],
        encoding='utf-8'
    )
