import requests
import datetime
import pandas as pd
import pytz # Для роботи з часовими поясами

# Функция для форматирования даты в формат Mapon API (UTC)
def format_datetime_for_mapon(dt_object: datetime.datetime) -> str:
    # Mapon ожидает ISO 8601 формат с UTC (Z)
    return dt_object.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'

# Функция для получения списка юнитов
def get_unit_list(api_key: str) -> list:
    url = f"https://mapon.com/api/v1/unit/list.json?key={api_key}"
    print(f"[Main] Попытка получить список юнитов по URL: {url}")
    try:
        response = requests.get(url)
        response.raise_for_status() # Вызывает исключение для HTTP ошибок (4xx или 5xx)
        data = response.json()
        print(f"[Main] Ответ от unit/list.json получен.")

        if 'data' in data and 'units' in data['data'] and isinstance(data['data']['units'], list):
            all_units = data['data']['units']
            print(f"[Main] Успешно получено {len(all_units)} юнитов из API.")
            
            filtered_units = []
            units_filtered_out = 0
            for unit in all_units:
                if isinstance(unit.get('mileage'), (int, float)) and unit['mileage'] > 0 and unit.get('unit_id') is not None:
                    filtered_units.append(unit)
                else:
                    print(f"[Main] Юнит \"{unit.get('label') or unit.get('number') or 'ID:' + str(unit.get('unit_id'))}\" (ID: {unit.get('unit_id')}) пропущен: mileage ({unit.get('mileage')}) отсутствует или равно 0, или unit_id недействителен.")
                    units_filtered_out += 1
            print(f"[Main] Всего юнитов пропущено (нет данных одометра из unit/list или некорректный ID): {units_filtered_out}.")
            print(f"[Main] Для дальнейшей обработки выбрано {len(filtered_units)} юнитов.")
            
            if not filtered_units:
                print('Внимание! После фильтрации не найдено ни одного юнита с показаниями одометра (mileage > 0) или действительным unit_id. Проверьте данные в Mapon.')
            
            return filtered_units
        else:
            print('Ошибка! Неожиданный формат ответа от Mapon API для unit/list.json. JSON-структура не содержит data.units.')
            print(f'Полный ответ: {response.text}')
            return []
    except requests.exceptions.RequestException as e:
        print(f"Критическая ошибка при получении списка юнитов: {e}")
        return []

# Функция для получения данных одометра CAN
def fetch_odometer(api_key: str, unit_id: str, datetime_obj: datetime.datetime):
    formatted_date = format_datetime_for_mapon(datetime_obj)
    url = f"https://mapon.com/api/v1/unit_data/can_point.json?key={api_key}&unit_id={unit_id}&datetime={formatted_date}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if data.get('data') and data['data'].get('units') and data['data']['units'][0].get('total_distance') and \
           data['data']['units'][0]['total_distance'].get('value') is not None:
            return data['data']['units'][0]['total_distance']['value']
        else:
            print(f"[Odometer] Нет данных одометра CAN для Unit ID {unit_id} на {formatted_date}. Полный ответ can_point: {data}")
            return None # Используем None для отсутствия данных
    except requests.exceptions.RequestException as e:
        print(f"[Odometer] Ошибка при получении одометра CAN для Unit ID {unit_id} на {formatted_date}: {e}")
        return None

