import streamlit as st
import datetime
import pytz # Для роботи з часовими поясами
import pandas as pd # Для роботи з DataFrame
from io import BytesIO # Для збереження Excel в пам'ять

# Імпортуємо нашу логіку з файлу mapon_api_client.py
from mapon_api_client import get_fleet_odometer_and_fuel_data

# --- Налаштування Streamlit сторінки ---
st.set_page_config(
    page_title="Звіт автопарку Mapon",
    page_icon="🚗",
    layout="wide" # Робимо сторінку широкою для кращого відображення таблиць
)

# Користувацькі CSS для стилізації
st.markdown("""
    <style>
    /* Основний контейнер для відступів та фону */
    .main .block-container {
        padding-top: 2rem;
        padding-right: 2rem;
        padding-left: 2rem;
        padding-bottom: 2rem;
        background-color: #f8f8f8; /* Дуже світло-сірий фон для основного контенту, як на Mapon */
    }

    /* Стиль для заголовків H1 */
    h1 {
        color: #333333; /* Темно-сірий/майже чорний */
        font-family: 'Arial', sans-serif;
        border-bottom: none; /* Приберемо нижню лінію для H1 */
        margin-bottom: 1.5rem; /* Збільшимо відступ після H1 */
    }
    /* Стиль для всіх інших заголовків (H2, H3, H4, H5, H6) */
    h2, h3, h4, h5, h6 {
        color: #333333; /* Темно-сірий/майже чорний, як на Mapon */
        font-family: 'Arial', sans-serif;
        border-bottom: 1px solid #e0e0e0; /* Легка лінія під заголовками */
        padding-bottom: 0.5rem;
        margin-bottom: 1rem;
    }

    /* Стиль для кнопок */
    .stButton>button {
        background-color: #7ab800; /* Колір Mapon */
        color: white;
        border-radius: 4px;
        border: none;
        padding: 10px 20px;
        font-size: 16px;
        font-weight: bold;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        transition: background-color 0.2s ease, box-shadow 0.2s ease; /* Плавний перехід */
    }
    .stButton>button:hover {
        background-color: #6aaa00; /* Темніший зелений при наведенні */
        color: white;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }

    /* Стиль для текстових полів (API Key) та інших input-ів */
    .stTextInput label, .stDateInput label, .stTimeInput label, .stMultiSelect label {
        color: #555555; /* Темніший колір для назви поля */
        font-size: 1rem;
        font-weight: bold;
        margin-bottom: 0.25rem; /* Зменшимо відступ між лейблом та полем */
        display: block; /* Забезпечимо, щоб лейбл займав свій рядок */
    }
    .stTextInput div[data-baseweb="input"] input,
    .stDateInput div[data-baseweb="input"] input,
    .stTimeInput div[data-baseweb="input"] input {
        border: 1px solid #b0b0b0; /* Трохи темніша рамка для кращого контрасту */
        border-radius: 4px;
        padding: 0.5rem 1rem;
        font-size: 1rem;
        color: #333333;
        box-shadow: inset 0 1px 3px rgba(0,0,0,0.1); /* Внутрішня тінь для ефекту глибини */
    }
    .stTextInput div[data-baseweb="input"]:focus-within,
    .stDateInput div[data-baseweb="input"]:focus-within,
    .stTimeInput div[data-baseweb="input"]:focus-within {
        border-color: #7ab800; /* Зелена рамка при фокусі */
        box-shadow: 0 0 0 0.1rem rgba(122, 184, 0, 0.25); /* Легка зелена тінь при фокусі */
    }

    /* Стилізація мультиселекта */
    /* Основний контейнер мультиселекта */
    .stMultiSelect div[data-baseweb="select"] {
        border: 1px solid #b0b0b0; /* Рамка для всього віджета */
        border-radius: 4px;
        box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);
    }
    /* Колір фону для вибраних елементів (колонок) */
    .stMultiSelect span[data-baseweb="tag"] {
        background-color: #eafbe1 !important; /* Дуже світлий зелений */
        color: #388e3c !important; /* Темно-зелений текст */
        border: 1px solid #7ab800 !important; /* Зелена рамка */
        border-radius: 4px !important;
        font-size: 0.75rem !important;
        padding: 4px 8px !important;
        margin: 2px !important;
    }
    /* Колір іконки закриття вибраного елемента */
    .stMultiSelect span[data-baseweb="tag"] svg {
        fill: #388e3c !important;
    }
    /* Колір фону при наведенні на опцію у випадаючому списку */
    div[role="option"]:hover {
        background-color: #f0f8ed !important; /* Світло-зелений при наведенні */
    }
    /* Колір тексту опції у випадаючому списку */
    div[role="option"] span {
        color: #333333 !important;
    }
    /* Зменшуємо шрифт для вибраних елементів в полі мультиселекта (дублюємо, бо специфічність) */
    div[data-baseweb="select"] span.css-1n74gkj {
        font-size: 0.75rem !important;
    }
    /* Зменшуємо шрифт для елементів у випадаючому списку мультиселекта (дублюємо) */
    div[data-baseweb="select"] div.css-1n74gkj {
        font-size: 0.75rem !important;
    }
    /* Кнопка розкриття мультиселекта (стрілочка) */
    div[data-testid="stMultiSelect"] div[role="button"] {
        border-color: #7ab800 !important; /* Зелена рамка навколо кнопки розкриття */
    }

    /* Стилізація тексту в попередженнях та інформації (збільшений контраст) */
    .stAlert {
        font-size: 14px;
        border-radius: 4px;
        padding: 10px 15px; /* Більші відступи */
        margin-top: 1rem;
        margin-bottom: 1rem;
    }
    .stAlert.st-ee { /* Для info */
        background-color: #e6f7ff;
        color: #0056b3;
        border-left: 5px solid #2196f3;
    }
    .stAlert.st-eb { /* Для success */
        background-color: #eafbe1;
        color: #388e3c;
        border-left: 5px solid #4caf50;
    }
    .stAlert.st-dd { /* Для warning */
        background-color: #fff9e6;
        color: #e65100;
        border-left: 5px solid #ff9800;
    }
    .stAlert.st-cc { /* Для error */
        background-color: #ffe6e6;
        color: #d32f2f;
        border-left: 5px solid #f44336;
    }

    /* Зменшення шрифту в таблиці DataFrame та покращення контрасту */
    .stDataFrame {
        font-size: 0.75rem !important;
        border: 1px solid #e0e0e0;
        border-radius: 4px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-top: 1.5rem; /* Відступ від попередніх елементів */
    }
    .stDataFrame table {
        font-size: 0.75rem !important;
        width: 100%;
        border-collapse: collapse; /* Приберемо подвійні межі */
    }
    .stDataFrame th, .stDataFrame td {
        font-size: 0.75rem !important;
        padding: 8px 12px;
        border-bottom: 1px solid #eeeeee; /* Легка межа між рядками */
        text-align: left;
    }
    .stDataFrame th {
        background-color: #f0f0f0;
        color: #555555;
        font-weight: bold;
        border-bottom: 2px solid #e0e0e0;
    }
    .stDataFrame tr:nth-child(even) {
        background-color: #f9f9f9;
    }
    .stDataFrame tr:hover {
        background-color: #e8f5e9;
    }
    
    /* Стилізація бічної панелі (якщо використовується) */
    .st-emotion-cache-vk33z2 { /* Цей клас може змінюватися в майбутніх версіях Streamlit */
        background-color: #212121; /* Дуже темний сірий/майже чорний, як на Mapon */
        color: #ffffff; /* Білий текст на бічній панелі */
    }
    .st-emotion-cache-vk33z2 .st-emotion-cache-1pxe4x4 {
        color: #dddddd; /* Світло-сірий для звичайних посилань */
    }
    .st-emotion-cache-vk33z2 .st-emotion-cache-1pxe4x4:hover {
        color: #7ab800; /* Зелений при наведенні */
    }
    .st-emotion-cache-vk33z2 .st-emotion-cache-1pxe4x4.active {
        color: #7ab800; /* Активний пункт зеленим */
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)


st.title("🌱 Звіт автопарку Mapon")
st.markdown("Тут ви можете отримати детальний звіт щодо одометра та витрат пального вашого автопарку за обраний період.")

# --- Введення API ключа ---
api_key = st.text_input("Введіть ваш Mapon API Key", type="password")

# Перевіряємо, чи введено API ключ
if not api_key:
    st.warning("Будь ласка, введіть ваш Mapon API Key для продовження.")
    st.stop()

# --- Вибір діапазону дат та часу ---
st.header("Оберіть період для звіту")

# Поточна дата та час в UTC
now_utc = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)

# Значення за замовчуванням: останні 24 години
default_start_datetime = now_utc - datetime.timedelta(days=1)
default_end_datetime = now_utc

# Віджети вибору дати
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Дата початку", value=default_start_datetime.date())
    start_time = st.time_input("Час початку (UTC)", value=default_start_datetime.time(), step=300)
with col2:
    end_date = st.date_input("Дата закінчення", value=default_end_datetime.date())
    end_time = st.time_input("Час закінчення (UTC)", value=default_end_datetime.time(), step=300)

# Об'єднуємо дату та час в один datetime об'єкт (в UTC)
start_datetime_full = datetime.datetime.combine(start_date, start_time).replace(tzinfo=pytz.utc)
end_datetime_full = datetime.datetime.combine(end_date, end_time).replace(tzinfo=pytz.utc)

# Перевірка, що дата початку не пізніше дати закінчення
if start_datetime_full > end_datetime_full:
    st.error("Помилка: Дата та час початку періоду не може бути пізніше дати та часу закінчення.")
    st.stop()

# --- Розділ для налаштування звіту (вибір колонок) ---
st.header("Налаштування звіту")

# Назви колонок повинні точно збігатися з тим, що повертає get_fleet_odometer_and_fuel_data у mapon_api_client.py
all_possible_columns = [
    'Номер Автомобіля',
    'Одометр CAN (початок)',
    'Одометр CAN (кінець)',
    'Пробіг (CAN, км)',
    'Паливо в баку (початок, л)',
    'Паливо в баку (кінець, л)',
    'Заправлено за період (л)',
    'Зливи за період (л)',
    'Витрата (датчик, л)',
    'Середня витрата (л/100км)'
]

selected_columns = st.multiselect(
    "Оберіть колонки для відображення у звіті:",
    options=all_possible_columns,
    default=all_possible_columns
)

if not selected_columns:
    st.warning("Будь ласка, оберіть хоча б одну колонку для відображення.")
    st.stop()


# --- Кнопка для запуску звіту ---
st.write("")
if st.button("Згенерувати звіт", help="Натисніть, щоб отримати дані з Mapon"):
    st.info("Завантаження даних... Це може зайняти деякий час в залежності від кількості автомобілів та обраного періоду.")

    # Запускаємо нашу основну функцію з mapon_api_client.py
    with st.spinner('Отримання даних з Mapon API...'):
        try:
            df = get_fleet_odometer_and_fuel_data(api_key, start_datetime_full, end_datetime_full)
            
            if not df.empty:
                st.success("Дані успішно завантажено!")
                st.write("")
                
                # Фільтруємо DataFrame за обраними колонками
                columns_to_show = [col for col in selected_columns if col in df.columns]
                
                if not columns_to_show:
                    st.warning("Обрані колонки не знайдено в отриманих даних. Відображаю всі доступні колонки.")
                    st.dataframe(df.style.highlight_null(), use_container_width=True)
                else:
                    st.subheader("Результати звіту")
                    df_display = df[columns_to_show]
                    st.dataframe(df_display.style.highlight_null(), use_container_width=True)

                # --- Кнопка для завантаження Excel ---
                st.write("")
                st.subheader("Завантажити звіт")
                
                @st.cache_data
                def convert_df_to_excel(df_to_convert):
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df_to_convert.to_excel(writer, index=False, sheet_name='Звіт по автопарку')
                        worksheet = writer.sheets['Звіт по автопарку']
                        for i, col in enumerate(df_to_convert.columns):
                            max_len = max(df_to_convert[col].astype(str).map(len).max(), len(col)) + 2
                            worksheet.set_column(i, i, max_len)
                    processed_data = output.getvalue()
                    return processed_data

                excel_data = convert_df_to_excel(df_display)
                st.download_button(
                    label="📥 Завантажити звіт у Excel",
                    data=excel_data,
                    file_name=f"Mapon_Звіт_Автопарку_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
            else:
                st.warning("Звіт не містить даних. Перевірте обраний період або переконайтесь, що Mapon API повернув дані для активних юнітів.")
        
        except Exception as e:
            st.error(f"Виникла помилка при завантаженні даних: {e}. Будь ласка, перевірте API Key та спробуйте ще раз.")
            st.exception(e)