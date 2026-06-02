"""mixins/grid_constructor.py — GridConstructorMixin.

Параметричний конструктор сітки-органайзера: панель UI + логіка створення,
редагування ячейок (drawer-divider) та рендер-хук. Спирається на grid_engine.
Дані зберігаються в placed_items як {"type":"grid","grid_config":{...},
"data":{summary},"x","y","rotation","color_idx","name"}.
"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
                               QDoubleSpinBox, QSpinBox, QComboBox, QCheckBox, QPushButton,
                               QStyle, QFrame, QMessageBox, QLineEdit)
from PySide6.QtCore import Qt, QTimer, QRectF, QRect, Signal
from PySide6.QtGui import QDoubleValidator

import grid_engine as ge


class _DimLineEdit(QLineEdit):
    """Поле інлайн-редактора: Tab/Space — перемкнути, Enter — застосувати, Esc — скасувати."""
    jump = Signal()
    commit = Signal()
    cancel = Signal()

    def keyPressEvent(self, ev):
        k = ev.key()
        if k in (Qt.Key_Space, Qt.Key_Tab):
            self.jump.emit(); ev.accept(); return
        if k in (Qt.Key_Return, Qt.Key_Enter):
            self.commit.emit(); ev.accept(); return
        if k == Qt.Key_Escape:
            self.cancel.emit(); ev.accept(); return
        super().keyPressEvent(ev)


class InlineDimEditor(QWidget):
    """Інлайн 'Ширина × Глибина' з фіксованим ×; Tab/Space перемикає поля."""
    committed = Signal(object, object)
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:#161616; border:1px solid #2a82da; border-radius:4px;")
        lay = QHBoxLayout(self); lay.setContentsMargins(4, 1, 4, 1); lay.setSpacing(1)
        self.w_edit = _DimLineEdit(); self.h_edit = _DimLineEdit()
        xlbl = QLabel("×")
        xlbl.setStyleSheet("color:#2a82da; font-weight:bold; background:transparent;")
        for e in (self.w_edit, self.h_edit):
            e.setAlignment(Qt.AlignCenter)
            e.setStyleSheet("background:transparent; color:#fff; border:none;")
            e.setValidator(QDoubleValidator(1.0, 9999.0, 1))
        lay.addWidget(self.w_edit); lay.addWidget(xlbl); lay.addWidget(self.h_edit)
        self.w_edit.jump.connect(self._focus_h)
        self.h_edit.jump.connect(self._focus_w)
        for e in (self.w_edit, self.h_edit):
            e.commit.connect(self._do_commit)
            e.cancel.connect(self.cancelled)

    def _focus_w(self):
        self.w_edit.setFocus(); self.w_edit.selectAll()

    def _focus_h(self):
        self.h_edit.setFocus(); self.h_edit.selectAll()

    def _do_commit(self):
        def pf(t):
            t = t.strip().replace(',', '.')
            try:
                return float(t)
            except ValueError:
                return None
        self.committed.emit(pf(self.w_edit.text()), pf(self.h_edit.text()))

    def set_values(self, w, h):
        self.w_edit.setText(f"{w:.0f}"); self.h_edit.setText(f"{h:.0f}")


class GridConstructorMixin:
    SEGMENT_MODES = [("Моноліт (1 шматок)", "none"),
                     ("Розрізати по столу", "bed"),
                     ("Ручне групування", "manual"),
                     ("Кожна ячейка окремо", "per_cell")]
    JOINT_MODES = [("Dovetail (безклейовий)", "dovetail"),
                   ("Без шва (встик)", "none")]

    # ───────────────────────────── UI ─────────────────────────────
    def _setup_grid_panel(self, left_layout):
        from ui_widgets import CollapsibleBox
        self._active_grid_idx_val = None
        self.grid_box = CollapsibleBox(
            "Конструктор сітки",
            self.style().standardIcon(QStyle.SP_FileDialogListView),
            "#3a5a3a", "#2e4a2e")
        lay = QVBoxLayout()

        def dsb(val, lo, hi, step, dec=1):
            s = QDoubleSpinBox(); s.setRange(lo, hi); s.setSingleStep(step)
            s.setDecimals(dec); s.setValue(val); return s

        def sb(val, lo, hi):
            s = QSpinBox(); s.setRange(lo, hi); s.setValue(val); return s

        form = QFormLayout()
        self.grid_outer_l = dsb(240, 20, 2000, 5)
        self.grid_outer_w = dsb(160, 20, 2000, 5)
        self.grid_outer_h = dsb(40, 5, 500, 1)
        self.grid_nx = sb(4, 1, 50)
        self.grid_ny = sb(3, 1, 50)
        self.grid_wall = dsb(2.0, 0.4, 10, 0.2, 2)
        form.addRow("Зовн. довжина L:", self.grid_outer_l)
        form.addRow("Зовн. ширина W:", self.grid_outer_w)
        form.addRow("Висота H:", self.grid_outer_h)
        form.addRow("Стовпців (X):", self.grid_nx)
        form.addRow("Рядів (Y):", self.grid_ny)
        form.addRow("Товщина стінки:", self.grid_wall)
        lay.addLayout(form)

        floor_row = QHBoxLayout()
        self.grid_floor_cb = QCheckBox("Дно")
        self.grid_floor_cb.setChecked(True)
        self.grid_floor_t = dsb(2.4, 0.4, 20, 0.2, 2)
        self.grid_floor_cb.toggled.connect(self.grid_floor_t.setEnabled)
        floor_row.addWidget(self.grid_floor_cb)
        floor_row.addWidget(QLabel("товщина:"))
        floor_row.addWidget(self.grid_floor_t)
        floor_row.addStretch()
        lay.addLayout(floor_row)

        form2 = QFormLayout()
        self.grid_segment = QComboBox()
        for label, _ in self.SEGMENT_MODES:
            self.grid_segment.addItem(label)
        self.grid_joint = QComboBox()
        for label, _ in self.JOINT_MODES:
            self.grid_joint.addItem(label)
        bed_row = QHBoxLayout()
        self.grid_bed_x = dsb(220, 50, 1000, 10)
        self.grid_bed_y = dsb(220, 50, 1000, 10)
        bed_row.addWidget(QLabel("X")); bed_row.addWidget(self.grid_bed_x)
        bed_row.addWidget(QLabel("Y")); bed_row.addWidget(self.grid_bed_y)
        cut_row = QHBoxLayout()
        self.grid_cut_x = QLineEdit(); self.grid_cut_x.setPlaceholderText("напр. 2,4")
        self.grid_cut_y = QLineEdit(); self.grid_cut_y.setPlaceholderText("напр. 2")
        cut_row.addWidget(QLabel("X")); cut_row.addWidget(self.grid_cut_x)
        cut_row.addWidget(QLabel("Y")); cut_row.addWidget(self.grid_cut_y)
        form2.addRow("Сегментація:", self.grid_segment)
        form2.addRow("Розмір столу:", self._wrap_layout(bed_row))
        form2.addRow("Ручні розрізи:", self._wrap_layout(cut_row))
        form2.addRow("Тип шва:", self.grid_joint)
        lay.addLayout(form2)
        self.grid_segment.currentIndexChanged.connect(self._update_segment_fields)
        self._update_segment_fields()

        self.grid_status = QLabel("↳ змінюйте параметри — сітка оновлюється автоматично")
        self.grid_status.setWordWrap(True)
        lay.addWidget(self.grid_status)

        hint = QLabel("2-клік по комірці у 2D → редагувати її розмір (з фіксацією)")
        hint.setStyleSheet("color:#888; font-size:11px;")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        # ── тултіпи (підказки при наведенні) ──
        self.grid_outer_l.setToolTip("Зовнішня довжина ящика по X (мм)")
        self.grid_outer_w.setToolTip("Зовнішня ширина ящика по Y (мм)")
        self.grid_outer_h.setToolTip("Висота ящика по Z (мм)")
        self.grid_nx.setToolTip("Скільки комірок по горизонталі (X)")
        self.grid_ny.setToolTip("Скільки комірок по вертикалі (Y)")
        self.grid_wall.setToolTip("Товщина всіх стінок (мм).\nКратна діаметру сопла (0.4) — міцніший друк")
        self.grid_floor_cb.setToolTip("Робити дно у відсіках (інакше наскрізні)")
        self.grid_floor_t.setToolTip("Товщина дна (мм)")
        self.grid_segment.setToolTip("Як ділити на окремі друковані шматки:\n"
                                     "• Моноліт — один шматок\n"
                                     "• По столу — авто-розбиття під розмір принтера\n"
                                     "• Ручне — свої лінії розрізу нижче\n"
                                     "• Кожна ячейка — кожен відсік окремо")
        self.grid_joint.setToolTip("З'єднання між шматками:\n"
                                   "• Dovetail — безклейовий замок (зсув по Z)\n"
                                   "• Без шва — рівний стик")
        self.grid_bed_x.setToolTip("Ширина столу принтера по X (мм)")
        self.grid_bed_y.setToolTip("Глибина столу принтера по Y (мм)")
        self.grid_cut_x.setToolTip("Розрізати ПІСЛЯ цих стовпців, напр. 2,4")
        self.grid_cut_y.setToolTip("Розрізати ПІСЛЯ цих рядів, напр. 2")

        # ── real-time: будь-яка зміна параметра оновлює сітку (з затримкою) ──
        self._grid_live_timer = QTimer(self)
        self._grid_live_timer.setSingleShot(True)
        self._grid_live_timer.timeout.connect(self._live_update_grid)
        for sb_w in (self.grid_outer_l, self.grid_outer_w, self.grid_outer_h,
                     self.grid_nx, self.grid_ny, self.grid_wall, self.grid_floor_t,
                     self.grid_bed_x, self.grid_bed_y):
            sb_w.valueChanged.connect(self._schedule_grid_update)
        self.grid_floor_cb.toggled.connect(self._schedule_grid_update)
        self.grid_segment.currentIndexChanged.connect(self._schedule_grid_update)
        self.grid_joint.currentIndexChanged.connect(self._schedule_grid_update)
        self.grid_cut_x.textChanged.connect(self._schedule_grid_update)
        self.grid_cut_y.textChanged.connect(self._schedule_grid_update)
        try:
            self.grid_box.toggle_button.toggled.connect(self._on_grid_box_toggled)
        except Exception:
            pass

        self.grid_box.setContentLayout(lay)
        left_layout.addWidget(self.grid_box)
        self.grid_box.setVisible(False)

        self._setup_cell_editor_panel(left_layout)

    def _setup_cell_editor_panel(self, left_layout):
        """Окремий згорнутий блок 'Редактор комірки' — авто-розгортається на 2-клік."""
        from ui_widgets import CollapsibleBox
        self._editing_cell = None
        self.cell_box = CollapsibleBox(
            "Редактор комірки",
            self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
            "#5a4a2e", "#473a24")
        lay = QVBoxLayout()
        self.cell_label = QLabel("Комірка: — (2-клік по комірці у 2D)")
        self.cell_label.setWordWrap(True)
        self.cell_label.setStyleSheet("font-weight:bold;")
        lay.addWidget(self.cell_label)

        form = QFormLayout()
        self.cell_w_spin = QDoubleSpinBox(); self.cell_w_spin.setRange(ge.MIN_CELL, 5000)
        self.cell_w_spin.setDecimals(1); self.cell_w_spin.setSingleStep(1)
        self.cell_h_spin = QDoubleSpinBox(); self.cell_h_spin.setRange(ge.MIN_CELL, 5000)
        self.cell_h_spin.setDecimals(1); self.cell_h_spin.setSingleStep(1)
        self.cell_w_lock = QCheckBox("🔒")
        self.cell_h_lock = QCheckBox("🔒")
        self.cell_w_spin.setToolTip("Ширина комірки = ширина її стовпця (мм).\nЗміна фіксує стовпець (lock).")
        self.cell_h_spin.setToolTip("Глибина комірки = висота її ряду (мм).\nЗміна фіксує ряд (lock).")
        self.cell_w_lock.setToolTip("Зафіксувати ширину: не змінюватиметься, коли правите інші комірки")
        self.cell_h_lock.setToolTip("Зафіксувати глибину: не змінюватиметься, коли правите інші комірки")
        wrow = QHBoxLayout(); wrow.addWidget(self.cell_w_spin); wrow.addWidget(self.cell_w_lock)
        hrow = QHBoxLayout(); hrow.addWidget(self.cell_h_spin); hrow.addWidget(self.cell_h_lock)
        form.addRow("Ширина Д:", self._wrap_layout(wrow))
        form.addRow("Глибина Ш:", self._wrap_layout(hrow))
        lay.addLayout(form)

        self.cell_unlock_btn = QPushButton(" Розблокувати все")
        self.cell_unlock_btn.setToolTip("Зняти всі фіксації — розміри знову розподілятимуться вільно")
        self.cell_unlock_btn.clicked.connect(self.unlock_all_cells)
        lay.addWidget(self.cell_unlock_btn)

        hint = QLabel("↳ Enter застосовує й фіксує. Або тягніть стінку у 2D.")
        hint.setStyleSheet("color:#888; font-size:11px;"); hint.setWordWrap(True)
        lay.addWidget(hint)

        self.cell_w_spin.editingFinished.connect(self._on_cell_w_edited)
        self.cell_h_spin.editingFinished.connect(self._on_cell_h_edited)
        self.cell_w_lock.toggled.connect(lambda v: self._on_cell_lock('x', v))
        self.cell_h_lock.toggled.connect(lambda v: self._on_cell_lock('y', v))

        self.cell_box.setContentLayout(lay)
        left_layout.addWidget(self.cell_box)
        self.cell_box.setVisible(False)

    def _wrap_layout(self, layout):
        w = QWidget(); w.setLayout(layout); return w

    # ───────────────────────────── config ─────────────────────────────
    def _update_segment_fields(self):
        seg = self.SEGMENT_MODES[self.grid_segment.currentIndex()][1]
        self.grid_bed_x.setEnabled(seg == 'bed')
        self.grid_bed_y.setEnabled(seg == 'bed')
        self.grid_cut_x.setEnabled(seg == 'manual')
        self.grid_cut_y.setEnabled(seg == 'manual')

    @staticmethod
    def _parse_cuts(text):
        out = []
        for tok in str(text).replace(';', ',').replace(' ', ',').split(','):
            tok = tok.strip()
            if tok.isdigit():
                out.append(int(tok))
        return out

    def _grid_config_from_panel(self):
        seg = self.SEGMENT_MODES[self.grid_segment.currentIndex()][1]
        joint = self.JOINT_MODES[self.grid_joint.currentIndex()][1]
        cfg = ge.default_config(
            outer_L=self.grid_outer_l.value(), outer_W=self.grid_outer_w.value(),
            outer_H=self.grid_outer_h.value(),
            nx=self.grid_nx.value(), ny=self.grid_ny.value(),
            wall=self.grid_wall.value(),
            floor_t=(self.grid_floor_t.value() if self.grid_floor_cb.isChecked() else 0.0),
            bed_x=self.grid_bed_x.value(), bed_y=self.grid_bed_y.value(),
            segment=seg, joint=joint)
        cfg['cut_x'] = self._parse_cuts(self.grid_cut_x.text())
        cfg['cut_y'] = self._parse_cuts(self.grid_cut_y.text())
        return cfg

    def _active_grid_idx(self):
        items = getattr(self, 'placed_items', [])
        if hasattr(self, 'placed_list'):
            row = self.placed_list.currentRow()
            if 0 <= row < len(items) and items[row].get("type") == "grid":
                return row
        v = getattr(self, '_active_grid_idx_val', None)
        if v is not None and 0 <= v < len(items) and items[v].get("type") == "grid":
            return v
        for i, it in enumerate(items):
            if it.get("type") == "grid":
                return i
        return None

    # ─────────────────────────── create / update ───────────────────────────
    def create_or_update_grid(self):
        if hasattr(self, 'mode_assem_btn') and not self.mode_assem_btn.isChecked():
            self.mode_assem_btn.setChecked(True)
        cfg = self._grid_config_from_panel()
        ok, msg = ge.validate(cfg)
        if not ok:
            self.grid_status.setText("⚠ " + msg)
            QMessageBox.warning(self, "Сітка", msg)
            return
        idx = self._active_grid_idx()
        if idx is None:
            item = {"type": "grid", "name": f"Сітка {cfg['nx']}x{cfg['ny']}",
                    "x": 0.0, "y": 0.0, "rotation": 0,
                    "color_idx": len(self.placed_items) % len(self.assembly_palette),
                    "grid_config": cfg, "data": ge.summary_data(cfg)}
            self.placed_items.append(item)
            self.placed_list.addItem(item["name"])
            idx = len(self.placed_items) - 1
        else:
            item = self.placed_items[idx]
            item["grid_config"] = cfg
            item["name"] = f"Сітка {cfg['nx']}x{cfg['ny']}"
            item["data"] = ge.summary_data(cfg)
            if idx < self.placed_list.count():
                self.placed_list.item(idx).setText(item["name"])
        self._active_grid_idx_val = idx
        self._refresh_after_grid_change(idx)

    # ─────────────────── real-time оновлення ───────────────────
    def _schedule_grid_update(self, *args):
        if hasattr(self, '_grid_live_timer'):
            self._grid_live_timer.start(350)

    def _on_grid_box_toggled(self, expanded):
        if not expanded:
            return
        if not (hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()):
            return
        idx = self._active_grid_idx()
        if idx is None:
            self._schedule_grid_update()          # перша поява панелі → створити сітку
        else:
            self._sync_panel_from_grid(idx)        # вже є сітка → підтягнути її параметри

    def _sync_panel_from_grid(self, idx):
        """Заповнює поля панелі з наявної сітки (без тригера live-оновлення)."""
        cfg = self.placed_items[idx]['grid_config']
        info = ge.layout_info(cfg)
        ws = [self.grid_outer_l, self.grid_outer_w, self.grid_outer_h, self.grid_nx,
              self.grid_ny, self.grid_wall, self.grid_floor_t, self.grid_bed_x,
              self.grid_bed_y, self.grid_floor_cb, self.grid_segment, self.grid_joint,
              self.grid_cut_x, self.grid_cut_y]
        for w in ws:
            w.blockSignals(True)
        self.grid_outer_l.setValue(info['outer_L']); self.grid_outer_w.setValue(info['outer_W'])
        self.grid_outer_h.setValue(cfg.get('outer_H', 40))
        self.grid_nx.setValue(len(cfg['col_widths'])); self.grid_ny.setValue(len(cfg['row_heights']))
        self.grid_wall.setValue(cfg.get('wall', 2.0))
        ft = cfg.get('floor_t', 0) or 0
        self.grid_floor_cb.setChecked(ft > 0)
        if ft > 0:
            self.grid_floor_t.setValue(ft)
        self.grid_bed_x.setValue(cfg.get('bed_x', 220)); self.grid_bed_y.setValue(cfg.get('bed_y', 220))
        seg = cfg.get('segment', 'none')
        self.grid_segment.setCurrentIndex(next((i for i, (_, k) in enumerate(self.SEGMENT_MODES) if k == seg), 0))
        jn = cfg.get('joint', 'dovetail')
        self.grid_joint.setCurrentIndex(next((i for i, (_, k) in enumerate(self.JOINT_MODES) if k == jn), 0))
        self.grid_cut_x.setText(','.join(map(str, cfg.get('cut_x', []) or [])))
        self.grid_cut_y.setText(','.join(map(str, cfg.get('cut_y', []) or [])))
        for w in ws:
            w.blockSignals(False)
        self._update_segment_fields()
        self._sync_cell_size_field()

    def _live_update_grid(self):
        if not (hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()):
            return
        L = self.grid_outer_l.value(); W = self.grid_outer_w.value(); H = self.grid_outer_h.value()
        nx = self.grid_nx.value(); ny = self.grid_ny.value(); wall = self.grid_wall.value()
        floor = self.grid_floor_t.value() if self.grid_floor_cb.isChecked() else 0.0
        seg = self.SEGMENT_MODES[self.grid_segment.currentIndex()][1]
        joint = self.JOINT_MODES[self.grid_joint.currentIndex()][1]
        bed_x = self.grid_bed_x.value(); bed_y = self.grid_bed_y.value()
        cut_x = self._parse_cuts(self.grid_cut_x.text()); cut_y = self._parse_cuts(self.grid_cut_y.text())
        idx = self._active_grid_idx()
        if idx is None:
            cfg = ge.default_config(outer_L=L, outer_W=W, outer_H=H, nx=nx, ny=ny, wall=wall,
                                    floor_t=floor, bed_x=bed_x, bed_y=bed_y, segment=seg, joint=joint)
            cfg['cut_x'] = cut_x; cfg['cut_y'] = cut_y
            ok, msg = ge.validate(cfg)
            if not ok:
                self.grid_status.setText("⚠ " + msg)
                return
            item = {"type": "grid", "name": f"Сітка {nx}x{ny}", "x": 0.0, "y": 0.0, "rotation": 0,
                    "color_idx": len(self.placed_items) % len(self.assembly_palette),
                    "grid_config": cfg, "data": ge.summary_data(cfg)}
            self.placed_items.append(item)
            self.placed_list.addItem(item["name"])
            idx = len(self.placed_items) - 1
        else:
            cfg = self.placed_items[idx]['grid_config']
            old_nx = len(cfg['col_widths']); old_ny = len(cfg['row_heights'])
            col_locked = (cfg.get('col_locked') or [False] * old_nx)[:old_nx]
            row_locked = (cfg.get('row_locked') or [False] * old_ny)[:old_ny]
            if nx != old_nx:
                cw = ge.auto_sizes(L, nx, wall); col_locked = [False] * nx
            else:
                cw = ge.rescale_free(cfg['col_widths'], L, wall, col_locked) or ge.auto_sizes(L, nx, wall)
            if ny != old_ny:
                rh = ge.auto_sizes(W, ny, wall); row_locked = [False] * ny
            else:
                rh = ge.rescale_free(cfg['row_heights'], W, wall, row_locked) or ge.auto_sizes(W, ny, wall)
            if cw is None or rh is None:
                self.grid_status.setText("⚠ Замалі розміри або зафіксовані комірки не влізають")
                return
            new_cfg = dict(cfg)
            new_cfg.update({'outer_L': L, 'outer_W': W, 'outer_H': H, 'nx': nx, 'ny': ny,
                            'wall': wall, 'floor_t': floor, 'segment': seg, 'joint': joint,
                            'bed_x': bed_x, 'bed_y': bed_y, 'cut_x': cut_x, 'cut_y': cut_y,
                            'col_widths': cw, 'row_heights': rh,
                            'col_locked': col_locked, 'row_locked': row_locked})
            ok, msg = ge.validate(new_cfg)
            if not ok:
                self.grid_status.setText("⚠ " + msg)
                return
            self.placed_items[idx]['grid_config'] = new_cfg
            self.placed_items[idx]['name'] = f"Сітка {nx}x{ny}"
            self.placed_items[idx]['data'] = ge.summary_data(new_cfg)
            if idx < self.placed_list.count():
                self.placed_list.item(idx).setText(self.placed_items[idx]['name'])
        self._active_grid_idx_val = idx
        self._refresh_after_grid_change(idx)

    def _refresh_after_grid_change(self, idx):
        cfg = self.placed_items[idx]["grid_config"]
        info = ge.layout_info(cfg)
        ft = cfg.get("floor_t", 0) or 0
        self.grid_status.setText(
            f"✅ {info['nx']}×{info['ny']} ячейок · {info['n_modules']} шматок(ів) на друк · "
            f"{info['outer_L']:.0f}×{info['outer_W']:.0f}×{cfg['outer_H']:.0f} мм"
            + (f" · дно {ft:.1f}мм" if ft else " · без дна"))
        self._sync_cell_size_field()
        self.mark_dirty()
        if hasattr(self, 'update_all_views'):
            self.update_all_views()

    # ──────────────────── cell editing (lock-aware) ────────────────────
    def _sync_cell_size_field(self):
        """Оновлює блок 'Редактор комірки' з поточної редагованої комірки."""
        tgt = getattr(self, '_editing_cell', None)
        if not tgt or not hasattr(self, 'cell_w_spin'):
            return
        gi, c, r = tgt
        if gi >= len(self.placed_items):
            return
        cfg = self.placed_items[gi].get('grid_config')
        if not cfg:
            return
        cw = cfg.get('col_widths', []); rh = cfg.get('row_heights', [])
        cl = cfg.get('col_locked', []); rl = cfg.get('row_locked', [])
        if c >= len(cw) or r >= len(rh):
            return
        inner_h = cfg.get('outer_H', 0) - (cfg.get('floor_t', 0) or 0)
        for wgt in (self.cell_w_spin, self.cell_h_spin, self.cell_w_lock, self.cell_h_lock):
            wgt.blockSignals(True)
        sel = getattr(self, '_selected_cells', None)
        if sel and getattr(self, '_sel_grid_idx', None) == gi and len(sel) > 1:
            cols = sorted({cc for cc, rr in sel}); rows = sorted({rr for cc, rr in sel})
            self.cell_label.setText(f"Вибрано {len(sel)} комірок · стовпці {cols} · ряди {rows}\n"
                                    f"Ширина → усім стовпцям, Глибина → усім рядам")
        else:
            self.cell_label.setText(f"Комірка [стовп. {c}, ряд {r}]   ·   В = {inner_h:.0f} мм")
        self.cell_w_spin.setValue(cw[c]); self.cell_h_spin.setValue(rh[r])
        self.cell_w_lock.setChecked(c < len(cl) and bool(cl[c]))
        self.cell_h_lock.setChecked(r < len(rl) and bool(rl[r]))
        for wgt in (self.cell_w_spin, self.cell_h_spin, self.cell_w_lock, self.cell_h_lock):
            wgt.blockSignals(False)

    def _editing_target(self):
        tgt = getattr(self, '_editing_cell', None)
        if tgt:
            return tgt
        idx = self._active_grid_idx()
        return (idx, 0, 0) if idx is not None else None

    def _on_cell_w_edited(self):
        tgt = self._editing_target()
        if tgt:
            self._apply_cell_size(tgt[0], tgt[1], tgt[2], self.cell_w_spin.value(), None)

    def _on_cell_h_edited(self):
        tgt = self._editing_target()
        if tgt:
            self._apply_cell_size(tgt[0], tgt[1], tgt[2], None, self.cell_h_spin.value())

    def _on_cell_lock(self, axis, val):
        tgt = self._editing_target()
        if tgt:
            self.set_grid_lock(tgt[0], axis, tgt[1] if axis == 'x' else tgt[2], val)

    def _grid_hint(self, msg):
        if hasattr(self, 'grid_status'):
            self.grid_status.setText(msg)
        try:
            self.statusBar().showMessage(msg, 4500)
        except Exception:
            pass

    def _apply_cell_size(self, placed_idx, c, r, new_w, new_h):
        """Маршрутизує правку: один або кілька (Ctrl-вибір) комірок."""
        sel = getattr(self, '_selected_cells', None)
        if sel and getattr(self, '_sel_grid_idx', None) == placed_idx and len(sel) > 1:
            cols = sorted({cc for cc, rr in sel}) if new_w is not None else None
            rows = sorted({rr for cc, rr in sel}) if new_h is not None else None
            self.set_grid_cells(placed_idx, cols=cols, rows=rows, new_w=new_w, new_h=new_h)
        else:
            self.set_grid_cell(placed_idx, c=c if new_w is not None else None,
                               r=r if new_h is not None else None, new_w=new_w, new_h=new_h)

    def set_grid_cell(self, placed_idx, c=None, r=None, new_w=None, new_h=None):
        """Задати розмір комірки з авто-фіксацією; решта вільних підлаштовується.
        Показує підказку, якщо немає вільних комірок підлаштувати."""
        if placed_idx >= len(self.placed_items):
            return
        cfg = self.placed_items[placed_idx]['grid_config']
        wall = cfg['wall']; info = ge.layout_info(cfg)
        hints = []
        changed = False
        if c is not None and new_w is not None:
            cl = cfg.setdefault('col_locked', [False] * len(cfg['col_widths']))
            while len(cl) < len(cfg['col_widths']):
                cl.append(False)
            free = [i for i in range(len(cfg['col_widths'])) if not cl[i] and i != c]
            cfg['col_widths'] = ge.redistribute_locked(cfg['col_widths'], c, new_w,
                                                        info['outer_L'], wall, cl)
            if not free:
                hints.append("ширину")
            elif abs(cfg['col_widths'][c] - new_w) > 1.0:
                hints.append("ширину (сусіди на мінімумі)")
            if 0 <= c < len(cl):
                cl[c] = True
            changed = True
        if r is not None and new_h is not None:
            rl = cfg.setdefault('row_locked', [False] * len(cfg['row_heights']))
            while len(rl) < len(cfg['row_heights']):
                rl.append(False)
            free = [i for i in range(len(cfg['row_heights'])) if not rl[i] and i != r]
            cfg['row_heights'] = ge.redistribute_locked(cfg['row_heights'], r, new_h,
                                                         info['outer_W'], wall, rl)
            if not free:
                hints.append("глибину")
            elif abs(cfg['row_heights'][r] - new_h) > 1.0:
                hints.append("глибину (сусіди на мінімумі)")
            if 0 <= r < len(rl):
                rl[r] = True
            changed = True
        if changed:
            self.placed_items[placed_idx]['data'] = ge.summary_data(cfg)
            self._active_grid_idx_val = placed_idx
            self._refresh_after_grid_change(placed_idx)
            if hints:
                self._grid_hint("⚠ Нема вільних комірок підлаштувати " + ", ".join(hints)
                                + " — розблокуйте сусідні (🔒) або змініть зовн. розмір.")

    def set_grid_cells(self, placed_idx, cols=None, rows=None, new_w=None, new_h=None):
        """Задати один розмір кільком стовпцям/рядам одночасно (Ctrl-вибір)."""
        if placed_idx >= len(self.placed_items):
            return
        cfg = self.placed_items[placed_idx]['grid_config']
        wall = cfg['wall']; info = ge.layout_info(cfg)
        if cols and new_w is not None:
            cl = cfg.setdefault('col_locked', [False] * len(cfg['col_widths']))
            while len(cl) < len(cfg['col_widths']):
                cl.append(False)
            tgt = {cc: new_w for cc in cols if 0 <= cc < len(cfg['col_widths'])}
            cfg['col_widths'] = ge.redistribute_locked_multi(cfg['col_widths'], tgt,
                                                             info['outer_L'], wall, cl)
            for cc in tgt:
                cl[cc] = True
        if rows and new_h is not None:
            rl = cfg.setdefault('row_locked', [False] * len(cfg['row_heights']))
            while len(rl) < len(cfg['row_heights']):
                rl.append(False)
            tgt = {rr: new_h for rr in rows if 0 <= rr < len(cfg['row_heights'])}
            cfg['row_heights'] = ge.redistribute_locked_multi(cfg['row_heights'], tgt,
                                                             info['outer_W'], wall, rl)
            for rr in tgt:
                rl[rr] = True
        self.placed_items[placed_idx]['data'] = ge.summary_data(cfg)
        self._active_grid_idx_val = placed_idx
        self._refresh_after_grid_change(placed_idx)

    def add_grid_split(self, placed_idx, axis, index, ratio=0.5):
        """Додати розріз: розділити стовпець/ряд index на два."""
        if placed_idx >= len(self.placed_items):
            return
        cfg = self.placed_items[placed_idx]['grid_config']
        if axis == 'x':
            sizes, locked, ok = ge.add_split(cfg['col_widths'], cfg.get('col_locked', []), index, ratio)
            if not ok:
                self._grid_hint("⚠ Комірка завузька, щоб її розділити."); return
            cfg['col_widths'] = sizes; cfg['col_locked'] = locked
        else:
            sizes, locked, ok = ge.add_split(cfg['row_heights'], cfg.get('row_locked', []), index, ratio)
            if not ok:
                self._grid_hint("⚠ Комірка занизька, щоб її розділити."); return
            cfg['row_heights'] = sizes; cfg['row_locked'] = locked
        self._after_structure_change(placed_idx, cfg)

    def remove_grid_line(self, placed_idx, axis, index):
        """Видалити стовпець/ряд index (його розмір додається до сусіда)."""
        if placed_idx >= len(self.placed_items):
            return
        cfg = self.placed_items[placed_idx]['grid_config']
        if axis == 'x':
            sizes, locked, ok = ge.remove_line(cfg['col_widths'], cfg.get('col_locked', []), index)
            if not ok:
                self._grid_hint("⚠ Не можна видалити останній стовпець."); return
            cfg['col_widths'] = sizes; cfg['col_locked'] = locked
        else:
            sizes, locked, ok = ge.remove_line(cfg['row_heights'], cfg.get('row_locked', []), index)
            if not ok:
                self._grid_hint("⚠ Не можна видалити останній ряд."); return
            cfg['row_heights'] = sizes; cfg['row_locked'] = locked
        self._after_structure_change(placed_idx, cfg)

    def _after_structure_change(self, placed_idx, cfg):
        cfg['nx'] = len(cfg['col_widths']); cfg['ny'] = len(cfg['row_heights'])
        self.placed_items[placed_idx]['data'] = ge.summary_data(cfg)
        self.placed_items[placed_idx]['name'] = f"Сітка {cfg['nx']}x{cfg['ny']}"
        if placed_idx < self.placed_list.count():
            self.placed_list.item(placed_idx).setText(self.placed_items[placed_idx]['name'])
        self._active_grid_idx_val = placed_idx
        self.clear_cell_selection()
        self._refresh_after_grid_change(placed_idx)
        self._sync_panel_from_grid(placed_idx)

    def toggle_cell_selection(self, placed_idx, c, r):
        if getattr(self, '_sel_grid_idx', None) != placed_idx:
            self._selected_cells = set()
        self._sel_grid_idx = placed_idx
        if not hasattr(self, '_selected_cells'):
            self._selected_cells = set()
        key = (c, r)
        if key in self._selected_cells:
            self._selected_cells.discard(key)
        else:
            self._selected_cells.add(key)
        self._active_grid_idx_val = placed_idx
        self._editing_cell = (placed_idx, c, r)
        if hasattr(self, 'cell_box'):
            self.cell_box.setVisible(True)
            try:
                if not self.cell_box.toggle_button.isChecked():
                    self.cell_box.toggle_button.click()
            except Exception:
                pass
        self._sync_cell_size_field()
        if hasattr(self, 'update_puzzle_view'):
            self.update_puzzle_view()

    def clear_cell_selection(self):
        if getattr(self, '_selected_cells', None):
            self._selected_cells = set()
            if hasattr(self, 'update_puzzle_view'):
                self.update_puzzle_view()

    def set_grid_lock(self, placed_idx, axis, index, locked):
        if placed_idx >= len(self.placed_items):
            return
        cfg = self.placed_items[placed_idx]['grid_config']
        key = 'col_locked' if axis == 'x' else 'row_locked'
        n = len(cfg['col_widths'] if axis == 'x' else cfg['row_heights'])
        arr = cfg.setdefault(key, [False] * n)
        while len(arr) < n:
            arr.append(False)
        if 0 <= index < n:
            arr[index] = bool(locked)
        self.placed_items[placed_idx]['data'] = ge.summary_data(cfg)
        self._refresh_after_grid_change(placed_idx)

    def unlock_all_cells(self):
        idx = self._active_grid_idx()
        if idx is None:
            return
        cfg = self.placed_items[idx]['grid_config']
        cfg['col_locked'] = [False] * len(cfg['col_widths'])
        cfg['row_locked'] = [False] * len(cfg['row_heights'])
        self._refresh_after_grid_change(idx)

    def open_grid_cell_editor(self, placed_idx, col=None, row=None):
        """2-клік по комірці: запам'ятати комірку, розгорнути блок, заповнити поля."""
        c = col if col is not None else 0
        r = row if row is not None else 0
        self._active_grid_idx_val = placed_idx
        self._editing_cell = (placed_idx, c, r)
        if hasattr(self, 'placed_list') and placed_idx < self.placed_list.count():
            self.placed_list.setCurrentRow(placed_idx)
        if hasattr(self, 'cell_box'):
            self.cell_box.setVisible(True)
            try:
                if not self.cell_box.toggle_button.isChecked():
                    self.cell_box.toggle_button.click()
            except Exception:
                pass
            if hasattr(self, 'scroll_area'):
                try:
                    self.scroll_area.ensureWidgetVisible(self.cell_box)
                except Exception:
                    pass
        self._sync_cell_size_field()

    def _open_inline_cell_editor(self, placed_idx, c, r, item):
        """Інлайн 'Ширина × Глибина' прямо поверх комірки (фіксований ×, Tab/Space)."""
        if placed_idx >= len(self.placed_items) or not hasattr(self, 'puzzle_canvas'):
            return
        cfg = self.placed_items[placed_idx]['grid_config']
        cw = cfg.get('col_widths', []); rh = cfg.get('row_heights', [])
        if c >= len(cw) or r >= len(rh):
            return
        info = ge.layout_info(cfg)
        s = item.SCALE
        ax, bx = info['cav_x'][c]; ay, by = info['cav_y'][r]
        oL = info['outer_L'] * s; oW = info['outer_W'] * s
        local = QRectF(-oL / 2 + ax * s, -oW / 2 + ay * s, (bx - ax) * s, (by - ay) * s)
        vrect = self.puzzle_canvas.mapFromScene(item.mapToScene(local)).boundingRect()
        if not hasattr(self, '_inline_editor'):
            self._inline_editor = InlineDimEditor(self.puzzle_canvas.viewport())
            self._inline_editor.committed.connect(self._on_inline_committed)
            self._inline_editor.cancelled.connect(self._inline_editor.hide)
        ed = self._inline_editor
        ed._target = (placed_idx, c, r)
        ed.set_values(cw[c], rh[r])
        ed.setToolTip("Ширина × Глибина (мм). Tab/Space — інше поле, Enter — застосувати")
        w = max(90, int(vrect.width())); h = 24
        ed.setGeometry(int(vrect.center().x() - w / 2), int(vrect.center().y() - h / 2), w, h)
        ed.show(); ed.raise_(); ed._focus_w()

    def _on_inline_committed(self, new_w, new_h):
        ed = getattr(self, '_inline_editor', None)
        if ed is None:
            return
        tgt = getattr(ed, '_target', None)
        ed.hide()
        if not tgt:
            return
        pidx, c, r = tgt
        if new_w is not None or new_h is not None:
            self._apply_cell_size(pidx, c, r, new_w, new_h)

    # ─────────────── перетягування стінки (з PuzzleGridItem) ───────────────
    def _grid_drag_status(self, cfg, axis, b):
        sizes = cfg['col_widths'] if axis == 'x' else cfg['row_heights']
        lbl = 'Стовпці' if axis == 'x' else 'Ряди'
        if hasattr(self, 'grid_status') and b + 1 < len(sizes):
            self.grid_status.setText(f"↔ {lbl} {b}↔{b+1}:  "
                                     f"{sizes[b]:.1f} / {sizes[b+1]:.1f} мм")

    def _finalize_grid_resize(self, placed_idx):
        if placed_idx >= len(self.placed_items):
            return
        cfg = self.placed_items[placed_idx]['grid_config']
        self.placed_items[placed_idx]['data'] = ge.summary_data(cfg)
        self._active_grid_idx_val = placed_idx
        self._sync_cell_size_field()
        self._refresh_after_grid_change(placed_idx)

    def _request_live_3d(self):
        """Throttled live-оновлення 3D під час перетягування (лише у спліт-режимі,
        щоб не вантажити залізо постійним перебудовуванням)."""
        if getattr(self, 'assem_submode', '') != 'split':
            return
        if not hasattr(self, '_live3d_timer'):
            self._live3d_timer = QTimer(self)
            self._live3d_timer.setSingleShot(True)
            self._live3d_timer.timeout.connect(self.generate_box)
        if not self._live3d_timer.isActive():
            self._live3d_timer.start(130)

    # ─────────────────────────── рендер-хук ───────────────────────────
    def _append_grid_item_meshes(self, item, items_with_colors):
        """Викликається з geometry._generate_assembly_from_params для type=='grid'."""
        cfg = item.get("grid_config")
        if not cfg:
            return
        try:
            mods = ge.build_modules(cfg)
        except Exception as e:
            print("grid build error:", e)
            return
        rot = item.get("rotation", 0)
        base = item.get("color_idx", 0)
        pal_len = len(getattr(self, 'assembly_palette', [0] * 8)) or 8
        ix, iy = item.get("x", 0.0), item.get("y", 0.0)
        for m in mods:
            mesh = m["mesh"]
            if mesh is None or len(mesh.faces) == 0:
                continue
            if rot:
                mesh.rotate_z(-rot)
            mesh.translate(ix, -iy, 0.0)
            items_with_colors.append((mesh, (base + m["color_idx"]) % pal_len))
