import logging
import time
import requests
import os
import json
from io import BytesIO

from telebot import TeleBot, types
from telebot import apihelper

from telebot.storage import StateMemoryStorage

import configs
import logs
import database
import keyboards
import supports
import errors
import calculators
import language_code
import ai_processor
import payment_calculator
import excel_exporter
import utils
import classes


apihelper.ENABLE_MIDDLEWARE = True

# Инициализация бота с state storage
state_storage = StateMemoryStorage()
bot = TeleBot(token=configs.telegram_bot_token, state_storage=state_storage)




# Middleware для проверки бана
@bot.middleware_handler(update_types=['message'])
def check_ban_middleware(bot_instance, message):
    user_id = message.from_user.id
    if database.is_user_banned(user_id):
        bot.send_message(
            chat_id=message.chat.id,
            text='⛔ Ваш аккаунт заблокирован за попытку prompt injection.'
        )
        return  # Прерываем обработку
    # Продолжаем обработку
    return True


# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start_handler(message: types.Message) -> None:
    """
    Обработчик команды /start. Приветствует пользователя.
    :param message: Объект сообщения от пользователя
    :return: None
    """
    user_id = message.from_user.id

    if database.is_user_banned(user_id):
        bot.send_message(message.chat.id, '⛔ Ваш аккаунт заблокирован.')
        return

    language = message.from_user.language_code

    user_data = supports.converter_user_data(message)
    if user_data:
        database.insert_user_data(user_id, user_data)

    if language not in language_code.language_list:
        language = language_code.default_language

    welcome_text = language_code.hello_dict[language]
    welcome_text += "\n\nВыберите сервис из меню ниже для расчёта необходимых ресурсов."

    bot.send_message(
        chat_id=message.chat.id,
        text=welcome_text,
        reply_markup=keyboards.main_keyboard(user_id)
    )
    logging.info(f'Пользователь {message.from_user.full_name} (id {user_id}) запустил бота')


# Обработчик команды /help
@bot.message_handler(commands=['help'])
def help_handler(message: types.Message) -> None:
    """
    Обработчик команды /help. Показывает справку.
    :param message: Объект сообщения от пользователя
    :return: None
    """
    help_text = """
🤖 Бот помощник по сайзингу инфраструктурных сервисов

Доступные команды:
/start - Запуск бота
/help - Справка
/menu - Главное меню

Доступные расчёты:
☕ Kafka - расчёт брокеров и хранилища
⎈ Kubernetes - расчёт нод и ресурсов
🗄️ Redis - расчёт памяти и инстансов
🐰 RabbitMQ - расчёт нод и очередей

🤖 AI-корректировка: В конце расчёта вы можете указать дополнительные условия, и ИИ скорректирует результаты с учётом ваших требований.

Просто выберите нужный сервис из меню!
"""
    bot.send_message(
        chat_id=message.chat.id,
        text=help_text,
        reply_markup=keyboards.help_keyboard()
    )


# Обработчик команды /menu
@bot.message_handler(commands=['menu'])
def menu_handler(message: types.Message) -> None:
    """
    Обработчик команды /menu. Показывает главное меню.
    :param message: Объект сообщения от пользователя
    :return: None
    """
    bot.send_message(
        chat_id=message.chat.id,
        text='Главное меню. Выберите сервис:',
        reply_markup=keyboards.main_keyboard(message.from_user.id)
    )


@bot.message_handler(func=lambda message: message.text.lower() in ['☕ kafka', 'kafka', 'кафка'])
def kafka_start(message: types.Message) -> None:
    """Начало процесса расчёта Kafka"""
    start_service_flow('kafka', message)


@bot.message_handler(func=lambda message: message.text.lower() in ['⎈ kubernetes', 'kubernetes', 'k8s', 'кубер'])
def k8s_start(message: types.Message) -> None:
    """Начало процесса расчёта Kubernetes"""
    start_service_flow('kubernetes', message)


@bot.message_handler(func=lambda message: message.text.lower() in ['🗄️ redis', 'redis', 'редис'])
def redis_start(message: types.Message) -> None:
    """Начало процесса расчёта Redis"""
    start_service_flow('redis', message)


@bot.message_handler(func=lambda message: message.text.lower() in ['🐰 rabbitmq', 'rabbitmq', 'rabbit', 'раббит'])
def rabbitmq_start(message: types.Message) -> None:
    """Начало процесса расчёта RabbitMQ"""
    start_service_flow('rabbitmq', message)


