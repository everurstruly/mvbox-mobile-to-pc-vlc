import sys
from PySide6 import QtGui, QtWidgets

# Import the refactored main window
from src.ui.main_window import MainWindow

def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setFont(QtGui.QFont("Inter", 10))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
