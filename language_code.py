default_language = 'ru'
language_list = ['ru', 'en']

hello_dict = {
    'ru': 'Добро пожаловать в бот помощник по сайзингу инфраструктурных сервисов! 🚀',
    'en': 'Welcome to the Infrastructure Sizing Helper Bot! 🚀'
}

messages = {
    'ru': {
        'choose_service': 'Выберите сервис для расчёта:',
        'kafka_selected': 'Вы выбрали Kafka. Давайте рассчитаем необходимые ресурсы.',
        'k8s_selected': 'Вы выбрали Kubernetes. Давайте рассчитаем необходимые ресурсы.',
        'redis_selected': 'Вы выбрали Redis. Давайте рассчитаем необходимые ресурсы.',
        'rabbitmq_selected': 'Вы выбрали RabbitMQ. Давайте рассчитаем необходимые ресурсы.',
        'unknown_command': 'Неизвестная команда. Используйте /help для справки.',
        'additional_conditions': 'Опишите дополнительные условия (минимум {} символов) или напишите "нет"/"skip":',
        'conditions_too_short': 'Пожалуйста, опишите условия подробнее (минимум {} символов) или напишите "нет"/"skip" для пропуска.',
        'prompt_injection_detected': '⚠️ Обнаружена попытка prompt injection. Ваш аккаунт заблокирован.',
        'ai_processing': '🤖 Анализирую дополнительные условия с помощью ИИ...',
        'ai_error': '❌ Ошибка при обработке через ИИ. Используются базовые расчёты.',
    },
    'en': {
        'choose_service': 'Choose a service for calculation:',
        'kafka_selected': 'You selected Kafka. Let\'s calculate the required resources.',
        'k8s_selected': 'You selected Kubernetes. Let\'s calculate the required resources.',
        'redis_selected': 'You selected Redis. Let\'s calculate the required resources.',
        'rabbitmq_selected': 'You selected RabbitMQ. Let\'s calculate the required resources.',
        'unknown_command': 'Unknown command. Use /help for help.',
        'additional_conditions': 'Describe additional conditions (minimum {} characters) or write "no"/"skip":',
        'conditions_too_short': 'Please describe the conditions in more detail (minimum {} characters) or write "no"/"skip" to skip.',
        'prompt_injection_detected': '⚠️ Prompt injection attempt detected. Your account has been banned.',
        'ai_processing': '🤖 Analyzing additional conditions using AI...',
        'ai_error': '❌ Error processing via AI. Using basic calculations.',
    }
}