def start_service_flow(service_name: str, message: types.Message) -> None:
    """Универсальная функция запуска процесса расчёта для любого сервиса"""
    user_id = message.from_user.id
    chat_id = message.chat.id

    config = utils.get_service_config(service_name)
    if not config:
        bot.send_message(chat_id, 'Ошибка: неизвестный сервис')
        return

    params = utils.get_ordered_parameters(service_name)
    if not params:
        bot.send_message(chat_id, 'Ошибка: параметры не настроены')
        return

    first_param = params[0]
    param_config = config['parameters'][first_param]

    msg = bot.send_message(
        chat_id=chat_id,
        text=f'{config["display_name"]} Расчёт кластера\n\n{param_config["text"]}',
        reply_markup=keyboards.range_keyboard(first_param, param_config['ranges'])
    )

    # Устанавливаем состояние и сохраняем метаданные
    state = utils.get_state_enum(service_name, first_param)
    bot.set_state(user_id, state, chat_id)

    with bot.retrieve_data(user_id, chat_id) as data:
        data['last_message_id'] = msg.message_id
        data['service_name'] = service_name


# === УНИВЕРСАЛЬНЫЕ CALLBACK HANDLERS ===

@bot.callback_query_handler(func=lambda call: call.data.startswith('range_'))
def handle_range_selection(call: types.CallbackQuery) -> None:
    """Универсальный обработчик выбора диапазона для любого параметра любого сервиса"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    # Парсим callback_data: range_param_name_value
    parts = call.data.split('_')
    param_name = '_'.join(parts[1:-1])
    value_str = parts[-1]

    # Получаем сервис из данных пользователя
    with bot.retrieve_data(user_id, chat_id) as data:
        service_name = data.get('service_name')

    if not service_name:
        bot.answer_callback_query(call.id, "Ошибка: сервис не определён")
        return

    service_config = utils.get_service_config(service_name)
    if not service_config or param_name not in service_config['parameters']:
        bot.answer_callback_query(call.id, "Ошибка: неизвестный параметр")
        return

    param_config = service_config['parameters'][param_name]

    # Преобразуем значение
    try:
        if param_config['validation']['type'] == bool:
            value = value_str.lower() == 'true'
        else:
            value = param_config['validation']['type'](value_str)
    except ValueError:
        bot.answer_callback_query(call.id, "Ошибка преобразования значения")
        return

    # Сохраняем значение
    with bot.retrieve_data(user_id, chat_id) as data:
        data[param_name] = value

    # Переходим к следующему шагу
    next_param = utils.get_next_parameter(service_name, param_name)

    if next_param == 'additional_conditions':
        # Последний шаг - показываем экран доп. условий
        with bot.retrieve_data(user_id, chat_id) as data:
            summary = utils.format_summary(service_name, data)

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=summary + language_code.messages['ru']['additional_conditions'].format(
                configs.min_additional_conditions_length),
            reply_markup=keyboards.additional_conditions_keyboard()
        )

        state_group = service_config.get('state_group')
        additional_state = getattr(eval(state_group), 'additional_conditions', None)
        if additional_state:
            bot.set_state(user_id, additional_state, chat_id)
    else:
        # Показываем следующий параметр
        with bot.retrieve_data(user_id, chat_id) as data:
            utils.show_parameter_screen(bot, service_name, chat_id, call.message.message_id, next_param, data)

        next_state = utils.get_state_enum(service_name, next_param)
        bot.set_state(user_id, next_state, chat_id)

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('custom_'))
def handle_custom_input_request(call: types.CallbackQuery) -> None:
    """Универсальный обработчик запроса на ввод своего значения"""
    param_name = call.data.replace('custom_', '')

    if param_name == 'conditions':
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text='✏️ ' + language_code.messages['ru']['additional_conditions'].format(
                configs.min_additional_conditions_length)
        )
        bot.answer_callback_query(call.id)
        return

    # Получаем сервис
    with bot.retrieve_data(call.from_user.id, call.message.chat.id) as data:
        service_name = data.get('service_name')

    if not service_name:
        bot.answer_callback_query(call.id, "Ошибка: сервис не определён")
        return

    service_config = utils.get_service_config(service_name)
    if not service_config or param_name not in service_config['parameters']:
        bot.answer_callback_query(call.id, "Ошибка: неизвестный параметр")
        return

    param_config = service_config['parameters'][param_name]
    validation = param_config['validation']

    hint = ''
    if 'min' in validation and 'max' in validation:
        hint = f'\nВведите число от {validation["min"]} до {validation["max"]}:'

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f'✏️ {param_config["text"]}{hint}'
    )
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('back_from_'))
def handle_back_navigation(call: types.CallbackQuery) -> None:
    """Универсальный обработчик кнопки 'Назад'"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    current_param = call.data.replace('back_from_', '')

    # Получаем сервис
    with bot.retrieve_data(user_id, chat_id) as data:
        service_name = data.get('service_name')

    if not service_name:
        bot.answer_callback_query(call.id, "Ошибка: сервис не определён")
        return

    # Определяем предыдущий параметр
    prev_param = utils.get_prev_parameter(service_name, current_param)

    if not prev_param:
        # Возврат в главное меню
        bot.delete_state(user_id, chat_id)
        bot.delete_message(chat_id, call.message.message_id)
        bot.send_message(
            chat_id=chat_id,
            text='Главное меню. Выберите сервис:',
            reply_markup=keyboards.main_keyboard(user_id)
        )
        bot.answer_callback_query(call.id)
        return

    # Показываем предыдущий экран
    with bot.retrieve_data(user_id, chat_id) as data:
        utils.show_parameter_screen(bot, service_name, chat_id, call.message.message_id, prev_param, data)

    prev_state = utils.get_state_enum(service_name, prev_param)
    bot.set_state(user_id, prev_state, chat_id)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('back_') and not call.data.startswith('back_from_'))
