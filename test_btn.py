import sys
from PySide6.QtWidgets import QApplication, QPushButton

def test_func():
    print("Button clicked without args!")

app = QApplication(sys.argv)
btn = QPushButton("Test")
btn.clicked.connect(test_func)
btn.click()
