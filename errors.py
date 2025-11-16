import os.path
import logging
import traceback

import telebot

import admins


def error_save(short_error:str,bot: telebot.TeleBot):
    """
    Сохраняет ошибку в файл и отправляет администраторам.
    :param short_error: Краткое описание ошибки
    :param bot: Экземпляр бота
    """
    full_error = traceback.format_exc()
    error_path = os.path.join('errors', 'last_error.log')
    
    with open(error_path, 'w', encoding='utf-8') as file:
        file.write(short_error)
        file.write('\n')
        file.write(full_error)
    
    for admin_id in admins.get_admin_list():
        try:
            logging.info(f'Отправка сообщения администратору с id: {admin_id}')
            bot.send_document(
                chat_id=admin_id,
                document=open(error_path, 'rb'),
                caption=f'Произошла ошибка в работе бота: {short_error}'
            )
        except (Exception, BaseException) as error:
            logging.error(f'Ошибка при отправке сообщения администратору: {error} \n {traceback.format_exc()}')
