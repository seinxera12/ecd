"""
ECD/settings_page.py
====================
Built-in Application Settings UI for configuring Groq and Gemini cloud API keys.
Styled with the unified #1a202c dark slate theme matching Instructions & About panels.
"""

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont

# Build-time constant for default developer credential bundling
HAS_BUNDLED_DEFAULTS = True


class TestConnectionWorker(QThread):
    """Background worker for lightweight non-blocking API key test connection calls."""
    result = Signal(bool, str)

    def __init__(self, groq_key: str, gemini_key: str):
        super().__init__()
        self.groq_key = groq_key
        self.gemini_key = gemini_key

    def run(self):
        statuses = []
        all_ok = True

        import requests

        # Test Groq Key if provided
        if self.groq_key:
            try:
                resp = requests.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {self.groq_key}"},
                    timeout=10
                )
                if resp.status_code == 200:
                    statuses.append("Groq API: Connected")
                elif resp.status_code == 401:
                    statuses.append("Groq API: Invalid Key")
                    all_ok = False
                elif resp.status_code == 429:
                    statuses.append("Groq API: Rate Limited (Network OK)")
                else:
                    statuses.append(f"Groq API: HTTP {resp.status_code}")
                    all_ok = False
            except Exception as e:
                statuses.append(f"Groq API: Connection error ({str(e)})")
                all_ok = False
        else:
            statuses.append("Groq API Key: Not provided")

        # Test Gemini Key if provided
        if self.gemini_key:
            try:
                resp = requests.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={self.gemini_key}",
                    timeout=10
                )
                if resp.status_code == 200:
                    statuses.append("Gemini API: Connected")
                elif resp.status_code in (400, 403):
                    statuses.append("Gemini API: Invalid Key")
                    all_ok = False
                elif resp.status_code == 429:
                    statuses.append("Gemini API: Quota/Rate Limited (Network OK)")
                else:
                    statuses.append(f"Gemini API: HTTP {resp.status_code}")
                    all_ok = False
            except Exception as e:
                statuses.append(f"Gemini API: Connection error ({str(e)})")
                all_ok = False
        else:
            statuses.append("Gemini API Key: Not provided")

        self.result.emit(all_ok, " | ".join(statuses))


