# Налаштування, збірка, тести

## Середовище розробки

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Залежності (`requirements.txt`): PySide6, pyqtgraph, PyOpenGL, numpy, mapbox-earcut, shapely,
pyinstaller. **cadquery прибрано** — застосунок працює на Python 3.11–3.13.

## Тести

```powershell
.\.venv\Scripts\python.exe test_grid_constructor.py
```

`test_grid_constructor.py` покриває:
- **Рушій**: розміри, drawer-divider, locks (`redistribute_locked`, `rescale_free`),
  `add_split` / `remove_line` / `redistribute_locked_multi`, сегментація, STL-експорт.
- **Інтеграцію** (offscreen Qt): створення сітки, рендер модулів, поячейкова правка з lock,
  save/load round-trip, перетягування стінки, розріз + Ctrl-мультивибір.
- **Регресію**: звичайна коробка (режим Генерація) досі генерується.

Запуск offscreen: `set QT_QPA_PLATFORM=offscreen` (тести роблять це самі).

## Збірка портативного EXE (Windows)

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\pyinstaller.exe box_generator.spec
# результат: dist\BoxGenerator_Portable\
```

`box_generator.spec` — one-folder, GUI (без консолі), виключає cadquery/OCP/casadi.
CI: `.github/workflows/build_windows.yml` (Python 3.10, `pyinstaller box_generator.spec`,
артефакт-папка).

## Структура файлів

```
main.py                 точка входу (+ venv-шим)
app.py                  BoxGeneratorApp (мікс-іни)
mesh_engine.py          екструзія, отвори, STL
grid_engine.py          рушій сітки
puzzle_item.py          2D-елементи сцени (Box / Compound / Grid)
ui_widgets.py           кастомні віджети
workers.py              GeometryWorker, MeshCache
mixins/
  ui_setup.py           побудова UI
  geometry.py           генерація геометрії, воркер, експорт
  assembly.py           2D-збирання
  bookmarks.py          пресети, пакетний експорт
  grid_constructor.py   конструктор сітки (UI + логіка)
requirements.txt
run_box_generator.bat   Windows-лаунчер
run_box_generator.sh    Linux-лаунчер
box_generator.spec      PyInstaller
test_grid_constructor.py
docs/                   ця документація
```

## Конвенції

- Геометрія — чиста (без Qt), щоб працювати у фоновому воркері.
- Файли читаються/пишуться з `encoding='utf-8'`; шляхи — через `os.path.join`.
- Коментарі та UI — українською.
