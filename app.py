import streamlit as st
import datetime
import pytz # Для работы с часовыми поясами
import pandas as pd # Для работы с DataFrame
from io import BytesIO # Для сохранения Excel в память

# Импортируем нашу логику из файла mapon_api_client.py
from mapon_api_client import get_fleet_odometer_and_fuel_data

# --- Настройки Streamlit страницы ---
st.set_page_config(
    page_title="Отчет по автопарку Mapon",
    page_icon="🚗",
    layout="wide" # Делаем страницу широкой для лучшего отображения таблиц
)

st.title("🚗 Отч")
st.markdown("Здесь вы можете получить детальный отчет по одометру и расходу топлива вашего автопарка за выбранный период.")

# --- Ввод API ключа ---
# Для локальной разработки можно попросить пользователя ввести ключ.
# При деплое на Streamlit Cloud, мы спрячем его в secrets.toml.
api_key = st.text_input("Введите ваш Mapon API Key", type="password")

if not api_key:
    st.warning("Пожалуйста, введите ваш Mapon API Key для продолжения.")
    st.stop() # Останавливаем выполнение, пока ключ не введен

# --- Выбор диапазона дат и времени ---
st.header("Выберите период для отчета")

# Текущая дата и время в UTC
now_utc = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)

# Значения по умолчанию: последние 24 часа
default_start_datetime = now_utc - datetime.timedelta(days=1)
default_end_datetime = now_utc

# Виджеты выбора даты
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Дата начала", value=default_start_datetime.date())
    start_time = st.time_input("Время начала (UTC)", value=default_start_datetime.time(), step=300) # шаг 5 минут
with col2:
    end_date = st.date_input("Дата окончания", value=default_end_datetime.date())
    end_time = st.time_input("Время окончания (UTC)", value=default_end_datetime.time(), step=300)

# Объединяем дату и время в один datetime объект (в UTC)
# Важно: date_input и time_input возвращают naive datetime (без tzinfo), поэтому явно добавляем UTC
start_datetime_full = datetime.datetime.combine(start_date, start_time).replace(tzinfo=pytz.utc)
end_datetime_full = datetime.datetime.combine(end_date, end_time).replace(tzinfo=pytz.utc)

# Проверка, что дата начала не позже даты окончания
if start_datetime_full > end_datetime_full:
    st.error("Ошибка: Дата и время начала периода не может быть позже даты и времени окончания.")
    st.stop()

# --- Кнопка для запуска отчета ---
st.write("") # Пустая строка для отступа
if st.button("Сгенерировать отчет", help="Нажмите, чтобы получить данные из Mapon"):
    st.info("Загрузка данных... Это может занять некоторое время в зависимости от количества автомобилей и выбранного периода.")

    # Запускаем нашу основную функцию из mapon_api_client.py
    # Используем st.spinner для отображения индикатора загрузки
    with st.spinner('Получение данных из Mapon API...'):
        try:
            df = get_fleet_odometer_and_fuel_data(api_key, start_datetime_full, end_datetime_full)
            
            if not df.empty:
                st.success("Данные успешно загружены!")
                st.write("") # Отступ
                st.subheader("Результаты отчета")
                
                # --- Отображение DataFrame ---
                st.dataframe(df.style.highlight_null(), use_container_width=True) # Временно убрали null_color

                # --- Кнопка для скачивания Excel ---
                st.write("") # Отступ
                st.subheader("Скачать отчет")
                
                @st.cache_data # Кэшируем функцию для генерации Excel, чтобы не пересчитывать при каждом ререндере
                def convert_df_to_excel(df_to_convert):
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df_to_convert.to_excel(writer, index=False, sheet_name='Отчет по автопарку')
                        # Опционально: автонастройка ширины колонок
                        worksheet = writer.sheets['Отчет по автопарку']
                        for i, col in enumerate(df_to_convert.columns):
                            max_len = max(df_to_convert[col].astype(str).map(len).max(), len(col)) + 2
                            worksheet.set_column(i, i, max_len)
                    processed_data = output.getvalue()
                    return processed_data

                excel_data = convert_df_to_excel(df)
                st.download_button(
                    label="📥 Скачать отчет в Excel",
                    data=excel_data,
                    file_name=f"Mapon_Fleet_Report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
            else:
                st.warning("Отчет не содержит данных. Проверьте выбранный период или убедитесь, что Mapon API вернул данные для активных юнитов.")
        
        except Exception as e:
            st.error(f"Произошла ошибка при загрузке данных: {e}. Пожалуйста, проверьте API Key и попробуйте еще раз.")
            st.exception(e) # Показывает полный traceback ошибки для отладки