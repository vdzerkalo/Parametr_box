import os
import sys


def _ensure_dependencies():
    """Якщо застосунок запущено інтерпретатором без залежностей (напр. системний
    `python main.py` замість venv), автоматично перезапускаємось через ./.venv,
    інакше показуємо зрозумілу підказку замість сирого ImportError."""
    try:
        import PySide6  # noqa: F401
        return
    except ImportError:
        pass
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, ".venv", "Scripts", "python.exe"),
                 os.path.join(here, ".venv", "bin", "python")):
        if (os.path.exists(cand) and
                os.path.normcase(os.path.abspath(cand)) !=
                os.path.normcase(os.path.abspath(sys.executable))):
            os.execv(cand, [cand, os.path.abspath(__file__)] + sys.argv[1:])
    sys.stderr.write(
        "\n[ParametrBox] Python-залежності не встановлено для цього інтерпретатора.\n"
        "  Windows:  двічі клацніть run_box_generator.bat\n"
        "  або:      py -3.11 -m venv .venv\n"
        "            .venv\\Scripts\\python -m pip install -r requirements.txt\n"
        "            .venv\\Scripts\\python main.py\n\n")
    sys.exit(1)


_ensure_dependencies()

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt

from app import BoxGeneratorApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setAttribute(Qt.AA_DontShowIconsInMenus, False)
    
    # Темна тема
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(45, 45, 45))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(30, 30, 30))
    palette.setColor(QPalette.AlternateBase, QColor(45, 45, 45))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)
    
    window = BoxGeneratorApp()
    window.show()
    sys.exit(app.exec())
