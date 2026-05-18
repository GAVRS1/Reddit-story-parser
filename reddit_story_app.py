from __future__ import annotations

import copy
import os
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QSizePolicy,
    QSpinBox,
    QDoubleSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from reddit_story_parser import DEFAULT_CONFIG, load_config, run_search, save_config


APP_NAME = "Reddit Story Parser"
SORT_OPTIONS = ("relevance", "hot", "top", "new", "comments")
TIME_OPTIONS = ("hour", "day", "week", "month", "year", "all")


def app_data_dir() -> Path:
    base = os.getenv("APPDATA")
    if base:
        return Path(base) / "RedditStoryParser"
    return Path.home() / ".reddit_story_parser"


def bundled_config_path() -> Path:
    if getattr(sys, "frozen", False):
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return bundle_root / "config.json"
    return Path(__file__).resolve().parent / "config.json"


def user_config_path() -> Path:
    return app_data_dir() / "config.json"


def default_output_dir() -> Path:
    documents = Path.home() / "Documents"
    if documents.exists():
        return documents / "Reddit Stories"
    return app_data_dir() / "stories"


def load_app_config() -> dict[str, Any]:
    config_path = user_config_path()
    if config_path.exists():
        return load_config(config_path)

    bundled = bundled_config_path()
    config = load_config(bundled) if bundled.exists() else copy.deepcopy(DEFAULT_CONFIG)
    output_dir = str(config.get("saving", {}).get("output_dir", "stories"))
    if not Path(output_dir).is_absolute():
        config["saving"]["output_dir"] = str(default_output_dir())
    save_config(config_path, config)
    return config


