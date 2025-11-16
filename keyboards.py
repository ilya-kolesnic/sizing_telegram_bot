import logging
from telebot import types

import database


def main_keyboard(user_id: int) -> types.ReplyKeyboardMarkup:
    """
    Создаёт основную клавиатуру для главного меню бота.
    :return: Объект ReplyKeyboardMarkup с кнопками главного меню
    """
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    button_1 = types.KeyboardButton('☕ Kafka')
    button_2 = types.KeyboardButton('⎈ Kubernetes')
    button_3 = types.KeyboardButton('🗄️ Redis')
    button_4 = types.KeyboardButton('🐰 RabbitMQ')
    pay_history_button = types.KeyboardButton('💰 История платежей')
    calc_history_button = types.KeyboardButton('📊 История расчётов')
    help_button = types.KeyboardButton('ℹ️ Помощь')
    markup.add(button_1, button_2)
    markup.add(button_3, button_4)

    # Добавляем кнопку экспорта только если есть расчёты
    if database.user_has_calculations(user_id=user_id):
        button_export = types.KeyboardButton('📤 Экспорт в Excel')
        markup.add(calc_history_button, button_export)
        markup.add(pay_history_button, help_button)
    else:
        markup.add(pay_history_button, help_button)

    logging.info('Создана клавиатура для главного меню')
    return markup


def help_keyboard() -> types.InlineKeyboardMarkup:
    """
    Создаёт inline-клавиатуру для меню помощи.
    :return: Объект InlineKeyboardMarkup с кнопками меню помощи
    """
    markup = types.InlineKeyboardMarkup()
    button_1 = types.InlineKeyboardButton(
        text='📖 Документация Kafka',
        url='https://kafka.apache.org/documentation/'
    )
    button_2 = types.InlineKeyboardButton(
        text='📖 Документация Kubernetes',
        url='https://kubernetes.io/docs/'
    )
    button_3 = types.InlineKeyboardButton(
        text='📖 Документация Redis',
        url='https://redis.io/documentation'
    )
    button_4 = types.InlineKeyboardButton(
        text='📖 Документация RabbitMQ',
        url='https://www.rabbitmq.com/documentation.html'
    )
    markup.add(button_1)
    markup.add(button_2)
    markup.add(button_3)
    markup.add(button_4)
    logging.info('Создана клавиатура для меню помощи')
    return markup


def cancel_keyboard() -> types.ReplyKeyboardMarkup:
    """
    Создаёт клавиатуру с кнопкой отмены.
    :return: Объект ReplyKeyboardMarkup с кнопкой отмены
    """
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button = types.KeyboardButton('❌ Отмена')
    markup.add(button)
    return markup


def range_keyboard(param_name: str, ranges: list) -> types.InlineKeyboardMarkup:
    """
    Создаёт inline-клавиатуру с диапазонами значений и возможностью ввода своего.
    :param param_name: Название параметра для callback_data
    :param ranges: Список кортежей (значение, подпись)
    :return: InlineKeyboardMarkup
    """
    markup = types.InlineKeyboardMarkup(row_width=2)

    # Добавляем кнопки с предустановленными значениями (по 2 в ряд)
    for i in range(0, len(ranges), 2):
        row_buttons = []
        for j in range(2):
            if i + j < len(ranges):
                value, label = ranges[i + j]
                callback_data = f"range_{param_name}_{value}"
                row_buttons.append(types.InlineKeyboardButton(text=label, callback_data=callback_data))
        markup.row(*row_buttons)

    # Кнопка "Ввести своё значение"
    custom_button = types.InlineKeyboardButton(
        text="✏️ Ввести своё значение",
        callback_data=f"custom_{param_name}"
    )

    # Кнопка "Назад" (для возврата к предыдущему шагу)
    back_button = types.InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=f"back_from_{param_name}"
    )

    markup.row(custom_button, back_button)
    return markup


def numeric_validation_keyboard(param_name: str) -> types.InlineKeyboardMarkup:
    """
    Создаёт клавиатуру для возврата к выбору после неверного ввода.
    :param param_name: Название параметра для callback_data
    :return: InlineKeyboardMarkup
    """
    markup = types.InlineKeyboardMarkup()
    back_button = types.InlineKeyboardButton(
        text="↩️ Вернуться к выбору",
        callback_data=f"back_{param_name}"
    )
    markup.add(back_button)
    return markup

def additional_conditions_keyboard() -> types.InlineKeyboardMarkup:
    """
    Создаёт inline-клавиатуру для шага с дополнительными условиями
    """
    markup = types.InlineKeyboardMarkup(row_width=1)
    skip_button = types.InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_conditions")
    custom_button = types.InlineKeyboardButton(text="✏️ Ввести условия", callback_data="custom_conditions")
    back_button = types.InlineKeyboardButton(text="↩️ Назад", callback_data="back_from_additional_conditions")
    markup.add(skip_button)
    markup.add(custom_button)
    markup.add(back_button)
    return markup