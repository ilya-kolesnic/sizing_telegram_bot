"""
Модуль с функциями расчёта ресурсов для различных инфраструктурных сервисов.
"""
import logging
import time
import database
from typing import Dict, Any


def calculate_kafka_sizing(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Рассчитывает размеры для Kafka кластера и сохраняет результат в базу данных.

    :param params: Словарь с параметрами:
        - messages_per_sec: количество сообщений в секунду
        - message_size_kb: средний размер сообщения в КБ
        - retention_hours: время хранения в часах
        - replication_factor: фактор репликации
    :param user_id: ID пользователя Telegram
    :param additional_conditions: Дополнительные условия от пользователя
    :param ai_adjustments: Корректировки, применённые ИИ
    :return: Словарь с результатами расчёта и ID сохранённого расчёта
    """
    try:
        messages_per_sec = params.get('messages_per_sec', 1000)
        message_size_kb = params.get('message_size_kb', 1)
        retention_hours = params.get('retention_hours', 24)
        replication_factor = params.get('replication_factor', 3)

        # Расчёт пропускной способности
        throughput_mb_sec = (messages_per_sec * message_size_kb) / 1024

        # Расчёт необходимого хранилища
        daily_data_gb = (throughput_mb_sec * 3600 * retention_hours) / 1024
        storage_needed_gb = daily_data_gb * replication_factor

        # Рекомендации по количеству брокеров
        brokers_count = max(3, replication_factor)

        # Рекомендации по памяти на брокер
        ram_per_broker_gb = max(8, int(storage_needed_gb / brokers_count / 10))

        # Рекомендации по CPU на брокер
        cpu_per_broker = max(4, int(messages_per_sec / 5000))

        result = {
            'throughput_mb_sec': round(throughput_mb_sec, 2),
            'storage_needed_gb': round(storage_needed_gb, 2),
            'brokers_count': brokers_count,
            'ram_per_broker_gb': ram_per_broker_gb,
            'cpu_per_broker': cpu_per_broker,
            'storage_per_broker_gb': round(storage_needed_gb / brokers_count * 1.2, 2),
            'replication_factor': replication_factor,
            'message_size_kb': message_size_kb,
            'retention_hours': retention_hours,
            'messages_per_sec': messages_per_sec,
            'calculated_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }

        logging.info(f'Kafka sizing calculated: {result}')
        return result
    except Exception as error:
        logging.error(f'Ошибка расчёта Kafka sizing: {error}')
        return {'error': str(error)}


def calculate_k8s_sizing(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Рассчитывает размеры для Kubernetes кластера.
    
    :param params: Словарь с параметрами:
        - pods_count: количество подов
        - avg_cpu_per_pod: средний CPU на под
        - avg_ram_per_pod_gb: средняя RAM на под в ГБ
        - high_availability: требуется ли HA
    :return: Словарь с результатами расчёта
    """
    try:
        pods_count = params.get('pods_count', 50)
        avg_cpu_per_pod = params.get('avg_cpu_per_pod', 0.5)
        avg_ram_per_pod_gb = params.get('avg_ram_per_pod_gb', 1)
        high_availability = params.get('high_availability', True)
        
        # Общие требования для подов
        total_cpu = pods_count * avg_cpu_per_pod
        total_ram_gb = pods_count * avg_ram_per_pod_gb
        
        # Накладные расходы на системные поды (10-20%)
        system_overhead = 1.2
        total_cpu_with_overhead = total_cpu * system_overhead
        total_ram_with_overhead = total_ram_gb * system_overhead
        
        # Рекомендуемое количество нод
        min_nodes = 3 if high_availability else 1
        cpu_per_node = 8  # Стандартная нода
        ram_per_node = 32  # Стандартная нода
        
        nodes_by_cpu = max(min_nodes, int(total_cpu_with_overhead / cpu_per_node) + 1)
        nodes_by_ram = max(min_nodes, int(total_ram_with_overhead / ram_per_node) + 1)
        
        nodes_count = max(nodes_by_cpu, nodes_by_ram)
        
        # Control plane
        control_plane_nodes = 3 if high_availability else 1
        
        result = {
            'total_cpu_required': round(total_cpu_with_overhead, 2),
            'total_ram_gb_required': round(total_ram_with_overhead, 2),
            'worker_nodes_count': nodes_count,
            'control_plane_nodes': control_plane_nodes,
            'recommended_node_size': f'{cpu_per_node} vCPU, {ram_per_node} GB RAM',
            'total_nodes': nodes_count + control_plane_nodes
        }
        
        logging.info(f'K8s sizing calculated: {result}')
        return result
    except Exception as error:
        logging.error(f'Ошибка расчёта K8s sizing: {error}')
        return {}


def calculate_redis_sizing(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Рассчитывает размеры для Redis кластера.
    
    :param params: Словарь с параметрами:
        - dataset_size_gb: размер данных в ГБ
        - operations_per_sec: операций в секунду
        - high_availability: требуется ли HA
        - persistence: требуется ли персистентность
    :return: Словарь с результатами расчёта
    """
    try:
        dataset_size_gb = params.get('dataset_size_gb', 10)
        operations_per_sec = params.get('operations_per_sec', 10000)
        high_availability = params.get('high_availability', True)
        persistence = params.get('persistence', True)
        
        # Накладные расходы Redis (fragmentation, etc)
        memory_overhead = 1.5 if persistence else 1.3
        total_memory_gb = dataset_size_gb * memory_overhead
        
        # Рекомендуемая RAM на инстанс (не более 64 GB для оптимальной работы)
        max_ram_per_instance = 64
        instances_count = max(1, int(total_memory_gb / max_ram_per_instance) + 1)
        
        # HA конфигурация (master + replicas)
        if high_availability:
            total_instances = instances_count * 2  # master + replica
            replicas = instances_count
        else:
            total_instances = instances_count
            replicas = 0
        
        # CPU рекомендации (Redis однопоточный, но нужны запас)
        cpu_per_instance = max(4, int(operations_per_sec / 50000))
        
        # Disk для persistence
        disk_per_instance_gb = 0
        if persistence:
            disk_per_instance_gb = round((total_memory_gb / instances_count) * 1.5, 2)
        
        result = {
            'total_memory_gb': round(total_memory_gb, 2),
            'master_instances': instances_count,
            'replica_instances': replicas,
            'total_instances': total_instances,
            'ram_per_instance_gb': round(total_memory_gb / instances_count, 2),
            'cpu_per_instance': cpu_per_instance,
            'disk_per_instance_gb': disk_per_instance_gb
        }
        
        logging.info(f'Redis sizing calculated: {result}')
        return result
    except Exception as error:
        logging.error(f'Ошибка расчёта Redis sizing: {error}')
        return {}


def calculate_rabbitmq_sizing(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Рассчитывает размеры для RabbitMQ кластера.
    
    :param params: Словарь с параметрами:
        - messages_per_sec: сообщений в секунду
        - message_size_kb: средний размер сообщения в КБ
        - queue_depth: глубина очереди (среднее количество сообщений)
        - high_availability: требуется ли HA
    :return: Словарь с результатами расчёта
    """
    try:
        messages_per_sec = params.get('messages_per_sec', 1000)
        message_size_kb = params.get('message_size_kb', 10)
        queue_depth = params.get('queue_depth', 10000)
        high_availability = params.get('high_availability', True)
        
        # Расчёт памяти для очередей
        queue_memory_gb = (queue_depth * message_size_kb) / (1024 * 1024)
        
        # Накладные расходы RabbitMQ
        system_overhead = 2.0
        total_memory_gb = queue_memory_gb * system_overhead
        
        # Рекомендуемое количество нод
        nodes_count = 3 if high_availability else 1
        
        # RAM на ноду (минимум 8 GB)
        ram_per_node_gb = max(8, int(total_memory_gb / nodes_count))
        
        # CPU на ноду
        cpu_per_node = max(4, int(messages_per_sec / 10000))
        
        # Disk для персистентности
        disk_per_node_gb = ram_per_node_gb * 2
        
        # Пропускная способность
        throughput_mb_sec = (messages_per_sec * message_size_kb) / 1024
        
        result = {
            'nodes_count': nodes_count,
            'ram_per_node_gb': ram_per_node_gb,
            'cpu_per_node': cpu_per_node,
            'disk_per_node_gb': disk_per_node_gb,
            'throughput_mb_sec': round(throughput_mb_sec, 2),
            'total_memory_gb': round(total_memory_gb, 2),
            'queue_memory_gb': round(queue_memory_gb, 2)
        }
        
        logging.info(f'RabbitMQ sizing calculated: {result}')
        return result
    except Exception as error:
        logging.error(f'Ошибка расчёта RabbitMQ sizing: {error}')
        return {}


def format_result(service_type: str, result: Dict[str, Any], ai_comment: str = None) -> str:
    """
    Форматирует результат расчёта в читаемую строку.
    
    :param service_type: Тип сервиса
    :param result: Результат расчёта
    :param ai_comment: Комментарий от ИИ о корректировках
    :return: Отформатированная строка
    """
    if not result:
        return "Ошибка при расчёте параметров."
    
    ai_section = ""
    if ai_comment:
        ai_section = f"\n🤖 Корректировки ИИ:\n{ai_comment}\n"
    
    if service_type == 'kafka':
        return f"""
📊 Результаты расчёта для Kafka:

🔸 Пропускная способность: {result['throughput_mb_sec']} МБ/сек
🔸 Необходимое хранилище: {result['storage_needed_gb']} ГБ
🔸 Количество брокеров: {result['brokers_count']}
🔸 RAM на брокер: {result['ram_per_broker_gb']} ГБ
🔸 CPU на брокер: {result['cpu_per_broker']} ядер
🔸 Хранилище на брокер: {result['storage_per_broker_gb']} ГБ
{ai_section}"""
    
    elif service_type == 'kubernetes':
        return f"""
📊 Результаты расчёта для Kubernetes:

🔸 Требуется CPU: {result['total_cpu_required']} ядер
🔸 Требуется RAM: {result['total_ram_gb_required']} ГБ
🔸 Worker-ноды: {result['worker_nodes_count']}
🔸 Control Plane ноды: {result['control_plane_nodes']}
🔸 Рекомендуемый размер ноды: {result['recommended_node_size']}
🔸 Всего нод: {result['total_nodes']}
{ai_section}"""
    
    elif service_type == 'redis':
        return f"""
📊 Результаты расчёта для Redis:

🔸 Общая память: {result['total_memory_gb']} ГБ
🔸 Master инстансов: {result['master_instances']}
🔸 Replica инстансов: {result['replica_instances']}
🔸 Всего инстансов: {result['total_instances']}
🔸 RAM на инстанс: {result['ram_per_instance_gb']} ГБ
🔸 CPU на инстанс: {result['cpu_per_instance']} ядер
🔸 Диск на инстанс: {result['disk_per_instance_gb']} ГБ
{ai_section}"""
    
    elif service_type == 'rabbitmq':
        return f"""
📊 Результаты расчёта для RabbitMQ:

🔸 Количество нод: {result['nodes_count']}
🔸 RAM на ноду: {result['ram_per_node_gb']} ГБ
🔸 CPU на ноду: {result['cpu_per_node']} ядер
🔸 Диск на ноду: {result['disk_per_node_gb']} ГБ
🔸 Пропускная способность: {result['throughput_mb_sec']} МБ/сек
🔸 Память для очередей: {result['queue_memory_gb']} ГБ
🔸 Общая память: {result['total_memory_gb']} ГБ
{ai_section}"""
    
    return "Неизвестный тип сервиса."


def format_history_item(calculation: dict) -> str:
    """
    Форматирует один элемент истории расчётов для отображения.
    :param calculation: Словарь с данными расчёта
    :return: Отформатированная строка
    """
    service_names = {
        'kafka': '☕ Kafka',
        'kubernetes': '⎈ Kubernetes',
        'redis': '🗄️ Redis',
        'rabbitmq': '🐰 RabbitMQ'
    }

    service_name = service_names.get(calculation['service_type'], calculation['service_type'])

    # Форматируем входные параметры
    input_params_text = ""
    if calculation['service_type'] == 'kafka':
        input_params_text = f"{calculation['input_params'].get('messages_per_sec', 0)} msg/sec, {calculation['input_params'].get('message_size_kb', 0)} KB/msg"
    elif calculation['service_type'] == 'kubernetes':
        input_params_text = f"{calculation['input_params'].get('pods_count', 0)} подов, HA: {'да' if calculation['input_params'].get('high_availability') else 'нет'}"
    elif calculation['service_type'] == 'redis':
        input_params_text = f"{calculation['input_params'].get('dataset_size_gb', 0)} GB данных, {calculation['input_params'].get('operations_per_sec', 0)} ops/sec"
    elif calculation['service_type'] == 'rabbitmq':
        input_params_text = f"{calculation['input_params'].get('messages_per_sec', 0)} msg/sec, {calculation['input_params'].get('queue_depth', 0)} в очереди"

    return f"""
📅 {calculation['created_at']}
{service_name}
📊 Параметры: {input_params_text}
🤖 Корректировки: {calculation['ai_adjustments']}
"""