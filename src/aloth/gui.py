"""Aloth GUI — чат с историей сессий + вкладки «Память», «Навыки», «Настройки» (PySide6).

Окно: вкладка «Чат» (сессии слева, переписка справа + поле ввода),
«Память» — факты L1, «Навыки» — файлы ~/.aloth/skills/*.md,
«Настройки» — матрица тулов (security.json) + HITL.
Агент живёт в отдельном потоке (QThread), UI не замирает.
Запуск: `aloth gui` или `python -m aloth.gui`.
"""

from __future__ import annotations

import asyncio
import html
import os
import sys
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from aloth import config
from aloth.core import build_agent
from aloth.files import FileTools
from aloth.home import ensure_home
from aloth.memory import MemoryStore
from aloth.security import KNOWN_TOOLS, SecurityPolicy
from aloth.sessions import SessionStore
from aloth.shell import Shell


class AgentWorker(QThread):
    """One-shot agent run in a worker thread. Emits (reply, error).

    HITL: tools with autoApprove=false emit approval_requested(tool, args)
    and block until resolve_approval(ok) is called from the UI thread.
    """

    done = Signal(str, str)
    approval_requested = Signal(str, str)

    def __init__(self, prompt: str, history: list[dict], profile: str, parent=None,
                 api_key: str | None = None):
        super().__init__(parent)
        self.prompt = prompt
        self.history = history
        self.profile = profile
        self.api_key = api_key
        self._event = threading.Event()
        self._ok = False

    def _approver(self, tool: str, args: str) -> bool:
        self._ok = False
        self._event.clear()
        self.approval_requested.emit(tool, args)
        self._event.wait(300)
        return self._ok

    def resolve_approval(self, ok: bool) -> None:
        self._ok = ok
        self._event.set()

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
                    approver=self._approver,
                    skills_dir=home / "skills",
                    api_key=self.api_key,
                )
                context = "\n".join(f"{m['role']}: {m['content']}" for m in self.history)
                full = f"{context}\nuser: {self.prompt}" if self.history else self.prompt
                result = asyncio.run(agent.run(full))
            finally:
                policy.close()
            self.done.emit(result.data if hasattr(result, "data") else str(result), "")
        except Exception as e:  # noqa: BLE001 — surface any failure to the UI
            self.done.emit("", str(e))


class MemoryTab(QWidget):
    """Факты L1: список, добавить, забыть."""

    def __init__(self, mem: MemoryStore):
        super().__init__()
        self.mem = mem
        self.list = QListWidget()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Новый факт…")
        self.input.returnPressed.connect(self._add)

        add_btn = QPushButton("Запомнить")
        add_btn.clicked.connect(self._add)
        forget_btn = QPushButton("Забыть выбранное")
        forget_btn.clicked.connect(self._forget)

        row = QHBoxLayout()
        row.addWidget(self.input)
        row.addWidget(add_btn)
        row.addWidget(forget_btn)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Что Aloth знает о пользователе (попадает в контекст каждого запроса):"))
        lay.addWidget(self.list)
        lay.addLayout(row)
        self._reload()

    def _reload(self) -> None:
        self.list.clear()
        self.list.addItems(self.mem.all())

    def _add(self) -> None:
        text = self.input.text().strip()
        if text:
            self.mem.add(text)
            self.input.clear()
            self._reload()

    def _forget(self) -> None:
        item = self.list.currentItem()
        if item:
            self.mem.forget(item.text())
            self._reload()


class SkillsTab(QWidget):
    """Файлы ~/.aloth/skills/*.md: список, редактор, создать, удалить."""

    def __init__(self, skills_dir: Path):
        super().__init__()
        self.dir = skills_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self._current: Path | None = None

        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._on_select)

        self.editor = QTextEdit()
        self.editor.setPlaceholderText("Инструкция для Aloth (Markdown)…")

        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self._save)
        new_btn = QPushButton("Новый")
        new_btn.clicked.connect(self._new)
        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(self._delete)

        btn_row = QHBoxLayout()
        btn_row.addWidget(save_btn)
        btn_row.addWidget(new_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch(1)

        right = QVBoxLayout()
        right.addWidget(self.editor)
        right.addLayout(btn_row)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.list)
        right_box = QWidget()
        right_box.setLayout(right)
        split.addWidget(right_box)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Навыки: файлы .md в доме Aloth, подхватываются как инструкции агенту."))
        lay.addWidget(split)
        self._reload()

    def _reload(self) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for f in sorted(self.dir.glob("*.md")):
            self.list.addItem(f.name)
        self.list.blockSignals(False)
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.editor.clear()
            self._current = None

    def _on_select(self, current: QListWidgetItem | None, _prev=None) -> None:
        if current is None:
            return
        self._current = self.dir / current.text()
        self.editor.setPlainText(self._current.read_text(encoding="utf-8"))

    def _save(self) -> None:
        if self._current:
            self._current.write_text(self.editor.toPlainText(), encoding="utf-8")

    def _new(self) -> None:
        n = 1
        while (self.dir / f"skill-{n}.md").exists():
            n += 1
        path = self.dir / f"skill-{n}.md"
        path.write_text("", encoding="utf-8")
        self._reload()
        for i in range(self.list.count()):
            if self.list.item(i).text() == path.name:
                self.list.setCurrentRow(i)
                break

    def _delete(self) -> None:
        if not self._current:
            return
        if QMessageBox.question(self, "Aloth", f"Удалить навык «{self._current.name}»?") != QMessageBox.Yes:
            return
        self._current.unlink(missing_ok=True)
        self._current = None
        self._reload()