class SettingsPage(QDialog):
    """Application Settings Dialog containing Groq and Gemini API credentials."""

    settings_saved = Signal()

    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self._test_worker = None

        self.setWindowTitle("ECD Application Settings")
        self.setFixedWidth(540)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a202c;
                color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                color: #ffffff;
            }
            QLineEdit {
                border: 1px solid #4a5568;
                border-radius: 6px;
                padding: 7px 10px;
                background-color: #1a202c;
                color: #ffffff;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #3182ce;
            }
            QPushButton {
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: bold;
                font-size: 12px;
            }
        """)

        self._build_ui()
        self.load_from_config()

    def _build_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setSpacing(14)
        main_lay.setContentsMargins(20, 20, 20, 20)

        # ── Header ──
        header_lbl = QLabel("Application Settings")
        header_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header_lbl.setStyleSheet("color: #ffffff; margin-bottom: 0px;")
        main_lay.addWidget(header_lbl)

        sub_lbl = QLabel("Manage your Groq and Gemini cloud API keys.")
        sub_lbl.setFont(QFont("Segoe UI", 9))
        sub_lbl.setStyleSheet("color: #a0aec0; margin-bottom: 2px;")
        main_lay.addWidget(sub_lbl)

        # ── Single Unified Card Container ──
        card_box = QFrame()
        card_box.setStyleSheet("""
            QFrame {
                background-color: #2d3748;
                border: 1px solid #4a5568;
                border-radius: 10px;
            }
        """)
        card_lay = QVBoxLayout(card_box)
        card_lay.setSpacing(12)
        card_lay.setContentsMargins(18, 16, 18, 16)

        card_title = QLabel("Cloud API Credentials")
        card_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        card_title.setStyleSheet("color: #63b3ed; border: none;")
        card_lay.addWidget(card_title)

        # Groq API Key
        groq_lbl = QLabel("Groq API Key:")
        groq_lbl.setStyleSheet("border: none; font-weight: bold; color: #e2e8f0;")
        card_lay.addWidget(groq_lbl)

        groq_row = QHBoxLayout()
        groq_row.setSpacing(8)
        self.groq_key_edit = QLineEdit()
        self.groq_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.groq_key_edit.setPlaceholderText("gsk_...")
        self.groq_toggle_btn = QPushButton("Show")
        self.groq_toggle_btn.setStyleSheet("""
            QPushButton { background: #4a5568; color: #ffffff; border: 1px solid #718096; padding: 6px 12px; }
            QPushButton:hover { background: #2d3748; }
        """)
        self.groq_toggle_btn.clicked.connect(lambda: self._toggle_echo(self.groq_key_edit, self.groq_toggle_btn))
        groq_row.addWidget(self.groq_key_edit)
        groq_row.addWidget(self.groq_toggle_btn)
        card_lay.addLayout(groq_row)

        # Gemini API Key
        gemini_lbl = QLabel("Gemini API Key:")
        gemini_lbl.setStyleSheet("border: none; font-weight: bold; color: #e2e8f0; margin-top: 4px;")
        card_lay.addWidget(gemini_lbl)

        gemini_row = QHBoxLayout()
        gemini_row.setSpacing(8)
        self.gemini_key_edit = QLineEdit()
        self.gemini_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key_edit.setPlaceholderText("AIza...")
        self.gemini_toggle_btn = QPushButton("Show")
        self.gemini_toggle_btn.setStyleSheet("""
            QPushButton { background: #4a5568; color: #ffffff; border: 1px solid #718096; padding: 6px 12px; }
            QPushButton:hover { background: #2d3748; }
        """)
        self.gemini_toggle_btn.clicked.connect(lambda: self._toggle_echo(self.gemini_key_edit, self.gemini_toggle_btn))
        gemini_row.addWidget(self.gemini_key_edit)
        gemini_row.addWidget(self.gemini_toggle_btn)
        card_lay.addLayout(gemini_row)

        # Subtle divider inside card
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #4a5568; border: none; max-height: 1px; margin-top: 4px; margin-bottom: 4px;")
        card_lay.addWidget(line)

        # Test Credentials Connection (Integrated directly inside the card)
        test_row = QHBoxLayout()
        test_row.setSpacing(8)
        self.test_btn = QPushButton("🔗  Test Credentials Connection")
        self.test_btn.setStyleSheet("""
            QPushButton { background: #3182ce; color: #ffffff; border: none; padding: 7px 14px; }
            QPushButton:hover { background: #2b6cb0; }
            QPushButton:disabled { background: #4a5568; color: #a0aec0; }
        """)
        self.test_btn.clicked.connect(self._on_test_connection)
        test_row.addWidget(self.test_btn)
        test_row.addStretch()
        card_lay.addLayout(test_row)

        self.test_status_lbl = QLabel("")
        self.test_status_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.test_status_lbl.setWordWrap(True)
        self.test_status_lbl.setStyleSheet("border: none; color: #e2e8f0;")
        card_lay.addWidget(self.test_status_lbl)

        main_lay.addWidget(card_box)

        # Inline Error Banner for Validation
        self.error_banner = QLabel("")
        self.error_banner.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.error_banner.setStyleSheet("""
            QLabel {
                color: #fff5f5;
                background: #742a2a;
                border: 1px solid #e53e3e;
                border-radius: 6px;
                padding: 8px 12px;
            }
        """)
        self.error_banner.setWordWrap(True)
        self.error_banner.setVisible(False)
        main_lay.addWidget(self.error_banner)

        # ── Action Buttons Footer ──
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(10)

        # Restore Defaults Button (Gated by HAS_BUNDLED_DEFAULTS)
        self.restore_btn = QPushButton("↺  Restore Default Settings")
        self.restore_btn.setStyleSheet("""
            QPushButton { background: #2d3748; color: #e2e8f0; border: 1px solid #4a5568; }
            QPushButton:hover { background: #4a5568; color: #ffffff; }
            QPushButton:disabled { background: #1a202c; color: #718096; border-color: #2d3748; }
        """)
        self.restore_btn.clicked.connect(self._on_restore_defaults)
        if not HAS_BUNDLED_DEFAULTS:
            self.restore_btn.setVisible(False)
            self.restore_btn.setEnabled(False)
        btn_bar.addWidget(self.restore_btn)

        btn_bar.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("""
            QPushButton { background: #4a5568; color: #ffffff; border: none; }
            QPushButton:hover { background: #2d3748; }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        btn_bar.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("💾  Save Settings")
        self.save_btn.setStyleSheet("""
            QPushButton { background: #3182ce; color: #ffffff; border: none; }
            QPushButton:hover { background: #2b6cb0; }
        """)
        self.save_btn.clicked.connect(self._on_save)
        btn_bar.addWidget(self.save_btn)

        main_lay.addLayout(btn_bar)

    # ── Helpers & State Management ──

    def _toggle_echo(self, edit_widget: QLineEdit, btn_widget: QPushButton):
        if edit_widget.echoMode() == QLineEdit.EchoMode.Password:
            edit_widget.setEchoMode(QLineEdit.EchoMode.Normal)
            btn_widget.setText("Hide")
        else:
            edit_widget.setEchoMode(QLineEdit.EchoMode.Password)
            btn_widget.setText("Show")

    def load_from_config(self):
        if self.config_manager:
            self.groq_key_edit.setText(self.config_manager.groq_key())
            self.gemini_key_edit.setText(self.config_manager.gemini_key())

    def get_form_credentials(self) -> dict:
        return {
            "groq_api_key": self.groq_key_edit.text().strip(),
            "gemini_api_key": self.gemini_key_edit.text().strip(),
        }

    # ── Test Connection ──

    def _on_test_connection(self):
        self.error_banner.setVisible(False)
        groq_k = self.groq_key_edit.text().strip()
        gemini_k = self.gemini_key_edit.text().strip()

        if not groq_k and not gemini_k:
            self.test_status_lbl.setText("No API keys entered to test.")
            self.test_status_lbl.setStyleSheet("color: #a0aec0; font-weight: bold; border: none;")
            return

        self.test_btn.setEnabled(False)
        self.test_btn.setText("⏳ Testing Connection...")
        self.test_status_lbl.setText("Testing API credentials...")
        self.test_status_lbl.setStyleSheet("color: #a0aec0; border: none;")

        self._test_worker = TestConnectionWorker(groq_k, gemini_k)
        self._test_worker.result.connect(self._on_test_result)
        self._test_worker.start()

    def _on_test_result(self, success: bool, msg: str):
        self.test_btn.setEnabled(True)
        self.test_btn.setText("🔗  Test Credentials Connection")
        if success:
            self.test_status_lbl.setText(msg)
            self.test_status_lbl.setStyleSheet("color: #68d391; font-weight: bold; border: none;")
        else:
            self.test_status_lbl.setText(f"Result: {msg}")
            self.test_status_lbl.setStyleSheet("color: #feb2b2; font-weight: bold; border: none;")

    # ── Validation & Save ──

    def _on_save(self):
        self.error_banner.setVisible(False)
        creds = self.get_form_credentials()

        # Save via ConfigManager
        if self.config_manager:
            ok, err = self.config_manager.save_config(creds)
            if not ok:
                self._show_validation_error(f"Failed to save settings: {err}")
                return

        self.settings_saved.emit()
        self.accept()

    def _show_validation_error(self, msg: str):
        self.error_banner.setText(f"Validation Error: {msg}")
        self.error_banner.setVisible(True)

    def _on_restore_defaults(self):
        if not HAS_BUNDLED_DEFAULTS:
            return

        res = QMessageBox.question(
            self,
            "Restore Default Settings",
            "Are you sure you want to restore default developer settings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if res == QMessageBox.StandardButton.Yes:
            if self.config_manager:
                self.config_manager.restore_defaults()
                self.load_from_config()
                self.test_status_lbl.setText("Default settings restored.")
                self.test_status_lbl.setStyleSheet("color: #63b3ed; border: none;")
