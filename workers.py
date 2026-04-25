"""
workers.py — Фонові QThread-воркери для важких CadQuery-обчислень.

Перенос tessellate та generate_geometry із UI-потоку у фоновий потік
дозволяє інтерфейсу залишатися чуйним під час генерації 3D-моделей.
"""

import hashlib
import numpy as np
from PySide6.QtCore import QThread, Signal


# ---------------------------------------------------------------------------
# GeometryWorker — виконує CadQuery-обчислення у фоновому потоці
# ---------------------------------------------------------------------------

class GeometryWorker(QThread):
    """
    Фоновий воркер для генерації 3D-геометрії та тесселяції.

    Сигнали:
        result_ready(verts_np, faces_np, colors_np, edge_pts_np, is_assembly)
            — випускається, коли mesh-дані готові до відображення
        error_occurred(str)
            — випускається при виникненні виключення під час обчислень
        started_work()
            — випускається одразу при старті (для показу індикатора)
    """

    result_ready = Signal(object, object, object, object, object, bool)
    error_occurred = Signal(str)
    started_work = Signal()

    def __init__(self, generate_func, tessellate_func, parent=None):
        """
        Args:
            generate_func: callable() → CadQuery shape/list — генерує геометрію
            tessellate_func: callable(shape, is_assembly) → (verts, faces, colors, edges)
                             — тесселює геометрію у numpy-масиви
        """
        super().__init__(parent)
        self._generate_func = generate_func
        self._tessellate_func = tessellate_func
        self._cancelled = False

    def cancel(self):
        """Позначити воркер як скасований (перевіряється перед emit)."""
        self._cancelled = True

    def run(self):
        self.started_work.emit()
        try:
            shape, is_assembly = self._generate_func()
            if self._cancelled:
                return
            verts, faces, colors, edges = self._tessellate_func(shape, is_assembly)
            if self._cancelled:
                return
            self.result_ready.emit(shape, verts, faces, colors, edges, is_assembly)
        except Exception as e:
            if not self._cancelled:
                import traceback
                traceback.print_exc()
                self.error_occurred.emit(str(e))


# ---------------------------------------------------------------------------
# MeshCache — кешування результатів тесселяції
# ---------------------------------------------------------------------------

class MeshCache:
    """
    Простий кеш LRU для numpy-масивів тесселяції.
    Ключ = SHA256-хеш рядкового представлення параметрів форми.
    """

    def __init__(self, max_size: int = 16):
        self._max_size = max_size
        self._cache: dict = {}   # key → (verts, faces, colors, edges)
        self._order: list = []   # для витіснення (LRU)

    @staticmethod
    def make_key(params: dict) -> str:
        """Обчислити ключ кешу з dict параметрів."""
        raw = str(sorted(params.items())).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def get(self, key: str):
        """Повернути кешований результат або None."""
        if key in self._cache:
            # оновити порядок LRU
            self._order.remove(key)
            self._order.append(key)
            return self._cache[key]
        return None

    def put(self, key: str, value: tuple):
        """Зберегти результат у кеш."""
        if key in self._cache:
            self._order.remove(key)
        elif len(self._cache) >= self._max_size:
            oldest = self._order.pop(0)
            del self._cache[oldest]
        self._cache[key] = value
        self._order.append(key)

    def clear(self):
        self._cache.clear()
        self._order.clear()