class SettingsTab(QWidget):
    """Матрица тулов security.json: enabled / autoApprove + сохранение."""

    def __init__(self, home: Path):
        super().__init__()
        self.policy = SecurityPolicy.load(home)
        self.table = QTableWidget(len(KNOWN_TOOLS), 3)
        self.table.setHorizontalHeaderLabels(["Тул", "Включён", "Авто-одобрение"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self._boxes: dict[str, tuple[QCheckBox, QCheckBox]] = {}

        for row, name in enumerate(KNOWN_TOOLS):
            entry = self.policy.matrix().get(name, {"enabled": False, "autoApprove": False})
            self.table.setItem(row, 0, QTableWidgetItem(name))
            enabled = QCheckBox()
            enabled.setChecked(bool(entry["enabled"]))
            approve = QCheckBox()
            approve.setChecked(bool(entry["autoApprove"]))
            self.table.setCellWidget(row, 1, enabled)
            self.table.setCellWidget(row, 2, approve)
            self._boxes[name] = (enabled, approve)

        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self._save)
        self.status = QLabel("")

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Включённые тулы доступны агенту. «Авто-одобрение» выкл. — "
                             "GUI спросит перед действием (HITL)."))
        lay.addWidget(self.table)
        row = QHBoxLayout()
        row.addWidget(save_btn)
        row.addWidget(self.status)
        row.addStretch(1)
        lay.addLayout(row)

    def _save(self) -> None:
        for name, (enabled, approve) in self._boxes.items():
            self.policy.set_tool(name, enabled.isChecked(), approve.isChecked())
        self.policy.save()
        self.status.setText("сохранено ✓")

    def close(self) -> None:
        self.policy.close()


class MainWindow(QMainWindow):
    def __init__(self, profile: str | None = None):
        super().__init__()
        self.home = ensure_home()
        settings = config.load(self.home)
        self.profile = profile or settings.profile
        self.api_key = settings.api_key
        if not (os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ALOTH_API_KEY")
                or self.api_key):
            if not self._setup_dialog():
                sys.exit(0)
        self.store = SessionStore(self.home / "data" / "sessions.db")
        self.current_sid: str | None = None
        self.worker: AgentWorker | None = None
        self._build_ui()
        self._reload_sessions()

    def _setup_dialog(self) -> bool:
        """Первый запуск: API-ключ DeepSeek + профиль доверия. True = сохранено."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Aloth — первый запуск")
        key = QLineEdit()
        key.setEchoMode(QLineEdit.Password)
        key.setPlaceholderText("DeepSeek API key (sk-…)")
        combo = QComboBox()
        combo.addItems(config.PROFILES)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Сохранить")
        buttons.button(QDialogButtonBox.Cancel).setText("Отмена")
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Введи API-ключ DeepSeek и выбери профиль доверия."))
        lay.addWidget(key)
        lay.addWidget(combo)
        lay.addWidget(buttons)
        if dlg.exec() != QDialog.Accepted:
            return False
        self.api_key = key.text().strip()
        config.save(self.home, config.Settings(api_key=self.api_key,
                                               profile=combo.currentText()))
        return True

    def _build_ui(self) -> None:
        self.setWindowTitle("Aloth")
        self.resize(900, 600)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._chat_tab(), "Чат")
        self.tabs.addTab(MemoryTab(MemoryStore(self.home / "data" / "memory.db")), "Память")
        self.tabs.addTab(SkillsTab(self.home / "skills"), "Навыки")
        self._settings = SettingsTab(self.home)
        self.tabs.addTab(self._settings, "Настройки")
        self.setCentralWidget(self.tabs)

    def _chat_tab(self) -> QWidget:
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

        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.addWidget(splitter)
        return tab

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
        self.worker = AgentWorker(text, history[:-1], self.profile, self,
                                  api_key=self.api_key)
        self.worker.done.connect(self._on_done)
        self.worker.approval_requested.connect(self._on_approval_request)
        self.worker.start()

    def _on_done(self, reply: str, error: str) -> None:
        self.worker = None
        self._set_busy(False)
        if error:
            self._append("assistant", f"[ошибка] {error}", save=False)
        else:
            self._append("assistant", reply, save=True)

    def _on_approval_request(self, tool: str, args: str) -> None:
        if self.worker is None:
            return
        ret = QMessageBox.question(
            self,
            "Aloth — подтверждение",
            f"Тул «{tool}» хочет:\n{args}\n\nРазрешить?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        self.worker.resolve_approval(ret == QMessageBox.Yes)

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
        self._settings.close()
        super().closeEvent(event)


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="aloth gui")
    p.add_argument("--profile", default=None,
                   choices=["readonly", "full"],
                   help="профиль доверия для shell (default: из настроек или readonly)")
    args = p.parse_args(argv)

    app = QApplication(sys.argv[:1])
    win = MainWindow(profile=args.profile)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
