import re
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *

class ValidationWorker(QThread):
    validationComplete = Signal(str, bool)  # message, has_issues
    findingsReady = Signal(list)  

    def __init__(self, prompt: str, parsed_data: dict, complexity: str = "Standard"):
        super().__init__()
        self.prompt = prompt
        self.parsed_data = parsed_data
        self.complexity = complexity


    def run(self):
        try:
            # 1. Physical local netlist validation
            netlist_ok = True
            physical_errors = []
            try:
                try:
                    from ECD.pin_model import compute_component_positions, generate_netlist, validate_netlist
                except ImportError:
                    from pin_model import compute_component_positions, generate_netlist, validate_netlist
                
                box_pos = compute_component_positions(self.parsed_data)
                netlist = generate_netlist(self.parsed_data, box_pos)
                netlist_ok, physical_errors = validate_netlist(netlist)
            except Exception as pe:
                # If physical parsing/layout itself crashes, that's a major issue!
                netlist_ok = False
                physical_errors = [f"Physical layout error: {pe}"]

            # 2. ERC (Electrical Rule Check) Tier 1 presence rules
            erc_findings = []
            try:
                try:
                    from ECD.erc import run_erc
                except ImportError:
                    from erc import run_erc
                erc_findings = run_erc(netlist, self.parsed_data)
            except Exception as ee:
                print(f"[ValidationWorker] ERC check error: {ee}")

            # 3. Semantic LLM validation (Ollama)
            try:
                from ECD.mermaid_generator import MermaidGenerator
            except ImportError:
                from mermaid_generator import MermaidGenerator
            self.mermaid_code = MermaidGenerator().generate_mermaid_code(self.parsed_data)

            complexity = self.complexity
            complexity_context = {
                "Simple": """COMPLEXITY: Simple mode is intentionally minimal.
- Only Phase (L) wire is shown. Neutral and Earth wires are deliberately hidden.
- No fault paths, no protection notes. This is expected and NOT a fault.
- Only validate: supply → breaker → loads chain integrity.""",

                "Neutral": """COMPLEXITY: Neutral / prompt-driven mode.
- The diagram contains ONLY what the user explicitly described. Nothing more is expected.
- Do NOT flag absent RCD, busbar, neutral bar, earth bar, fault paths, or outgoing MCBs
  unless the user specifically asked for them in their prompt.
- Do NOT flag missing protection notes or fault current paths — these are never expected here.
- ONLY flag: components the user asked for that are genuinely absent, or a broken
  supply → load chain (e.g. load with no upstream connection at all).""",

                "Standard": """COMPLEXITY: Standard mode shows L/N/E but has intentional omissions.
- Fault protection paths are deliberately excluded. Do NOT flag missing fault paths.
- Outgoing MCBs (branch breakers) are excluded by default, UNLESS the user explicitly requested a specific quantity or list of loads/circuits (e.g. 'three loads', '3 circuits', '4 motors'). If the user asked for N loads/circuits, flag if N outgoing breakers/loads are not present.
- Validate: supply → breaker → busbar → neutral bar → earth bar → loads connectivity.""",

                 "Detailed": """COMPLEXITY: Detailed mode is the full diagram.
- All components must be present: supply, main breaker, RCD, busbar, neutral bar, earth bar, outgoing MCBs, loads.
- RCD MUST appear between main breaker and busbar. Flag if missing (unless user explicitly excluded it).
- Fault path MUST route through RCD: EBar → RCD → MainCB trip. Flag if fault path skips RCD.
- Outgoing MCBs: if user named N specific circuits, expect N outgoing breaker nodes.
- Protection notes on main breaker and RCD MUST be present. Flag if missing.
- Validate everything strictly.
- Exception: if user said "no RCD" or "no fault path", do NOT flag their absence."""
            }.get(complexity, "")

            system_prompt = f"""You are an expert electrical diagram validator.
You will receive:
1. The user's original prompt
2. The complexity level and what it intentionally omits
3. The generated Mermaid sequence diagram code

{complexity_context}

Your job is to compare the user's intent against the Mermaid output and flag ONLY real problems:
- Components the user explicitly asked for but are missing (accounting for complexity omissions above)
- Logically incorrect electrical flow (e.g. load directly connected to supply with no breaker)
- Components present that the user never asked for
- In Detailed mode only: missing fault paths or protection notes

Do NOT flag components that are intentionally hidden by the complexity level.
Also, check if the diagram and circuit workflow practically makes sense or not. 
For example, if there is a load connected directly to the supply with no breaker, that is a real issue and should be flagged, even if the user didn't explicitly say "I want a breaker". The diagram must be logically correct as an electrical distribution system, not just contain the components mentioned by the user.

Respond in this exact format:
STATUS: OK or ISSUES_FOUND
FINDINGS:
- finding 1
- finding 2
(or write "None" if STATUS is OK)

Be concise. Only flag real problems."""

            llm_findings = []
            try:
                try:
                    from ECD.llm.ollama_client import OllamaClient
                except ImportError:
                    from llm.ollama_client import OllamaClient

                user_content = (
                    f"USER PROMPT:\n{self.prompt}\n\n"
                    f"MERMAID CODE:\n{self.mermaid_code}"
                )
                client = OllamaClient(model="mistral:7b-instruct")
                text = client.chat(system_prompt.strip(), user_content, max_tokens=512)
                text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

                is_ok = "STATUS: OK" in text or "STATUS:OK" in text
                findings_block = text.split("FINDINGS:")[-1].strip() if "FINDINGS:" in text else ""
                if is_ok:
                    llm_findings = []
                else:
                    llm_findings = [
                        line.lstrip("- ").strip()
                        for line in findings_block.splitlines()
                        if line.strip() and line.strip() != "None"
                    ]
            except Exception as e:
                # LLM unavailable or failed — proceed with physical and ERC findings
                print(f"[ValidationWorker] LLM semantic check skipped: {e}")

            # 4. Merge findings into 3 visually distinct sections
            all_finding_strings = []
            findings_sections = []

            if physical_errors:
                sec_lines = ["<b>⚡ Connectivity Errors (Netlist Graph):</b>"]
                sec_lines.extend(f"• {e}" for e in physical_errors)
                findings_sections.append("<br>".join(sec_lines))
                all_finding_strings.extend(physical_errors)

            if erc_findings:
                sec_lines = ["<b>🛡️ Electrical Rule Checks (ERC):</b>"]
                for f in erc_findings:
                    comp_info = f" ({', '.join(f.components)})" if f.components else ""
                    if f.severity == "ERROR":
                        sev_badge = "<span style='color:#9b2c2c; font-weight:bold;'>[ERROR]</span>"
                    elif f.severity == "WARNING":
                        sev_badge = "<span style='color:#b7791f; font-weight:bold;'>[WARNING]</span>"
                    else:
                        sev_badge = f"[{f.severity}]"
                    sec_lines.append(f"• <b>[{f.code}]</b> {sev_badge}{comp_info}: {f.message}")
                findings_sections.append("<br>".join(sec_lines))
                all_finding_strings.extend([f.message for f in erc_findings])

            if llm_findings:
                sec_lines = ["<b>🤖 AI Suggestions (Semantic Review):</b>"]
                sec_lines.extend(f"• {f}" for f in llm_findings)
                findings_sections.append("<br>".join(sec_lines))
                all_finding_strings.extend(llm_findings)

            has_issues = len(all_finding_strings) > 0
            
            # Format combined output response
            status_line = "STATUS: ISSUES_FOUND" if has_issues else "STATUS: OK"
            findings_text = "<br><br>".join(findings_sections) if findings_sections else "None"
            response_text = f"{status_line}\nFINDINGS:\n{findings_text}"
            
            self.validationComplete.emit(response_text, has_issues)
            if has_issues and all_finding_strings:
                self.findingsReady.emit(all_finding_strings)
        except Exception as e:
            self.validationComplete.emit(f"Validation error: {e}", True)


