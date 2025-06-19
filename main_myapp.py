import streamlit as st
import pandas as pd
from scipy.optimize import linprog  # ← ОБЯЗАТЕЛЬНО


# --- Загрузка данных ---
df_ingr_all = pd.read_csv('ingredients_2.csv')
cols_to_divide = ['Вода', 'Белки', 'Углеводы', 'Жиры']

for col in cols_to_divide:
    df_ingr_all[col] = df_ingr_all[col].astype(str).str.replace(',', '.', regex=False)
    df_ingr_all[col] = pd.to_numeric(df_ingr_all[col], errors='coerce')

df_ingr_all[cols_to_divide] = df_ingr_all[cols_to_divide] / 100
df_ingr_all['ингредиент и описание'] = df_ingr_all['Ингредиент'] + ' — ' + df_ingr_all['Описание']

# --- Инициализация состояния ---
if "selected_ingredients" not in st.session_state:
    st.session_state.selected_ingredients = set()

st.title("🍲 Выбор ингредиентов")

# --- Раскрывающийся выбор: категория > ингредиент > описание ---
for category in df_ingr_all['Категория'].dropna().unique():
    with st.expander(f"📂 Категория: {category}"):
        df_cat = df_ingr_all[df_ingr_all['Категория'] == category]
        for ingredient in df_cat['Ингредиент'].dropna().unique():
            with st.expander(f"🍖 Ингредиент: {ingredient}"):
                df_ing = df_cat[df_cat['Ингредиент'] == ingredient]
                for desc in df_ing['Описание'].dropna().unique():
                    label = f"{ingredient} — {desc}"
                    key = f"{category}_{ingredient}_{desc}"
                    if st.button(f"Добавить: {label}", key=key):
                        st.session_state.selected_ingredients.add(label)

# --- Показываем выбранные ---
st.markdown("### ✅ Выбранные ингредиенты:")
if st.session_state.selected_ingredients:
    for i in sorted(st.session_state.selected_ingredients):
        col1, col2 = st.columns([5, 1])
        col1.write(i)
        if col2.button("❌", key=f"remove_{i}"):
            st.session_state.selected_ingredients.remove(i)
else:
    st.info("Вы пока не выбрали ни одного ингредиента.")

# Пример: доступ к выбранным
ingredient_names = list(st.session_state.selected_ingredients)
food = df_ingr_all.set_index("ингредиент и описание")[cols_to_divide].to_dict(orient='index')


# --- Ограничения по количеству каждого ингредиента ---
if ingredient_names:
    st.subheader("Ограничения по количеству ингредиентов (в % от 100 г):")
    ingr_ranges = []
    for ingr in ingredient_names:
        ingr_ranges.append(st.slider(f"{ingr}", 0, 100, (5, 30)))

    # --- Ограничения по нутриентам ---
    st.subheader("Ограничения по нутриентам:")
    nutr_ranges = {}
    for nutr in cols_to_divide:
        nutr_ranges[nutr] = st.slider(f"{nutr}", 0, 100, (0, 100))

    # --- Построение задачи LP ---
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

    # --- Целевая функция ---
    st.subheader("Что максимизировать?")
    selected_maximize = st.multiselect(
        "Выберите нутриенты для максимизации:",
        cols_to_divide,
        default=cols_to_divide
    )

    f = [-sum(food[i][nutr] for nutr in selected_maximize) for i in ingredient_names]

    # --- Запуск оптимизации ---
    if st.button("🔍 Рассчитать оптимальный состав"):
        res = linprog(f, A_ub=A, b_ub=b, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")

        if res.success:
            st.success("✅ Решение найдено!")
            result = {name: round(val * 100, 2) for name, val in zip(ingredient_names, res.x)}
            st.markdown("### 📦 Состав (в граммах на 100 г):")
            for name, value in result.items():
                st.write(f"{name}: **{value} г**")

            st.markdown("### 💪 Питательная ценность на 100 г:")
            nutrients = {
                nutr: round(sum(res.x[i] * food[name][nutr] for i, name in enumerate(ingredient_names)) * 100, 2)
                for nutr in cols_to_divide
            }
            for k, v in nutrients.items():
                st.write(f"**{k}:** {v} г")
        else:
            st.error("❌ Не удалось найти оптимальное решение. Попробуйте другие параметры.")
else:
    st.info("👈 Пожалуйста, выберите хотя бы один ингредиент.")