def handle_back_after_validation_error(call: types.CallbackQuery) -> None:
    """Возврат к выбору после ошибки валидации"""
    user_id = call.from_user.id
    param_name = call.data.replace('back_', '')

    with bot.retrieve_data(user_id, call.message.chat.id) as data:
        service_name = data.get('service_name')
        if service_name:
            utils.show_parameter_screen(bot, service_name, call.message.chat.id, call.message.message_id, param_name, data)

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == 'skip_conditions')
def handle_skip_conditions(call: types.CallbackQuery) -> None:
    """Обработка пропуска дополнительных условий"""
    bot.answer_callback_query(call.id)
    bot.delete_message(call.message.chat.id, call.message.message_id)

    with bot.retrieve_data(call.from_user.id, call.message.chat.id) as data:
        data['additional_conditions'] = None
        service_name = data.get('service_name')
        params = data

    if not service_name:
        bot.send_message(call.message.chat.id, 'Ошибка: сервис не определён')
        return

    # Выполняем расчет
    perform_calculation(service_name, call.message, params, None)


def perform_calculation(service_name: str, message: types.Message, params: dict, additional_conditions: str = None):
    """Универсальная функция выполнения расчёта для любого сервиса"""
    service_config = utils.get_service_config(service_name)
    if not service_config:
        bot.send_message(message.chat.id, 'Ошибка: неизвестный сервис')
        return

    user_id = message.chat.id

    logging.info(f'Пользователь {user_id} запустил расчёт {service_name}')

    # Получаем функцию калькулятора
    calculator_name = service_config.get('calculator')
    calculator_func = getattr(calculators, calculator_name, None)

    if not calculator_func:
        bot.send_message(message.chat.id, f'Ошибка: калькулятор {calculator_name} не найден')
        return

    # Базовый расчёт
    try:
        base_result = calculator_func(params)
    except Exception as e:
        logging.error(f'Ошибка расчёта {service_name}: {e}')
        bot.send_message(message.chat.id, 'Ошибка при выполнении расчёта')
        return

    final_result = base_result.copy()
    ai_comment = None

    # ИИ обработка
    if additional_conditions:
        bot.send_message(message.chat.id, language_code.messages['ru']['ai_processing'])
        adjusted_result, ai_comment = ai_processor.adjust_sizing_with_ai(
            service_name, params, base_result, additional_conditions
        )

        if ai_comment == 'PROMPT_INJECTION_DETECTED':
            database.ban_user(user_id)
            bot.send_message(
                message.chat.id,
                language_code.messages['ru']['prompt_injection_detected']
            )
            bot.delete_state(user_id, message.chat.id)
            logging.warning(f'Пользователь {user_id} забанен за prompt injection')
            return

        if adjusted_result:
            final_result = adjusted_result
        elif ai_comment is None:
            bot.send_message(message.chat.id, language_code.messages['ru']['ai_error'])

    # Формирование результата
    result_text = calculators.format_result(service_name, final_result, ai_comment)
    cost_details = payment_calculator.calculate_monthly_cost(service_name, final_result)

    # Сохранение в БД
    calculation_id = database.save_calculation(
        user_id, service_name, params, final_result,
        ai_comment, additional_conditions
    )

    # Отправка результата
    bot.send_message(chat_id=message.chat.id, text=result_text)
    bot.delete_state(user_id, message.chat.id)
    offer_payment_for_calculation(message, calculation_id, cost_details)