class SearchWorker(QObject):
    log = Signal(str)
    progress = Signal(int, int)
    result = Signal(dict)
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__()
        self.config = copy.deepcopy(config)
        self._stop_requested = False

    def request_stop(self) -> None:
        self._stop_requested = True

    def run(self) -> None:
        try:
            summary = run_search(
                self.config,
                log=self.log.emit,
                progress=self.progress.emit,
                result=self.result.emit,
                should_stop=lambda: self._stop_requested,
            )
        except Exception as exc:  # noqa: BLE001 - surface all worker errors to UI.
            self.failed.emit(str(exc))
            return

        self.finished.emit(summary)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1180, 760)
        self.config = load_app_config()
        self.worker: SearchWorker | None = None
        self.thread: QThread | None = None
        self.output_dir = Path(str(self.config["saving"]["output_dir"]))

        self._build_ui()
        self._load_config_to_ui(self.config)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title_wrap = QVBoxLayout()
        title = QLabel(APP_NAME)
        title.setObjectName("title")
        subtitle = QLabel("Поиск историй Reddit по ключевым словам и сохранение в TXT")
        subtitle.setObjectName("subtitle")
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addLayout(title_wrap, 1)

        brand = QLabel("by.Gavrs")
        brand.setObjectName("brand")
        brand.setAlignment(Qt.AlignCenter)
        header.addWidget(brand)
        layout.addLayout(header)

        main = QHBoxLayout()
        main.setSpacing(16)
        layout.addLayout(main, 1)

        settings_card = self._card("Настройки")
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(18, 18, 18, 18)
        settings_layout.setSpacing(14)
        settings_layout.addWidget(self._card_title("Настройки"))
        main.addWidget(settings_card, 4)

        self.keywords_edit = QPlainTextEdit()
        self.keywords_edit.setObjectName("keywords")
        self.keywords_edit.setPlaceholderText("Каждое ключевое слово или фраза с новой строки")
        self.keywords_edit.setMinimumHeight(106)
        settings_layout.addWidget(self._field("Ключевые слова", self.keywords_edit))

        search_grid = QGridLayout()
        search_grid.setHorizontalSpacing(12)
        search_grid.setVerticalSpacing(10)
        self.subreddit_edit = QLineEdit()
        self.subreddit_edit.setPlaceholderText("например AskReddit, stories, relationships")
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 100)
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(SORT_OPTIONS)
        self.time_combo = QComboBox()
        self.time_combo.addItems(TIME_OPTIONS)
        search_grid.addWidget(QLabel("Subreddit"), 0, 0)
        search_grid.addWidget(self.subreddit_edit, 0, 1, 1, 3)
        search_grid.addWidget(QLabel("Лимит"), 1, 0)
        search_grid.addWidget(self.limit_spin, 1, 1)
        search_grid.addWidget(QLabel("Сортировка"), 1, 2)
        search_grid.addWidget(self.sort_combo, 1, 3)
        search_grid.addWidget(QLabel("Период"), 2, 0)
        search_grid.addWidget(self.time_combo, 2, 1)
        settings_layout.addLayout(search_grid)

        save_group = QGroupBox("Сохранение")
        save_layout = QGridLayout(save_group)
        save_layout.setHorizontalSpacing(12)
        save_layout.setVerticalSpacing(10)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Папка для TXT-файлов")
        browse_btn = QPushButton("Выбрать")
        browse_btn.clicked.connect(self._choose_output_dir)
        self.min_chars_spin = QSpinBox()
        self.min_chars_spin.setRange(0, 1_000_000)
        self.max_chars_spin = QSpinBox()
        self.max_chars_spin.setRange(0, 1_000_000)
        self.sleep_spin = QDoubleSpinBox()
        self.sleep_spin.setRange(0.0, 60.0)
        self.sleep_spin.setSingleStep(0.25)
        self.sleep_spin.setDecimals(2)
        self.skip_nsfw_check = QCheckBox("Пропускать NSFW")
        save_layout.addWidget(QLabel("Папка"), 0, 0)
        save_layout.addWidget(self.output_edit, 0, 1, 1, 2)
        save_layout.addWidget(browse_btn, 0, 3)
        save_layout.addWidget(QLabel("Мин. символов"), 1, 0)
        save_layout.addWidget(self.min_chars_spin, 1, 1)
        save_layout.addWidget(QLabel("Макс. символов"), 1, 2)
        save_layout.addWidget(self.max_chars_spin, 1, 3)
        save_layout.addWidget(QLabel("Пауза, сек"), 2, 0)
        save_layout.addWidget(self.sleep_spin, 2, 1)
        save_layout.addWidget(self.skip_nsfw_check, 2, 2, 1, 2)
        settings_layout.addWidget(save_group)

        api_group = QGroupBox("Reddit API (необязательно)")
        api_layout = QGridLayout(api_group)
        api_layout.setHorizontalSpacing(12)
        api_layout.setVerticalSpacing(10)
        self.client_id_edit = QLineEdit()
        self.client_secret_edit = QLineEdit()
        self.client_secret_edit.setEchoMode(QLineEdit.Password)
        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.user_agent_edit = QLineEdit()
        api_layout.addWidget(QLabel("Client ID"), 0, 0)
        api_layout.addWidget(self.client_id_edit, 0, 1)
        api_layout.addWidget(QLabel("Secret"), 0, 2)
        api_layout.addWidget(self.client_secret_edit, 0, 3)
        api_layout.addWidget(QLabel("Username"), 1, 0)
        api_layout.addWidget(self.username_edit, 1, 1)
        api_layout.addWidget(QLabel("Password"), 1, 2)
        api_layout.addWidget(self.password_edit, 1, 3)
        api_layout.addWidget(QLabel("User-Agent"), 2, 0)
        api_layout.addWidget(self.user_agent_edit, 2, 1, 1, 3)
        api_hint = QLabel("Если Reddit возвращает 403 Blocked, заполните эти поля из Reddit app типа script.")
        api_hint.setObjectName("hint")
        api_hint.setWordWrap(True)
        reddit_apps_btn = QPushButton("Открыть Reddit apps")
        reddit_apps_btn.clicked.connect(self._open_reddit_apps)
        api_layout.addWidget(api_hint, 3, 0, 1, 3)
        api_layout.addWidget(reddit_apps_btn, 3, 3)
        settings_layout.addWidget(api_group)

        actions = QHBoxLayout()
        self.start_btn = QPushButton("Начать поиск")
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.clicked.connect(self._start_search)
        self.stop_btn = QPushButton("Стоп")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_search)
        save_btn = QPushButton("Сохранить настройки")
        save_btn.clicked.connect(self._save_settings)
        open_btn = QPushButton("Открыть папку")
        open_btn.clicked.connect(self._open_output_dir)
        actions.addWidget(self.start_btn)
        actions.addWidget(self.stop_btn)
        actions.addWidget(save_btn)
        actions.addWidget(open_btn)
        settings_layout.addLayout(actions)
        settings_layout.addStretch(1)

        results_card = self._card("Результаты")
        results_layout = QVBoxLayout(results_card)
        results_layout.setContentsMargins(18, 18, 18, 18)
        results_layout.setSpacing(12)
        results_layout.addWidget(self._card_title("Результаты"))
        main.addWidget(results_card, 6)

        self.summary_label = QLabel("Готов к поиску")
        self.summary_label.setObjectName("summary")
        results_layout.addWidget(self.summary_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        results_layout.addWidget(self.progress)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Статус", "Название", "Subreddit", "Символы", "Файл"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        results_layout.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        clear_btn = QPushButton("Очистить таблицу")
        clear_btn.clicked.connect(lambda: self.table.setRowCount(0))
        config_btn = QPushButton("Открыть config")
        config_btn.clicked.connect(self._open_config_file)
        bottom.addWidget(clear_btn)
        bottom.addWidget(config_btn)
        bottom.addStretch(1)
        results_layout.addLayout(bottom)

        log_card = self._card("Лог")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(16, 14, 16, 16)
        log_layout.addWidget(self._card_title("Лог"))
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumHeight(104)
        log_layout.addWidget(self.log_edit)
        layout.addWidget(log_card)

        self.setCentralWidget(root)

    def _card(self, title: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        frame.setProperty("title", title)
        return frame

    def _card_title(self, title: str) -> QLabel:
        label = QLabel(title)
        label.setObjectName("cardTitle")
        return label

    def _field(self, label: str, widget: QWidget) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        title = QLabel(label)
        title.setObjectName("fieldLabel")
        layout.addWidget(title)
        layout.addWidget(widget)
        return wrap

    def _load_config_to_ui(self, config: dict[str, Any]) -> None:
        reddit = config["reddit"]
        search = config["search"]
        saving = config["saving"]
        self.keywords_edit.setPlainText("\n".join(str(x) for x in search.get("keywords", [])))
        self.subreddit_edit.setText(str(search.get("subreddit", "")))
        self.limit_spin.setValue(int(search.get("limit", 25)))
        self.sort_combo.setCurrentText(str(search.get("sort", "relevance")))
        self.time_combo.setCurrentText(str(search.get("time_filter", "all")))
        self.output_edit.setText(str(saving.get("output_dir", default_output_dir())))
        self.min_chars_spin.setValue(int(saving.get("min_chars", 1000)))
        self.max_chars_spin.setValue(int(saving.get("max_chars", 10000)))
        self.sleep_spin.setValue(float(saving.get("sleep_seconds", 1.0)))
        self.skip_nsfw_check.setChecked(bool(saving.get("skip_nsfw", True)))
        self.client_id_edit.setText(str(reddit.get("client_id", "")))
        self.client_secret_edit.setText(str(reddit.get("client_secret", "")))
        self.username_edit.setText(str(reddit.get("username", "")))
        self.password_edit.setText(str(reddit.get("password", "")))
        self.user_agent_edit.setText(str(reddit.get("user_agent", "")))
        self.output_dir = Path(self.output_edit.text()).expanduser()

    def _config_from_ui(self) -> dict[str, Any]:
        keywords = [line.strip() for line in self.keywords_edit.toPlainText().splitlines() if line.strip()]
        output_dir = Path(self.output_edit.text().strip() or str(default_output_dir())).expanduser()
        return {
            "reddit": {
                "client_id": self.client_id_edit.text().strip(),
                "client_secret": self.client_secret_edit.text().strip(),
                "username": self.username_edit.text().strip(),
                "password": self.password_edit.text(),
                "user_agent": self.user_agent_edit.text().strip(),
            },
            "search": {
                "keywords": keywords,
                "subreddit": self.subreddit_edit.text().strip(),
                "limit": self.limit_spin.value(),
                "sort": self.sort_combo.currentText(),
                "time_filter": self.time_combo.currentText(),
            },
            "saving": {
                "output_dir": str(output_dir),
                "min_chars": self.min_chars_spin.value(),
                "max_chars": self.max_chars_spin.value(),
                "sleep_seconds": self.sleep_spin.value(),
                "skip_nsfw": self.skip_nsfw_check.isChecked(),
            },
        }

    def _choose_output_dir(self) -> None:
        current = self.output_edit.text().strip() or str(default_output_dir())
        selected = QFileDialog.getExistingDirectory(self, "Выберите папку", current)
        if selected:
            self.output_edit.setText(selected)

    def _save_settings(self) -> None:
        self.config = self._config_from_ui()
        self.output_dir = Path(self.config["saving"]["output_dir"])
        save_config(user_config_path(), self.config)
        self._log(f"Settings saved: {user_config_path()}")

    def _start_search(self) -> None:
        config = self._config_from_ui()
        if not config["search"]["keywords"]:
            QMessageBox.warning(self, APP_NAME, "Добавьте хотя бы одно ключевое слово.")
            return

        self.config = config
        self.output_dir = Path(config["saving"]["output_dir"])
        save_config(user_config_path(), self.config)
        self.table.setRowCount(0)
        self.log_edit.clear()
        self.summary_label.setText("Идет поиск...")
        self.progress.setValue(0)
        self._set_running(True)

        self.thread = QThread(self)
        self.worker = SearchWorker(config)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self._log)
        self.worker.progress.connect(self._set_progress)
        self.worker.result.connect(self._add_result)
        self.worker.finished.connect(self._search_finished)
        self.worker.failed.connect(self._search_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self._clear_thread_refs)
        self.thread.start()

    def _stop_search(self) -> None:
        if self.worker:
            self.worker.request_stop()
            self.stop_btn.setEnabled(False)
            self.summary_label.setText("Останавливаю после текущего поста...")

    def _set_progress(self, current: int, total: int) -> None:
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(min(current, max(total, 1)))

    def _add_result(self, item: dict[str, Any]) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        values = [
            item.get("status", ""),
            item.get("title", ""),
            f"r/{item.get('subreddit', 'unknown')}",
            str(item.get("chars", 0)),
            item.get("path", "") or item.get("url", ""),
        ]
        for column, value in enumerate(values):
            cell = QTableWidgetItem(str(value))
            if column == 0 and str(value) == "saved":
                cell.setData(Qt.ForegroundRole, Qt.GlobalColor.darkGreen)
            self.table.setItem(row, column, cell)

    def _search_finished(self, summary: dict[str, Any]) -> None:
        self.summary_label.setText(
            f"Готово: сохранено {summary.get('saved', 0)}, пропущено {summary.get('skipped', 0)}"
        )
        self._set_running(False)

    def _search_failed(self, message: str) -> None:
        self.summary_label.setText("Ошибка поиска")
        self._set_running(False)
        self._log(f"ERROR: {message}")
        if "403" in message or "публичный поиск" in message:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle(APP_NAME)
            box.setText("Reddit заблокировал публичный поиск без авторизации.")
            box.setInformativeText(
                "Заполните блок Reddit API данными из Reddit app типа script: "
                "client_id, client_secret, username, password и user_agent."
            )
            open_button = box.addButton("Открыть Reddit apps", QMessageBox.ActionRole)
            box.addButton(QMessageBox.Ok)
            box.exec()
            if box.clickedButton() == open_button:
                self._open_reddit_apps()
            return

        QMessageBox.critical(self, APP_NAME, message)

    def _clear_thread_refs(self) -> None:
        self.worker = None
        self.thread = None

    def _set_running(self, running: bool) -> None:
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)

    def _open_output_dir(self) -> None:
        output = Path(self.output_edit.text().strip() or str(default_output_dir())).expanduser()
        output.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(output.resolve())))

    def _open_config_file(self) -> None:
        self._save_settings()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(user_config_path().resolve())))

    def _open_reddit_apps(self) -> None:
        QDesktopServices.openUrl(QUrl("https://www.reddit.com/prefs/apps"))

    def _log(self, message: str) -> None:
        self.log_edit.appendPlainText(message)


