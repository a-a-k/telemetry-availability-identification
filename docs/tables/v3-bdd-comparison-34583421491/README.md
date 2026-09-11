# Полные таблицы сравнения CUDD

- [all_measurements.csv](all_measurements.csv): 9456 строк.
- [batch_resources.csv](batch_resources.csv): 48 строк.
- [exact_bounds.csv](exact_bounds.csv): 8668 строк.
- [structural_absences.csv](structural_absences.csv): 39 строк.
- [paired_case_ratios.csv](paired_case_ratios.csv): 2364 строк.
- [solver_summary.csv](solver_summary.csv): 44 строк.
- [synthetic_grid.csv](synthetic_grid.csv): 27 строк.

Отношение Tспец/TBDD больше единицы означает преимущество BDD. Парные отношения сначала берутся в каждом раунде одного случая, затем медиана трёх; агрегат — медиана этих значений по случаям. Это технические повторы, не новые кампании. CPU и RSS пакета включают загрузку и проверку, время отдельного solve — нет.