# === УНИВЕРСАЛЬНЫЙ MESSAGE HANDLER ===

@bot.message_handler(state=[
    classes.KafkaSizing.messages_per_sec, classes.KafkaSizing.message_size_kb,
    classes.KafkaSizing.retention_hours, classes.KafkaSizing.replication_factor,
    classes.K8sSizing.pods_count, classes.K8sSizing.avg_cpu_per_pod,
    classes.K8sSizing.avg_ram_per_pod_gb, classes.K8sSizing.high_availability,
    classes.RedisSizing.dataset_size_gb, classes.RedisSizing.operations_per_sec,
    classes.RedisSizing.high_availability, classes.RedisSizing.persistence,
    classes.RabbitMQSizing.messages_per_sec, classes.RabbitMQSizing.message_size_kb,
    classes.RabbitMQSizing.queue_depth, classes.RabbitMQSizing.high_availability
])
def handle_parameter_input(message: types.Message) -> None:
    """Универсальный обработчик ввода параметров для всех сервисов"""
    if message.text == '❌ Отмена':
        bot.delete_state(message.from_user.id, message.chat.id)
        bot.send_message(message.chat.id, 'Операция отменена.',
                         reply_markup=keyboards.main_keyboard(message.from_user.id))
        return

    user_id = message.from_user.id
    chat_id = message.chat.id

    # Определяем сервис и параметр из состояния
    current_state = bot.get_state(user_id, chat_id)

    with bot.retrieve_data(user_id, chat_id) as data:
        service_name = data.get('service_name')

    if not service_name:
        bot.send_message(chat_id, 'Ошибка: сервис не определён')
        return

    # Определяем параметр из состояния
    service_name_from_state, param_name = utils.get_service_by_state(str(current_state))

    if not param_name:
        # Пытаемся извлечь имя параметра из имени состояния
        state_name = str(current_state).split(':')[-1]
        param_name = state_name

    service_config = utils.get_service_config(service_name)
    if not service_config or param_name not in service_config['parameters']:
        bot.send_message(chat_id, f'Ошибка: параметр {param_name} не найден')
        return

    param_config = service_config['parameters'][param_name]

    # Валидация и парсинг ввода
    try:
        value = utils.parse_parameter_value(service_name, param_name, message.text)

        # Сохраняем значение
        with bot.retrieve_data(user_id, chat_id) as data:
            data[param_name] = value
            last_msg_id = data.get('last_message_id')

        # Удаляем сообщение пользователя
        try:
            bot.delete_message(chat_id, message.message_id)
        except:
            pass

        # Переходим к следующему шагу
        next_param = utils.get_next_parameter(service_name, param_name)

        if next_param == 'additional_conditions':
            # Последний шаг
            with bot.retrieve_data(user_id, chat_id) as data:
                summary = utils.format_summary(service_name, data)

            try:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=last_msg_id,
                    text=summary + language_code.messages['ru']['additional_conditions'].format(
                        configs.min_additional_conditions_length),
                    reply_markup=keyboards.additional_conditions_keyboard()
                )
            except:
                msg = bot.send_message(
                    chat_id=chat_id,
                    text=summary + language_code.messages['ru']['additional_conditions'].format(
                        configs.min_additional_conditions_length),
                    reply_markup=keyboards.additional_conditions_keyboard()
                )
                with bot.retrieve_data(user_id, chat_id) as data:
                    data['last_message_id'] = msg.message_id

            # Устанавливаем состояние additional_conditions
            state_group = service_config.get('state_group')
            additional_state = getattr(eval(state_group), 'additional_conditions', None)
            if additional_state:
                bot.set_state(user_id, additional_state, chat_id)
        else:
            # Показываем следующий параметр
            with bot.retrieve_data(user_id, chat_id) as data:
                new_msg_id = utils.show_parameter_screen(bot, service_name, chat_id, last_msg_id, next_param, data)
                if new_msg_id != last_msg_id:
                    data['last_message_id'] = new_msg_id

            next_state = utils.get_state_enum(service_name, next_param)
            bot.set_state(user_id, next_state, chat_id)

    except ValueError as e:
        error_msg = param_config['validation'].get('error', str(e))
        bot.send_message(
            chat_id,
            error_msg,
            reply_markup=keyboards.numeric_validation_keyboard(param_name)
        )