# Функция для получения уровня топлива
def fetch_fuel_level(api_key: str, unit_id: str, target_datetime: datetime.datetime, fuel_type: str):
    # Для получения уровня топлива на конкретный момент, запрашиваем данные за весь день,
    # чтобы найти ближайшую точку
    start_of_day = datetime_from_utc_timestamp(target_datetime.timestamp()).replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = datetime_from_utc_timestamp(target_datetime.timestamp()).replace(hour=23, minute=59, second=59, microsecond=999999)

    formatted_from = format_datetime_for_mapon(start_of_day)
    formatted_till = format_datetime_for_mapon(end_of_day)

    data_source = 'sensor'
    url = f"https://mapon.com/api/v1/fuel/data.json?key={api_key}&unit_id={unit_id}&from={formatted_from}&till={formatted_till}&data_source={data_source}"

    print(f"[FuelLevel] Запрос уровня топлива для Unit ID {unit_id} (тип: {fuel_type}, целевое время: {format_datetime_for_mapon(target_datetime)}) в диапазоне {formatted_from} - {formatted_till}")

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        # Поиск данных в секции 'sensor'
        raw_values_sensor = data.get('data', {}).get('sensor', {}).get('tanks', [{}])[0].get('values')
        if raw_values_sensor and isinstance(raw_values_sensor, list) and len(raw_values_sensor) > 0:
            print(f"[FuelLevel] Получено {len(raw_values_sensor)} сырых SENSOR точек от API для Unit ID {unit_id}.")
            points = sorted([
                {'datetime': datetime.datetime.fromisoformat(point['gmt'].replace('Z', '+00:00')), 'value': point['value']}
                for point in raw_values_sensor if isinstance(point.get('value'), (int, float)) and point['value'] >= 0
            ], key=lambda x: x['datetime'])

            if not points:
                print(f"[FuelLevel] Для Unit ID {unit_id} (тип: {fuel_type}): Все SENSOR точки отфильтрованы или отсутствуют.")
            else:
                found_point = None
                if fuel_type == 'start':
                    # Ищем первую точку НА или ПОСЛЕ целевого времени
                    found_point = next((p for p in points if p['datetime'] >= target_datetime), None)
                    if not found_point:
                        found_point = points[0] # Fallback to first available point in the day
                        print(f"[FuelLevel] Для 'start' (ID {unit_id}): Точная точка не найдена, использована первая доступная в дне: {format_datetime_for_mapon(found_point['datetime'])}")
                elif fuel_type == 'end':
                    # Ищем последнюю точку НА или ДО целевого времени
                    for p in reversed(points):
                        if p['datetime'] <= target_datetime:
                            found_point = p
                            break
                    if not found_point:
                        found_point = points[-1] # Fallback to last available point in the day
                        print(f"[FuelLevel] Для 'end' (ID {unit_id}): Точная точка не найдена, использована последняя доступная в дне: {format_datetime_for_mapon(found_point['datetime'])}")
                
                if found_point:
                    print(f"[FuelLevel] Для {fuel_type} (ID {unit_id}) использована SENSOR-точка {format_datetime_for_mapon(found_point['datetime'])} со значением {found_point['value']:.2f}")
                    return round(found_point['value'], 2)

        else:
            print(f"[FuelLevel] Нет данных sensor.tanks для Unit ID {unit_id}.")

        # Если в 'sensor' ничего не нашлось, ищем в 'can'
        raw_values_can = data.get('data', {}).get('can', {}).get('tanks', [{}])[0].get('values')
        if raw_values_can and isinstance(raw_values_can, list) and len(raw_values_can) > 0:
            print(f"[FuelLevel] Нет данных sensor.tanks, но есть {len(raw_values_can)} сырых CAN точек от API для Unit ID {unit_id}.")
            points = sorted([
                {'datetime': datetime.datetime.fromisoformat(point['gmt'].replace('Z', '+00:00')), 'value': point['value']}
                for point in raw_values_can if isinstance(point.get('value'), (int, float)) and point['value'] >= 0
            ], key=lambda x: x['datetime'])

            if not points:
                print(f"[FuelLevel] Для Unit ID {unit_id} (тип: {fuel_type}): Все CAN точки отфильтрованы или отсутствуют.")
            else:
                found_point = None
                if fuel_type == 'start':
                    found_point = next((p for p in points if p['datetime'] >= target_datetime), None)
                    if not found_point:
                        found_point = points[0]
                elif fuel_type == 'end':
                    for p in reversed(points):
                        if p['datetime'] <= target_datetime:
                            found_point = p
                            break
                    if not found_point:
                        found_point = points[-1]
                
                if found_point:
                    print(f"[FuelLevel] Для {fuel_type} (ID {unit_id}) использована CAN-точка {format_datetime_for_mapon(found_point['datetime'])} со значением {found_point['value']:.2f}")
                    return round(found_point['value'], 2)
        else:
            print(f"[FuelLevel] Нет данных can.tanks для Unit ID {unit_id}. ")
    
    except requests.exceptions.RequestException as e:
        print(f"[FuelLevel] Критическая ошибка при получении уровня топлива для Unit ID {unit_id} (тип: {fuel_type}) на {format_datetime_for_mapon(target_datetime)} : {e}")
    
    print(f"[FuelLevel] Для Unit ID {unit_id} на {format_datetime_for_mapon(target_datetime)} (тип: {fuel_type}): Данные по топливу не найдены.")
    return None # Используем None для отсутствия данных

