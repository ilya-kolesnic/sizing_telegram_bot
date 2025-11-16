import logging
import database


def check_is_admin(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь администратором.
    :param user_id: ID пользователя в Telegram
    :return: True если администратор, иначе False
    """
    conn, cursor = database.postgre_init()
    if conn is None or cursor is None:
        logging.error('Ошибка подключения к БД')
        return False

    try:
        cursor.execute(
            'SELECT is_admin FROM users WHERE user_id = %s AND is_banned = FALSE',
            (user_id,)
        )
        result = cursor.fetchone()
        return bool(result[0]) if result else False
    except Exception as error:
        logging.error(f'Ошибка проверки прав пользователя: {error}')
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def get_admin_list() -> list:
    """
    Возвращает список администраторов.
    :return: Список ID администраторов
    """
    conn, cursor = database.postgre_init()
    if conn is None or cursor is None:
        logging.error('Ошибка подключения к БД')
        return []

    try:
        cursor.execute(
            'SELECT user_id FROM users WHERE is_admin = TRUE AND is_banned = FALSE'
        )
        result = cursor.fetchall()
        return [row[0] for row in result] if result else []
    except Exception as error:
        logging.error(f'Ошибка получения списка администраторов: {error}')
        return []
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()