@bot.message_handler(state=[
    classes.KafkaSizing.additional_conditions,
    classes.K8sSizing.additional_conditions,
    classes.RedisSizing.additional_conditions,
    classes.RabbitMQSizing.additional_conditions
])
def handle_additional_conditions(message: types.Message) -> None:
    """Универсальный обработчик дополнительных условий для всех сервисов"""
    if message.text == '❌ Отмена':
        bot.delete_state(message.from_user.id, message.chat.id)
        bot.send_message(
            message.chat.id,
            'Операция отменена.',
            reply_markup=keyboards.main_keyboard(message.from_user.id)
        )
        return

    additional_conditions = message.text.strip()

    # Проверка на skip
    if additional_conditions.lower() in ['нет', 'no', 'skip', '-']:
        additional_conditions = None
    elif len(additional_conditions) < configs.min_additional_conditions_length:
        bot.send_message(
            message.chat.id,
            language_code.messages['ru']['conditions_too_short'].format(configs.min_additional_conditions_length),
            reply_markup=keyboards.additional_conditions_keyboard()
        )
        return

    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        service_name = data.get('service_name')
        params = data
        last_msg_id = data.get('last_message_id')

    if not service_name:
        bot.send_message(message.chat.id, 'Ошибка: сервис не определён')
        return

    # Удаляем последнее inline-сообщение
    try:
        bot.delete_message(message.chat.id, last_msg_id)
    except:
        pass

    # Выполняем расчёт
    perform_calculation(service_name, message, params, additional_conditions)


# === ФУНКЦИЯ ФОРМИРОВАНИЯ ПЛАТЕЖА ПОСЛЕ РАСЧЁТА ===
def offer_payment_for_calculation(message: types.Message, calculation_id: int, cost_details: dict) -> None:
    """
    Предлагает пользователю оплатить расчёт
    """
    payment_text = payment_calculator.format_payment_invoice(cost_details)

    # Создаём inline-кнопку для оплаты
    markup = types.InlineKeyboardMarkup()
    pay_button = types.InlineKeyboardButton(
        text=f"💳 Оплатить {cost_details['total_monthly_rub']}",
        callback_data=f"pay_calc_{calculation_id}"
    )
    markup.add(pay_button)

    bot.send_message(
        chat_id=message.chat.id,
        text=payment_text + "\n\nХотите оплатить этот расчёт?",
        reply_markup=markup
    )
    logging.info(f'Предложение пользователю оплатить расчёт {calculation_id}')

