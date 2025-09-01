import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from PySide6.QtCore import QCoreApplication, QTranslator, QLocale

from app.ui import MainWindow
from app.utils import get_system_locale, resource_path, setup_logging

def load_translation(app):
    sys_locale = QLocale(get_system_locale())
    translator = QTranslator(app)
    translation_path = resource_path(f'translations/{sys_locale.name()}.qm')
    if translator.load(translation_path):
        QCoreApplication.installTranslator(translator)
        return True
    return False

if __name__ == "__main__":  
    setup_logging()
    app = QApplication(sys.argv)
    load_translation(app)
    app.setFont(QFont("Segoe UI", 9))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())