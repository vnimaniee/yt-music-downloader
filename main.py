import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from app.ui import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 9))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())