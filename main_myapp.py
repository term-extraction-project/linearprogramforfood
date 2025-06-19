import streamlit as st
from scipy.optimize import linprog
import pandas as pd

# --- Загрузка и предобработка данных ---
df_ingr_all = pd.read_csv('ingredients_2.csv')
cols_to_divide = ['Вода', 'Белки', 'Углеводы', 'Жиры']

for col in cols_to_divide:
    df_ingr_all[col] = df_ingr_all[col].astype(str).str.replace(',', '.', regex=False)
    df_ingr_all[col] = pd.to_numeric(df_ingr_all[col], errors='coerce')

df_ingr_all[cols_to_divide] = df_ingr_all[cols_to_divide] / 100
df_ingr_all['ингредиент и описание'] = df_ingr_all['Ингредиент'] + ' — ' + df_ingr_all['Описание']

# --- Словарь: название → нутриенты ---
food = df_ingr_all.set_index("ингредиент и описание")[cols_to_divide].to_dict(orient='index')

st.title("🥣 Оптимизация состава корма")

# --- Выбор ингредиентов из выпадающего списка ---
ingredient_options = df_ingr_all["ингредиент и описание"].dropna().unique().tolist()
ingredient_names = st.multiselect(
    "Выберите ингредиенты (можно несколько):",
    options=ingredient_options,
    placeholder="Нажмите для выбора...",
)

# --- Показ химического состава для выбранного ингредиента (если выбран 1) ---
if len(ingredient_names) == 1:
    row = df_ingr_all[df_ingr_all['ингредиент и описание'] == ingredient_names[0]].iloc[0]
    st.sidebar.markdown(f"### 🧾 Состав: **{row['Ингредиент']}**")
    st.sidebar.markdown(f"_Категория: {row['Категория']}_")
    st.sidebar.markdown(f"_Описание: {row['Описание']}_")

    df_nutr = pd.DataFrame({
        "Нутриент": ["Белки", "Жиры", "Углеводы", "Влага"],
        "На 100 г": [
            round(row["Белки"] * 100, 1) if pd.notnull(row["Белки"]) else None,
            round(row["Жиры"] * 100, 1) if pd.notnull(row["Жиры"]) else None,
            round(row["Углеводы"] * 100, 1) if pd.notnull(row["Углеводы"]) else None,
            round(row["Вода"] * 100, 1) if pd.notnull(row["Вода"]) else None,
        ]
    })
    df_nutr.index = [''] * len(df_nutr)
    st.sidebar.markdown("#### Химический состав:")
    st.sidebar.table(df_nutr)

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