APP_QSS = """
QWidget#root {
    background: #f4f6fb;
    color: #111827;
    font-family: "Segoe UI Variable", "Inter", "Segoe UI";
    font-size: 10pt;
}

QLabel#title {
    font-size: 26pt;
    font-weight: 800;
    color: #0f172a;
}

QLabel#subtitle {
    color: #64748b;
    font-size: 10.5pt;
}

QLabel#hint {
    color: #64748b;
    font-size: 9.5pt;
}

QLabel#cardTitle {
    color: #0f172a;
    font-size: 13pt;
    font-weight: 850;
}

QLabel#brand {
    min-width: 96px;
    padding: 8px 14px;
    border-radius: 16px;
    background: #111827;
    color: #ffffff;
    font-weight: 800;
}

QFrame#card {
    background: #ffffff;
    border: 1px solid #dfe5ef;
    border-radius: 18px;
}

QLabel#fieldLabel, QGroupBox {
    color: #334155;
    font-weight: 700;
}

QGroupBox {
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    margin-top: 10px;
    padding: 14px 12px 12px 12px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    background: #ffffff;
}

QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    border: 1px solid #cbd5e1;
    border-radius: 10px;
    padding: 8px 10px;
    background: #f8fafc;
    selection-background-color: #2563eb;
}

QPlainTextEdit#keywords {
    font-size: 10.5pt;
}

QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #2563eb;
    background: #ffffff;
}

QPushButton {
    border: 1px solid #cbd5e1;
    border-radius: 10px;
    padding: 9px 13px;
    background: #ffffff;
    color: #1f2937;
    font-weight: 700;
}

QPushButton:hover {
    background: #f1f5f9;
    border-color: #94a3b8;
}

QPushButton#primaryButton {
    background: #2563eb;
    border-color: #2563eb;
    color: #ffffff;
}

QPushButton#primaryButton:hover {
    background: #1d4ed8;
}

QPushButton:disabled {
    color: #94a3b8;
    background: #f1f5f9;
}

QCheckBox {
    color: #334155;
    font-weight: 650;
    spacing: 9px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 6px;
    border: 2px solid #94a3b8;
    background: #ffffff;
}

QCheckBox::indicator:checked {
    border: 2px solid #2563eb;
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.55, fx:0.5, fy:0.5, stop:0 #2563eb, stop:0.38 #2563eb, stop:0.42 #ffffff, stop:1 #ffffff);
}

QProgressBar {
    height: 12px;
    border: 0;
    border-radius: 6px;
    background: #e2e8f0;
    text-align: center;
}

QProgressBar::chunk {
    border-radius: 6px;
    background: #2563eb;
}

QTableWidget {
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    background: #ffffff;
    gridline-color: #e2e8f0;
    selection-background-color: #dbeafe;
}

QHeaderView::section {
    background: #f8fafc;
    border: 0;
    border-bottom: 1px solid #e2e8f0;
    padding: 9px;
    color: #475569;
    font-weight: 800;
}

QLabel#summary {
    color: #0f172a;
    font-size: 12pt;
    font-weight: 800;
}
"""


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_QSS)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
