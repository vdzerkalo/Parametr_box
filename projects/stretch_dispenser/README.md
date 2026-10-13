# projects/stretch_dispenser — розмотувач стрейч-плівки на струбцинах (Bambu Lab A1 · PETG)

Універсальний під довжину плівки (вісь із секцій + муфти), діаметр гільзи 36–54 мм і будь-який край столу (струбцини, тримач крутиться кроками 15°).

| Папка | Що це |
|---|---|
| `v2_all_printed/` | **Основний.** Все друкується, нічого докуповувати. Старт: `3mf/Stretch_Dispenser_A1_PETG.3mf` (1 файл, 4 пластини). Опис, збірка, SPEC: `v2_all_printed/README.md` |
| `v1_hardware/` | Варіант із метизами (шпилька M10, болти, гайки): менше друку, міцніша різьба. |

AI-швидкий старт: `cd v2_all_printed && pip install -r requirements.txt && python generate.py ШИРИНА_ПЛІВКИ ID_ГІЛЬЗИ` (за замовч. 530 46), далі `python calc.py ШИРИНА ID` (скільки секцій осі), `python verify_project.py`, `python assemble.py ШИРИНА ID` (колізії/різьби).
Довжини секцій осі: бібліотека `rod_lengths` (60…200 мм) на окремій пластині `3mf/Axle_Rod_Library_A1_PETG.3mf`; обирайте під свій принтер/плівку.
`assembly_preview.stl` (29 МБ) у git не зберігається: `python assemble.py` / `python render.py` створюють його заново.
