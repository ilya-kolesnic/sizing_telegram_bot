from telebot import TeleBot

import configs
import classes
import keyboards


def get_service_config(service_name: str) -> dict:
    """Получает конфигурацию сервиса"""
    return configs.SERVICE_CONFIGS.get(service_name, {})


def get_ordered_parameters(service_name: str) -> list:
    """Возвращает параметры сервиса в порядке их следования"""
    config = get_service_config(service_name)
    if not config or 'parameters' not in config:
        return []

    params = config['parameters']
    return sorted(params.keys(), key=lambda x: params[x]['order'])


def get_state_enum(service_name: str, param_name: str):
    """Получает enum состояния по имени сервиса и параметра"""
    config = get_service_config(service_name)
    state_group_name = config.get('state_group')

    # Мапинг state groups
    state_groups = {
        'classes.KafkaSizing': classes.KafkaSizing,
        'classes.K8sSizing': classes.K8sSizing,
        'classes.RedisSizing': classes.RedisSizing,
        'classes.RabbitMQSizing': classes.RabbitMQSizing
    }

    state_group = state_groups.get(state_group_name)
    if not state_group:
        return None

    # Получаем состояние по имени параметра
    return getattr(state_group, param_name, None)


def get_service_by_state(state_str: str) -> tuple:
    """Определяет сервис и параметр по строковому представлению состояния"""
    # Парсим строку типа "KafkaSizing:messages_per_sec"
    for service_name, service_config in configs.SERVICE_CONFIGS.items():
        state_group = service_config.get('state_group')
        if state_str.startswith(state_group):
            # Извлекаем имя параметра из состояния
            param_name = state_str.split(':')[-1] if ':' in state_str else None
            return service_name, param_name
    return None, None


def get_next_parameter(service_name: str, current_param: str) -> str:
    """Возвращает следующий параметр в последовательности"""
    params = get_ordered_parameters(service_name)
    try:
        current_index = params.index(current_param)
        if current_index < len(params) - 1:
            return params[current_index + 1]
    except (ValueError, IndexError):
        pass
    return 'additional_conditions'


def get_prev_parameter(service_name: str, current_param: str) -> str:
    """Возвращает предыдущий параметр в последовательности"""
    if current_param == 'additional_conditions':
        params = get_ordered_parameters(service_name)
        return params[-1] if params else None

    params = get_ordered_parameters(service_name)
    try:
        current_index = params.index(current_param)
        if current_index > 0:
            return params[current_index - 1]
    except (ValueError, IndexError):
        pass
    return None


def format_summary(service_name: str, data: dict, up_to_param: str = None) -> str:
    """Форматирует сводку введённых параметров"""
    service_config = get_service_config(service_name)
    if not service_config:
        return ''

    summary = []
    params = get_ordered_parameters(service_name)

    for param in params:
        if param in data and data[param] is not None:
            param_config = service_config['parameters'][param]
            display_template = param_config.get('display', '{value}')
            summary.append(f'✅ Установлено: {display_template.format(value=data[param])}')

        if param == up_to_param:
            break

    return '\n'.join(summary) + '\n\n' if summary else ''


def show_parameter_screen(bot: TeleBot, service_name: str, chat_id: int, message_id: int,
                          param_name: str, data: dict, edit: bool = True) -> int:
    """Показывает экран выбора параметра"""
    config = get_service_config(service_name)
    if not config or param_name not in config['parameters']:
        return message_id

    param_config = config['parameters'][param_name]

    # Формируем сводку предыдущих параметров
    params = get_ordered_parameters(service_name)
    prev_param = params[params.index(param_name) - 1] if params.index(param_name) > 0 else None
    summary = format_summary(service_name, data, prev_param)

    text = summary + param_config['text']
    markup = keyboards.range_keyboard(param_name, param_config['ranges'])

    if edit:
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=markup
            )
            return message_id
        except:
            pass

    # Если редактирование не удалось или edit=False, отправляем новое
    msg = bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)
    return msg.message_id


def parse_parameter_value(service_name: str, param_name: str, text: str):
    """Парсит и валидирует введённое значение параметра"""
    config = get_service_config(service_name)
    if not config or param_name not in config['parameters']:
        raise ValueError("Unknown parameter")

    param_config = config['parameters'][param_name]
    validation = param_config['validation']

    # Кастомный парсер (например, для boolean)
    if 'custom_parse' in param_config:
        return param_config['custom_parse'](text)

    # Стандартная валидация
    value_type = validation['type']
    value = value_type(text)

    # Проверка диапазона (если есть)
    if 'min' in validation and 'max' in validation:
        if value < validation['min'] or value > validation['max']:
            raise ValueError(validation['error'])

    return value