# === ОБРАБОТЧИК НАЖАТИЯ КНОПКИ ОПЛАТЫ ===
@bot.callback_query_handler(func=lambda call: call.data.startswith('pay_calc_'))
def handle_payment_request(call: types.CallbackQuery) -> None:
    """Обработка запроса на оплату расчёта"""
    calculation_id = int(call.data.split('_')[-1])
    user_id = call.from_user.id

    logging.info(f'Поиск расчёта {calculation_id} пользователя {user_id}')

    # Получаем детали расчёта из базы
    conn, cursor = database.postgre_init()
    if conn is None:
        bot.answer_callback_query(call.id, "Ошибка подключения к базе данных")
        return

    try:
        cursor.execute(
            """
            SELECT c.service_type, c.result_params, p.id as payment_id, p.payment_status
            FROM calculations c
            LEFT JOIN payments p ON c.id = p.calculation_id AND p.user_id = %s
            WHERE c.id = %s AND c.user_id = %s
            """,
            (user_id, calculation_id, user_id)
        )
        result = cursor.fetchone()

        if not result:
            bot.answer_callback_query(call.id, "Расчёт не найден")
            return

        service_type = result[0]
        result_params = result[1] if isinstance(result[1], dict) else json.loads(json.dumps(result[1]))
        # Рассчитываем стоимость
        cost_details = payment_calculator.calculate_monthly_cost(service_type, result_params)

        if result[2] and result[3]:
            payment_id = result[2]
            payment_status = result[3]

            # Проверяем, не оплачен ли уже этот расчёт
            if payment_id and payment_status == 'successful':
                bot.answer_callback_query(call.id, "Этот расчёт уже оплачен!")
                return
        else:
            # Сохраняем платёж в базе
            payment_id = database.save_payment(
                user_id=user_id,
                calculation_id=calculation_id,
                amount=cost_details['total_monthly_rub'],
                currency=cost_details['currency'],
                payload=f"{service_type}_calculation_{calculation_id}"
            )
            if not payment_id:
                bot.answer_callback_query(call.id, "Ошибка создания платежа")
                return

        # Формируем детали для платежа
        prices = []
        for component, price in cost_details['components'].items():
            # Telegram принимает суммы в наименьших единицах валюты (центы для RUB)
            prices.append(types.LabeledPrice(label=component[:30], amount=int(price * 100)))

        bot.send_invoice(
            chat_id=call.message.chat.id,
            title=f'Оплата расчёта {service_type}',
            description=f'Месячная стоимость инфраструктуры для {service_type}',
            invoice_payload=f"{service_type}_{calculation_id}_{payment_id}",
            provider_token=configs.payment_provider_token,
            currency='RUB',
            prices=prices,
            need_name=True,
            need_email=True,
            need_phone_number=True,
            start_parameter=f"payment_{payment_id}"
        )

        # Удаляем inline-кнопку
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )

        bot.answer_callback_query(call.id, 'Нажмите кнопку "Заплатить"')

    except Exception as error:
        logging.error(f'Ошибка при формировании платежа: {error}')
        bot.answer_callback_query(call.id, "Ошибка при формировании платежа")
    finally:
        conn.close()


# === ОБРАБОТЧИК ПРЕДВАРИТЕЛЬНОЙ ПРОВЕРКИ ПЛАТЕЖА ===
@bot.pre_checkout_query_handler(func=lambda query: True)
def handle_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery) -> None:
    """Обработка предварительной проверки платежа"""
    try:
        # Здесь можно добавить дополнительную валидацию
        bot.answer_pre_checkout_query(
            pre_checkout_query_id=pre_checkout_query.id,
            ok=True
        )
        logging.info(f"Предварительная проверка платежа успешна для пользователя {pre_checkout_query.from_user.id}")
    except Exception as error:
        logging.error(f'Ошибка при предварительной проверке платежа: {error}')
        bot.answer_pre_checkout_query(
            pre_checkout_query_id=pre_checkout_query.id,
            ok=False,
            error_message="Произошла ошибка при проверке платежа. Попробуйте позже."
        )


# === ОБРАБОТЧИК УСПЕШНОГО ПЛАТЕЖА ===
@bot.message_handler(content_types=['successful_payment'])
def handle_successful_payment(message: types.Message) -> None:
    """Обработка успешного платежа"""
    payment_info = message.successful_payment

    user_id = message.from_user.id
    full_name = message.from_user.full_name
    logging.info(f"Обработка успешного платежа от пользователя {full_name} (id {user_id}), информация платежа: {payment_info}")

    # Разбираем payload
    payload_parts = payment_info.invoice_payload.split('_')
    if len(payload_parts) < 3:
        logging.error(f"Неверный формат payload: {payment_info.invoice_payload}")
        bot.send_message(
            chat_id=message.chat.id,
            text="Ошибка обработки платежа. Обратитесь в поддержку."
        )
        return

    service_type = payload_parts[0]
    try:
        payment_id = int(payload_parts[2])
    except (ValueError, TypeError):
        errors.error_save(short_error=f"Неверный формат payment_id в payload: {payload_parts[2]}",bot=bot)
        return

    # Обновляем статус платежа
    success = database.update_payment_status(
        payment_id=payment_id,
        status='successful',
        provider_charge_id=payment_info.provider_payment_charge_id,
        telegram_charge_id=payment_info.telegram_payment_charge_id
    )

    if success:
        # Формируем сообщение об успешной оплате
        success_message = f"""
✅ Платёж успешно завершён!
Сервис: {service_type}
Сумма: {payment_info.total_amount / 100:.2f}
ID платежа: {payment_id}

Ваш расчёт оплачен на один месяц использования указанных ресурсов.
Спасибо за доверие! 🚀
"""
        bot.send_message(
            chat_id=message.chat.id,
            text=success_message,
            reply_markup=keyboards.main_keyboard(user_id)
        )

        logging.info(f"Успешный платёж от пользователя {full_name} (id {user_id}), ID платежа: {payment_id}")
    else:
        bot.send_message(
            chat_id=message.chat.id,
            text="Платёж прошёл успешно, но возникла ошибка при обновлении статуса в базе. Обратитесь в поддержку."
        )
        logging.error(f"Ошибка обновления статуса платежа {payment_id} для пользователя {user_id}")


