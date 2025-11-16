import logging
from typing import Dict, Any
import telebot


def converter_user_data(message: telebot.types.Message) -> Dict[str, Any] | None:
    """
    Конвертирует данные пользователя из объекта сообщения в словарь.
    :param message: Объект сообщения содержащий информацию о пользователе
    :return: Словарь с данными пользователя или None в случае ошибки
    """
    try:
        user = message.from_user
        user_data = {
            'id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': user.full_name,
            'username': user.username,
            'language_code': user.language_code,
            'is_bot': user.is_bot,
            'is_premium': user.is_premium if hasattr(user, 'is_premium') else False,
        }
        return user_data
    except Exception as error:
        logging.error(f'Ошибка конвертирования данных пользователя: {error}')
        return None
