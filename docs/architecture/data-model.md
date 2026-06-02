# Модель даних

## `placed_items`

Список елементів сцени збирання. Три типи:

### `box` — звичайна коробка
```json
{
  "type": "box",
  "name": "box_1",
  "data": {
    "length": 100, "width": 50, "height": 30, "wall_t": 3,
    "tab_base": 20, "tab_tip": 30, "tab_depth": 10, "clearance": 0.0, "fillet": 0.0,
    "side_top": 0, "side_bottom": 1, "side_left": 1, "side_right": 0,
    "side_top_count": 1, "...": "..."
  },
  "x": 0.0, "y": 0.0, "rotation": 0, "color_idx": 0
}
```
Сторони: `0` = шип (male), `1` = паз (female), `2` = пряма.

### `compound` — обʼєднані коробки
```json
{
  "type": "compound",
  "parts": [ { "data": {…}, "rel_x": 0, "rel_y": 0 }, { "data": {…}, "rel_x": 50, "rel_y": 0 } ],
  "data": {…summary…}, "x": …, "y": …, "rotation": 0, "color_idx": 1
}
```
Внутрішні зубці ховаються при рендері (`is_internal`); `parts[]` дозволяє розʼєднати назад.

### `grid` — сітка-органайзер
```json
{
  "type": "grid",
  "name": "Сітка 4x3",
  "grid_config": { …див. grid-engine.md… },
  "data": { "length": 240, "width": 160, "height": 40 },
  "x": 0.0, "y": 0.0, "rotation": 0, "color_idx": 0
}
```
`data` — лише summary (щоб спільні обходи `placed_items` не падали); справжня модель — у
`grid_config`. Рендер: `_append_grid_item_meshes` → `grid_engine.build_modules`.

## Сумісність типів (guards)

Спільний код (`get_item_under_cursor`, `update_adaptive_grid`, `_update_decorations`,
`ensure_unique_colors`) читає `item["data"]["length"/"width"/"height"]` — тому всі типи
мають `data` зі summary. Спеціальні гілки додано для `grid`:
- `_generate_assembly_from_params` (geometry.py) — рендер;
- `update_puzzle_view` (assembly.py) — `PuzzleGridItem`;
- `try_auto_snap` — сітка не прилипає;
- `on_live_height_changed` — висота йде в `grid_config['outer_H']`;
- `on_placed_item_changed` — синхронізує панель конструктора.

## Збереження

- **Збірка** → JSON: `{ "placed_items": [...], "unplaced_items": [...] }`.
  `grid_config` (вкладені dict/list) серіалізується без проблем.
- **Авто-стан** → реєстр `HKCU\Software\KasNew\BoxGenerator` (QSettings); відновлюється при старті
  (`load_auto_settings` → `set_preset_dict`).
- **Пресети** → окремі `.json` у теці `presets/`.