# === ОБРАБОТЧИК ИСТОРИИ ПЛАТЕЖЕЙ ===
@bot.message_handler(func=lambda message: message.text == '💰 История платежей')
def payments_history_handler(message: types.Message) -> None:
    """Показывает историю платежей пользователя."""
    user_id = message.from_user.id
    payments = database.get_user_payments(user_id, limit=5)

    if not payments:
        bot.send_message(
            chat_id=message.chat.id,
            text='📋 У вас пока нет платежей.',
            reply_markup=keyboards.main_keyboard(user_id)
        )
        return

    # Формируем сообщение с историей платежей
    history_text = "💰 Ваша история платежей:\n\n"
    for payment in payments:
        status_emoji = "✅" if payment['status'] == 'successful' else "⏳" if payment['status'] == 'pending' else "❌"
        service_name = payment_calculator.get_service_name(payment['service_type'])

        history_text += f"{status_emoji} {payment['created_at']}\n"
        history_text += f"Сервис: {service_name}\n"
        history_text += f"Сумма: {payment['amount']:.2f} {payment['currency']}\n"
        history_text += f"Статус: {payment['status']}\n"
        history_text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    bot.send_message(
        chat_id=message.chat.id,
        text=history_text,
        reply_markup=keyboards.main_keyboard(user_id)
    )


# Обработчик для кнопки "История расчётов"
@bot.message_handler(func=lambda message: message.text == '📊 История расчётов')
def history_handler(message: types.Message) -> None:
    """Показывает историю расчётов пользователя."""
    user_id = message.from_user.id

    # Получаем историю расчётов
    calculations = database.get_user_calculations_history(user_id)

    if not calculations:
        bot.send_message(
            chat_id=message.chat.id,
            text='📋 У вас пока нет сохранённых расчётов.',
            reply_markup=keyboards.main_keyboard(user_id)
        )
        return

    # Формируем сообщение с историей
    history_text = "📋 Ваши последние расчёты:\n\n"
    for calc in calculations:
        history_text += calculators.format_history_item(calc)

    # Добавляем информацию о том, как получить полные детали
    history_text += "\nДля получения полных результатов и экспорта в Excel выполните новый расчёт или выберите расчёт из списка выше."

    bot.send_message(
        chat_id=message.chat.id,
        text=history_text,
        reply_markup=keyboards.main_keyboard(message.from_user.id)  # True так как у пользователя есть расчёты
    )


# Обработчик для кнопки "Экспорт в Excel"
@bot.message_handler(func=lambda message: message.text == '📤 Экспорт в Excel')
def export_excel_handler(message: types.Message) -> None:
    """Обработчик экспорта расчётов в Excel."""
    try:
        user_id = message.from_user.id
        # Получаем расчёты пользователя
        calculations = database.get_user_calculations_history(user_id)

        if not calculations:
            bot.send_message(
                chat_id=message.chat.id,
                text="У вас нет сохранённых расчётов для экспорта.",
                reply_markup=keyboards.main_keyboard(user_id)
            )
            return

        # Экспортируем в Excel
        excel_buffer = excel_exporter.export_calculation_to_excel(calculations[-1])

        if not excel_buffer or not isinstance(excel_buffer, BytesIO):
            bot.send_message(
                chat_id=message.chat.id,
                text="❌ Ошибка при создании Excel файла. Попробуйте позже.",
                reply_markup=keyboards.main_keyboard(user_id)
            )
            return

        # Отправляем файл пользователю
        file_name = f"calculation_{calculations[-1]['created_at'].replace(' ', '_').replace(':', '-')}.xlsx"
        bot.send_document(
            chat_id=message.chat.id,
            document=excel_buffer.getvalue(),
            visible_file_name=file_name,
            caption="📊 Ваш последний расчёт в формате Excel",
            reply_markup=keyboards.main_keyboard(user_id)
        )

        logging.info(f"Пользователь {user_id} успешно экспортировал расчёт в Excel")
        excel_buffer.close()

    except Exception as error:
        logging.error(f"Ошибка при экспорте в Excel: {error}")
        errors.error_save(short_error=f"Ошибка экспорта в Excel: {str(error)}", bot=bot)
        bot.send_message(
            chat_id=message.chat.id,
            text="❌ Произошла ошибка при экспорте данных. Администраторы уведомлены.",
            reply_markup=keyboards.main_keyboard(message.from_user.id)
        )


