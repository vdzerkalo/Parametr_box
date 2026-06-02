# Рушій сітки (`grid_engine.py`)

Чистий рушій конструктора-органайзера (без Qt). Будує модулі зі спільними стінками,
рахує перерозподіл розмірів із фіксаціями, обробляє сегментацію та зʼєднання.

## `grid_config` (модель даних)

```python
{
  'outer_L', 'outer_W', 'outer_H',     # зовнішні габарити, мм
  'nx', 'ny',                           # к-сть стовпців / рядів
  'wall',                               # товщина стінок, мм
  'floor_t',                            # товщина дна (0 = без дна)
  'col_widths': [...nx],                # ВНУТРІШНІ розміри комірок (джерело істини)
  'row_heights': [...ny],
  'col_locked': [...nx],                # прапорці фіксації (bool)
  'row_locked': [...ny],
  'bed_x', 'bed_y',                     # розмір столу принтера
  'cut_x': [...], 'cut_y': [...],       # ручні індекси розрізів
  'segment',                            # 'none' | 'bed' | 'manual' | 'per_cell'
  'joint',                              # 'dovetail' | 'none'
  'seam_clear', 'seam_tab_w', 'seam_tab_ratio', 'seam_spacing',
}
```

`outer` фіксований; `col_widths`/`row_heights` — джерело істини. `outer_L` завжди дорівнює
`sum(col_widths) + wall*(nx+1)`.

## Розміри (solve-from-outer, drawer-divider)

| Функція | Призначення |
|---|---|
| `inner_total(outer, n, wall)` | Корисна довжина = `outer − wall*(n+1)` |
| `auto_sizes(outer, n, wall)` | Рівні розміри комірок |
| `redistribute(sizes, idx, new_val, …)` | Задати одну комірку, решту перерозподілити пропорційно |
| `redistribute_locked(sizes, idx, new_val, …, locked)` | Те саме, але **locked** комірки не змінюються; дельту поглинають лише вільні |
| `redistribute_locked_multi(sizes, {idx: val}, …, locked)` | Задати кілька комірок одночасно (Ctrl-вибір) |
| `rescale_free(sizes, new_outer, wall, locked)` | Зміна `outer`: locked незмінні, вільні масштабуються |
| `resize_outer(sizes, new_outer, wall)` | Пропорційне масштабування (без locks) |

Усі зберігають суму = `inner_total` і клампують до `MIN_CELL` (6 мм). Якщо вільних комірок
немає / locked не влізають — повертають частковий результат, а UI показує підказку.

## Структурні операції

| Функція | Призначення |
|---|---|
| `add_split(sizes, locked, index, ratio)` | Розділити комірку index на дві (за `ratio`); `(sizes, locked, ok)` |
| `remove_line(sizes, locked, index)` | Видалити комірку, додавши її розмір до сусіда |

## Сегментація на модулі

`_groups(sizes, wall, bed, mode, cuts)` повертає групи індексів:
- `none` → одна група (моноліт);
- `bed` → жадібне пакування під `bed` (найменше число шматків);
- `manual` → за `cuts`;
- `per_cell` → кожна комірка окремо.

`layout_info(config)` віддає `cav_x`, `cav_y` (інтервали комірок), `col_groups`, `row_groups`,
`outer_L/W`, `n_modules`.

## Побудова геометрії: `build_modules(config)`

Повертає список модулів `{mesh, color_idx, cols, rows, bounds}` (центровано навколо (0,0),
низ на z=0). Для кожного модуля (група стовпців × група рядів):

1. **Оболонка** = прямокутник модуля; на швах між модулями — **dovetail-зубці** (трапеції,
   ширші на кінчику) як вертикальний слайд-замок (male на +X/+Y, female з зазором на −).
2. **Порожнини** комірок віднімаються (`shapely.difference`) → полігон зі стінками (з отворами).
3. **Стінки** екструдуються на всю висоту; якщо `floor_t > 0` — додається **дно** (накладається
   знизу, слайсер зварює).
4. Шов проходить по **центру спільної стінки** — кожен модуль отримує `wall/2` на стику, разом
   формують повну стінку; dovetail глибиною `wall/2` зчіплює їх.

Деталі рендер-інтеграції — `GridConstructorMixin._append_grid_item_meshes`
(позиціювання за `item.x/y`, поворот, колір модуля).

## Допоміжне

- `summary_data(config)` → `{length, width, height}` (для `item['data']`, сумісність із guards).
- `validate(config)` → `(ok, msg)` (мін. розмір комірки, дно тонше за висоту тощо).
