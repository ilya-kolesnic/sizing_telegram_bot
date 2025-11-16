import logging
from typing import Dict, Any
import configs


def get_service_name(service_type: str) -> str:
    """Возвращает название сервиса в человекочитаемом формате"""
    service_names = {
        'kafka': '☕ Kafka',
        'kubernetes': '⎈ Kubernetes',
        'redis': '🗄️ Redis',
        'rabbitmq': '🐰 RabbitMQ'
    }
    return service_names.get(service_type, service_type)

def calculate_monthly_cost(service_type: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Рассчитывает месячную стоимость на основе результатов sizing.
    :param service_type: Тип сервиса
    :param result: Результаты sizing
    :return: Словарь с деталями стоимости
    """
    
    if service_type == 'kafka':
        brokers_cost = result.get('brokers_count', 0) * configs.pricing['kafka']['broker']
        storage_cost = result.get('storage_needed_gb', 0) * configs.pricing['kafka']['storage_gb']
        total_cost = brokers_cost + storage_cost
        
        return {
            'service': 'Kafka',
            'components': {
                f"Брокеры ({result.get('brokers_count', 0)} шт)": brokers_cost,
                f"Хранилище ({result.get('storage_needed_gb', 0):.2f} GB)": storage_cost
            },
            'total_monthly_rub': round(total_cost, 2),
            'currency': 'RUB'
        }
    
    elif service_type == 'kubernetes':
        control_plane_cost = result.get('control_plane_nodes', 0) * configs.pricing['kubernetes']['control_plane_node']
        worker_cost = result.get('worker_nodes_count', 0) * configs.pricing['kubernetes']['worker_node']
        total_cost = control_plane_cost + worker_cost
        
        return {
            'service': 'Kubernetes',
            'components': {
                f"Control Plane ({result.get('control_plane_nodes', 0)} нод)": control_plane_cost,
                f"Worker ноды ({result.get('worker_nodes_count', 0)} нод)": worker_cost
            },
            'total_monthly_rub': round(total_cost, 2),
            'currency': 'RUB'
        }
    
    elif service_type == 'redis':
        instances_cost = result.get('total_instances', 0) * configs.pricing['redis']['instance']
        ram_cost = result.get('total_memory_gb', 0) * configs.pricing['redis']['ram_gb']
        total_cost = instances_cost + ram_cost
        
        return {
            'service': 'Redis',
            'components': {
                f"Инстансы ({result.get('total_instances', 0)} шт)": instances_cost,
                f"RAM ({result.get('total_memory_gb', 0):.2f} GB)": ram_cost
            },
            'total_monthly_rub': round(total_cost, 2),
            'currency': 'RUB'
        }
    
    elif service_type == 'rabbitmq':
        nodes_cost = result.get('nodes_count', 0) * configs.pricing['rabbitmq']['node']
        ram_cost = result.get('total_memory_gb', 0) * configs.pricing['rabbitmq']['ram_gb']
        total_cost = nodes_cost + ram_cost
        
        return {
            'service': 'RabbitMQ',
            'components': {
                f"Ноды ({result.get('nodes_count', 0)} шт)": nodes_cost,
                f"RAM ({result.get('total_memory_gb', 0):.2f} GB)": ram_cost
            },
            'total_monthly_rub': round(total_cost, 2),
            'currency': 'RUB'
        }
    
    return {}


def format_payment_invoice(cost_details: Dict[str, Any]) -> str:
    """
    Форматирует invoice для отображения пользователю.
    :param cost_details: Детали стоимости
    :return: Отформатированная строка
    """
    if not cost_details:
        return "Ошибка расчёта стоимости."
    
    invoice_text = f"""
💰 Счёт от {configs.payment_provider_name}

📦 Сервис: {cost_details['service']}

📋 Компоненты:
"""
    
    for component, price in cost_details['components'].items():
        invoice_text += f"  • {component}: {price:.2f}\n"
    
    invoice_text += f"""
━━━━━━━━━━━━━━━━━━━━
Итого в месяц: {cost_details['total_monthly_rub']} {cost_details['currency']}

⚡️ При оплате в течении первого часа - бонусные балы.
"""
    
    return invoice_text
