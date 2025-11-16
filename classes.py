from telebot.handler_backends import State, StatesGroup

# Определение состояний для сбора данных
class KafkaSizing(StatesGroup):
    messages_per_sec = State()
    message_size_kb = State()
    retention_hours = State()
    replication_factor = State()
    additional_conditions = State()


class K8sSizing(StatesGroup):
    pods_count = State()
    avg_cpu_per_pod = State()
    avg_ram_per_pod_gb = State()
    high_availability = State()
    additional_conditions = State()


class RedisSizing(StatesGroup):
    dataset_size_gb = State()
    operations_per_sec = State()
    high_availability = State()
    persistence = State()
    additional_conditions = State()


class RabbitMQSizing(StatesGroup):
    messages_per_sec = State()
    message_size_kb = State()
    queue_depth = State()
    high_availability = State()
    additional_conditions = State()


class ExportState(StatesGroup):
    waiting_for_export = State()


class PaymentState(StatesGroup):
    waiting_for_payment = State()