# Функция для получения сводных данных по топливу (заправки, сливы, расход)
def fetch_fuel_summary_data(api_key: str, unit_id: str, start_date: datetime.datetime, end_date: datetime.datetime):
    formatted_from = format_datetime_for_mapon(start_date)
    formatted_till = format_datetime_for_mapon(end_date)
    url = f"https://mapon.com/api/v1/fuel/summary.json?key={api_key}&unit_id={unit_id}&from={formatted_from}&till={formatted_till}"

    total_refuelled = None
    total_drained = None
    total_consumed = None

    print(f"[FuelSummary] Запрос сводных данных топлива для Unit ID {unit_id} в диапазоне {formatted_from} - {formatted_till}")

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if isinstance(data.get('data'), list) and len(data['data']) > 0:
            unit_summary = data['data'][0]

            if 'sensor' in unit_summary:
                if isinstance(unit_summary['sensor'].get('fueled'), (int, float)):
                    total_refuelled = round(unit_summary['sensor']['fueled'], 2)
                if isinstance(unit_summary['sensor'].get('drained'), (int, float)):
                    total_drained = round(unit_summary['sensor']['drained'], 2)
                if isinstance(unit_summary['sensor'].get('total_consumed'), (int, float)):
                    total_consumed = round(unit_summary['sensor']['total_consumed'], 2)
                print(f"[FuelSummary] Для Unit ID {unit_id} использованы данные 'sensor': Заправлено: {total_refuelled} л, Слито: {total_drained} л, Расход: {total_consumed} л.")
            elif 'can' in unit_summary: # Fallback to CAN if sensor is not available
                print(f"[FuelSummary] Для Unit ID {unit_id} отсутствуют данные 'sensor'. Используем 'can'.")
                if isinstance(unit_summary['can'].get('fueled'), (int, float)):
                    total_refuelled = round(unit_summary['can']['fueled'], 2)
                if isinstance(unit_summary['can'].get('drained'), (int, float)):
                    total_drained = round(unit_summary['can']['drained'], 2)
                if isinstance(unit_summary['can'].get('total_consumed'), (int, float)):
                    total_consumed = round(unit_summary['can']['total_consumed'], 2)
                print(f"[FuelSummary] Для Unit ID {unit_id} использованы данные 'can': Заправлено: {total_refuelled} л, Слито: {total_drained} л, Расход: {total_consumed} л.")
            else:
                print(f"[FuelSummary] Для Unit ID {unit_id} отсутствуют данные 'sensor' и 'can' в ответе fuel/summary.json.")

            return {
                'refuelled': total_refuelled,
                'drained': total_drained,
                'consumed': total_consumed
            }
        else:
            print(f"Неожиданный формат ответа fuel/summary.json для Unit ID {unit_id}. data не массив или пуст. Полный ответ: {response.text}")
            return {
                'refuelled': None,
                'drained': None,
                'consumed': None
            }
    except requests.exceptions.RequestException as e:
        print(f"Критическая ошибка при получении сводных данных топлива для Unit ID {unit_id}: {e}")
        return {
            'refuelled': None,
            'drained': None,
            'consumed': None
        }

# Вспомогательная функция для преобразования timestamp в datetime в UTC
def datetime_from_utc_timestamp(ts: float) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(ts, tz=pytz.utc)


