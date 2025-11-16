# Infrastructure Sizing Bot

Telegram-бот помощник для расчёта размеров инфраструктурных сервисов с поддержкой AI-корректировок.

## Поддерживаемые сервисы

- ☕ **Kafka** - расчёт брокеров, хранилища и ресурсов
- ⎈ **Kubernetes** - расчёт worker-нод, control plane и ресурсов
- 🗄️ **Redis** - расчёт памяти, инстансов и репликации
- 🐰 **RabbitMQ** - расчёт нод, очередей и ресурсов

## Особенности

🤖 **AI-корректировка**: В конце каждого расчёта можно указать дополнительные условия (например, "требуется соответствие PCI DSS" или "планируется рост нагрузки в 3 раза"), и ИИ скорректирует результаты с учётом этих требований.

🛡️ **Защита от prompt injection**: Автоматическая детекция попыток манипуляции промптами с блокировкой аккаунтов нарушителей.

💰 **Расчёт стоимости**: Автоматический расчёт месячной стоимости от поставщика BestCloudSolution.

## Установка

1. Клонируйте репозиторий
2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Создайте бота через @BotFather в Telegram и получите токен
4. Установите переменную окружения с API ключом OpenRouter:
```bash
export OPENROUTER_API_KEY="your_key_here"
```

5. Откройте `config.py` и вставьте ваш Telegram токен в `telegram_bot_token`

## Запуск

```bash
python main.py
```

## Использование

1. Запустите бота командой `/start`
2. Выберите нужный сервис из меню
3. Следуйте инструкциям бота для ввода параметров
4. В конце укажите дополнительные условия (минимум 20 символов) или пропустите этот шаг
5. Получите расчёт с учётом AI-корректировок и стоимость

## Примеры дополнительных условий

- "Требуется соответствие стандарту PCI DSS"
- "Планируется рост нагрузки в 3 раза в следующем квартале"
- "


@bot.message_handler(state=KafkaSizing.messages_per_sec)
def kafka_messages_per_sec(message: types.Message) -> None:
    """Получение количества сообщений в секунду."""
    if message.text == '❌ Отмена':
        bot.delete_state(message.from_user.id, message.chat.id)
        bot.send_message(message.chat.id, 'Операция отменена.', reply_markup=keyboards.main_keyboard())
        return
    
    try:
        messages = int(message.text)
        if messages <= 0:
            raise ValueError
        
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data['messages_per_sec'] = messages
        
        bot.send_message(
            chat_id=message.chat.id,
            text='Введите средний размер сообщения в КБ:'
        )
        bot.set_state(message.from_user.id, KafkaSizing.message_size_kb, message.chat.id)
    except ValueError:
        bot.send_message(message.chat.id, 'Пожалуйста, введите корректное положительное число.')


@bot.message_handler(state=KafkaSizing.message_size_kb)
def kafka_message_size(message: types.Message) -> None:
    """Получение размера сообщения."""
    if message.text == '❌ Отмена':
        bot.delete_state(message.from_user.id, message.chat.id)
        bot.send_message(message.chat.id, 'Операция отменена.', reply_markup=keyboards.main_keyboard())
        return
    
    try:
        size = float(message.text)
        if size <= 0:
            raise ValueError
        
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data['message_size_kb'] = size
        
        bot.send_message(
            chat_id=message.chat.id,
            text='Введите время хранения сообщений в часах:'
        )
        bot.set_state(message.from_user.id, KafkaSizing.retention_hours, message.chat.id)
    except ValueError:
        bot.send_message(message.chat.id, 'Пожалуйста, введите корректное положительное число.')


@bot.message_handler(state=KafkaSizing.retention_hours)
def kafka_retention(message: types.Message) -> None:
    """Получение времени хранения."""
    if message.text == '❌ Отмена':
        bot.delete_state(message.from_user.id, message.chat.id)
        bot.send_message(message.chat.id, 'Операция отменена.', reply_markup=keyboards.main_keyboard())
        return
    
    try:
        hours = int(message.text)
        if hours <= 0:
            raise ValueError
        
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data['retention_hours'] = hours
        
        bot.send_message(
            chat_id=message.chat.id,
            text='Введите фактор репликации (обычно 3):'
        )
        bot.set_state(message.from_user.id, KafkaSizing.replication_factor, message.chat.id)
    except ValueError:
        bot.send_message(message.chat.id, 'Пожалуйста, введите корректное положительное число.')


