import streamlit as st
from scipy.optimize import linprog
import pandas as pd




df_ingr_all = pd.read_csv('ingredients_2.csv')
cols_to_divide = [ 'Вода', 'Белки', 'Углеводы', 'Жиры']

for col in cols_to_divide:
    df_ingr_all[col] = df_ingr_all[col].astype(str).str.replace(',', '.', regex=False)
    df_ingr_all[col] = pd.to_numeric(df_ingr_all[col], errors='coerce')
    

df_ingr_all[cols_to_divide] = df_ingr_all[[ 'Вода', 'Белки', 'Углеводы', 'Жиры']] / 100
df_ingr_all['ингредиент и описание'] = df_ingr_all['Ингредиент'] + ' - ' + df_ingr_all['Описание']

food=df_ingr_all.set_index("ингредиент и описание")[cols_to_divide].to_dict(orient='index')


st.title("Состав ингредиентов")

# Создаём уникальный ID для выбора (ингредиент + подвид)
if "selected_ingredient" not in st.session_state:
    st.session_state.selected_ingredient = None
if "selected_subtype" not in st.session_state:
    st.session_state.selected_subtype = None

# Категории
for category in df_ingr_all['Категория'].unique():
    with st.expander(f"Категория: {category}"):
        df_cat = df_ingr_all[df_ingr_all['Категория'] == category]

        for ingredient in df_cat['Ингредиент'].unique():
            with st.expander(f"Ингредиент: {ingredient}"):
                df_ing = df_cat[df_cat['Ингредиент'] == ingredient]

                for sub in df_ing['Описание'].unique():
                    key = f"{category}_{ingredient}_{sub}"
                    if st.button(f"Выбрать: {ingredient} — {sub}", key=key):
                        st.session_state.selected_ingredient = ingredient
                        st.session_state.selected_subtype = sub

st.sidebar.write("Белки:", row['Белки'])
st.sidebar.write("Жиры:", row['Жиры'])
st.sidebar.write("Углеводы:", row['Углеводы'])
st.sidebar.write("Вода:", row['Вода'])

nutr_data = {
    'Нутриент': ['Белки', 'Жиры', 'Углеводы', 'Влага'],
    'На 100 г': [
        row['Белки'] * 100,
        row['Жиры'] * 100,
        row['Углеводы'] * 100,
        row['Вода'] * 100
    ]
}
nutr_df = pd.DataFrame(nutr_data)
st.sidebar.markdown("#### Химический состав:")
st.sidebar.dataframe(nutr_df.style.format({"На 100 г": "{:.1f} г"}))

# ✅ Проверка и отображение состава


if st.session_state.selected_ingredient and st.session_state.selected_subtype:
    # Явное приведение к строке и удаление пробелов (иногда бывают лишние)
    selected_ing = str(st.session_state.selected_ingredient).strip()
    selected_desc = str(st.session_state.selected_subtype).strip()

    filtered = df_ingr_all[
        (df_ingr_all['Ингредиент'].astype(str).str.strip() == selected_ing) &
        (df_ingr_all['Описание'].astype(str).str.strip() == selected_desc)
    ]

    st.write("DEBUG – найдено строк:", filtered.shape[0])  # ⬅️ временно покажем, что найдено

    if not filtered.empty:
        row = filtered.iloc[0]

        # Заголовок
        st.sidebar.markdown(f"### 🥣 **{row['Ингредиент']}**")
        st.sidebar.markdown(f"_Категория: {row['Категория']}_")
        st.sidebar.markdown(f"_Описание: {row['Описание']}_")

        # Таблица с составом
        nutr_data = {
            'Нутриент': ['Белки', 'Жиры', 'Углеводы', 'Влага'],
            'На 100 г': [
                f"{row['Белки'] * 100:.1f} г" if pd.notnull(row['Белки']) else "н/д",
                f"{row['Жиры'] * 100:.1f} г" if pd.notnull(row['Жиры']) else "н/д",
                f"{row['Углеводы'] * 100:.1f} г" if pd.notnull(row['Углеводы']) else "н/д",
                f"{row['Вода'] * 100:.1f} г" if pd.notnull(row['Вода']) else "н/д"
            ]
        }

        nutr_df = pd.DataFrame(nutr_data)
        st.sidebar.markdown("#### Химический состав:")
        st.sidebar.table(nutr_df)
    else:
        st.sidebar.warning("⚠️ Не удалось найти состав.")



st.title("Оптимизация состава рациона")

# --- Выбор ингредиентов ---
ingredient_names = st.multiselect("Выберите ингредиенты:", list(food.keys()))

# --- Указание диапазонов количества каждого ингредиента ---
st.subheader("Ограничения по количеству ингредиентов (в % от общего состава, 100 г):")
ingr_ranges = []
for ingr in ingredient_names:
    ingr_ranges.append(st.slider(f"{ingr}", 0, 100, (5, 30)))

# --- Ограничения по нутриентам ---
st.subheader("Ограничения по нутриентам:")
nutr_ranges = {}
for nutr in cols_to_divide:
    nutr_ranges[nutr] = st.slider(f"{nutr}", 0, 100, (0, 100))

# --- Построение задачи линейного программирования ---
A = [
    [food[ing][nutr] if val > 0 else -food[ing][nutr]
     for ing in ingredient_names]
    for nutr in nutr_ranges
    for val in (-nutr_ranges[nutr][0]/100, nutr_ranges[nutr][1]/100)
]
b = [
    val / 100 for nutr in nutr_ranges
    for val in (-nutr_ranges[nutr][0], nutr_ranges[nutr][1])
]

A_eq = [[1 for _ in ingredient_names]]
b_eq = [1.0]

bounds = [(low/100, high/100) for (low, high) in ingr_ranges]
st.subheader("Что максимизировать?")
selected_maximize = st.multiselect(
    "Выберите нутриенты для максимизации:",
    ['Вода', 'Белки', 'Углеводы', 'Жиры'],
    default=['Вода', 'Белки', 'Углеводы', 'Жиры']  # по умолчанию все
)

f = [-sum(food[i][nutr] for nutr in selected_maximize) for i in ingredient_names]

# --- Кнопка запуска оптимизации ---
if st.button("Рассчитать оптимальный состав"):
    res = linprog(f, A_ub=A, b_ub=b, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")

    if res.success:
        st.success("Решение найдено!")
        result = {name: round(val * 100, 2) for name, val in zip(ingredient_names, res.x)}
        st.subheader("Состав (% от общего веса):")
        for name, value in result.items():
            st.write(f"{name}: {value} г")

        st.subheader("Питательная ценность (на 100 г):")
        nutrients = {
            nutr: round(sum(res.x[i] * food[name][nutr] for i, name in enumerate(ingredient_names)) * 100, 2)
            for nutr in cols_to_divide
        }
        for k, v in nutrients.items():
            st.write(f"{k}: {v}")
    else:
        st.error("Не удалось найти оптимальное решение. Попробуйте другие параметры.")
