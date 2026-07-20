# sidebar.py
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *
# from PyQt5.QtCore import QWIDGETSIZE_MAX


try:
    from ECD.constants import COMPLEXITY_LEVELS
except ImportError:
    from constants import COMPLEXITY_LEVELS


class NoScrollComboBox(QComboBox):
    """QComboBox that ignores mouse wheel events so sidebar scrolling is not intercepted."""
    def wheelEvent(self, event):
        event.ignore()


class Sidebar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(16)
        lay.setContentsMargins(22, 20, 22, 20)

        self._collapsed = False
        self._toggle_btn = QPushButton("◀ Hide")
        self._toggle_btn.setFixedHeight(24)
        self._toggle_btn.setStyleSheet(
            "QPushButton{background:#cbd5e0;border:none;border-radius:4px;"
            "font-size:11px;font-weight:bold;color:#2d3748;}"
            "QPushButton:hover{background:#a0aec0;}"
        )
        self._toggle_btn.clicked.connect(self._toggle_collapse)
        lay.addWidget(self._toggle_btn)

        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        content_lay = QVBoxLayout(self._content)
        content_lay.setSpacing(12)
        content_lay.setContentsMargins(4, 4, 4, 8)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.scroll_area.setWidget(self._content)
        lay.addWidget(self.scroll_area)

        self.setMinimumWidth(320)
        self.setMaximumWidth(400)   

        title = QLabel("Electrical Diagram Generator")
        title.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        title.setStyleSheet("color:#2c5282; margin-bottom:4px;")
        title.setWordWrap(True)
        content_lay.addWidget(title)

        content_lay.addWidget(QLabel("Diagram description:"))
        self.prompt_text = QTextEdit()
        self.prompt_text.setPlaceholderText(
            "Describe your electrical system…\n"
            "e.g. 'Main supply, breaker, busbar, neutral bar, earth bar, load circuits at 415V'"
        )
        self.prompt_text.setMinimumHeight(140)
        self.prompt_text.setMaximumHeight(220)
        self.prompt_text.setStyleSheet(
            "border:1px solid #cbd5e0; border-radius:5px; padding:6px; font-size:12px;"
            "color:#000000; background:#ffffff;"
        )
        content_lay.addWidget(self.prompt_text)

        detail_row = QHBoxLayout()
        detail_lbl = QLabel("Detail Level:")
        detail_lbl.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        detail_lbl.setStyleSheet("color:#2d3748;")
        detail_row.addWidget(detail_lbl)

        self.complexity_combo = NoScrollComboBox()
        self.complexity_combo.addItems(["Simple", "Neutral", "Standard", "Detailed"])
        self.complexity_combo.setCurrentText("Neutral")
        self.complexity_combo.setStyleSheet("""
            QComboBox {
                color: #ffffff;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 5px;
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: white;
            }
            QComboBox QAbstractItemView::item {
                color: #000000;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #e2e8f0;
                color: #000000;
            }
        """)
        self.complexity_combo.currentTextChanged.connect(self._on_complexity_changed)
        detail_row.addWidget(self.complexity_combo, 1)
        content_lay.addLayout(detail_row)

        self.complexity_hint = QLabel(COMPLEXITY_LEVELS["Standard"]["description"])
        self.complexity_hint.setFont(QFont("Arial", 9))
        self.complexity_hint.setStyleSheet("color:#718096; font-style:italic; margin-bottom:4px;")
        self.complexity_hint.setWordWrap(True)
        content_lay.addWidget(self.complexity_hint)

        content_lay.addWidget(QLabel("Quick templates:"))
        self.tmpl_combo = NoScrollComboBox()
        self.tmpl_combo.addItems([
            "Basic Distribution",
            "Industrial Panel",
            "Residential Board",
            "Three-Phase System",
            "Safety Earth System",
            "日本語: 基本的な配電",
        ])
        self.tmpl_combo.setStyleSheet("""
            QComboBox {
                color: #000000;
                background: #ffffff;
                border: 1px solid #cbd5e0;
                border-radius: 5px;
                padding: 4px 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #000000;
            }
        """)
        self.tmpl_combo.currentTextChanged.connect(self._load_template)
        content_lay.addWidget(self.tmpl_combo)

        gen_btn = QPushButton("⚡  Generate Diagram")
        gen_btn.setStyleSheet("""
            QPushButton {background:#2c5282;color:#fff;border:none;border-radius:6px;
                         padding:10px;font-weight:bold;font-size:12px;margin-top:8px;}
            QPushButton:hover {background:#2a4365;}
            QPushButton:pressed {background:#1a365d;}
        """)
        gen_btn.clicked.connect(self._generate)
        content_lay.addWidget(gen_btn)

        self.reset_view_btn = QPushButton("🔍  Reset View")
        self.reset_view_btn.setStyleSheet("""
            QPushButton {background:#4a5568;color:#fff;border:none;border-radius:6px;
                         padding:8px;font-size:12px;margin-top:4px;}
            QPushButton:hover {background:#2d3748;}
            QPushButton:disabled {background:#cbd5e0;color:#718096;}
        """)
        self.reset_view_btn.clicked.connect(self._reset_view)
        content_lay.addWidget(self.reset_view_btn)

        self.reset_btn = QPushButton("↺  Revert to Original")
        self.reset_btn.setStyleSheet("""
            QPushButton {background:#63b3ed;color:#fff;border:none;border-radius:6px;
                         padding:8px;font-size:12px;margin-top:4px;}
            QPushButton:hover {background:#4299e1;}
            QPushButton:disabled {background:#cbd5e0;color:#718096;}
        """)
        self.reset_btn.clicked.connect(self._reset)
        self.reset_btn.setEnabled(False)
        content_lay.addWidget(self.reset_btn)

        content_lay.addStretch()

        hint = QLabel(
            "💡 Double-click any text to edit it in-place."
        )
        hint.setFont(QFont("Arial", 9))
        hint.setStyleSheet("color:#718096; margin-top:10px;")
        hint.setWordWrap(True)
        content_lay.addWidget(hint)

        self.setMinimumWidth(320)
        self.setMaximumWidth(400)
        self.setObjectName("SidebarRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "#SidebarRoot{background:#f7fafc;border:1px solid #e2e8f0;border-radius:14px;}"
            "QLabel{color:#2d3748;}"
        )

        self._update_complexity_style("Neutral")

    def _toggle_collapse(self):
        self._collapsed = not self._collapsed
        self._content.setVisible(not self._collapsed)
        if self._collapsed:
            self.layout().setContentsMargins(4, 12, 4, 12)
            self.setFixedWidth(40)
            self._toggle_btn.setText("▶")
        else:
            self.layout().setContentsMargins(22, 20, 22, 20)
            self.setMinimumWidth(320)
            self.setMaximumWidth(400)
            self._toggle_btn.setText("◀ Hide")

    def _on_complexity_changed(self, level: str):
        self.complexity_hint.setText(COMPLEXITY_LEVELS["Neutral"]["description"])
        self._update_complexity_style(level)

    def _update_complexity_style(self, level: str):
        colors = {"Neutral":  "#f59e0b", "Simple": "#10b981", "Standard": "#3b82f6", "Detailed": "#8b5cf6"}
        c = colors.get(level, "#f59e0b")
        self.complexity_combo.setStyleSheet(f"""
            QComboBox {{
                color: #000000;
                background: {c};
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 5px;
                border: none;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{ color: #000; background: #fff; }}
        """)

    def _load_template(self, name):
        templates = {
            "Basic Distribution": "Main incoming supply at 415V, main circuit breaker, busbar distribution, neutral bar, earth bar, and load circuits for lights and sockets.",
            "Industrial Panel":   "Three-phase 415V incoming supply, main MCCB breaker, copper busbar system, multiple outgoing MCBs for motors, neutral bar and earth bar.",
            "Residential Board":  "Single-phase 230V supply, main MCB, individual circuit breakers for lighting, power sockets, kitchen appliances, with safety earth.",
            "Three-Phase System": "Three-phase RYB supply at 415V, main breaker, busbar distribution, balanced load circuits, neutral return path, protective earth.",
            "Safety Earth System":"Electrical safety diagram focused on earthing: main earth bar connections, circuit protective conductors, equipment earth points, neutral bar.",
            "日本語: 基本的な配電": "主電源230V/415V、メインブレーカー、バスバー、中性線バー、接地バー、照明とコンセントの負荷回路を含む基本的な電力配電図。",
        }
        if name in templates:
            self.prompt_text.setPlainText(templates[name])

    def _generate(self):
        prompt = self.prompt_text.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Empty Prompt", "Please enter a diagram description.")
            return
        complexity = self.complexity_combo.currentText()
        if hasattr(self.main_window, 'canvas'):
            self.main_window.canvas.generate_from_prompt(prompt, complexity)
            # reset_btn is re-enabled by _finalise_generation once the diagram is ready

    def _reset_view(self):
        if hasattr(self.main_window, 'canvas') and self.main_window.canvas:
            self.main_window.canvas.reset_view()

    def _reset(self):
        if hasattr(self.main_window, 'canvas') and self.main_window.canvas:
            self.main_window.canvas.revert_to_original()
