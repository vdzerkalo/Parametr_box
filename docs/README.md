# Документація ParametrBox

**ParametrBox** — параметричний генератор коробок та органайзерів для 3D-друку (FDM).
GUI на PySide6; геометрія — власний mesh-рушій (numpy + mapbox_earcut + shapely),
без CAD-ядра; експорт у STL.

## 📂 Зміст

### Користувацький гайд
- [Початок роботи](user-guide/getting-started.md) — встановлення, запуск, системні вимоги
- [Режим «Генерація»](user-guide/box-mode.md) — одна коробка з пазловими стиками + кришка
- [Режим «Збирання»](user-guide/assembly-mode.md) — 2D-пазл, snap, merge, бібліотека пресетів
- [**Конструктор сітки**](user-guide/grid-constructor.md) — органайзер з ячейок (головна нова фіча)

### Архітектура
- [Огляд](architecture/overview.md) — структура застосунку, потік даних, мікс-іни
- [Mesh-рушій](architecture/geometry-engine.md) — `mesh_engine.py`: екструзія, отвори, STL
- [Рушій сітки](architecture/grid-engine.md) — `grid_engine.py`: модель, перерозподіл, модулі
- [Модель даних](architecture/data-model.md) — `placed_items`, `grid_config`, збереження

### Розробка
- [Налаштування, збірка, тести](development/setup-build-test.md)
- [Нотатки по Windows](development/windows-notes.md)

### Журнал
- [CHANGELOG](CHANGELOG.md) — історія змін, включно з останніми

## Швидкий старт

```bat
run_box_generator.bat
```

Далі: режим **Збирання** → панель **«Конструктор сітки»** → задайте розміри → сітка зʼявиться
сама. Детальніше — у [гайді конструктора](user-guide/grid-constructor.md).