# Обработчик для кнопки "Помощь"
@bot.message_handler(func=lambda message: message.text == 'ℹ️ Помощь')
def help_button_handler(message: types.Message) -> None:
    """Обработчик кнопки помощи."""
    help_handler(message)


@bot.message_handler(func=lambda message: True)
def unknown_message(message: types.Message) -> None:
    """Обработчик неизвестных сообщений."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    current_state = bot.get_state(user_id, chat_id)

    if current_state:
        state_str = str(current_state)

        # Проверяем, находится ли пользователь в состоянии ввода параметра или доп. условий
        if ':additional_conditions' in state_str:
            # Пользователь в состоянии ввода дополнительных условий
            handle_additional_conditions(message)
        elif ':' in state_str:
            # Пользователь в состоянии ввода параметра (формат "ServiceSizing:param_name")
            # Получаем сервис из данных пользователя, а не из state_str
            with bot.retrieve_data(user_id, chat_id) as data:
                service_name = data.get('service_name')

            if service_name:
                # Перенаправляем на универсальный обработчик ввода параметров
                handle_parameter_input(message)
            else:
                # Сервис не определён - сбрасываем состояние
                bot.delete_state(user_id, chat_id)
                bot.send_message(
                    chat_id=chat_id,
                    text='Произошла ошибка. Пожалуйста, начните заново.',
                    reply_markup=keyboards.main_keyboard(user_id)
                )
        else:
            # Неизвестное состояние - сбрасываем
            bot.delete_state(user_id, chat_id)
            bot.send_message(
                chat_id=chat_id,
                text='Произошла ошибка. Пожалуйста, начните заново.',
                reply_markup=keyboards.main_keyboard(user_id)
            )
    else:
        bot.send_message(
            chat_id=chat_id,
            text='Неизвестная команда. Используйте меню для выбора действия.',
            reply_markup=keyboards.main_keyboard(user_id)
        )


def check_internet() -> bool:
    """
    Проверяет доступность интернет-соединения.
    :return: True если интернет доступен, False в противном случае
    """
    try:
        requests.get('https://api.telegram.org', timeout=2)
        return True
    except:
        return False


def run_bot() -> None:
    """
    Запускает бота в режиме polling с обработкой ошибок.
    :return: None
    """
    logs.setup_logs()
    database.create_tables()
    
    if not configs.openrouter_api_key:
        logging.warning('⚠️ OPENROUTER_API_KEY не установлен! AI-функции будут недоступны.')
    
    run = True
    
    while run:
        logging.info('Цикл запустился')
        try:
            run = False
            waiting = False
            
            # Ожидание подключения к интернету
            while not check_internet():
                if not waiting:
                    logging.info('Ожидание сетевого подключения...')
                waiting = True
                time.sleep(5)
            
            logging.info('Бот запустился')
            bot.polling(interval=2, timeout=30, long_polling_timeout=60, none_stop=True)
            time.sleep(1)
            
        except requests.exceptions.ConnectionError as error:
            logging.error(f'Произошла ошибка с сетью. Соединение порвалось: {error}')
            time.sleep(2)
            run = True
            
        except requests.exceptions.ReadTimeout as error:
            logging.error(f'Произошла ошибка с сетью. Обрыв соединение, время вышло: {error}')
            time.sleep(2)
            run = True
            
        except KeyboardInterrupt:
            logging.info('Остановка бота')
            bot.stop_polling()
            break
            
        except (Exception, BaseException) as error:
            errors.error_save(short_error=str(error), bot=bot)
            logging.error(f'Polling failed: {error}')
            run = True


if __name__ == '__main__':
    run_bot()
