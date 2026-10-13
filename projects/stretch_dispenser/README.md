# projects/stretch_dispenser — розмотувач стрейч-плівки на струбцинах (Bambu Lab A1 · PETG)

Універсальний під довжину плівки (вісь із секцій + муфти), діаметр гільзи 36–54 мм і будь-який край столу (струбцини, тримач крутиться кроками 15°).

| Папка | Що це |
|---|---|
| `v2_all_printed/` | **Основний.** Все друкується, нічого докуповувати. Старт: `3mf/Stretch_Dispenser_A1_PETG.3mf` (1 файл, 4 пластини). Опис, збірка, SPEC: `v2_all_printed/README.md` |
| `v1_hardware/` | Варіант із метизами (шпилька M10, болти, гайки): менше друку, міцніша різьба. |

AI-швидкий старт: `cd v2_all_printed && pip install -r requirements.txt && python generate.py ШИРИНА_ПЛІВКИ ID_ГІЛЬЗИ` (за замовч. 530 50), далі `python calc.py ШИРИНА ID` (скільки секцій осі), `python verify_project.py`, `python assemble.py ШИРИНА ID` (колізії/різьби).
Обмеження принтера власника: деталь не вища за 225 мм (`max_print_h`), тому секція осі 200 мм.
`assembly_preview.stl` (29 МБ) у git не зберігається: `python assemble.py` / `python render.py` створюють його заново.
