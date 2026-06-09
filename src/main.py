import sys
from PyQt5.QtWidgets import QApplication
from src.app import UniversalFlasherUI


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Universal Flasher & UI")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("LxveAce")

    window = UniversalFlasherUI()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
