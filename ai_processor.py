import logging
import requests
import json
from typing import Dict, Any, Tuple, Optional
import configs


def detect_prompt_injection(text: str) -> bool:
    """
    Детектирует попытки prompt injection в тексте пользователя.
    :param text: Текст от пользователя
    :return: True если обнаружена инъекция, False иначе
    """
    if not configs.prompt_injection_detection_enabled:
        return False

    # Список подозрительных паттернов
    suspicious_patterns = [
        'ignore previous',
        'ignore all',
        'disregard',
        'forget everything',
        'new instructions',
        'system:',
        'assistant:',
        'you are now',
        'act as',
        'pretend you are',
        'roleplay as',
        '<prompt>',
        '</prompt>',
        'ignore above',
        'override instructions',
        'bypass',
        'jailbreak',
        'dan mode',
        'developer mode',
        'admin mode',
        'root access',
        'sudo mode',
        'unrestricted',
        'without limitations',
        'забудь предыдущие',
        'игнорируй инструкции',
        'веди себя как',
        'притворись',
        'новые инструкции',
    ]

    text_lower = text.lower()

    # Проверка на подозрительные паттерны
    for pattern in suspicious_patterns:
        if pattern in text_lower:
            logging.warning(f'Обнаружен подозрительный паттерн: {pattern}')
            return True

    # Проверка на попытки манипуляции системными промптами
    if text.count('"') > 15 or text.count("'") > 15:
        logging.warning('Подозрительное количество кавычек в тексте')
        return True

    # Проверка на попытки использования специальных тегов
    if '<system>' in text_lower or '</system>' in text_lower:
        logging.warning('Обнаружены системные теги')
        return True

    # Проверка на чрезмерную длину (может быть попыткой переполнения контекста)
    if len(text) > 2000:
        logging.warning('Слишком длинный текст дополнительных условий')
        return True

    return False


def validate_adjusted_result(base_result: Dict[str, Any],
                             adjusted_result: Dict[str, Any],
                             service_type: str) -> bool:
    """
    Проверяет корректность скорректированного результата от AI.
    :param base_result: Базовый результат расчёта
    :param adjusted_result: Скорректированный результат от AI
    :param service_type: Тип сервиса
    :return: True если результат валиден
    """
    if not isinstance(adjusted_result, dict):
        logging.error('adjusted_result не является словарём')
        return False

    # Проверяем, что структура совпадает с базовым результатом
    base_keys = set(base_result.keys())
    adjusted_keys = set(adjusted_result.keys())

    if base_keys != adjusted_keys:
        logging.error(f'Структура результата не совпадает. Base: {base_keys}, Adjusted: {adjusted_keys}')
        return False

    # Проверяем типы данных и разумность значений
    for key, value in adjusted_result.items():
        base_value = base_result[key]

        # Проверка типов
        if type(value) != type(base_value):
            logging.error(f'Тип значения {key} изменился: {type(base_value)} -> {type(value)}')
            return False

        # Проверка численных значений
        if isinstance(value, (int, float)):
            # Значения не должны быть отрицательными
            if value < 0:
                logging.error(f'Отрицательное значение для {key}: {value}')
                return False

            # Значения не должны увеличиваться более чем в 10 раз
            if base_value > 0 and value > base_value * 10:
                logging.error(f'Слишком большое увеличение {key}: {base_value} -> {value}')
                return False

            # Значения не должны уменьшаться более чем в 10 раз
            if value > 0 and base_value > value * 10:
                logging.error(f'Слишком большое уменьшение {key}: {base_value} -> {value}')
                return False

    return True


