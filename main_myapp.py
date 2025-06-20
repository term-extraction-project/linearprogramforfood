import streamlit as st
import pandas as pd
from scipy.optimize import linprog  # ← ОБЯЗАТЕЛЬНО
import numpy as np
import itertools
import matplotlib.pyplot as plt
import textwrap



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
for category in df_ingr_all['Категория'].dropna().unique():
    with st.expander(f"{category}"):
        df_cat = df_ingr_all[df_ingr_all['Категория'] == category]
        for ingredient in df_cat['Ингредиент'].dropna().unique():
            with st.expander(f"{ingredient}"):
                df_ing = df_cat[df_cat['Ингредиент'] == ingredient]
                for desc in df_ing['Описание'].dropna().unique():
                    label = f"{ingredient} — {desc}"
                    key = f"{category}_{ingredient}_{desc}"
                    if st.button(f"{desc}", key=key):
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

            with st.spinner("🔄 Ищем по другому методу..."):
        
                    step = 1  # шаг в процентах
                    variants = []
                    ranges = [np.arange(low, high + step, step) for (low, high) in ingr_ranges]
        
                    # Генерация всех комбинаций, которые дают в сумме 100 г
                    for combo in itertools.product(*ranges):
                        if abs(sum(combo) - 100) < 1e-6:
                            variants.append(combo)
        
                    best_recipe = None
                    min_penalty = float("inf")
        
                    for combo in variants:
                        values = dict(zip(ingredient_names, combo))
        
                        totals = {nutr: 0.0 for nutr in cols_to_divide}
                        for i, ingr in enumerate(ingredient_names):
                            for nutr in cols_to_divide:
                                totals[nutr] += values[ingr] * food[ingr][nutr]
        
                        # Штраф за отклонения от допустимых диапазонов
                        penalty = 0
                        for nutr in cols_to_divide:
                            val = totals[nutr]
                            min_val = nutr_ranges[nutr][0]
                            max_val = nutr_ranges[nutr][1]
        
                            if val < min_val:
                                penalty += min_val - val
                            elif val > max_val:
                                penalty += val - max_val
        
                        if penalty < min_penalty:
                            min_penalty = penalty
                            best_recipe = (values, totals)

            if best_recipe:
                values, totals = best_recipe
                st.success("⚙️ Найден состав вручную (перебором):")

                st.markdown("### 📦 Состав (в граммах на 100 г):")
                for name, val in values.items():
                    st.write(f"{name}: **{round(val, 2)} г**")

                st.markdown("### 💪 Питательная ценность на 100 г:")
                for nutr in cols_to_divide:
                    st.write(f"**{nutr}:** {round(totals[nutr], 2)} г")

                               
                # --- График 1: Состав ингредиентов ---
                fig1, ax1 = plt.subplots(figsize=(10, 6))
                
                ingr_vals = [values[i] for i in ingredient_names]
                ingr_lims = ingr_ranges
                
                lower_errors = [val - low for val, (low, high) in zip(ingr_vals, ingr_lims)]
                upper_errors = [high - val for val, (low, high) in zip(ingr_vals, ingr_lims)]
                
                wrapped_ingredients = ['\n'.join(textwrap.wrap(label, 10)) for label in ingredient_names]
                
                ax1.errorbar(wrapped_ingredients, ingr_vals, yerr=[lower_errors, upper_errors],
                             fmt='o', capsize=5, color='#FF4B4B', ecolor='#CCCED1', elinewidth=2)
                ax1.set_ylabel("Значение")
                ax1.set_title("Ингредиенты: значения и ограничения")
                ax1.set_ylim(0, 100)
                ax1.grid(True, axis='y', linestyle='-', color='#e6e6e6', alpha=0.7)
                ax1.tick_params(axis='x', rotation=0)
                ax1.spines['top'].set_color('white')
                ax1.spines['right'].set_visible(False)
                
                st.pyplot(fig1)
                
                # --- График 2: Питательные вещества ---
                fig2, ax2 = plt.subplots(figsize=(10, 6))
                
                nutrients = list(nutr_ranges.keys())
                nutr_vals = [totals[n] for n in nutrients]
                nutr_lims = [nutr_ranges[n] for n in nutrients]
                
                for i, (nutrient, val, (low, high)) in enumerate(zip(nutrients, nutr_vals, nutr_lims)):
                    ax2.plot([i, i], [low, high], color='#CCCED1', linewidth=4, alpha=0.5)
                    ax2.plot(i, val, 'o', color='#FF4B4B')
                
                ax2.set_xticks(range(len(nutrients)))
                ax2.set_xticklabels(nutrients, rotation=0)
                ax2.set_ylabel("Граммы")
                ax2.set_title("Питательные вещества: значения и допустимые границы")
                ax2.set_ylim(0, 100)
                ax2.grid(True, axis='y', linestyle='-', color='#e6e6e6', alpha=0.7)
                ax2.spines['top'].set_color('white')
                ax2.spines['right'].set_visible(False)
                
                st.pyplot(fig2)
             

            
           
            
            else:
                st.error("🚫 Не удалось найти подходящий состав даже вручную.")

else:
    st.info("👈 Пожалуйста, выберите хотя бы один ингредиент.")
    