# Основная функция, которая будет запускаться (потом интегрируем в Streamlit)
def get_fleet_odometer_and_fuel_data(api_key: str, start_datetime: datetime.datetime, end_datetime: datetime.datetime) -> pd.DataFrame:
    
    if start_datetime > end_datetime:
        print("Ошибка: Дата и время начала периода не может быть позже даты и времени окончания.")
        return pd.DataFrame()

    filtered_units = get_unit_list(api_key)
    if not filtered_units:
        return pd.DataFrame()

    results = []

    for current_unit in filtered_units:
        current_unit_id = current_unit['unit_id']
        unit_name = current_unit.get('number') or current_unit.get('label') or f"Unit {current_unit_id}"

        print(f"--- Начинаем обработку юнита: {unit_name} (ID: {current_unit_id}) ---")

        odometer_start = fetch_odometer(api_key, current_unit_id, start_datetime)
        odometer_end = fetch_odometer(api_key, current_unit_id, end_datetime)

        distance = None
        numeric_distance = 0.0
        if isinstance(odometer_start, (int, float)) and isinstance(odometer_end, (int, float)):
            numeric_distance = odometer_end - odometer_start
            distance = round(numeric_distance, 2)
            if numeric_distance < 0:
                distance = f"Сброс ({distance} км)"
            elif numeric_distance == 0:
                distance = "0.00"
        else:
            distance = "Нет данных для расчета"

        # Убедимся, что numeric_distance - это число для дальнейших расчетов
        if isinstance(distance, str) and "Сброс" in distance:
            numeric_distance = 0.0
        elif isinstance(distance, str) and distance != "Нет данных для расчета":
            try:
                numeric_distance = float(distance)
            except ValueError:
                numeric_distance = 0.0
        elif not isinstance(distance, (int, float)):
            numeric_distance = 0.0
        
        # Заставляем numeric_distance быть положительным для расчета расхода, если он стал отрицательным из-за "сброса"
        if numeric_distance < 0:
            numeric_distance = 0.0


        fuel_level_start = fetch_fuel_level(api_key, current_unit_id, start_datetime, 'start')
        fuel_level_end = fetch_fuel_level(api_key, current_unit_id, end_datetime, 'end')
        
        fuel_summary_data = fetch_fuel_summary_data(api_key, current_unit_id, start_datetime, end_datetime)

        average_consumption = None
        consumed_numeric = fuel_summary_data['consumed']

        if isinstance(consumed_numeric, (int, float)) and consumed_numeric >= 0 and \
           isinstance(numeric_distance, (int, float)) and numeric_distance > 0:
            average_consumption = round((consumed_numeric / numeric_distance) * 100, 2)
        elif isinstance(consumed_numeric, (int, float)) and consumed_numeric > 0 and numeric_distance == 0:
            average_consumption = 'Нет пробега'
        
        results.append({
            'Номер Автомобіля': unit_name,
            'Одометр CAN (початок)': odometer_start,
            'Одометр CAN (кінець)': odometer_end,
            'Пробіг (CAN, км)': distance,
            'Паливо в баку (початок, л)': fuel_level_start,
            'Паливо в баку (кінець, л)': fuel_level_end,
            'Заправлено за період (л)': fuel_summary_data['refuelled'],
            'Зливи за період (л)': fuel_summary_data['drained'],
            'Витрата (датчик, л)': fuel_summary_data['consumed'],
            'Середня витрата (л/100км)': average_consumption
        })
    
    # Создаем pandas DataFrame из списка словарей
    df = pd.DataFrame(results)
    return df

# Пример использования (позже это будет часть Streamlit)
if __name__ == '__main__':
    # Эти даты и время будут браться из виджетов Streamlit
    # Важно: Mapon API ожидает даты в UTC. При выборе дат в Streamlit, убедитесь, что они переводятся в UTC.
    # Для простоты примера, я использую datetime.datetime.utcnow() для создания UTC времени.
    # В реальном приложении Streamlit, мы будем брать даты из input полей и переводить их в UTC.
    API_KEY = "YOUR_MAPON_API_KEY" # Замените на ваш реальный API ключ для тестирования
    start_date_example = datetime.datetime(2024, 6, 1, 0, 0, 0, tzinfo=pytz.utc) # UTC
    end_date_example = datetime.datetime(2024, 6, 17, 23, 59, 59, tzinfo=pytz.utc) # UTC

    print(f"Запускаем получение данных с {start_date_example} по {end_date_example}")
    
    final_df = get_fleet_odometer_and_fuel_data(API_KEY, start_date_example, end_date_example)
    print("\n--- Результаты ---")
    print(final_df)
    
    # Сохранение в Excel (пример)
    # final_df.to_excel("fleet_report.xlsx", index=False)
    # print("Отчет сохранен в fleet_report.xlsx")