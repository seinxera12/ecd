import re
import json
import os
try:
    from ECD.constants import COMPLEXITY_LEVELS
except ImportError:
    from constants import COMPLEXITY_LEVELS



class MermaidGenerator:
    def __init__(self):
        self.components_map = {
            "main incoming supply": {"en": "Main Incoming Supply<br/>(230V / 415V)", "ja": "主電源<br/>(230V / 415V)"},
            "main breaker": {"en": "Main Breaker<br/>(MCB/MCCB)", "ja": "主遮断器<br/>(MCB/MCCB)"},
            "rcd": {"en": "RCD<br/>(Earth Fault Protection)", "ja": "漏電遮断器<br/>(RCD/RCBO)"},
            "busbar": {"en": "Busbar<br/>(Distribution)", "ja": "母線<br/>(配電)"},
            "neutral bar": {"en": "NBar", "ja": "中性線バー"},
            "earth bar": {"en": "EBar", "ja": "接地バー"},
            "outgoing mcbs": {"en": "Outgoing MCBs", "ja": "出力MCB"},
            "load circuits": {"en": "Load Circuits<br/>(Lights, Sockets)", "ja": "負荷回路<br/>(照明、コンセント)"},
        }
        self.keywords_map = {
            "incoming": {
                "en": [
                    "incoming", "supply", "source", "230v", "415v", "mains", "grid", "utility", "infeed", "line in",
                    "three-phase", "3-phase", "three phase", "3phase", "ryb", "ryw", "rst", "uvw",
                    "single-phase", "1-phase", "single phase",
                ],
                "ja": [
                    "主電源", "受電", "電源", "入力電源",
                    "三相", "単相", "系統",
                ],
            },            
            "breaker": {
                "en": [
                    "breaker", "mcb", "mccb", "protection", "circuit breaker", "main cb", "main breaker",
                    "isolator", "isolating switch", "main switch", "elcb",
                    "fuse", "fuse switch", "switch fuse", "acb", "vcb", "contactor",
                ],
                "ja": [
                    "遮断器", "ブレーカー", "ブレーカ",
                    "主開閉器", "漏電遮断器", "配線用遮断器",
                    "ヒューズ", "開閉器",
                ],
            },

            "rcd": {
                "en": ["rcd", "rcbo", "elcb", "residual current", "earth fault", "leakage",
                    "earth leakage", "ground fault", "residual", "30ma", "100ma", "300ma"],
                "ja": ["漏電遮断器", "漏電ブレーカー", "漏電", "地絡", "残留電流"],
            },

            "busbar": {
                "en": [
                    "busbar", "distribution", "panel", "bus bar", "bus-bar", "copper bar", "copper strip", 
                    "db", "distribution board", "distribution box", "switchboard", "switchgear", "mdb", "pcc", "mcc",                                 
                ],
                "ja": [
                    "母線", "バスバー", "配電盤", "分電盤",
                    "銅バー", "主幹", "盤",
                ],
            },            
            
            "neutral": {
                "en": [
                    "neutral", "return",
                    "neutral bar", "n bar", "n-bar",
                    "neutral link", "neutral terminal",
                    "neutral bus", "common neutral",
                    "neutral return", "return path",
                    # three-phase star point terms
                    "star point", "centre point",
                ],
                "ja": [
                    "中性線", "ニュートラル", "零線", "N線",
                    "中性点", "中性線バー",
                ],
            },            

            "earth": {
                "en": [
                    "earth", "ground", "safety",
                    "earth bar", "e bar", "e-bar",
                    "earthing", "grounding",
                    "protective earth", "pe",
                    "cpc", "safety earth", "protective conductor",
                    "bonding", "equipotential bonding",
                    "earth terminal", "earth bus",
                    "chassis earth", "frame earth",
                ],
                "ja": [
                    "接地", "アース", "グラウンド", "地線",
                    "保護接地", "接地バー", "PE線",
                ],
            }, 

            "outgoing": {
                "en": [
                    "outgoing", "branch", "circuit",
                    "sub breaker", "sub-breaker", "sub mcb",
                    "outgoing mcb", "outgoing breaker",
                    "final circuit", "branch circuit",
                    "feeder", "sub feeder",
                    "downstream breaker", "individual breaker",
                    "motor breaker", "lighting breaker",
                ],
                "ja": [
                    "出力", "分岐", "回路",
                    "分岐ブレーカー", "出力MCB", "子ブレーカー",
                ],
            },

           
            "load": {
                "en": [
                    "load", "circuit", "light", "socket", "appliance",
                    # common load descriptions users write
                    "lighting", "lights", "lamps", "luminaire",
                    "power socket", "outlet", "plug point",
                    "motor", "pump", "fan", "hvac", "air conditioning",
                    "equipment", "machine", "device", "consumer",
                    "balanced load", "unbalanced load",
                    "three-phase load", "single-phase load",
                ],
                "ja": [
                    "負荷", "回路", "照明", "コンセント",
                    "モーター", "ポンプ", "機器", "電気機器",
                ],
            },
        }
        self.symbol_asset_map = {
            "maincb": "maincb.svg",
            "ebar":   "ebar.svg",
            "loads":  "loads.svg",
        }
        self.symbol_svgs = self._load_symbol_svgs()
        self.diagram_labels = {
            "section_incoming":     {"en": "Incoming Source",               "ja": "入力電源"},
            "section_distribution": {"en": "Distribution Panel Components", "ja": "分電盤部品"},
            "section_load":         {"en": "Load Side",                     "ja": "負荷側"},
            "note_power_entry":     {"en": "1. INCOMING POWER ENTRY",       "ja": "1. 受電"},
            "note_internal":        {"en": "2. INTERNAL DISTRIBUTION",      "ja": "2. 内部配電"},
            "note_outgoing":        {"en": "3. OUTGOING CIRCUITS",          "ja": "3. 出力回路"},
            "note_fault":           {"en": "4. FAULT CURRENT PATH (E)",     "ja": "4. 故障電流経路 (E)"},            
            "wire_phase":           {"en": "Phase/Line Wire (L)",           "ja": "相線/ラインワイヤ (L)"},
            "wire_neutral":         {"en": "Neutral Wire (N)",              "ja": "中性線 (N)"},
            "wire_earth":           {"en": "Earth Wire (E)",                "ja": "接地線 (E)"},
            "action_energize":      {"en": "Energize Busbar (L)",           "ja": "母線を励磁 (L)"},
            "action_protection":    {"en": "Protection: Overload/Short",    "ja": "保護: 過負荷/短絡"},
            "action_rcd_monitor":   {"en": "Current Monitoring (RCD)",      "ja": "電流監視 (RCD)"},
            "action_rcd_pass":      {"en": "Protected Distribution (L)",    "ja": "保護配電 (L)"},
            "action_rcd_note":      {"en": "RCD: Residual Current\nTrip", "ja": "RCD: 漏電検知\n30mA以下でトリップ"},
            "action_distribute":    {"en": "Distribute to Branch Breakers", "ja": "分岐ブレーカーに配電"},
            "action_feed":          {"en": "Line (L) - Protected Feed",     "ja": "ライン (L) - 保護給電"},
            "action_return":        {"en": "Neutral (N) - Return Path",     "ja": "中性線 (N) - 帰路"},
            "action_safety":        {"en": "Earth (E) - Safety Grounding",  "ja": "接地 (E) - 安全接地"},
            "action_fault":         {"en": "Fault Current Detected (E)",    "ja": "故障電流検知 (E)"},
            "action_fault_return":  {"en": "Fault Return Path to Source",         "ja": "故障電流帰路 (電源へ)"},
            "action_rcd_isolate":   {"en": "Open Contacts — Isolate Circuit",     "ja": "接点開放 — 回路遮断"},
            "action_rcd_trip":      {"en": "RCD Trip Signal",               "ja": "RCDトリップ信号"},
            "action_cb_open":       {"en": "Circuit Open — Supply Isolated", "ja": "回路開放 — 電源遮断"},
        }

    def _load_symbol_svgs(self):
        """Load the IEC symbol SVGs, stripping the XML prolog and outer
        <svg>/viewBox wrapper so only the inner markup remains — this lets
        applySymbols() in the JS editor insert it into its own sized wrapper."""
        base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "symbols")
        loaded = {}
        for comp_id, filename in self.symbol_asset_map.items():
            path = os.path.join(base_dir, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                content = re.sub(r'<\?xml[^>]*\?>', '', content, flags=re.IGNORECASE)
                match = re.search(r'<svg[^>]*>(.*)</svg>', content, flags=re.DOTALL | re.IGNORECASE)
                inner = match.group(1).strip() if match else content.strip()
                loaded[comp_id] = inner
            except Exception as e:
                print(f"[symbol load] failed to load {comp_id} from {path}: {e}")
        return loaded

    def _ordered_component_ids(self, parsed_data):
        """Component IDs in the same order they're declared as Mermaid
        participants — i.e. the same list order used as the topology proxy
        elsewhere in the project (e.g. the DXF exporter)."""
        return [cid for cid, _ in parsed_data.get("components", [])]

    def detect_language(self, text):
        if re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]').search(text):
            return "ja"
        return "en"

    def _compute_sequence_height(self, parsed_data):
        """Dynamically size actor boxes so symbol + label always fit,
        based on the longest label actually present this generation —
        computed before Mermaid renders, so nothing needs post-hoc resizing."""
        base_height = 130          # fits symbol (up to 80px) + one line of label
        extra_per_wrap_line = 16   # additional height per extra wrapped line

        labels = [label for _, label in parsed_data.get("components", [])]
        max_len = max((len(label) for label in labels), default=0)

        # Rough estimate: labels longer than ~20 chars are likely to wrap
        # to a second line at the current font size; longer than ~40, a third.
        extra_lines = 0
        if max_len > 40:
            extra_lines = 2
        elif max_len > 20:
            extra_lines = 1

        return base_height + extra_lines * extra_per_wrap_line
    

    def parse_prompt(self, prompt_text, complexity_level="Neutral"):
        print('parsing prompt with hardcoded rules')
        if not prompt_text or not isinstance(prompt_text, str):
            return {"components": self.get_default_components("en", "230V / 415V", "Standard"),
                    "voltage": "230V / 415V", "language": "en", "complexity": complexity_level}

        exclusions = {
            "rcd":  ["no rcd", "no residual", "no earth fault"],
            "nbar": ["no neutral"],
            "ebar": ["no earth", "no ground"],
            "bus":  ["no busbar", "no bus"],
        }
        prompt_lower = prompt_text.lower()

        # ✅ Assign BEFORE use
        language = self.detect_language(prompt_text)
        voltage_text = "230V / 415V"

        try:
            for pattern in [r'(\d+)\s*[Vv]\s*[/／]?\s*(\d+)\s*[Vv]', r'(\d+)\s*[Vv]', r'(\d+)\s*volts?']:
                m = re.search(pattern, prompt_text)
                if m:
                    voltage_text = f"{m.group(1)}V / {m.group(2)}V" if len(m.groups()) >= 2 else f"{m.group(1)}V"
                    break
        except Exception:
            pass

        # Extract outgoing branch breakers from the prompt text if detailed/neutral complexity or if outcb_N is mentioned
        outcb_list = []
        for line in prompt_text.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            if line_str.startswith(("-", "*", "•", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "10", "11", "12", "13", "14", "15")):
                if "mcb" in line_str.lower() or "breaker" in line_str.lower() or "circuit" in line_str.lower() or "|" in line_str:
                    lbl = line_str.lstrip("-*•0123456789. \t").strip()
                    if lbl:
                        match = re.search(r'(?:mcb|breaker)\s*(\d+)', line_str.lower())
                        idx = int(match.group(1)) if match else (len(outcb_list) + 1)
                        outcb_list.append((f"outcb_{idx}", lbl))
                        
        NUMBER_WORDS = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15
        }
        if not outcb_list:
            match = re.search(r'\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen)\s*(?:outgoing|branch)?\s*(?:lamp|light|motor|socket|outlet|appliance|device|load|breaker|circuit|mcb|outcb|outcr|\s)*\s*(?:loads|breakers|circuits|mcbs|motors|outlets|lamps|lights)\b', prompt_lower)
            if match:
                num_str = match.group(1)
                n_cb = int(num_str) if num_str.isdigit() else NUMBER_WORDS.get(num_str, 1)
                n_cb = min(n_cb, 15)
                generic_label = self.components_map["outgoing mcbs"][language]
                for i in range(1, n_cb + 1):
                    outcb_list.append((f"outcb_{i}", f"{generic_label} {i}"))

        def is_explicitly_excluded(cid: str) -> bool:
            cid_lower = cid.lower()
            if "supply" in cid_lower:
                if any(kw in prompt_lower for kw in ["no supply", "without supply", "exclude supply", "omit supply", "no incoming"]):
                    return True
                return bool(re.search(r'\b(?:no|without|exclude|omit|(?:do|does|did)\s+not\s+include|don\'?t\s+include)\b.{0,60}?\b(?:supply|mains|incoming)\b', prompt_lower))
            if "maincb" in cid_lower or "breaker" in cid_lower:
                if any(kw in prompt_lower for kw in ["direct connection", "connected directly", "no maincb", "no main breaker", "without main breaker", "without a main breaker", "no breaker", "without breaker", "do not include a main breaker", "do not include main breaker", "ブレーカーなし", "主遮断器なし", "主遮断器は含めない", "主遮断器不要", "ブレーカー不要", "直接接続"]):
                    return True
                return bool(re.search(r'\b(?:no|without|exclude|omit|(?:do|does|did)\s+not\s+include|don\'?t\s+include)\b.{0,60}?\b(?:main\s+)?(?:cb|breaker|mcb|mccb)\b', prompt_lower))
            if "rcd" in cid_lower or "rcbo" in cid_lower:
                if any(kw in prompt_lower for kw in ["direct connection", "connected directly", "no rcd", "no rcbo", "no residual", "no earth fault", "without rcd", "漏電遮断器なし", "漏電遮断器は含めない", "rcdなし"]):
                    return True
                return bool(re.search(r'\b(?:no|without|exclude|omit|(?:do|does|did)\s+not\s+include|don\'?t\s+include)\b.{0,60}?\b(?:rcd|rcbo|residual|earth\s+fault)\b', prompt_lower))
            if "nbar" in cid_lower:
                if any(kw in prompt_lower for kw in ["no neutral", "without neutral", "中性線なし", "中性バーなし"]):
                    return True
                return bool(re.search(r'\b(?:no|without|exclude|omit|(?:do|does|did)\s+not\s+include|don\'?t\s+include)\b.{0,60}?\b(?:neutral|nbar|n-bar|n\s+bar)\b', prompt_lower))
            if "ebar" in cid_lower:
                if any(kw in prompt_lower for kw in ["no earth", "no ground", "without earth", "without ground", "接地バーなし", "アースなし", "接地なし"]):
                    return True
                return bool(re.search(r'\b(?:no|without|exclude|omit|(?:do|does|did)\s+not\s+include|don\'?t\s+include)\b.{0,60}?\b(?:earth|ground|ebar|e-bar|e\s+bar)\b', prompt_lower))
            if "bus" in cid_lower:
                if any(kw in prompt_lower for kw in ["no busbar", "no bus"]):
                    return True
                return bool(re.search(r'\b(?:no|without|exclude|omit|(?:do|does|did)\s+not\s+include|don\'?t\s+include)\b.{0,60}?\b(?:busbar|bus\s+bar|bus)\b', prompt_lower))
            return False

        # For Neutral mode, keyword-detect from prompt instead of using empty allowed list
        if complexity_level == "Neutral":
            KEYWORD_TO_COMPONENT = {
                "supply":  ["supply", "mains", "source", "incoming", "grid"],
                "maincb":  ["breaker", "mcb", "mccb", "circuit breaker", "main cb"],
                "rcd":     ["rcd", "rcbo", "residual", "earth fault"],
                "bus":     ["busbar", "bus bar", "bus-bar", "distribution"],
                "nbar":    ["neutral bar", "neutral link", "n bar"],
                "ebar":    ["earth bar", "earth terminal", "e bar"],
                "loads":   ["load", "loads", "lighting", "socket", "appliance", "circuit", "lamp"],
            }
            all_possible = self.get_default_components(language, voltage_text, "Standard")
            all_possible_dict = dict(all_possible)

            found_ids = []
            for cid, keywords in KEYWORD_TO_COMPONENT.items():
                if any(kw in prompt_lower for kw in keywords):
                    if not is_explicitly_excluded(cid):
                        found_ids.append(cid)

            # Always ensure supply and loads if detected; fallback to supply+maincb+loads minimum
            if not found_ids:
                found_ids = ["supply", "maincb", "loads"]

            found_components = [
                (cid, all_possible_dict[cid]) for cid in found_ids
                if cid in all_possible_dict
                and not is_explicitly_excluded(cid)
            ]
        else:
            # Non-Neutral: use the complexity level's allowed list
            found_components = self.get_default_components(language, voltage_text, complexity_level)
            comp_dict = dict(found_components)
            if "supply" in comp_dict:
                comp_dict["supply"] = self.components_map["main incoming supply"][language].replace(
                    "230V / 415V", voltage_text
                )
            found_components = [
                (cid, lbl) for cid, lbl in comp_dict.items()
                if not is_explicitly_excluded(cid)
            ]

        # Detect multiple supplies (e.g. supply 1 and supply 2, grid and generator, 2系統の電源)
        if re.search(r'\b(?:supply\s*(?:1\s*and\s*(?:supply\s*)?2|[a-b]\s*and\s*supply\s*[a-b])|mains\s*1\s*and\s*(?:mains\s*)?2|(?:two|2)\s+(?:main\s+)?supplies|dual\s+supplies?|(?:main\s+)?(?:grid|mains|utility)\s+(?:supply\s+)?and\s+(?:backup\s+)?(?:generator|secondary|auxiliary)\s+supply)\b|(?:主電源|電源).*?(?:副電源|発電機|2系統)', prompt_lower):
            if not any(c == "supply_2" for c, _ in found_components):
                found_components.insert(1, ("supply_2", f"Secondary Supply ({voltage_text})"))

        if complexity_level != "Simple" and outcb_list:
            try:
                from ECD.pin_model import get_base_type
            except ImportError:
                from pin_model import get_base_type
            found_components = [(cid, lbl) for cid, lbl in found_components if get_base_type(cid) != "outcb"]
            loads_idx = next((i for i, (cid, _) in enumerate(found_components) if cid == "loads"), len(found_components))
            found_components[loads_idx:loads_idx] = outcb_list

        phase_hint = None
        if re.search(r'\b(?:three[-\s]*phase|3[-\s]*phase|三相)\b', prompt_lower):
            phase_hint = "three-phase"
        elif re.search(r'\b(?:single[-\s]*phase|1[-\s]*phase|単相)\b', prompt_lower):
            phase_hint = "single-phase"

        if re.search(r'\b(?:spare_block|spare_terminal|spare_cb|unwired|spare)\b', prompt_lower):
            if not any(c == "spare_block" for c, _ in found_components):
                found_components.append(("spare_block", "Spare Component"))

        if re.search(r'\b(?:loads_1|loads\s*1)\b', prompt_lower):
            if not any(c == "loads_1" for c, _ in found_components):
                found_components.append(("loads_1", "Load 1"))

        if re.search(r'\b(?:motor_3ph|3ph_motor|3[-\s]*phase\s*motor|three[-\s]*phase\s*motor)\b', prompt_lower):
            if not any(c == "motor_3ph" for c, _ in found_components):
                found_components.append(("motor_3ph", "3-Phase Motor"))

        custom_conns = None
        if re.search(r'\b(?:feeds?\s*back|loop|cyclic|cycle)\b', prompt_lower):
            custom_conns = [("supply", "maincb"), ("maincb", "bus"), ("bus", "outcb_1"), ("outcb_1", "loads"), ("outcb_1", "maincb")]
            if not any(c == "outcb_1" for c, _ in found_components):
                found_components.append(("outcb_1", "Branch Breaker 1"))

        ret_dict = {"components": found_components, "voltage": voltage_text,
                    "phase_hint": phase_hint,
                    "language": language, "complexity": complexity_level,
                    "prompt": prompt_text}
        if custom_conns:
            ret_dict["connections"] = custom_conns
        return ret_dict

    def get_default_components(self, language, voltage_text="230V / 415V", complexity_level="Standard"):
        level_cfg = COMPLEXITY_LEVELS[complexity_level]
        allowed_ids = level_cfg["components"]  # outcb_N no longer in here for Detailed

        # allowed_ids = COMPLEXITY_LEVELS[complexity_level]["components"]
        all_defaults = [
            ("supply", self.components_map["main incoming supply"][language].replace("230V / 415V", voltage_text)),
            ("maincb", self.components_map["main breaker"][language]),
            ("rcd",    self.components_map["rcd"][language]),
            ("bus",    self.components_map["busbar"][language]),
            ("nbar",   self.components_map["neutral bar"][language]),
            ("ebar",   self.components_map["earth bar"][language]),
            ("loads",  self.components_map["load circuits"][language]),
        ]

        return [(cid, lbl) for cid, lbl in all_defaults if cid in allowed_ids]

    def generate_mermaid_code(self, parsed_data):
        try:
            from ECD.dxf_generator import ensure_connections
        except ImportError:
            from dxf_generator import ensure_connections
            
        connections = ensure_connections(parsed_data)
        # Normalize connections to set for easy O(1) checks
        conn_set = {(src.lower(), dst.lower()) for src, dst in connections}

        components = [(cid.lower(), lbl) for cid, lbl in parsed_data.get("components", [])]
        language   = parsed_data.get("language", "en")
        complexity = parsed_data.get("complexity", "Neutral")
        comp_map   = {cid: lbl for cid, lbl in components}
        
        try:
            from ECD.pin_model import get_base_type
        except ImportError:
            from pin_model import get_base_type
            
        outcbs = [cid.lower() for cid, _ in components if get_base_type(cid) == "outcb" and cid.lower() != "outcb"]
        if outcbs and "loads" not in comp_map:
            components.append(("loads", "Loads" if language == "en" else "負荷回路"))
            comp_map["loads"] = "Loads" if language == "en" else "負荷回路"
        L          = self.diagram_labels

        # ── Merge flags ───────────────────────────────────────────────────────────────────
        # Complexity defaults WIN when they require True.
        # The LLM can add True flags (e.g. user asked for fault paths on Standard),
        # but must NOT suppress flags that the complexity level mandates.
        # This fixes Detailed mode where Mistral often returns show_fault_paths=false.
        complexity_cfg = COMPLEXITY_LEVELS.get(complexity, COMPLEXITY_LEVELS["Neutral"])
        llm_flags = parsed_data.get("flags", {})

        prompt_text = parsed_data.get("prompt", "")

        EXPLICIT_ENABLE_KEYWORDS = {
            "show_fault_paths":       ["fault path", "fault current", "earth fault path"],
            "show_neutral":           ["neutral wire", "show neutral", "include neutral"],
            "show_earth":             ["earth wire", "show earth", "include earth"],
            "show_rcd":               ["rcd", "residual current", "earth fault protection"],
            "show_protection_notes":  ["protection note", "show notes", "annotation"],
        }

        def _prompt_explicitly_enables(key, text):
            t = text.lower()
            return any(kw in t for kw in EXPLICIT_ENABLE_KEYWORDS.get(key, []))

        def _merge_flag(key):
            complexity_val = complexity_cfg[key]
            llm_val = llm_flags.get(key, None)

            # If complexity REQUIRES False (e.g. Simple hides fault paths),
            # only override if the prompt explicitly asks for it
            if complexity_val is False:
                # Only allow True if LLM was explicitly instructed by prompt
                # (prompt_text is stored in parsed_data["prompt"])
                prompt_explicitly_requests = _prompt_explicitly_enables(key, prompt_text)
                return True if prompt_explicitly_requests else False

            # If complexity requires True, LLM cannot suppress it
            if complexity_val is True:
                return True

            # Neutral / unset — LLM decides
            return llm_val if llm_val is not None else complexity_val


        cfg = {
            "show_neutral":          _merge_flag("show_neutral"),
            "show_earth":            _merge_flag("show_earth"),
            "show_rcd":              _merge_flag("show_rcd"),
            "show_protection_notes": _merge_flag("show_protection_notes"),
            "show_fault_paths":      _merge_flag("show_fault_paths"),
        }

        voltage_str = parsed_data.get("voltage", "")
        prompt_text = parsed_data.get("prompt", "")   # see note below about storing prompt

        try:
            from ECD.pin_model import determine_phase_mode
        except ImportError:
            from pin_model import determine_phase_mode
        phase_hint = parsed_data.get("phase_hint") or parsed_data.get("flags", {}).get("phase_hint")
        is_three_phase = determine_phase_mode(voltage_str, phase_hint) == "three"

        def clean_label(lbl):
            return re.sub(r'<br\s*/?>', ' ', lbl).strip()

        def get_label(key):
            val = L.get(key, {}).get(language, "")
            if is_three_phase:
                val = val.replace(" (L)", " (L1/L2/L3)").replace(" (L線)", " (L1/L2/L3)").replace("(RCD)", "(RCD L1/L2/L3)")
            return val

        # ── Build participant ID map — handle dynamic outcb_1..5 and custom IDs ──────────────────
        pid = {
            "supply": "supply",
            "maincb": "maincb",
            "rcd":    "rcd",
            "rcbo":   "rcbo",
            "bus":    "bus",
            "nbar":   "nbar",
            "ebar":   "ebar",
            "outcb":  "outcb",
            "loads":  "loads",
        }
        # Add dynamic and custom entries
        for cid, _ in components:
            cid_lower = cid.lower()
            if cid_lower not in pid:
                pid[cid_lower] = cid_lower

        outcb_ids = [cid.lower() for cid, _ in components if get_base_type(cid.lower()) == "outcb" and cid.lower() != "outcb"]
        # Also support legacy single "outcb"
        if "outcb" in comp_map and not outcb_ids:
            outcb_ids = ["outcb"]

        lines = ["sequenceDiagram",  ""]

        # ── Box: Incoming Source ──────────────────────────────────────────────────
        lines.append(f'    box rgb(238,242,255) "{L["section_incoming"][language]}"')
        if "supply" in comp_map:
            lines.append(f'        participant {pid["supply"]} as {clean_label(comp_map["supply"])}')
        lines.append("    end")
        lines.append("")

        # ── Box: Distribution Panel ───────────────────────────────────────────────
        lines.append(f'    box rgb(240,253,244) "{L["section_distribution"][language]}"')
        
        # Build panel components in input order, preserving relative layout order
        known_standard_ids = {"supply", "loads"}
        dist_order = []
        for cid, _ in components:
            cid_lower = cid.lower()
            if cid_lower not in known_standard_ids:
                dist_order.append(cid_lower)
                
        for cid in dist_order:
            if cid in comp_map:
                lines.append(f'        participant {pid[cid]} as {clean_label(comp_map[cid])}')
        lines.append("    end")
        lines.append("")

        # ── Box: Load Side ────────────────────────────────────────────────────────
        lines.append(f'    box rgb(255,247,237) "{L["section_load"][language]}"')
        if "loads" in comp_map:
            lines.append(f'        participant {pid["loads"]} as {clean_label(comp_map["loads"])}')
        lines.append("    end")
        lines.append("")

        lines.append("   autonumber")
        lines.append("")

        # ── Section 1: Incoming Power Entry ──────────────────────────────────────
        if "supply" in comp_map:
            note_right_order = ["loads", "ebar", "nbar"] + list(reversed(outcb_ids)) + ["bus", "rcd", "maincb"]
            all_pids_in_order = [pid[c] for c in note_right_order if c in comp_map]
            if len(all_pids_in_order) >= 2:
                lines.append(f'    Note over {all_pids_in_order[0]},{all_pids_in_order[-1]}: {L["note_power_entry"][language]}')
            else:
                lines.append(f'    Note over {pid["supply"]}: {L["note_power_entry"][language]}')

            # Phase wire: supply → maincb
            if "maincb" in comp_map and ("supply", "maincb") in conn_set:
                phase_label = L["wire_phase"][language]
                if is_three_phase:
                    phase_label = f"3-Phase Supply (L1/L2/L3) — {voltage_str}" if language == "en" else f"三相電源 (L1/L2/L3) — {voltage_str}"
                lines.append(f'    {pid["supply"]}->>{pid["maincb"]}: {phase_label}')
            # Neutral: supply → nbar
            if cfg["show_neutral"] and "nbar" in comp_map:
                lines.append(f'    {pid["supply"]}->>{pid["nbar"]}: {L["wire_neutral"][language]}')
            # Earth: supply → ebar
            if cfg["show_earth"] and "ebar" in comp_map:
                lines.append(f'    {pid["supply"]}-->>{pid["ebar"]}: {L["wire_earth"][language]}')
            lines.append("")

        # ── Section 2: Internal Distribution ─────────────────────────────────────
        if "maincb" in comp_map:
            dist_pids = [pid[c] for c in ["maincb", "rcd", "bus", "nbar", "ebar"] + outcb_ids if c in comp_map]
            if len(dist_pids) >= 2:
                lines.append(f'    Note over {dist_pids[0]},{dist_pids[-1]}: {L["note_internal"][language]}')
            elif dist_pids:
                lines.append(f'    Note over {dist_pids[0]}: {L["note_internal"][language]}')           
            if cfg["show_protection_notes"]:
                lines.append(f'    Note right of {pid["maincb"]}: {"Overcurrent / Short Circuit Protection" if language == "en" else "過電流/短絡保護"}')
                if cfg["show_rcd"] and "rcd" in comp_map:
                    lines.append(f'    Note right of {pid["rcd"]}: {"Earth Fault / Residual Current Protection" if language == "en" else "地絡/残留電流保護"}')

            # maincb → rcd
            if cfg["show_rcd"] and "rcd" in comp_map and ("maincb", "rcd") in conn_set:
                lines.append(f'    {pid["maincb"]}->>{pid["rcd"]}: {get_label("action_rcd_monitor")}')
                
                # rcd → bus
                if "bus" in comp_map and ("rcd", "bus") in conn_set:
                    lines.append(f'    {pid["rcd"]}->>{pid["bus"]}: {get_label("action_rcd_pass")}')
                elif outcb_ids:
                    for oid in outcb_ids:
                        if ("rcd", oid) in conn_set:
                            lines.append(f'    {pid["rcd"]}->>{pid[oid]}: {get_label("action_distribute")}')
            else:
                # No RCD
                if "bus" in comp_map and ("maincb", "bus") in conn_set:
                    lines.append(f'    {pid["maincb"]}->>{pid["bus"]}: {get_label("action_energize")}')
                elif outcb_ids:
                    for oid in outcb_ids:
                        if ("maincb", oid) in conn_set:
                            lines.append(f'    {pid["maincb"]}->>{pid[oid]}: {get_label("action_distribute")}')

            # bus → outcb_N
            if "bus" in comp_map and outcb_ids:
                for oid in outcb_ids:
                    if ("bus", oid) in conn_set:
                        lines.append(f'    {pid["bus"]}->>{pid[oid]}: {get_label("action_distribute")}')

            # Custom component connections in the panel
            try:
                from ECD.pin_model import get_base_type
            except ImportError:
                from pin_model import get_base_type
            for src, dst in connections:
                src_base = get_base_type(src)
                dst_base = get_base_type(dst)
                
                # Check if this edge involves a custom/unrecognized component in the panel
                is_custom_src = src_base not in {"supply", "maincb", "rcd", "rcbo", "bus", "nbar", "ebar", "loads", "outcb"}
                is_custom_dst = dst_base not in {"supply", "maincb", "rcd", "rcbo", "bus", "nbar", "ebar", "loads", "outcb"}
                
                if is_custom_src or is_custom_dst:
                    # Determine a friendly label
                    if is_three_phase:
                        if src_base == "maincb":
                            lbl = "Main Feed (L1/L2/L3)" if language == "en" else "主給電 (L1/L2/L3)"
                        elif dst_base == "rcd" or dst_base == "rcbo":
                            lbl = "Monitored Feed (L1/L2/L3)" if language == "en" else "監視給電 (L1/L2/L3)"
                        elif dst_base == "bus":
                            lbl = "Protected Distribution (L1/L2/L3)" if language == "en" else "保護配電 (L1/L2/L3)"
                        elif dst_base == "loads" or dst_base.startswith("load_"):
                            lbl = "Protected Feed (L1/L2/L3)" if language == "en" else "保護給電 (L1/L2/L3)"
                        else:
                            lbl = "Phase Connection (L1/L2/L3)" if language == "en" else "相接続 (L1/L2/L3)"
                    else:
                        if src_base == "maincb":
                            lbl = "Main Feed (L)" if language == "en" else "主給電 (L)"
                        elif dst_base == "rcd" or dst_base == "rcbo":
                            lbl = "Monitored Feed (L)" if language == "en" else "監視給電 (L)"
                        elif dst_base == "bus":
                            lbl = "Protected Distribution (L)" if language == "en" else "保護配電 (L)"
                        elif dst_base == "loads" or dst_base.startswith("load_"):
                            lbl = "Protected Feed (L)" if language == "en" else "保護給電 (L)"
                        else:
                            lbl = "Phase Connection (L)" if language == "en" else "相接続 (L)"
                        
                    lines.append(f'    {pid[src]}->>{pid[dst]}: {lbl}')

            lines.append("")

        # ── Section 3: Outgoing Circuits ──────────────────────────────────────────
        if "loads" in comp_map:
            load_src_order = outcb_ids + ["bus", "rcd", "maincb"]
            load_src_cid = next((c for c in load_src_order if c in comp_map), None)

            if load_src_cid is None:
                lines.append(f'    Note over {pid["loads"]}: ⚠ WARNING: No upstream protection found')
            else:
                if load_src_cid != "loads":
                    lines.append(f'    Note over {pid[load_src_cid]},{pid["loads"]}: {L["note_outgoing"][language]}')
                else:
                    lines.append(f'    Note over {pid["loads"]}: {L["note_outgoing"][language]}')

                if outcb_ids:
                    if is_three_phase:
                        feed_label = "Protected Feed (L1/L2/L3)" if language == "en" else "保護給電 (L1/L2/L3)"
                    else:
                        feed_label = "Protected Feed (L)" if language == "en" else "保護給電 (L)"
                    for oid in outcb_ids:
                        if (oid, "loads") in conn_set or any(src == oid and (dst == "loads" or dst.startswith("load_")) for src, dst in conn_set):
                            lines.append(f'    {pid[oid]}->>{pid["loads"]}: {feed_label}')
                elif load_src_cid and load_src_cid != "loads":
                    lines.append(f'    {pid[load_src_cid]}->>{pid["loads"]}: {get_label("action_feed")}')

                # Neutral return and earth
                if cfg["show_neutral"] and "nbar" in comp_map:
                    lines.append(f'    {pid["loads"]}->>{pid["nbar"]}: {L["action_return"][language]}')
                if cfg["show_earth"] and "ebar" in comp_map:
                    lines.append(f'    {pid["ebar"]}-->>{pid["loads"]}: {L["action_safety"][language]}')

            lines.append("")


        # ── Section 4: Fault Protection Paths ─────────────────────────────────
        if cfg["show_fault_paths"] and "ebar" in comp_map and "loads" in comp_map:
            L = self.diagram_labels
            language = parsed_data.get("language", "en")

            lines.append("")
            lines.append(f'    Note over {pid["ebar"]},{pid["loads"]}: {L["note_fault"][language]}')

            # Step 1: Fault current flows from load through CPC to Earth Bar
            lines.append(f'    {pid["loads"]}-->>{pid["ebar"]}: {L["action_fault"][language]}')

            # Step 2: Fault return path travels from Earth Bar back to supply source
            if cfg["show_rcd"] and "rcd" in comp_map and "maincb" in comp_map and "supply" in comp_map:
                lines.append(f'    {pid["ebar"]}-->>{pid["rcd"]}: {L["action_fault_return"][language]}')
                lines.append(f'    {pid["rcd"]}-->>{pid["maincb"]}: {L["action_rcd_trip"][language]}')
                lines.append(f'    {pid["maincb"]}-->>{pid["supply"]}: {L["action_cb_open"][language]}')
            else:
                if "supply" in comp_map:
                    lines.append(f'    {pid["ebar"]}-->>{pid["supply"]}: {L["action_fault_return"][language]}')

            # Step 3: RCD monitors live vs neutral
            if cfg["show_rcd"] and "rcd" in comp_map:
                lines.append(f'    Note over {pid["rcd"]}: {"Monitors L vs N current | Trips on imbalance ≥ 30mA" if language == "en" else "L線とN線の電流を監視 | 30mA以上の不平衡でトリップ"}')
        return "\n".join(lines)