@bot.message_handler(state=KafkaSizing.replication_factor)
def kafka_replication(message: types.Message) -> None:
    """Получение фактора репликации."""
    if message.text == '❌ Отмена':
        bot.delete_state(message.from_user.id, message.chat.id)
        bot.send_message(message.chat.id, 'Операция отменена.', reply_markup=keyboards.main_keyboard())
        return
    
    try:
        replication = int(message.text)
        if replication <= 0:
            raise ValueError
        
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data['replication_factor'] = replication
        
        bot.send_message(
            chat_id=message.chat.id,
            text=language_code.messages['ru']['additional_conditions'].format(config.min_additional_conditions_length)
        )
        bot.set_state(message.from_user.id, KafkaSizing.additional_conditions, message.chat.id)
    except ValueError:
        bot.send_message(message.chat.id, 'Пожалуйста, введите корректное положительное число.')


@bot.message_handler(state=KafkaSizing.additional_conditions)
def kafka_additional_conditions(message: types.Message) -> None:
    """Получение дополнительных условий и выполнение расчёта с ИИ."""
    if message.text == '❌ Отмена':
        bot.delete_state(message.from_user.id, message.chat.id)
        bot.send_message(message.chat.id, 'Операция отменена.', reply_markup=keyboards.main_keyboard())
        return
    
    additional_conditions = message.text.strip()
    
    # Проверка на skip
    if additional_conditions.lower() in ['нет', 'no', 'skip', '-']:
        additional_conditions = None
    elif len(additional_conditions) < config.min_additional_conditions_length:
        bot.send_message(
            message.chat.id,
            language_code.messages['ru']['conditions_too_short'].format(config.min_additional_conditions_length)
        )
        return
    
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        params = data
    
    # Базовый расчёт
    base_result = calculators.calculate_kafka_sizing(params)
    final_result = base_result.copy()
    ai_comment = None
    
    # Если есть дополнительные условия - обработка через ИИ
    if additional_conditions:
        bot.send_message(message.chat.id, language_code.messages['ru']['ai_processing'])
        
        adjusted_result, ai_comment = ai_processor.adjust_sizing_with_ai(
            'kafka', params, base_result, additional_conditions
        )
        
        # Проверка на prompt injection
        if ai_comment == 'PROMPT_INJECTION_DETECTED':
            database.ban_user(message.from_user.id)
            bot.send_message(
                message.chat.id,
                language_code.messages['ru']['prompt_injection_detected']
            )
            bot.delete_state(message.from_user.id, message.chat.id)
            logging.warning(f'Пользователь {message.from_user.id} забанен за prompt injection')
            return
        
        if adjusted_result:
            final_result = adjusted_result
        elif ai_comment is None:
            bot.send_message(message.chat.id, language_code.messages['ru']['ai_error'])
    
    # Формирование результата
    result_text = calculators.format_result('kafka', final_result, ai_comment)
    
    # Расчёт стоимости
    cost_details = payment_calculator.calculate_monthly_cost('kafka', final_result)
    payment_text = payment_calculator.format_payment_invoice(cost_details)
    
    # Сохранение в БД
    database.save_calculation(
        message.from_user.id, 'kafka', params, final_result,
        ai_comment, additional_conditions
    )
    
    bot.send_message(chat_id=message.chat.id, text=result_text)
    bot.send_message(chat_id=message.chat.id, text=payment_text, reply_markup=keyboards.main_keyboard())
    bot.delete_state(message.from_user.id, message.chat.id)


# === KUBERNETES SIZING FLOW ===
@bot.message_handler(func=lambda message: message.text in ['⎈ Kubernetes', 'kubernetes', 'k8s', 'кубер'])
def k8s_start(message: types.Message) -> None:
    """Начало процесса расчёта Kubernetes."""
    bot.send_message(
        chat_id=message.chat.id,
        text='⎈ Расчёт Kubernetes кластера\\n\\nВведите планируемое количество подов:',
        reply_markup=keyboards.cancel_keyboard()
    )
    bot.set_

