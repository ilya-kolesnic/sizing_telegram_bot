import pandas as pd
from io import BytesIO
import logging
from typing import Dict, Any, Optional

def export_calculation_to_excel(calculation_data: Dict[str, Any]) -> Optional[BytesIO]:
    """
    Экспортирует данные расчёта в Excel файл
    :param calculation_data: Словарь с данными расчёта
    :return: BytesIO объект с Excel файлом или None в случае ошибки
    """
    try:
        # Создание DataFrame с данными расчёта
        data = {
            'Параметр': [
                'Тип сервиса',
                'Входные параметры',
                'Результаты расчёта',
                'AI корректировки',
                'Дополнительные условия',
                'Дата расчёта'
            ],
            'Значение': [
                calculation_data.get('service_type', ''),
                str(calculation_data.get('input_params', {})),
                str(calculation_data.get('result_params', {})),
                calculation_data.get('ai_adjustments', 'Не применялись'),
                calculation_data.get('additional_conditions', 'Не указаны'),
                calculation_data.get('created_at', '')
            ]
        }
        
        df = pd.DataFrame(data)
        
        # Создание Excel файла в памяти
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Результат расчёта')
            
            # Автоматическая ширина колонок
            worksheet = writer.sheets['Результат расчёта']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = (max_length + 2)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        logging.info('Экспорт расчёта в Excel выполнен успешно')
        return output
    except Exception as error:
        logging.error(f'Ошибка при экспорте в Excel: {error}')
        return None
