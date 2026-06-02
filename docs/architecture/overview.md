# Архітектура: огляд

## Стек

- **GUI**: PySide6 (Qt6), темна Fusion-тема.
- **Геометрія**: власний mesh-рушій на `numpy` + `mapbox_earcut` (тріангуляція) + `shapely`
  (2D-булеві операції). CAD-ядро (cadquery) **не використовується**.
- **3D-перегляд**: `pyqtgraph.opengl` (GLViewWidget).
- **Експорт**: ASCII STL.

## Точка входу

- `main.py` — створює `QApplication`, темну палітру, головне вікно. Містить **шим**, що
  перемикається на `.venv`, якщо в інтерпретаторі бракує залежностей.
- `app.py` — клас `BoxGeneratorApp(QMainWindow, …mixins)`.

## Мікс-іни (вся логіка)

`BoxGeneratorApp` збирається з мікс-інів — кожен відповідає за свою частину:

| Мікс-ін | Файл | Відповідальність |
|---|---|---|
| `UISetupMixin` | `mixins/ui_setup.py` | Побудова UI, режими, перемикання перегляду, `mark_dirty` |
| `GeometryMixin` | `mixins/geometry.py` | Генерація геометрії коробки/збірки, воркер, експорт STL |
| `AssemblyMixin` | `mixins/assembly.py` | 2D-збирання: snap, split, merge, flatten, 2D-сцена |
| `BookmarksMixin` | `mixins/bookmarks.py` | Пресети/закладки, пакетний експорт |
| `GridConstructorMixin` | `mixins/grid_constructor.py` | Конструктор сітки: панель, правки, lock, рендер-хук |

Інші модулі:
- `mesh_engine.py` — низькорівнева геометрія ([деталі](geometry-engine.md)).
- `grid_engine.py` — рушій сітки-органайзера ([деталі](grid-engine.md)).
- `puzzle_item.py` — 2D-елементи сцени: `PuzzleBoxItem`, `CompoundPuzzleItem`, `PuzzleGridItem`.
- `ui_widgets.py` — кастомні віджети: `CollapsibleBox`, `ToolboxListWidget`, `PuzzleGraphicsView`,
  `SnapDialog`, `ExportFolderDialog`, `BookmarksTreeWidget`.
- `workers.py` — `GeometryWorker` (QThread) і `MeshCache`.

## Потік даних (генерація)

```
UI (зміна параметра)
   → mark_dirty / regen_timer (debounce)
   → generate_box()                     # захоплює Qt-параметри в UI-потоці
   → GeometryWorker (QThread)
        → _generate_single/assembly_from_params()   # чиста геометрія, без Qt
        → _do_tessellate()                            # MeshData → numpy для GL
   → result_ready (сигнал)
   → _on_geometry_ready()               # оновлює GLMeshItem у 3D-в’юпорті
```

- Важкі обчислення — у фоновому потоці; Qt-обʼєкти не торкаються з воркера.
- `MeshCache` кешує результати за ключем параметрів; повторні запити миттєві.
- Якщо воркер зайнятий — нові запити **коалесуються** (зберігається лише останній).

## Збірка та сітка

`placed_items` — список елементів сцени трьох типів: `box`, `compound`, `grid`
([Модель даних](data-model.md)). `_generate_assembly_from_params` рендерить кожен:
для `grid` викликається `GridConstructorMixin._append_grid_item_meshes` →
`grid_engine.build_modules`.

## Перегляд: спліт 2D+3D

3D-в’юпорт і 2D-пазл лежать в одному `QSplitter` (`view_split`). `_set_view_mode('2d'|'3d'|'split')`
керує видимістю кожного. У режимі `split` правки у 2D оновлюють 3D через throttle.
