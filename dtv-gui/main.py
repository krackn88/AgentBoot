#!/usr/bin/env python3
"""Standalone DirectTV checker GUI."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QThread
from PyQt6.QtGui import QAction, QFont, QGuiApplication
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from dtv.checker import check_account, parse_combo
from dtv.proxy import parse_proxy, parse_proxy_lines
from worker import CheckerWorker

APP_STYLE = """
QMainWindow, QWidget { background: #f0f3f8; color: #1a2332; }
QGroupBox {
    font-weight: 600; border: 1px solid #d8dee9; border-radius: 10px;
    margin-top: 12px; padding-top: 14px; background: #ffffff;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
QTextEdit, QLineEdit, QListWidget {
    background: #f7f9fc; border: 1px solid #d8dee9; border-radius: 8px;
    padding: 8px; font-family: "Consolas", "Courier New", monospace; font-size: 12px;
}
QPushButton {
    background: #ffffff; border: 1px solid #d8dee9; border-radius: 8px;
    padding: 8px 14px; font-weight: 600;
}
QPushButton:hover { background: #eef4ff; border-color: #0066cc; }
QPushButton#primary { background: #0066cc; color: white; border-color: #0066cc; }
QPushButton#primary:hover { background: #0052a3; }
QPushButton#danger { background: #fdecef; color: #dc3545; border-color: #f0c8cf; }
QLabel#statValue { font-size: 20px; font-weight: 700; }
QLabel#statLabel { color: #64748b; font-size: 11px; font-weight: 600; }
"""


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DTV Checker")
        self.resize(1180, 760)
        self._worker: CheckerWorker | None = None
        self._smoke_thread: QThread | None = None
        self._combo_file: Path | None = None

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        stats = QHBoxLayout()
        self.stat_labels = {}
        for key, title in [
            ("progress", "Progress"),
            ("hits", "Hits"),
            ("cpm", "CPM"),
            ("bads", "Invalid"),
            ("fails", "Inactive"),
            ("errors", "Errors"),
        ]:
            box = QVBoxLayout()
            label = QLabel(title)
            label.setObjectName("statLabel")
            value = QLabel("0")
            value.setObjectName("statValue")
            box.addWidget(label)
            box.addWidget(value)
            stats.addLayout(box)
            self.stat_labels[key] = value
        layout.addLayout(stats)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)

        combo_box = QGroupBox("Combos")
        combo_layout = QVBoxLayout(combo_box)
        self.combo_edit = QTextEdit()
        self.combo_edit.setPlaceholderText("email@example.com:password123")
        combo_layout.addWidget(self.combo_edit)
        combo_btns = QHBoxLayout()
        load_combo_btn = QPushButton("Load file")
        load_combo_btn.clicked.connect(self.load_combo_file)
        clear_combo_btn = QPushButton("Clear")
        clear_combo_btn.clicked.connect(self.combo_edit.clear)
        combo_btns.addWidget(load_combo_btn)
        combo_btns.addWidget(clear_combo_btn)
        combo_btns.addStretch()
        combo_layout.addLayout(combo_btns)
        self.combo_file_label = QLabel("No file loaded")
        self.combo_file_label.setStyleSheet("color:#64748b;font-size:11px;")
        combo_layout.addWidget(self.combo_file_label)
        left_layout.addWidget(combo_box)

        proxy_box = QGroupBox("Proxies")
        proxy_layout = QVBoxLayout(proxy_box)
        self.proxy_edit = QTextEdit()
        self.proxy_edit.setPlaceholderText("host:port:user:pass")
        self.proxy_edit.setMaximumHeight(90)
        proxy_layout.addWidget(self.proxy_edit)
        left_layout.addWidget(proxy_box)

        smoke_box = QGroupBox("Smoke test")
        smoke_layout = QVBoxLayout(smoke_box)
        self.smoke_edit = QLineEdit()
        self.smoke_edit.setPlaceholderText("email@example.com:password123")
        smoke_layout.addWidget(self.smoke_edit)
        smoke_btn = QPushButton("Run smoke test")
        smoke_btn.clicked.connect(self.run_smoke_test)
        smoke_layout.addWidget(smoke_btn)
        self.smoke_result = QLabel("")
        self.smoke_result.setWordWrap(True)
        self.smoke_result.setStyleSheet("font-family:monospace;font-size:11px;")
        smoke_layout.addWidget(self.smoke_result)
        left_layout.addWidget(smoke_box)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Threads"))
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 50)
        self.threads_spin.setValue(5)
        controls.addWidget(self.threads_spin)
        self.start_btn = QPushButton("Start")
        self.start_btn.setObjectName("primary")
        self.start_btn.clicked.connect(self.start_job)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("danger")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_job)
        controls.addWidget(self.start_btn)
        controls.addWidget(self.stop_btn)
        controls.addStretch()
        left_layout.addLayout(controls)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)

        hits_box = QGroupBox("Hits (active only)")
        hits_layout = QVBoxLayout(hits_box)
        hit_btns = QHBoxLayout()
        copy_sel_btn = QPushButton("Copy selected")
        copy_sel_btn.clicked.connect(self.copy_selected_hits)
        copy_all_btn = QPushButton("Copy all")
        copy_all_btn.clicked.connect(self.copy_all_hits)
        delete_sel_btn = QPushButton("Delete selected")
        delete_sel_btn.setObjectName("danger")
        delete_sel_btn.clicked.connect(self.delete_selected_hits)
        clear_hits_btn = QPushButton("Clear")
        clear_hits_btn.clicked.connect(self.hits_list.clear)
        hit_btns.addWidget(copy_sel_btn)
        hit_btns.addWidget(copy_all_btn)
        hit_btns.addWidget(delete_sel_btn)
        hit_btns.addWidget(clear_hits_btn)
        hit_btns.addStretch()
        hits_layout.addLayout(hit_btns)
        self.hits_list = QListWidget()
        self.hits_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        hits_layout.addWidget(self.hits_list)
        right_layout.addWidget(hits_box, stretch=2)

        log_box = QGroupBox("Live log")
        log_layout = QVBoxLayout(log_box)
        log_btns = QHBoxLayout()
        clear_log_btn = QPushButton("Clear log")
        clear_log_btn.clicked.connect(self.log_edit.clear)
        log_btns.addWidget(clear_log_btn)
        log_btns.addStretch()
        log_layout.addLayout(log_btns)
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        log_layout.addWidget(self.log_edit)
        right_layout.addWidget(log_box, stretch=1)

        splitter.addWidget(right)
        splitter.setSizes([420, 760])
        layout.addWidget(splitter)

        menu = self.menuBar().addMenu("File")
        export_action = QAction("Export hits...", self)
        export_action.triggered.connect(self.export_hits)
        menu.addAction(export_action)

    def append_log(self, text: str) -> None:
        self.log_edit.append(text)
        bar = self.log_edit.verticalScrollBar()
        bar.setValue(bar.maximum())

    def update_stats(self, data: dict) -> None:
        total = data.get("total", 0)
        checked = data.get("checked", 0)
        self.stat_labels["progress"].setText(f"{checked} / {total}")
        self.stat_labels["hits"].setText(str(data.get("hits", 0)))
        self.stat_labels["cpm"].setText(str(data.get("cpm", 0)))
        self.stat_labels["bads"].setText(str(data.get("bads", 0)))
        self.stat_labels["fails"].setText(str(data.get("fails", 0)))
        self.stat_labels["errors"].setText(str(data.get("errors", 0)))

    def proxy_lines(self) -> list[str]:
        return [line.strip() for line in self.proxy_edit.toPlainText().splitlines() if line.strip()]

    def load_combo_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load combos", "", "Text files (*.txt *.csv)")
        if not path:
            return
        self._combo_file = Path(path)
        self.combo_file_label.setText(f"Loaded: {self._combo_file.name}")
        self.combo_edit.clear()
        self.combo_edit.setPlaceholderText(f"Using file: {self._combo_file.name}")

    def _parse_combos_from_text(self) -> list[tuple[str, str]]:
        combos = []
        for line in self.combo_edit.toPlainText().splitlines():
            parsed = parse_combo(line)
            if parsed:
                combos.append(parsed)
        return combos

    def start_job(self) -> None:
        if self._worker and self._worker.isRunning():
            return

        text_combos = self._parse_combos_from_text()
        combo_file = self._combo_file
        if not text_combos and (combo_file is None or not combo_file.exists()):
            QMessageBox.warning(self, "DTV Checker", "Add combos or load a combo file.")
            return

        proxies = self.proxy_lines()
        parsed, invalid = parse_proxy_lines(proxies)
        if invalid and not parsed:
            QMessageBox.warning(self, "DTV Checker", "All proxy lines are invalid.")
            return

        self.log_edit.clear()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        use_file = combo_file if combo_file and combo_file.exists() and not text_combos else None
        use_combos = text_combos if text_combos else None

        self._worker = CheckerWorker(
            combos=use_combos,
            combo_file=use_file,
            proxies=proxies,
            threads=self.threads_spin.value(),
        )
        self._worker.signals.log.connect(self.append_log)
        self._worker.signals.stats.connect(self.update_stats)
        self._worker.signals.hit.connect(self.add_hit)
        self._worker.signals.finished.connect(self.on_job_finished)
        self._worker.start()

    def stop_job(self) -> None:
        if self._worker:
            self._worker.stop()
            self.append_log("Stopping...")

    def on_job_finished(self) -> None:
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def add_hit(self, line: str) -> None:
        self.hits_list.addItem(QListWidgetItem(line))

    def copy_selected_hits(self) -> None:
        lines = [item.text() for item in self.hits_list.selectedItems()]
        if lines:
            QGuiApplication.clipboard().setText("\n".join(lines))

    def copy_all_hits(self) -> None:
        lines = [self.hits_list.item(i).text() for i in range(self.hits_list.count())]
        if lines:
            QGuiApplication.clipboard().setText("\n".join(lines))

    def delete_selected_hits(self) -> None:
        for item in self.hits_list.selectedItems():
            row = self.hits_list.row(item)
            self.hits_list.takeItem(row)

    def export_hits(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export hits", "hits.txt", "Text files (*.txt)")
        if not path:
            return
        lines = [self.hits_list.item(i).text() for i in range(self.hits_list.count())]
        Path(path).write_text("\n".join(lines), encoding="utf-8")

    def run_smoke_test(self) -> None:
        combo_line = self.smoke_edit.text().strip()
        if not combo_line:
            combo_line = next(
                (line.strip() for line in self.combo_edit.toPlainText().splitlines() if line.strip()),
                "",
            )
        if not combo_line:
            QMessageBox.warning(self, "Smoke test", "Enter a smoke test combo.")
            return

        parsed = parse_combo(combo_line)
        if not parsed:
            QMessageBox.warning(self, "Smoke test", "Combo must be email:password")
            return

        email, password = parsed
        proxy = None
        proxy_lines = self.proxy_lines()
        if proxy_lines:
            try:
                parsed_proxies, _ = parse_proxy_lines(proxy_lines)
                if parsed_proxies:
                    proxy = parsed_proxies[0]
            except ValueError:
                pass

        self.smoke_result.setText("Testing...")
        self.smoke_result.setStyleSheet("color:#64748b;font-family:monospace;font-size:11px;")

        class SmokeThread(QThread):
            def __init__(self, email, password, proxy):
                super().__init__()
                self.email = email
                self.password = password
                self.proxy = proxy
                self.result_line = ""
                self.ok = False

            def run(self):
                result = check_account(self.email, self.password, proxy=self.proxy, timeout=60)
                self.result_line = result.format_line()
                self.ok = result.status == "HIT"

        thread = SmokeThread(email, password, proxy)
        self._smoke_thread = thread

        def done():
            color = "#0d9f6e" if thread.ok else "#dc3545"
            self.smoke_result.setStyleSheet(f"color:{color};font-family:monospace;font-size:11px;")
            self.smoke_result.setText(thread.result_line)
            self.append_log(f"[smoke] {thread.result_line}")

        thread.finished.connect(done)
        thread.start()


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = QFont("Segoe UI", 10)
    if sys.platform.startswith("linux"):
        font = QFont("Ubuntu", 10)
    app.setFont(font)
    app.setStyleSheet(APP_STYLE)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
