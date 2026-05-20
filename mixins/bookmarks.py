import os
import sys
import json
import shutil
import zipfile
import subprocess
import copy
import cadquery as cq

from PySide6.QtWidgets import (QTreeWidgetItem, QMessageBox, QInputDialog, QMenu, 
                               QFileDialog, QStyle, QColorDialog, QProgressDialog, 
                               QApplication, QDialog)
from PySide6.QtGui import QColor, QIcon, QPainter, QAction
from PySide6.QtCore import Qt

from ui_widgets import ExportFolderDialog

class BookmarksMixin:
    def get_preset_dict(self):
        return {
            "length": self.len_input.value(),
            "width": self.wid_input.value(),
            "height": self.hei_input.value(),
            "tab_base": self.tab_wbase_input.value(),
            "tab_tip": self.tab_wtip_input.value(),
            "tab_depth": self.tab_depth_input.value(),
            "clearance": self.tab_clearance_input.value(),
            "fillet": self.tab_fillet_input.value(),
            "side_top": self.side_top.currentIndex(),
            "side_bottom": self.side_bottom.currentIndex(),
            "side_left": self.side_left.currentIndex(),
            "side_right": self.side_right.currentIndex(),
            "side_top_count": self.side_top_count.value(),
            "side_bottom_count": self.side_bottom_count.value(),
            "side_left_count": self.side_left_count.value(),
            "side_right_count": self.side_right_count.value(),
            "gen_lid": self.generate_lid_cb.isChecked(),
            "lid_tol": self.lid_tolerance_input.value(),
            "lid_ext": self.lid_extrusion_input.value(),
            "lid_h": self.lid_height_input.value(),
            "bed_x": self.bed_x_input.value(),
            "bed_y": self.bed_y_input.value(),
            "exp_preset": self.preset_box.is_expanded(),
            "exp_dim": self.dim_box.is_expanded(),
            "exp_tab": self.tab_box.is_expanded(),
            "exp_sides": self.sides_box.is_expanded(),
            "exp_bed": self.bed_box.is_expanded(),
            "exp_lid": self.lid_box_coll.is_expanded(),
            "settings_pos": getattr(self, "settings_pos", "left"),
            "placed_items": copy.deepcopy(getattr(self, "placed_items", [])),
            "unplaced_items": copy.deepcopy(getattr(self, "unplaced_items", [])),
            "hide_labels": self.hide_labels_cb.isChecked() if hasattr(self, 'hide_labels_cb') else False,
            "collision_check": self.collision_cb.isChecked() if hasattr(self, 'collision_cb') else False
        }

    def set_preset_dict(self, data):
        def safe_set(widget, key, v_type=float):
            if key in data:
                try:
                    widget.setValue(v_type(data[key]))
                except: pass

        safe_set(self.len_input, "length")
        safe_set(self.wid_input, "width")
        safe_set(self.hei_input, "height")
        safe_set(self.tab_wbase_input, "tab_base")
        safe_set(self.tab_wtip_input, "tab_tip")
        safe_set(self.tab_depth_input, "tab_depth")
        safe_set(self.tab_clearance_input, "clearance")
        safe_set(self.tab_fillet_input, "fillet")
        
        if "side_top" in data: self.side_top.setCurrentIndex(int(data["side_top"]))
        if "side_bottom" in data: self.side_bottom.setCurrentIndex(int(data["side_bottom"]))
        if "side_left" in data: self.side_left.setCurrentIndex(int(data["side_left"]))
        if "side_right" in data: self.side_right.setCurrentIndex(int(data["side_right"]))
        
        safe_set(self.side_top_count, "side_top_count", int)
        safe_set(self.side_bottom_count, "side_bottom_count", int)
        safe_set(self.side_left_count, "side_left_count", int)
        safe_set(self.side_right_count, "side_right_count", int)

        if "gen_lid" in data:
            val = data["gen_lid"]
            if isinstance(val, str):
                bool_val = val.lower() == 'true'
            else:
                bool_val = bool(val)
            self.generate_lid_cb.setChecked(bool_val)

        if "lid_tol" in data: safe_set(self.lid_tolerance_input, "lid_tol")
        if "lid_ext" in data: safe_set(self.lid_extrusion_input, "lid_ext")
        if "lid_h" in data: safe_set(self.lid_height_input, "lid_h")
        if "bed_x" in data: safe_set(self.bed_x_input, "bed_x")
        if "bed_y" in data: safe_set(self.bed_y_input, "bed_y")
        
        def to_bool(v):
            if isinstance(v, bool): return v
            return str(v).lower() == 'true'

        if "exp_preset" in data: self.preset_box.set_expanded(to_bool(data["exp_preset"]))
        if "exp_dim" in data: self.dim_box.set_expanded(to_bool(data["exp_dim"]))
        if "exp_tab" in data: self.tab_box.set_expanded(to_bool(data["exp_tab"]))
        if "exp_sides" in data: self.sides_box.set_expanded(to_bool(data["exp_sides"]))
        if "exp_bed" in data: self.bed_box.set_expanded(to_bool(data["exp_bed"]))
        if "exp_lid" in data: self.lid_box_coll.set_expanded(to_bool(data["exp_lid"]))
        
        if "settings_pos" in data:
            self.settings_pos = str(data["settings_pos"])
            self.apply_ui_layout()
            
        if "placed_items" in data:
            raw = data["placed_items"]
            if isinstance(raw, list):
                self.placed_items = copy.deepcopy(raw)
            else:
                self.placed_items = []
            if hasattr(self, "placed_list"):
                self.placed_list.clear()
                for item in self.placed_items:
                    if isinstance(item, dict) and "name" in item:
                        self.placed_list.addItem(item["name"])
        
        if "unplaced_items" in data:
            raw = data["unplaced_items"]
            if isinstance(raw, list):
                self.unplaced_items = copy.deepcopy(raw)
            else:
                self.unplaced_items = []
            if hasattr(self, "unplaced_list"):
                self.unplaced_list.clear()
                for item in self.unplaced_items:
                    if isinstance(item, dict) and "name" in item:
                        self.unplaced_list.addItem(item["name"])

                    
        if "hide_labels" in data:
            val = to_bool(data["hide_labels"])
            if hasattr(self, 'hide_labels_cb'):
                self.hide_labels_cb.setChecked(val)
                
        if "collision_check" in data:
            val = to_bool(data["collision_check"])
            if hasattr(self, 'collision_cb'):
                self.collision_cb.setChecked(val)

        if hasattr(self, "update_adaptive_grid"):
            self.update_adaptive_grid()
        if hasattr(self, "update_assembly_ui_state"):
            self.update_assembly_ui_state()
        if hasattr(self, "update_puzzle_view") and getattr(self, "assem_submode", "puzzle") == "puzzle":
            self.update_puzzle_view()
        
        self.update_grid()

    def refresh_bookmarks(self):
        self.bookmarks_tree.blockSignals(True)
        try:
            self.bookmarks_tree.clear()
            self._populate_tree(self.presets_dir, self.bookmarks_tree.invisibleRootItem())
            if self.search_input.text():
                self.filter_bookmarks(self.search_input.text())
        finally:
            self.bookmarks_tree.blockSignals(False)

    def get_colored_folder_icon(self, color_hex):
        base_icon = self.style().standardIcon(QStyle.SP_DirIcon)
        if not color_hex:
            return base_icon
            
        try:
            color = QColor(color_hex)
            pixmap = base_icon.pixmap(24, 24)
            painter = QPainter(pixmap)
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), color)
            painter.end()
            return QIcon(pixmap)
        except:
            return base_icon

    def _populate_tree(self, path, parent_item):
        if not os.path.exists(path): return
        items = os.listdir(path)
        items.sort()
        
        for name in items:
            if name.startswith('.'): continue
            full_path = os.path.join(path, name)
            if os.path.isdir(full_path):
                color_file = os.path.join(full_path, ".folder_color")
                icon_color = None
                if os.path.exists(color_file):
                    try:
                        with open(color_file, 'r') as f:
                            icon_color = f.read().strip()
                    except: pass

                folder_item = QTreeWidgetItem(parent_item, [name])
                folder_item.setIcon(0, self.get_colored_folder_icon(icon_color))
                folder_item.setData(0, Qt.UserRole, full_path)
                self._populate_tree(full_path, folder_item)
        
        for name in items:
            full_path = os.path.join(path, name)
            if os.path.isfile(full_path) and name.endswith(".json"):
                file_item = QTreeWidgetItem(parent_item, [name.replace(".json", "")])
                file_item.setIcon(0, self.style().standardIcon(QStyle.SP_FileIcon))
                file_item.setData(0, Qt.UserRole, full_path)
                
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    if "placed_items" in data:
                        tt = f"Збірка: {len(data['placed_items'])} об'єктів"
                    else:
                        L = data.get("length", 0)
                        W = data.get("width", 0)
                        H = data.get("height", 0)
                        tt = f"Розміри: {L}x{W}x{H} мм"
                        if data.get("gen_lid"): tt += "\nЗ кришкою"
                    file_item.setToolTip(0, tt)
                except:
                    pass

    def on_bookmark_clicked(self, item, column):
        path = item.data(0, Qt.UserRole)
        is_assembly = hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()
        
        if is_assembly:
            if os.path.isdir(path):
                self.populate_toolbox(path)
            elif os.path.isfile(path) and path.endswith(".json"):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if "placed_items" in data and len(data["placed_items"]) > 0:
                        self.placed_items = data.get("placed_items", [])
                        self.unplaced_items = data.get("unplaced_items", [])
                        self.placed_list.clear()
                        for p in self.placed_items: self.placed_list.addItem(p["name"])
                        self.unplaced_list.clear()
                        for u in self.unplaced_items: self.unplaced_list.addItem(u["name"])
                        self.mark_dirty()
                        self.update_adaptive_grid()
                        self.update_assembly_ui_state()
                        if getattr(self, 'assem_submode', 'puzzle') == 'puzzle':
                            if hasattr(self, 'update_puzzle_view'):
                                self.update_puzzle_view()
                        else:
                            self.generate_box()
                    else:
                        item_name = os.path.basename(path).replace(".json", "")
                        new_item = {
                            "name": item_name,
                            "data": data,
                            "x": 0.0,
                            "y": 0.0,
                            "rotation": 0,
                            "color_idx": len(getattr(self, 'placed_items', [])) % len(getattr(self, 'assembly_palette', ['#ff0000']))
                        }
                        self.placed_items.append(new_item)
                        self.placed_list.addItem(item_name)
                        self.generate_box()
                        self.update_assembly_ui_state()
                except Exception as e:
                    QMessageBox.warning(self, "Помилка", f"Не вдалося завантажити:\n{e}")
        else:
            if os.path.isfile(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    self.set_preset_dict(data)
                    self.generate_box()
                except Exception as e:
                    QMessageBox.critical(self, "Помилка", f"Не вдалося завантажити закладку:\n{str(e)}")

    def save_as_bookmark(self):
        selected = self.bookmarks_tree.currentItem()
        target_dir = self.presets_dir
        if selected:
            data_path = selected.data(0, Qt.UserRole)
            if os.path.isdir(data_path):
                target_dir = data_path
            else:
                target_dir = os.path.dirname(data_path)
        
        is_assembly = hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()
        title = "Нова збірка" if is_assembly else "Нова закладка"
        name, ok = QInputDialog.getText(self, title, "Введіть назву:")
        if ok and name:
            filename = name if name.endswith(".json") else name + ".json"
            full_path = os.path.join(target_dir, filename)
            
            if os.path.exists(full_path):
                confirm = QMessageBox.question(self, "Перезапис", f"'{name}' вже існує. Перезаписати існуючу?", 
                                               QMessageBox.Yes | QMessageBox.No)
                if confirm != QMessageBox.Yes:
                    return

            if is_assembly:
                self.save_assembly_to_path(full_path)
            else:
                try:
                    with open(full_path, 'w', encoding='utf-8') as f:
                        json.dump(self.get_preset_dict(), f, indent=4)
                    self.refresh_bookmarks()
                except Exception as e:
                    QMessageBox.critical(self, "Помилка", f"Не вдалося зберегти:\n{e}")

    def create_preset_folder(self):
        selected = self.bookmarks_tree.currentItem()
        target_dir = self.presets_dir
        if selected:
            data_path = selected.data(0, Qt.UserRole)
            if os.path.isdir(data_path):
                target_dir = data_path
            else:
                target_dir = os.path.dirname(data_path)
        
        name, ok = QInputDialog.getText(self, "Нова папка", "Назва папки:")
        if ok and name:
            full_path = os.path.join(target_dir, name)
            try:
                if not os.path.exists(full_path):
                    os.makedirs(full_path)
                self.refresh_bookmarks()
            except Exception as e:
                QMessageBox.critical(self, "Помилка", f"Не вдалося створити папку:\n{e}")

    def overwrite_selected_bookmark(self):
        item = self.bookmarks_tree.currentItem()
        if not item:
            QMessageBox.warning(self, "Помилка", "Будь ласка, спочатку оберіть закладку (файл .json) у списку.")
            return
            
        target_path = item.data(0, Qt.UserRole)
        if not os.path.isfile(target_path) or not target_path.endswith(".json"):
            QMessageBox.warning(self, "Помилка", "Оберіть саме файл закладки для заміни.")
            return

        name = item.text(0)
        is_assembly = hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()
        msg = f"Ви впевнені, що хочете перезаписати '{name}' поточними параметрами?"
        if is_assembly: msg = f"Ви впевнені, що хочете перезаписати збірку '{name}'?"
        
        confirm = QMessageBox.question(self, "Замінити", msg, QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            if is_assembly:
                self.save_assembly_to_path(target_path)
            else:
                try:
                    with open(target_path, 'w', encoding='utf-8') as f:
                        json.dump(self.get_preset_dict(), f, indent=4)
                    QMessageBox.information(self, "Успіх", f"Закладку '{name}' успішно оновлено.")
                except Exception as e:
                    QMessageBox.critical(self, "Помилка", f"Не вдалося оновити:\n{e}")

    def show_bookmarks_context_menu(self, pos):
        item = self.bookmarks_tree.itemAt(pos)
        target_path = item.data(0, Qt.UserRole) if item else self.presets_dir
        is_file = os.path.isfile(target_path) if item else False
        is_dir = os.path.isdir(target_path) if item else True

        menu = QMenu()
        
        new_bookmark_act = QAction(" Зберегти нову закладку сюди", self)
        new_bookmark_act.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        new_folder_act = QAction(" Створити папку тут", self)
        new_folder_act.setIcon(self.style().standardIcon(QStyle.SP_DirIcon))
        
        save_assem_here_act = None
        is_assem_mode = hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()

        if is_assem_mode and is_dir:
            save_assem_here_act = QAction(" Зберегти ПОТОЧНУ збірку сюди", self)
            save_assem_here_act.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
            menu.addAction(save_assem_here_act)
            menu.addSeparator()

        update_action = None
        rename_action = None
        delete_action = None
        copy_action = None
        color_action = None
        export_all_stl_act = None
        export_all_step_act = None
        
        if item:
            if is_file:
                update_action = QAction(" Перезаписати поточними параметрами", self)
                update_action.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
                menu.addAction(update_action)
                menu.addSeparator()
            
            if is_dir:
                color_action = QAction(" Колір папки", self)
                color_action.setIcon(self.style().standardIcon(QStyle.SP_FileDialogContentsView))
                menu.addAction(color_action)
                
                export_all_stl_act = QAction(" Експортувати все у STL", self)
                export_all_stl_act.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
                menu.addAction(export_all_stl_act)
                
                export_all_step_act = QAction(" Експортувати все у STEP", self)
                export_all_step_act.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
                menu.addAction(export_all_step_act)
 
            copy_action = QAction(" Копіювати", self)
            copy_action.setIcon(self.style().standardIcon(QStyle.SP_FileDialogContentsView))
            rename_action = QAction(" Перейменувати", self)
            rename_action.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
            delete_action = QAction(" Видалити", self)
            delete_action.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
            
            menu.addAction(copy_action)
            menu.addAction(rename_action)
            menu.addAction(delete_action)
            menu.addSeparator()

        menu.addAction(new_bookmark_act)
        menu.addAction(new_folder_act)
        
        action = menu.exec(self.bookmarks_tree.viewport().mapToGlobal(pos))
        if not action: return

        if action == update_action:
            is_assembly = hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()
            if is_assembly:
                self.save_assembly_to_path(target_path)
            else:
                try:
                    with open(target_path, 'w', encoding='utf-8') as f:
                        json.dump(self.get_preset_dict(), f, indent=4)
                    QMessageBox.information(self, "Успіх", f"Закладку '{item.text(0)}' успішно оновлено.")
                except Exception as e:
                    QMessageBox.warning(self, "Помилка", f"Не вдалося оновити:\n{e}")

        elif action == save_assem_here_act:
            name, ok = QInputDialog.getText(self, "Нова збірка", "Назва збірки:")
            if ok and name:
                filename = name if name.endswith(".json") else name + ".json"
                full_path = os.path.join(target_path, filename)
                self.save_assembly_to_path(full_path)

        elif action == color_action:
            color_file = os.path.join(target_path, ".folder_color")
            current_color = "#ffffff"
            if os.path.exists(color_file):
                try:
                    with open(color_file, 'r') as f: current_color = f.read().strip()
                except: pass
            
            color = QColorDialog.getColor(QColor(current_color), self, f"Колір для '{item.text(0)}'")
            if color.isValid():
                try:
                    with open(color_file, 'w') as f:
                        f.write(color.name())
                    self.refresh_bookmarks()
                except Exception as e:
                    QMessageBox.warning(self, "Помилка", f"Не вдалося зберегти колір:\n{e}")

        elif action == new_bookmark_act:
            self.save_as_bookmark()
            
        elif action == new_folder_act:
            self.create_preset_folder()

        elif action == rename_action:
            new_name, ok = QInputDialog.getText(self, "Перейменування", "Нова назва:", text=item.text(0))
            if ok and new_name:
                parent_dir = os.path.dirname(target_path)
                suffix = ".json" if os.path.isfile(target_path) else ""
                new_path = os.path.join(parent_dir, new_name + suffix)
                try:
                    os.rename(target_path, new_path)
                    self.refresh_bookmarks()
                except Exception as e:
                    QMessageBox.warning(self, "Помилка", f"Не вдалося перейменувати:\n{e}")

        elif action == copy_action:
            parent_dir = os.path.dirname(target_path)
            base_name = os.path.basename(target_path)
            if is_file:
                name_part = base_name.replace(".json", "")
                suffix = ".json"
            else:
                name_part = base_name
                suffix = ""
            
            new_name = f"{name_part}_copy"
            new_path = os.path.join(parent_dir, new_name + suffix)
            
            counter = 2
            while os.path.exists(new_path):
                new_path = os.path.join(parent_dir, f"{name_part}_copy_{counter}{suffix}")
                counter += 1
            
            try:
                if is_file:
                    shutil.copy2(target_path, new_path)
                else:
                    shutil.copytree(target_path, new_path)
                self.refresh_bookmarks()
            except Exception as e:
                QMessageBox.warning(self, "Помилка", f"Не вдалося скопіювати:\n{e}")
        
        elif action == delete_action:
            confirm = QMessageBox.question(self, "Видалення", f"Ви впевнені, що хочете видалити '{item.text(0)}'?", 
                                           QMessageBox.Yes | QMessageBox.No)
            if confirm == QMessageBox.Yes:
                try:
                    if os.path.isdir(target_path):
                        shutil.rmtree(target_path)
                    else:
                        os.remove(target_path)
                    self.refresh_bookmarks()
                except Exception as e:
                    QMessageBox.warning(self, "Помилка видалення:\n{e}")
        
        elif action == export_all_stl_act:
            self.export_folder_bookmarks(target_path, "stl")
        elif action == export_all_step_act:
            self.export_folder_bookmarks(target_path, "step")

    def undo(self):
        if not self.undo_stack:
            self.statusBar().showMessage("Немає дій для скасування", 2000)
            return
        
        self.redo_stack.append(self.get_preset_dict())
        
        state = self.undo_stack.pop()
        self._apply_history_state(state)
        self.statusBar().showMessage("Скасовано (Undo)", 2000)

    def redo(self):
        if not self.redo_stack:
            self.statusBar().showMessage("Немає дій для повтору", 2000)
            return
            
        self.undo_stack.append(self.get_preset_dict())
        
        state = self.redo_stack.pop()
        self._apply_history_state(state)
        self.statusBar().showMessage("Повторено (Redo)", 2000)

    def _apply_history_state(self, state):
        self._suppress_history = True
        try:
            self.set_preset_dict(state)
            self.generate_box()
            self.last_state = state
        finally:
            self._suppress_history = False

    def filter_bookmarks(self, text):
        text = text.lower()
        
        def filter_item(item):
            item_text = item.text(0).lower()
            matches = text in item_text
            
            any_child_matches = False
            for i in range(item.childCount()):
                if filter_item(item.child(i)):
                    any_child_matches = True
            
            should_show = matches or any_child_matches
            item.setHidden(not should_show)
            if matches and text:
                p = item.parent()
                while p:
                    p.setExpanded(True)
                    p = p.parent()
            return should_show

        root = self.bookmarks_tree.invisibleRootItem()
        for i in range(root.childCount()):
            filter_item(root.child(i))

    def export_folder_bookmarks(self, folder_path, fmt):
        json_files = sorted([f for f in os.listdir(folder_path) if f.endswith(".json")])
        if not json_files:
            QMessageBox.information(self, "Інфо", "У цій папці немає закладок (.json)")
            return

        dlg = ExportFolderDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        settings = dlg.get_settings()

        if settings["zip"]:
            export_dest, _ = QFileDialog.getSaveFileName(self, "Зберегти ZIP", folder_path + ".zip", "ZIP Files (*.zip)")
            if not export_dest: return
            output_dir = os.path.join(os.path.dirname(export_dest), "_tmp_export_" + str(os.getpid()))
            if os.path.exists(output_dir): shutil.rmtree(output_dir)
            os.makedirs(output_dir)
        else:
            output_dir = QFileDialog.getExistingDirectory(self, "Оберіть папку для експорту")
            if not output_dir: return
            export_dest = output_dir

        current_data = self.get_preset_dict()
        current_mode_is_assem = hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()
        old_placed = list(getattr(self, 'placed_items', []))
        old_unplaced = list(getattr(self, 'unplaced_items', []))

        count = 0
        errors = []
        all_shapes_to_combine = []
        
        progress = QProgressDialog("Експорт закладок...", "Скасувати", 0, len(json_files), self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for i, filename in enumerate(json_files):
                if progress.wasCanceled(): break
                
                progress.setValue(i)
                progress.setLabelText(f"Обробка {filename}...")
                QApplication.processEvents()
                
                full_path = os.path.join(folder_path, filename)
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    is_assem_data = "placed_items" in data
                    if is_assem_data:
                        if hasattr(self, 'mode_assem_btn'): self.mode_assem_btn.setChecked(True)
                        self.placed_items = data.get("placed_items", [])
                        self.unplaced_items = data.get("unplaced_items", [])
                        shape = self.generate_assembly_geometry()
                    else:
                        if hasattr(self, 'mode_assem_btn'): self.mode_assem_btn.setChecked(False)
                        self.set_preset_dict(data)
                        shape = self.generate_geometry()
                    
                    if shape:
                        if is_assem_data and isinstance(shape, list):
                            objs = [s[0].val() if hasattr(s[0], 'val') else s[0] for s in shape]
                            final_shape = cq.Compound.makeCompound(objs) if objs else None
                        else:
                            final_shape = shape.val() if hasattr(shape, "val") else shape
                        
                        if final_shape:
                            if settings["combine"]:
                                all_shapes_to_combine.append(final_shape)
                            else:
                                out_name = filename.replace(".json", "." + fmt)
                                cq.exporters.export(final_shape, os.path.join(output_dir, out_name), fmt.upper())
                            count += 1
                except Exception as e:
                    errors.append(f"{filename}: {str(e)}")
            
            if settings["combine"] and all_shapes_to_combine:
                progress.setLabelText("Об'єднання та фінальний експорт...")
                combined = cq.Compound.makeCompound(all_shapes_to_combine)
                base_name = os.path.basename(folder_path) or "export"
                cq.exporters.export(combined, os.path.join(output_dir, f"{base_name}.{fmt}"), fmt.upper())

            if settings["zip"]:
                progress.setLabelText("Створення ZIP-архіву...")
                with zipfile.ZipFile(export_dest, 'w', zipfile.ZIP_DEFLATED) as z:
                    for root, dirs, files in os.walk(output_dir):
                        for f in files:
                            z.write(os.path.join(root, f), f)
                shutil.rmtree(output_dir)

            progress.setValue(len(json_files))
        finally:
            QApplication.restoreOverrideCursor()
            if hasattr(self, 'mode_assem_btn'): 
                self.mode_assem_btn.setChecked(current_mode_is_assem)
            self.placed_items = old_placed
            self.unplaced_items = old_unplaced
            self.set_preset_dict(current_data)
            self.generate_box()
        
        finish_msg = f"Оброблено {count} файлів."
        if settings["zip"]: finish_msg += f"\nАрхів збережено: {export_dest}"
        if errors: finish_msg += "\n\nПомилки:\n" + "\n".join(errors[:10])
        QMessageBox.information(self, "Експорт завершено", finish_msg)

    def open_presets_folder(self):
        try:
            if sys.platform == 'win32':
                os.startfile(self.presets_dir)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', self.presets_dir])
            else:
                subprocess.Popen(['xdg-open', self.presets_dir])
        except Exception as e:
            QMessageBox.warning(self, "Помилка", f"Не вдалося відкрити папку:\n{e}")

    def export_library_zip(self):
        path, _ = QFileDialog.getSaveFileName(self, "Експорт бібліотеки", "presets_backup.zip", "ZIP Files (*.zip)")
        if not path: return
        
        try:
            with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(self.presets_dir):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, self.presets_dir)
                        zipf.write(full_path, rel_path)
            QMessageBox.information(self, "Успіх", f"Бібліотеку успішно експортовано у {path}")
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося експортувати ZIP:\n{e}")

    def import_library_zip(self):
        path, _ = QFileDialog.getOpenFileName(self, "Імпорт бібліотеки", "", "ZIP Files (*.zip)")
        if not path: return
        
        confirm = QMessageBox.question(self, "Імпорт", 
                                       "Ви хочете ЗАМІНИТИ поточну бібліотеку (Yes) чи ДОДАТИ нові файли (No)?",
                                       QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        
        if confirm == QMessageBox.Cancel: return
        
        try:
            if confirm == QMessageBox.Yes:
                for item in os.listdir(self.presets_dir):
                    p = os.path.join(self.presets_dir, item)
                    if os.path.isdir(p): shutil.rmtree(p)
                    else: os.remove(p)
            
            with zipfile.ZipFile(path, 'r') as zipf:
                zipf.extractall(self.presets_dir)
            
            self.refresh_bookmarks()
            QMessageBox.information(self, "Успіх", "Бібліотеку успішно імпортовано.")
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося імпортувати ZIP:\n{e}")
