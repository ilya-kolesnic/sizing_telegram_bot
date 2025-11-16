import json
import logging
import psycopg
from typing import Tuple, Dict, List, Any
import configs


def postgre_init() -> Tuple[psycopg.Connection | None, psycopg.Cursor | None]:
    """
    Устанавливает соединение с PostgreSQL и возвращает объекты подключения и курсор
    :return: Кортеж из соединения и курсора. В случае ошибки вернёт None, None
    """
    try:
        conn = psycopg.connect(
            dbname=configs.sql_database['db_name'],
            user=configs.sql_database['user'],
            password=configs.sql_database['password'],
            host=configs.sql_database['host'],
            port=configs.sql_database['port']
        )
        cursor = conn.cursor()
        logging.info('Успешное подключение к базе данных PostgreSQL')
        return conn, cursor
    except psycopg.Error as error:
        logging.error(f'Ошибка подключения к БД PostgreSQL: {error}')
        return None, None


def create_tables() -> None:
    """
    Создаёт необходимые таблицы в базе данных PostgreSQL.
    :return: None
    """
    conn, cursor = postgre_init()
    if conn is None:
        return
    try:
        # Таблица пользователей
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                user_data JSONB NOT NULL,
                is_admin BOOLEAN NOT NULL DEFAULT FALSE,
                is_banned BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Таблица расчётов
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS calculations (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                service_type TEXT NOT NULL,
                input_params JSONB NOT NULL,
                result_params JSONB NOT NULL,
                ai_adjustments TEXT,
                additional_conditions TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
            """
        )
        # Таблица платежей
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                calculation_id INTEGER NOT NULL,
                amount NUMERIC(10, 2) NOT NULL,
                currency TEXT NOT NULL DEFAULT 'RUB',
                provider_payment_charge_id TEXT,
                telegram_payment_charge_id TEXT,
                payload TEXT NOT NULL,
                payment_status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (calculation_id) REFERENCES calculations (id)
            )
            """
        )
        conn.commit()
        logging.info('Таблицы успешно созданы или проверены')
    except psycopg.Error as error:
        logging.error(f'Ошибка создания таблиц: {error}')
    finally:
        conn.close()


def insert_user_data(user_id: int, user_data: Dict[str, Any]) -> None:
    """
    Вставляет или обновляет данные пользователя в базе данных.
    :param user_id: ID пользователя Telegram
    :param user_data: Словарь с данными пользователя
    :return: None
    """
    conn, cursor = postgre_init()
    if conn is None:
        return
    user_data_json = json.dumps(user_data)
    try:
        cursor.execute(
            """
            INSERT INTO users (user_id, user_data, is_admin) 
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id)
            DO UPDATE SET user_data = EXCLUDED.user_data
            """,
            (user_id, user_data_json, False)
        )
        conn.commit()
        logging.info('Данные пользователя успешно сохранены в БД')
    except psycopg.Error as error:
        logging.error(f'Ошибка записи в таблицу users: {error}')
    finally:
        conn.close()