def adjust_sizing_with_ai(service_type: str,
                          base_params: Dict[str, Any],
                          base_result: Dict[str, Any],
                          additional_conditions: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Использует AI для анализа дополнительных условий и корректировки sizing.
    :param service_type: Тип сервиса (kafka, kubernetes, redis, rabbitmq)
    :param base_params: Базовые входные параметры
    :param base_result: Базовые результаты расчёта
    :param additional_conditions: Дополнительные условия от пользователя
    :return: Кортеж (скорректированный_результат, комментарий_ИИ)
    """

    if not configs.openrouter_api_key:
        logging.error('OpenRouter API key не установлен')
        return None, None

    # Проверка на prompt injection
    if detect_prompt_injection(additional_conditions):
        logging.warning(f'Обнаружена попытка prompt injection: {additional_conditions[:100]}...')
        return None, 'PROMPT_INJECTION_DETECTED'

    # Формирование промпта для ИИ
    system_prompt = """You are an expert infrastructure sizing consultant. Your task is to analyze additional requirements and adjust resource calculations.

CRITICAL RULES:
1. Return ONLY valid JSON, no markdown, no explanations outside JSON
2. JSON must have exactly two keys: "adjusted_result" and "comment"
3. "adjusted_result" must have IDENTICAL structure to base_result with adjusted numerical values
4. "comment" must be in Russian and explain changes
5. Only adjust if there's a clear technical reason based on the conditions
6. Be conservative: adjust by 20-50% for most cases, not 2-5x
7. Never return negative values or zeros for resource counts
8. If no adjustment needed, return original values with comment explaining why

Example response format:
{
  "adjusted_result": {
    "brokers": 5,
    "storage_gb": 1200,
    "ram_per_broker_gb": 16
  },
  "comment": "Увеличено количество брокеров с 3 до 5 для обеспечения высокой доступности и отказоустойчивости согласно требованию о 99.99% uptime"
}"""

    user_prompt = f"""Analyze infrastructure sizing adjustment request.

Service: {service_type}

Current Configuration:
{json.dumps(base_params, indent=2, ensure_ascii=False)}

Calculated Resources:
{json.dumps(base_result, indent=2, ensure_ascii=False)}

User Requirements:
{additional_conditions}

Consider:
- High availability and redundancy needs
- Performance requirements (throughput, latency, IOPS)
- Compliance and security requirements
- Scaling and growth expectations
- Cost optimization vs reliability trade-offs

Return JSON with adjusted values and explanation in Russian."""

    try:
        headers = {
            'Authorization': f'Bearer {configs.openrouter_api_key}',
            'Content-Type': 'application/json',
        }

        payload = {
            'model': configs.openrouter_model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            'temperature': 0.2,
            'max_tokens': 1500,
            'response_format': {'type': 'json_object'}
        }

        logging.info(f'Отправка запроса к OpenRouter API для сервиса: {service_type}')

        response = requests.post(
            configs.openrouter_api_url,
            headers=headers,
            json=payload,
            timeout=30
        )

        # Детальное логирование ошибок
        if response.status_code != 200:
            logging.error(f'OpenRouter API вернул статус {response.status_code}')
            logging.error(f'Ответ: {response.text}')
            return None, None

        response.raise_for_status()
        result = response.json()

        # Проверка структуры ответа от OpenRouter
        if 'choices' not in result or not result['choices']:
            logging.error('Некорректный ответ от OpenRouter API: отсутствует choices')
            return None, None

        ai_response = result['choices'][0]['message']['content']
        logging.info(f'Получен ответ от AI (первые 200 символов): {ai_response[:200]}...')

        # Очистка ответа от markdown блоков
        ai_response = ai_response.strip()

        # Парсинг JSON
        try:
            parsed_response = json.loads(ai_response)
        except json.JSONDecodeError as e:
            logging.error(f'Ошибка парсинга JSON от AI: {e}')
            logging.error(f'Ответ AI: {ai_response}')
            return None, None

        # Проверка наличия обязательных ключей
        if 'adjusted_result' not in parsed_response:
            logging.error('Отсутствует ключ adjusted_result в ответе AI')
            return None, None

        if 'comment' not in parsed_response:
            logging.error('Отсутствует ключ comment в ответе AI')
            return None, None

        adjusted_result = parsed_response['adjusted_result']
        comment = parsed_response['comment']

        # Валидация скорректированного результата
        if not validate_adjusted_result(base_result, adjusted_result, service_type):
            logging.error('Скорректированный результат не прошёл валидацию')
            return None, None

        logging.info(f'AI корректировка успешна. Комментарий: {comment[:100]}...')
        return adjusted_result, comment

    except requests.exceptions.Timeout:
        logging.error('Таймаут при запросе к OpenRouter API')
        return None, None
    except requests.exceptions.ConnectionError:
        logging.error('Ошибка подключения к OpenRouter API')
        return None, None
    except requests.exceptions.RequestException as error:
        logging.error(f'Ошибка запроса к OpenRouter API: {error}')
        return None, None
    except json.JSONDecodeError as error:
        logging.error(f'Ошибка парсинга JSON: {error}')
        return None, None
    except KeyError as error:
        logging.error(f'Отсутствует ожидаемый ключ в ответе API: {error}')
        return None, None
    except Exception as error:
        logging.error(f'Неожиданная ошибка при обработке AI: {error}', exc_info=True)
        return None, None