"""Aloth GUI — чат с историей сессий (PySide6). Минимум на старт.

Окно: слева список сессий, справа переписка + поле ввода.
Агент живёт в отдельном потоке (QThread), UI не замирает.
Запуск: `aloth gui` или `python -m aloth.gui`.
"""

from __future__ import annotations

import asyncio
import html
import sys

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from aloth.core import build_agent
from aloth.files import FileTools
from aloth.home import ensure_home
from aloth.memory import MemoryStore
from aloth.security import SecurityPolicy
from aloth.sessions import SessionStore
from aloth.shell import Shell


class AgentWorker(QThread):
    """One-shot agent run in a worker thread. Emits (reply, error)."""

    done = Signal(str, str)

    def __init__(self, prompt: str, history: list[dict], profile: str, parent=None):
        super().__init__(parent)
        self.prompt = prompt
        self.history = history
        self.profile = profile

    def run(self) -> None:
        try:
            home = ensure_home()
            policy = SecurityPolicy.load(home)
            try:
                agent = build_agent(
                    memory=MemoryStore(home / "data" / "memory.db"),
                    files=FileTools(home),
                    shell=Shell(profile=self.profile),
                    security=policy,
                )
                context = "\n".join(f"{m['role']}: {m['content']}" for m in self.history)
                full = f"{context}\nuser: {self.prompt}" if self.history else self.prompt
                result = asyncio.run(agent.run(full))
            finally:
                policy.close()
            self.done.emit(result.data if hasattr(result, "data") else str(result), "")
        except Exception as e:  # noqa: BLE001 — surface any failure to the UI
            self.done.emit("", str(e))


class MainWindow(QMainWindow):
    def __init__(self, profile: str = "readonly"):
        super().__init__()
        self.profile = profile
        self.store = SessionStore(ensure_home() / "data" / "sessions.db")
        self.current_sid: str | None = None
        self.worker: AgentWorker | None = None
        self._build_ui()
        self._reload_sessions()

    def _build_ui(self) -> None:
        self.setWindowTitle("Aloth")
        self.resize(900, 600)

        self.session_list = QListWidget()
        self.session_list.currentItemChanged.connect(self._on_session_changed)

        self.chat = QTextBrowser()
        self.chat.setOpenExternalLinks(True)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Сообщение… (Enter — отправить)")
        self.input.returnPressed.connect(self._on_send)

        self.send_btn = QPushButton("Отправить")
        self.send_btn.clicked.connect(self._on_send)

        new_btn = QPushButton("Новая сессия")
        new_btn.clicked.connect(self._new_session)

        left = QVBoxLayout()
        left.addWidget(QLabel("Сессии"))
        left.addWidget(self.session_list)
        left.addWidget(new_btn)

        right = QVBoxLayout()
        right.addWidget(self.chat)
        row = QHBoxLayout()
        row.addWidget(self.input)
        row.addWidget(self.send_btn)
        right.addLayout(row)

        splitter = QSplitter(Qt.Horizontal)
        left_box = QWidget()
        left_box.setLayout(left)
        right_box = QWidget()
        right_box.setLayout(right)
        splitter.addWidget(left_box)
        splitter.addWidget(right_box)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)

    # --- sessions ---

    def _reload_sessions(self) -> None:
        self.session_list.blockSignals(True)
        self.session_list.clear()
        for s in self.store.list_sessions():
            item = QListWidgetItem(s["title"])
            item.setData(Qt.UserRole, s["id"])
            self.session_list.addItem(item)
        self.session_list.blockSignals(False)
        if self.session_list.count():
            self.session_list.setCurrentRow(0)
        else:
            self._new_session()

    def _new_session(self) -> None:
        sid = self.store.create_session()
        self._reload_sessions()
        for i in range(self.session_list.count()):
            if self.session_list.item(i).data(Qt.UserRole) == sid:
                self.session_list.setCurrentRow(i)
                break

    def _on_session_changed(self, current: QListWidgetItem | None, _prev=None) -> None:
        if current is None:
            return
        self.current_sid = current.data(Qt.UserRole)
        self._render_history(self.store.history(self.current_sid))

    # --- chat ---

    def _render_history(self, history: list[dict]) -> None:
        self.chat.clear()
        for m in history:
            self._append(m["role"], m["content"], save=False)

    def _append(self, role: str, content: str, save: bool) -> None:
        if save and self.current_sid:
            self.store.add_message(self.current_sid, role, content)
        label = "Вы" if role == "user" else "Aloth"
        color = "#8b5e3c" if role == "user" else "#1a5276"
        self.chat.append(
            f'<p style="margin:4px 0"><b style="color:{color}">{label}:</b> '
            f'<span style="white-space:pre-wrap">{html.escape(content)}</span></p>'
        )

    def _on_send(self) -> None:
        text = self.input.text().strip()
        if not text or self.worker is not None or self.current_sid is None:
            return
        self.input.clear()
        self._append("user", text, save=True)
        self._set_busy(True)

        history = self.store.history(self.current_sid, limit=20)
        self.worker = AgentWorker(text, history[:-1], self.profile, self)
        self.worker.done.connect(self._on_done)
        self.worker.start()

    def _on_done(self, reply: str, error: str) -> None:
        self.worker = None
        self._set_busy(False)
        if error:
            self._append("assistant", f"[ошибка] {error}", save=False)
        else:
            self._append("assistant", reply, save=True)

    def _set_busy(self, busy: bool) -> None:
        self.input.setEnabled(not busy)
        self.send_btn.setEnabled(not busy)
        if busy:
            self.chat.append(
                '<p style="color:#888;margin:4px 0"><i>Aloth печатает…</i></p>'
            )

    def closeEvent(self, event) -> None:  # noqa: N802 — Qt override
        if self.worker is not None:
            self.worker.wait(2000)
        self.store.close()
        super().closeEvent(event)


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="aloth gui")
    p.add_argument("--profile", default="readonly",
                   choices=["readonly", "full"],
                   help="профиль доверия для shell (default: readonly)")
    args = p.parse_args(argv)

    app = QApplication(sys.argv[:1])
    win = MainWindow(profile=args.profile)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