class MermaidFixWorker(QThread):
    """
    LLM #3: receives the current Mermaid code + validation findings and returns
    a corrected Mermaid code string.

    Rules enforced in the system prompt:
    - ONLY add missing participants / arrows. Never delete existing ones.
    - Return raw sequenceDiagram code only — no markdown fences, no explanation.
    - Preserve all existing participant aliases, box groupings, and arrow labels.
    """

    fixComplete = Signal(str)   # emits corrected mermaid code on success
    fixFailed   = Signal(str)   # emits error message on failure

    def __init__(
        self,
        mermaid_code: str,
        findings: list,
        prompt: str,
        complexity: str = "Standard",
    ):
        super().__init__()
        self.mermaid_code = mermaid_code
        self.findings     = findings
        self.prompt       = prompt
        self.complexity   = complexity

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _strip_fences(text: str) -> str:
        """Remove markdown code fences if the model wraps its output in them."""
        text = text.strip()
        # Strip ```mermaid ... ``` or ``` ... ```
        text = re.sub(r'^```[a-zA-Z]*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
        return text.strip()

    @staticmethod
    def _extract_mermaid(text: str) -> str:
        """
        Robustly extract a sequenceDiagram block from text that may have:
        - A prose preamble ("Here is the fixed code:\n...")
        - Markdown fences anywhere in the response (not just at start/end)
        - Bare code with no fences at all

        Strategy:
        1. Try to find a fenced block containing sequenceDiagram.
        2. If not found, extract from the first occurrence of 'sequenceDiagram' to end.
        3. If still not found, return the text as-is (caller will reject via _is_valid_mermaid).
        """
        # 1. Look for a fenced code block that contains sequenceDiagram
        fenced = re.search(
            r'```[a-zA-Z]*\n?(sequenceDiagram.*?)```',
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if fenced:
            return fenced.group(1).strip()

        # 2. Extract from the first 'sequenceDiagram' keyword onward
        idx = text.find("sequenceDiagram")
        if idx != -1:
            return text[idx:].strip()

        # 3. Return as-is — _is_valid_mermaid will reject it
        return text.strip()

    @staticmethod
    def _is_valid_mermaid(text: str) -> bool:
        """Minimal sanity check: must start with sequenceDiagram and have arrows."""
        return (
            text.strip().startswith("sequenceDiagram")
            and ("->>" in text or "-->" in text)
        )

    @staticmethod
    def _sanitize_labels(code: str) -> str:
        """
        Replace characters that are valid in Mermaid label strings but break
        Mermaid 10.x's parser when used in arrow labels or participant aliases.
        Called after fence-stripping, before the validity check.
        """
        # Fix lines with arrow labels: replace bare < > & with safe equivalents
        def _fix_arrow_line(m):
            prefix = m.group(1)   # e.g.  "    Supply->>MainCB: "
            label  = m.group(2)   # the label text after the colon
            label  = label.replace('&', 'and')
            label  = label.replace('<', '(').replace('>', ')')
            # Remove or replace em-dash (—) which some LLMs emit
            label  = label.replace('—', '-').replace('–', '-')
            return prefix + label

        # Match arrow lines: optional spaces, SRC->>/-->>DEST: LABEL
        code = re.sub(
            r'([ \t]*\w[\w ]*(?:->>|-->>)\w[\w ]*:[ \t]*)(.*)',
            _fix_arrow_line,
            code,
            flags=re.MULTILINE,
        )

        def _fix_note_over(m):
            prefix = m.group(1)          # "    Note over "
            participants = [p.strip() for p in m.group(2).split(',')]
            label = m.group(3)           # ": some text"
            if len(participants) > 2:
                return f"{prefix}{participants[0]},{participants[-1]}{label}"
            return m.group(0)

        code = re.sub(
            r'([ \t]*Note over )([\w ,]+?)(:.*)',
            _fix_note_over,
            code,
            flags=re.MULTILINE,
        )

        return code

    @staticmethod
    def _is_valid_mermaid(text: str) -> bool:
        """Minimal sanity check: must start with sequenceDiagram and have arrows."""
        stripped = text.strip()
        if not stripped.startswith("sequenceDiagram"):
            return False
        if "->>" not in stripped and "-->" not in stripped:
            return False
        # Mermaid 10.x requires autonumber to be on its own line (if present)
        for line in stripped.splitlines():
            line = line.strip()
            if line.startswith("autonumber") and len(line) > len("autonumber"):
                return False   # "autonumber 1" or "autonumber participant X" — both invalid
        return True

    # ── thread entry ──────────────────────────────────────────────────────────

    def run(self):
        findings_text = "\n".join(f"- {f}" for f in self.findings)

        complexity_rules = {
            "Simple":   "Only Phase (L) wire is shown. Do NOT add neutral, earth, RCD, or fault paths.",
            "Neutral":  "Add only what the original user prompt describes. Do not add standard defaults.",
            "Standard": "Do NOT add fault paths or outgoing MCBs. You may add supply, main breaker, RCD, busbar, neutral bar, earth bar, loads.",
            "Detailed": "You may add any missing electrical component required for a complete distribution diagram.",
        }.get(self.complexity, "")

        system_prompt = f"""You are an expert electrical diagram code editor for Mermaid sequenceDiagram syntax.

You will receive:
1. The user's original description of what they want
2. The current Mermaid sequenceDiagram code that was generated
3. A list of validation findings — problems found in the diagram

Your task is to fix the Mermaid code by addressing every finding listed.

=== STRICT RULES ===
1. NEVER remove or rename any existing participant, box, note, or arrow.
   Existing components may have been added by the complexity level and must be preserved.
2. ONLY add new participants and/or new arrows to fix the identified issues.
3. New participants must be added inside the correct box section (box...end block).
   - Components belonging to the distribution panel go inside the green box.
   - Load-side components go inside the orange box.
   - If a component does not fit an existing box, add it after the last end keyword
     as a standalone participant before the autonumber line.
4. New arrows must follow Mermaid sequenceDiagram syntax:
   - Solid arrow:  A->>B: label
   - Dashed arrow: A-->>B: label
5. Maintain logical electrical flow: supply → breaker → [rcd] → busbar → loads.
   New arrows must not violate this order.
6. Do NOT add components that the user explicitly excluded (e.g. "no RCD", "no neutral").
7. Complexity constraint for this diagram: {complexity_rules}

=== OUTPUT FORMAT ===
Return ONLY the corrected Mermaid sequenceDiagram code.
No explanation. No markdown fences. No preamble. Start with: sequenceDiagram"""

        user_content = (
            f"USER DESCRIPTION:\n{self.prompt}\n\n"
            f"VALIDATION FINDINGS TO FIX:\n{findings_text}\n\n"
            f"CURRENT MERMAID CODE:\n{self.mermaid_code}\n\n"
            f"FIXED MERMAID CODE:"
        )

        # ── Pre-flight: some findings can only be resolved by REMOVING components.
        # The fix worker is add-only, so we detect those cases and bail early
        # with a helpful message instead of sending a doomed prompt to the LLM.
        REMOVAL_KEYWORDS = [
            "should not", "must not", "must be removed", "should be removed",
            "not expected", "unwanted", "absent in simple", "should be absent",
            "fault path", "remove", "delete", "excess",
        ]
        add_only_impossible = all(
            any(kw in f.lower() for kw in REMOVAL_KEYWORDS)
            for f in self.findings
        ) and self.findings  # only trigger if there actually are findings

        if add_only_impossible:
            self.fixFailed.emit(
                "Fix Issues cannot resolve this automatically.\n\n"
                "The validator found components that should be removed (e.g. a fault path "
                "in Simple mode), but the fix engine can only add missing components — it "
                "cannot delete existing ones.\n\n"
                "Please regenerate the diagram using a lower complexity level, or remove "
                "the unwanted component from your prompt."
            )
            return

        try:
            try:
                from ECD.llm.ollama_client import OllamaClient
            except ImportError:
                from llm.ollama_client import OllamaClient

            client = OllamaClient(model="mistral:7b-instruct")
            raw = client.chat(system_prompt.strip(), user_content, max_tokens=1536)
            # Strip any <think>...</think> blocks (some reasoning models emit these)
            raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
            # Robustly extract the sequenceDiagram block from anywhere in the response
            fixed_code = self._extract_mermaid(raw)
            fixed_code = self._sanitize_labels(fixed_code)

            if not self._is_valid_mermaid(fixed_code):
                self.fixFailed.emit(
                    f"Fix worker returned invalid Mermaid output.\n\nRaw response:\n{raw[:400]}"
                )
                return

            self.fixComplete.emit(fixed_code)

        except Exception as e:
            self.fixFailed.emit(str(e))



class ValidationPanel(QWidget):
    fixRequested = Signal()   # emitted when user clicks "Fix Issues"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_findings: list = []
        self._build_ui()
        self.hide()

    def _build_ui(self):
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(4)

        header = QHBoxLayout()
        self.icon_lbl = QLabel("🔍")
        self.title_lbl = QLabel("Validating diagram…")
        self.title_lbl.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header.addWidget(self.icon_lbl)
        header.addWidget(self.title_lbl)
        header.addStretch()

        # Fix Issues button — enabled only when there are real findings
        self.fix_btn = QPushButton("🔧 Fix Issues")
        self.fix_btn.setFixedHeight(24)
        self.fix_btn.setEnabled(False)
        self.fix_btn.setStyleSheet("""
            QPushButton {
                background:#c53030;color:#fff;
                border:none;border-radius:4px;
                padding:2px 10px;font-size:11px;font-weight:bold;
            }
            QPushButton:hover   { background:#9b2c2c; }
            QPushButton:pressed { background:#742a2a; }
            QPushButton:disabled{ background:#cbd5e0;color:#718096; }
        """)
        self.fix_btn.setToolTip("Auto-patch the diagram to resolve the findings above")
        self.fix_btn.clicked.connect(self._on_fix_clicked)
        header.addWidget(self.fix_btn)

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.setStyleSheet("border:none; color:#718096; font-size:12px;")
        self.close_btn.clicked.connect(self.hide)
        header.addWidget(self.close_btn)
        lay.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; }
            QScrollBar:vertical { width: 0px; height: 0px; background: transparent; }
            QScrollBar::handle:vertical { width: 0px; height: 0px; background: transparent; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; width: 0px; }
        """)

        self.findings_lbl = QLabel("")
        self.findings_lbl.setWordWrap(True)
        self.findings_lbl.setFont(QFont("Arial", 9))
        self.findings_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        scroll.setWidget(self.findings_lbl)
        
        lay.addWidget(scroll)

        self.setStyleSheet("""
            ValidationPanel {
                border: 1px solid #93c5fd;
                border-radius: 6px;
                background: #bfdbfe;
            }
            QLabel {
                color: #1a202c;
                background: transparent;
            }
        """)
        self.setMinimumHeight(100)

    def set_findings(self, findings: list):
        """Store parsed findings so the Fix button can forward them."""
        self._current_findings = findings
        self.fix_btn.setEnabled(bool(findings))

    def _on_fix_clicked(self):
        self.fixRequested.emit()

    def show_loading(self):
        self.setStyleSheet("""
            ValidationPanel { border:1px solid #93c5fd; border-radius:6px; background:#bfdbfe; }
            QLabel { color:#1a202c; background:transparent; }
        """)
        self.icon_lbl.setText("🔍")
        self.title_lbl.setText("Validating diagram against prompt…")
        self.findings_lbl.setText("")
        self.fix_btn.setEnabled(False)
        self._current_findings = []
        self.show()

    def show_fixing(self):
        """Called when MermaidFixWorker starts — disables Fix button, shows progress."""
        self.setStyleSheet("""
            ValidationPanel { border:1px solid #93c5fd; border-radius:6px; background:#bfdbfe; }
            QLabel { color:#1a202c; background:transparent; }
        """)
        self.icon_lbl.setText("⏳")
        self.title_lbl.setText("Applying fixes via LLM…")
        self.findings_lbl.setText("The LLM is patching the diagram structure. This normally takes 10–15 seconds. Please wait.")
        self.fix_btn.setEnabled(False)
        self.show()

    def show_fix_error(self, error_msg: str):
        """Called when MermaidFixWorker fails."""
        self.setStyleSheet("""
            ValidationPanel { border:1px solid #93c5fd; border-radius:6px; background:#bfdbfe; }
            QLabel { color:#1a202c; background:transparent; }
        """)
        self.icon_lbl.setText("❌")
        self.title_lbl.setText("Fix failed")
        self.findings_lbl.setText(f"Could not apply fix: {error_msg[:200]}")
        self.fix_btn.setEnabled(bool(self._current_findings))  # re-enable so user can retry
        self.show()

    def show_result(self, text: str, has_issues: bool):
        self.setStyleSheet("""
            ValidationPanel { border:1px solid #93c5fd; border-radius:6px; background:#bfdbfe; }
            QLabel { color:#1a202c; background:transparent; }
        """)
        if has_issues:
            self.icon_lbl.setText("⚠️")
            self.title_lbl.setText("Potential issues found")
        else:
            self.icon_lbl.setText("✅")
            self.title_lbl.setText("Diagram looks good")
            self.fix_btn.setEnabled(False)

        findings = ""
        if "FINDINGS:" in text:
            findings = text.split("FINDINGS:")[-1].strip()
        self.findings_lbl.setText(findings if findings and findings != "None" else "")
        self.show()