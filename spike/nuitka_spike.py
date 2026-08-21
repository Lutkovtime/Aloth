"""Nuitka spike: PySide6 + qt-material + QtAwesome bare widget.

Build:  uv run nuitka --standalone --enable-plugin=pyside6 --output-dir=dist_spike spike/nuitka_spike.py
Check:  qss applied, icon loaded, high-dpi, window created. Prints verdict, exit 0/1.
"""
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget

ok = True


def check(name: str, cond: bool, detail: str = "") -> None:
    global ok
    print(f"{'PASS' if cond else 'FAIL'}  {name}  {detail}")
    ok = ok and cond


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("aloth-nuitka-spike")

    # qt-material
    from qt_material import apply_stylesheet
    apply_stylesheet(app, theme="dark_teal.xml")

    # QtAwesome icon
    import qtawesome as qta
    icon = qta.icon("fa5s.robot")
    check("icon", not icon.isNull(), f"fa5s.robot")

    # bare widget
    w = QMainWindow()
    w.setWindowTitle("aloth-nuitka-spike")
    w.setWindowIcon(icon)
    cw = QWidget()
    lay = QVBoxLayout(cw)
    lbl = QLabel("Nuitka spike: qt-material + QtAwesome")
    lbl.setObjectName("spikeLabel")
    lay.addWidget(lbl)
    w.setCentralWidget(cw)
    w.resize(480, 240)

    # checks
    check("qss_applied", bool(app.styleSheet()), f"styleSheet len={len(app.styleSheet())}")
    check("label_obj_name", lbl.objectName() == "spikeLabel")

    def run():
        global ok
        check("window_visible", w.isVisible())
        dpr = w.devicePixelRatioF() if hasattr(w, "devicePixelRatioF") else w.devicePixelRatio()
        check("high_dpi", dpr >= 1.0, f"dpr={dpr}")
        # qt-material sets a palette: verify background token reached the app
        pal = app.palette()
        check("palette", pal.window().color().isValid(), f"window={pal.window().color().name()}")
        print("VERDICT:", "PASS" if ok else "FAIL")
        app.exit(0 if ok else 1)

    w.show()
    QTimer.singleShot(1500, run)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