def save_calculation(user_id: int, service_type: str, input_params: Dict,
                     result_params: Dict, ai_adjustments: str = None,
                     additional_conditions: str = None) -> int:
    """
    Сохраняет результаты расчёта в базу данных.
    :param user_id: ID пользователя
    :param service_type: Тип сервиса (kafka, k8s, redis, rabbitmq)
    :param input_params: Входные параметры расчёта
    :param result_params: Результаты расчёта
    :param ai_adjustments: Корректировки от ИИ
    :param additional_conditions: Дополнительные условия пользователя
    :return: int calculation id
    """
    conn, cursor = postgre_init()
    if conn is None:
        return
    try:
        cursor.execute(
            """
            INSERT INTO calculations (user_id, service_type, input_params, result_params, 
                                     ai_adjustments, additional_conditions)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (user_id, service_type, json.dumps(input_params), json.dumps(result_params),
             ai_adjustments, additional_conditions)
        )
        conn.commit()
        result = cursor.fetchone()
        logging.info(f'Расчёт для {service_type} сохранён в БД: {result[0]}')
        return int(result[0]) if result else 0
    except psycopg.Error as error:
        logging.error(f'Ошибка сохранения расчёта: {error}')
        return 0
    finally:
        conn.close()


def ban_user(user_id: int) -> None:
    """
    Блокирует пользователя в базе данных.
    :param user_id: ID пользователя
    :return: None
    """
    conn, cursor = postgre_init()
    if conn is None:
        return
    try:
        cursor.execute(
            """
            UPDATE users SET is_banned = TRUE WHERE user_id = %s
            """,
            (user_id,)
        )
        conn.commit()
        logging.warning(f'Пользователь {user_id} заблокирован')
    except psycopg.Error as error:
        logging.error(f'Ошибка блокировки пользователя: {error}')
    finally:
        conn.close()


def is_user_banned(user_id: int) -> bool:
    """
    Проверяет, заблокирован ли пользователь.
    :param user_id: ID пользователя
    :return: True если заблокирован, False иначе
    """
    conn, cursor = postgre_init()
    if conn is None:
        return False
    try:
        cursor.execute(
            """
            SELECT is_banned FROM users WHERE user_id = %s
            """,
            (user_id,)
        )
        result = cursor.fetchone()
        return bool(result[0]) if result else False
    except psycopg.Error as error:
        logging.error(f'Ошибка проверки бана пользователя: {error}')
        return False


def user_has_calculations(user_id: int) -> bool:
    """
    Проверяет, есть ли у пользователя сохранённые расчёты.
    :param user_id: ID пользователя
    :return: True если есть расчёты, False иначе
    """
    conn, cursor = postgre_init()
    if conn is None:
        return False
    try:
        cursor.execute(
                """
                SELECT COUNT(*) 
                FROM calculations as c 
                INNER JOIN users as u ON c.user_id = u.user_id 
                WHERE (c.user_id = %s) AND (u.is_banned = FALSE)
                """,
                (user_id,)
        )
        result = cursor.fetchone()
        return result[0] > 0 if result else False
    except psycopg.Error as error:
        logging.error(f'Ошибка проверки расчётов пользователя (id {user_id}): {error}')
        return False
    finally:
        conn.close()


def get_user_calculations_history(user_id: int, limit: int = 1) -> list:
    """
    Получает историю расчётов пользователя.
    :param user_id: ID пользователя
    :param limit: Максимальное количество записей (по умолчанию 1)
    :return: Список расчётов в формате словарей
    """
    conn, cursor = postgre_init()
    if conn is None or cursor is None:
        return []

    try:
        cursor.execute(
            """
            SELECT id, created_at, service_type, input_params, result_params, 
                   ai_adjustments, additional_conditions
            FROM calculations 
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (user_id, limit)
        )
        results = cursor.fetchall()
        calculations = []

        for row in results:
            # row - это кортеж, обращаемся по индексам
            calculation = {
                'id': row[0],
                'created_at': row[1].strftime("%d.%m.%Y %H:%M") if row[1] else None,
                'service_type': row[2],
                'input_params': row[3] if isinstance(row[3], dict) else json.loads(json.dumps(row[3])),
                'result_params': row[4] if isinstance(row[4], dict) else json.loads(json.dumps(row[4])),
                'ai_adjustments': row[5] or 'Без корректировок',
                'additional_conditions': row[6] or 'Не указаны'
            }
            calculations.append(calculation)

        return calculations
    except psycopg.Error as error:
        logging.error(f'Ошибка получения истории расчётов: {error}')
        return []
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def save_payment(user_id: int, calculation_id: int, amount: float, currency: str = 'RUB',
                 payload: str = '') -> int | None:
    """
    Сохраняет информацию о платеже в базу данных.
    :param user_id: ID пользователя
    :param calculation_id: ID расчёта
    :param amount: Сумма платежа
    :param currency: Валюта
    :param payload: Данные платежа
    :return: ID созданного платежа
    """
    conn, cursor = postgre_init()
    if conn is None:
        return 0
    try:
        cursor.execute(
            """
            INSERT INTO payments (user_id, calculation_id, amount, currency, payload)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (user_id, calculation_id, amount, currency, payload)
        )
        conn.commit()
        result = cursor.fetchone()
        payment_id = result[0] if result else None
        logging.info(f'Платёж #{payment_id} для расчёта {calculation_id} успешно сохранён в БД')
        return payment_id
    except psycopg.Error as error:
        logging.error(f'Ошибка сохранения платежа: {error}')
        return 0
    finally:
        conn.close()


def update_payment_status(payment_id: int, status: str,
                          provider_charge_id: str = None,
                          telegram_charge_id: str = None) -> bool:
    """
    Обновляет статус платежа.
    :param payment_id: ID платежа
    :param status: Новый статус
    :param provider_charge_id: ID платежа у провайдера
    :param telegram_charge_id: ID платежа в Telegram
    :return: True если успешно, False иначе
    """
    conn, cursor = postgre_init()
    if conn is None:
        return False
    try:
        cursor.execute(
            """
            UPDATE payments 
            SET payment_status = %s, 
                provider_payment_charge_id = %s, 
                telegram_payment_charge_id = %s
            WHERE id = %s
            """,
            (status, provider_charge_id, telegram_charge_id, payment_id)
        )
        conn.commit()
        logging.info(f'Статус платежа #{payment_id} обновлён на {status}')
        return True
    except psycopg.Error as error:
        logging.error(f'Ошибка обновления статуса платежа: {error}')
        return False
    finally:
        conn.close()


def get_user_payments(user_id: int, limit: int = 1) -> List[Dict[str, Any]]:
    """
    Получает историю платежей пользователя.
    :param user_id: ID пользователя
    :param limit: Максимальное количество записей
    :return: Список платежей
    """
    conn, cursor = postgre_init()
    if conn is None:
        return []
    try:
        cursor.execute(
            """
            SELECT p.id, p.amount, p.currency, p.payment_status, p.created_at,
                   c.service_type, c.result_params
            FROM payments p
            JOIN calculations c ON p.calculation_id = c.id
            WHERE p.user_id = %s
            ORDER BY p.created_at DESC
            LIMIT %s
            """,
            (user_id, limit)
        )
        results = cursor.fetchall()
        payments = []

        for row in results:
            payment = {
                'id': row[0],
                'amount': float(row[1]),
                'currency': row[2],
                'status': row[3],
                'created_at': row[4].strftime("%d.%m.%Y %H:%M") if row[4] else None,
                'service_type': row[5],
                'result_params': row[6] if isinstance(row[6], dict) else json.loads(json.dumps(row[6]))
            }
            payments.append(payment)

        return payments
    except psycopg.Error as error:
        logging.error(f'Ошибка получения истории платежей: {error}')
        return []
    finally:
        conn.close()
