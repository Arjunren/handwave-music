APP_STYLE = """
QMainWindow, QDialog { background: #090b12; color: #f5f7ff; }
QWidget { color: #f5f7ff; font-family: "Segoe UI", "Inter", sans-serif; font-size: 14px; }
QFrame#Card { background: #121621; border: 1px solid #222838; border-radius: 18px; }
QFrame#TopBar { background: transparent; border: none; }
QLabel#Brand { font-size: 22px; font-weight: 800; letter-spacing: 2px; color: #ffffff; }
QLabel#Eyebrow { color: #9098ad; font-size: 11px; font-weight: 700; letter-spacing: 2px; }
QLabel#Title { font-size: 27px; font-weight: 750; color: #ffffff; }
QLabel#Artist { color: #a6aec2; font-size: 15px; }
QLabel#Muted { color: #71798d; }
QLabel#Gesture { color: #68edff; font-size: 17px; font-weight: 650; }
QLabel#Empty { color: #8e96aa; font-size: 15px; }
QPushButton { background: #1b2030; border: 1px solid #2b3245; border-radius: 12px; padding: 9px 14px; }
QPushButton:hover { background: #242b3d; border-color: #414a63; }
QPushButton:pressed { background: #151a27; }
QPushButton#Primary { background: #a65cff; border: none; color: white; font-size: 19px; font-weight: 700; border-radius: 23px; min-width: 46px; min-height: 46px; padding: 0px; }
QPushButton#Primary:hover { background: #b97cff; }
QPushButton#Round { border-radius: 19px; min-width: 38px; min-height: 38px; padding: 0px; font-size: 17px; }
QPushButton#Toggle:checked { background: #153f45; color: #68edff; border-color: #28717d; }
QPushButton#Active { color: #c993ff; border-color: #7040a6; }
QListWidget { background: transparent; border: none; outline: none; padding: 4px; }
QListWidget::item { background: transparent; color: #b9c0d2; border-radius: 10px; padding: 10px 9px; margin: 2px 0px; }
QListWidget::item:hover { background: #1b2030; }
QListWidget::item:selected { background: #242039; color: #d9b8ff; border-left: 3px solid #a65cff; }
QSlider::groove:horizontal { height: 5px; background: #2a3040; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #a65cff; border-radius: 2px; }
QSlider::handle:horizontal { background: #ffffff; width: 14px; margin: -5px 0; border-radius: 7px; }
QComboBox, QSpinBox, QDoubleSpinBox { background: #1a1f2d; border: 1px solid #30384c; border-radius: 8px; padding: 7px 10px; min-width: 105px; }
QComboBox QAbstractItemView { background: #171b27; selection-background-color: #6f3ba2; border: 1px solid #30384c; }
QScrollBar:vertical { background: transparent; width: 8px; }
QScrollBar::handle:vertical { background: #30374b; min-height: 28px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QToolTip { background: #1d2230; color: white; border: 1px solid #3a4257; padding: 5px; }
"""
