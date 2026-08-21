# ECD Sample Prompts

Sample prompts for all four complexity levels, in English and Japanese. Copy-paste any of these directly into the prompt input field.

---

## Complexity Levels — Quick Reference

| Level | Use When |
|-------|---------|
| **Simple** | You only need a basic schematic showing power flow — no protection devices, no neutral/earth |
| **Neutral** | You want exactly what you describe — nothing added, nothing assumed |
| **Standard** | Professional diagram with RCD protection, neutral bar, earth bar |
| **Detailed** | Full documentation with individual circuit breakers per load and fault paths |

---

## Simple

Phase wire only. No RCD, no neutral, no earth. Use this for quick concept diagrams.

**English**

```
Single phase 230V panel with main supply and 63A main breaker.
```

```
Basic 230V AC supply with a 100A main switch and three lamp loads.
```

```
415V three-phase supply with a 200A main MCCB and two motor loads.
```

**Japanese (日本語)**

```
単相230V AC。主電源と63Aメイン遮断器のみ。
```

```
230V AC基本配電。100Aメインスイッチと3つの照明負荷。
```

```
415V三相電源、200AメインMCCBと2台のモータ負荷。
```

---

## Neutral

Only what you describe is included. The LLM does not add any default components. Use this for maximum control.

**English**

```
Single phase 230V panel with grid supply, 63A main breaker, busbar, neutral bar, earth bar, and 2 socket circuits.
```

```
Single phase 230V panel with Grid Supply, Generator Backup, ATS (Automatic Transfer Switch), 63A main breaker, busbar, N-bar, E-bar, and 3 emergency circuits.
```

```
415V AC three-phase industrial control panel with 150A main breaker, 100mA earth fault breaker, copper busbar, neutral bar, earth bar, 5.5kW induction motor, 7.5kW pump motor, and 3kW HVAC load.
```

```
230V single phase distribution board with 100A main MCCB, 30mA RCD, 2 lighting circuits, and 2 power socket circuits.
```

```
230V panel, main supply, 40A breaker, no RCD, no earth, single load.
```

**Japanese (日本語)**

```
単相230V AC配電盤。グリッド電源、63Aメイン遮断器、ブスバー、中性線バー、接地バー、2つのコンセント回路。
```

```
単相230V AC配電盤。グリッド電源、非常用発電機バックアップ、ATS（自動切換装置）、63Aメイン遮断器、ブスバー、Nバー、Eバー、3つの非常用回路。
```

```
415V AC三相産業用制御盤。150Aメイン遮断器、100mA漏電遮断器（ELCB）、銅ブスバー、中性線バー、接地バー、5.5kW誘導モータ、7.5kWポンプモータ、3kW空調負荷。
```

```
230V単相配電盤。100AメインMCCB、30mA漏電遮断器、2つの照明回路と2つのコンセント回路。
```

```
230V配電盤。主電源、40A遮断器、漏電遮断器なし、接地なし、単一負荷。
```

---

## Standard

Adds default protection automatically: RCD, busbar, neutral bar, earth bar. Good for professional residential and commercial boards.

**English**

```
Standard 230V single phase residential distribution board.
```

```
230V single phase panel with main supply, main breaker, RCD, busbar, neutral bar, earth bar, lighting circuits, and socket circuits.
```

```
415V three-phase distribution board with main MCCB, RCD protection, copper busbar, neutral link, and earth terminal for a commercial building.
```

```
Standard single phase 230V board for a small office with lights, sockets, and HVAC.
```

**Japanese (日本語)**

```
標準的な単相230V AC住宅用分電盤。
```

```
単相230V配電盤。主電源、メイン遮断器、漏電遮断器、ブスバー、中性線バー、接地バー、照明回路、コンセント回路。
```

```
商業ビル用415V三相配電盤。メインMCCB、漏電保護、銅ブスバー、中性線リンク、接地端子。
```

```
照明、コンセント、空調を含む小規模オフィス用単相230V標準分電盤。
```

---

## Detailed

Full documentation-grade output. Generates individual branch breakers (`outcb_N`) and loads for every named circuit. Includes fault paths and protection notes.

**English**

```
230V single phase distribution board with 100A main MCCB, 30mA RCD, copper busbar, neutral link, earth terminal, lighting circuit 1, lighting circuit 2, socket circuit 1, socket circuit 2, and HVAC circuit.
```

```
415V AC three-phase industrial control panel with 150A main MCCB, 100mA earth fault relay, copper busbar, neutral bar, earth bar, 5.5kW induction motor, 7.5kW centrifugal pump motor, 3kW HVAC compressor, and 2kW lighting panel.
```

```
Single phase 230V panel with Grid Supply, Generator Backup, ATS (Automatic Transfer Switch), 63A main breaker, busbar, neutral bar, earth bar, emergency lighting circuit, emergency power socket circuit, and fire alarm circuit.
```

```
Three-phase 415V factory distribution panel with 250A main MCCB, 300mA RCCB, copper busbar system, neutral bar, earth bar, 11kW conveyor motor, 7.5kW compressor motor, 5.5kW cooling fan motor, 3kW lighting distribution panel, and 2kW control panel supply.
```

**Japanese (日本語)**

```
単相230V AC配電盤。100AメインMCCB、30mA漏電遮断器、銅ブスバー、中性線リンク、接地端子、照明回路1、照明回路2、コンセント回路1、コンセント回路2、空調回路。
```

```
415V AC三相産業用制御盤。150AメインMCCB、100mA地絡継電器、銅ブスバー、中性線バー、接地バー、5.5kW誘導モータ、7.5kW遠心ポンプモータ、3kW空調コンプレッサ、2kW照明分電盤。
```

```
単相230V配電盤。グリッド電源、非常用発電機バックアップ、ATS（自動切換装置）、63Aメイン遮断器、ブスバー、中性線バー、接地バー、非常用照明回路、非常用電源コンセント回路、火災警報回路。
```

```
三相415Vファクトリ配電盤。250AメインMCCB、300mA漏電遮断器、銅ブスバー、中性線バー、接地バー、11kWコンベアモータ、7.5kWコンプレッサモータ、5.5kW冷却ファンモータ、3kW照明分電盤、2kW制御盤電源。
```

---

## Multiple Sources & ATS Panels

Use these when a panel has more than one incoming supply — typically a grid connection and a generator or solar backup connected through an Automatic Transfer Switch (ATS).

**Rules to follow:**
- Always name **both** supplies explicitly (e.g. `Grid Supply` and `Generator Backup`).
- Always include `ATS` or `Automatic Transfer Switch` in the prompt.
- The app routes both supplies into the ATS inputs and the ATS output into the main breaker automatically.
- ERC-001 (single supply rule) is suppressed when an ATS is detected.

**English**

```
Single phase 230V panel with Grid Supply, Generator Backup, ATS (Automatic Transfer Switch), 63A main breaker, busbar, N-bar, E-bar, and 3 emergency circuits.
```

```
Single phase 230V panel with mains supply, diesel generator backup, automatic transfer switch, 100A main MCCB, busbar, neutral bar, earth bar, emergency lighting circuit, emergency power circuit, and fire alarm feed.
```

```
Three-phase 415V panel with utility grid supply, standby generator, ATS, 250A main MCCB, copper busbar, neutral bar, earth bar, 11kW conveyor motor, 7.5kW pump motor, and 3kW control panel.
```

```
230V single phase UPS panel with mains input, UPS output, manual bypass switch (ATS), 63A main breaker, and 4 critical load circuits.
```

**Japanese (日本語)**

```
単相230V配電盤。グリッド電源、非常用発電機バックアップ、ATS（自動切換装置）、63Aメイン遮断器、ブスバー、Nバー、Eバー、3つの非常用回路。
```

```
単相230V配電盤。商用電源、ディーゼル発電機バックアップ、自動切換装置、100AメインMCCB、ブスバー、中性線バー、接地バー、非常用照明回路、非常用電源回路、火災警報回路。
```

```
三相415V配電盤。系統電源、スタンバイ発電機、ATS、250AメインMCCB、銅ブスバー、中性線バー、接地バー、11kWコンベアモータ、7.5kWポンプモータ、3kW制御盤。
```

```
単相230V UPS配電盤。商用入力、UPS出力、手動バイパススイッチ（ATS）、63Aメイン遮断器、4つの重要負荷回路。
```

---

## Custom & Special Diagrams

Custom components are any device the app doesn't recognise as a standard type (`supply`, `maincb`, `rcd`, `rcbo`, `bus`, `nbar`, `ebar`, `outcb`, `loads`). The app renders them as a generic symbol and adds a **Custom Device** row to the CAD legend table automatically.

Common custom components: surge protection device (SPD), energy meter, contactor, soft-starter, capacitor bank, ATSE, solar inverter, transformer.

**English**

```
Single phase 230V panel with main supply, energy meter, 63A main breaker, surge protection device (SPD), busbar, neutral bar, earth bar, and 3 load circuits.
```

```
230V single phase board with grid supply, solar inverter input, ATS, 100A main MCCB, busbar, neutral bar, earth bar, and 4 mixed load circuits.
```

```
Three-phase 415V motor control center with 200A main MCCB, copper busbar, neutral bar, earth bar, 3 contactors with soft-starters for 11kW conveyor motor, 7.5kW pump motor, and 5.5kW fan motor.
```

```
415V three-phase panel with utility supply, transformer (415V/230V step-down), 63A main breaker, RCD, neutral bar, earth bar, and lighting loads.
```

```
Single phase 230V panel with main supply, 100A main breaker, capacitor bank for power factor correction, busbar, neutral bar, earth bar, and 5 outgoing circuits.
```

**Japanese (日本語)**

```
単相230V配電盤。主電源、電力量計、63Aメイン遮断器、サージ防護装置（SPD）、ブスバー、中性線バー、接地バー、3つの負荷回路。
```

```
単相230V配電盤。グリッド電源、太陽光インバータ入力、ATS、100AメインMCCB、ブスバー、中性線バー、接地バー、4つの混合負荷回路。
```

```
三相415Vモータ制御センター。200AメインMCCB、銅ブスバー、中性線バー、接地バー、ソフトスタータ付き電磁接触器で11kWコンベアモータ、7.5kWポンプモータ、5.5kWファンモータを制御。
```

```
三相415V配電盤。系統電源、変圧器（415V/230Vステップダウン）、63Aメイン遮断器、漏電遮断器、中性線バー、接地バー、照明負荷。
```

```
単相230V配電盤。主電源、100Aメイン遮断器、力率改善用コンデンサバンク、ブスバー、中性線バー、接地バー、5つの引出回路。
```

---

## Tips for Writing Good Prompts

- **Name your loads specifically** — `5.5kW induction motor` is better than `motor`. Each named device gets its own branch breaker (`outcb_N`).
- **State the voltage** — include `230V`, `415V`, etc. If you don't, the app defaults to `unspecified`.
- **State the phase** — say `single phase` or `three-phase` if it matters. Otherwise the app infers from context.
- **Use "no RCD"** to explicitly exclude components, e.g. `simple 230V panel, no RCD, no earth, just a main breaker and two loads`.
- **ATS panels** — always name both supplies (`Grid Supply` and `Generator Backup`) and mention `ATS`. The app handles the dual-supply routing automatically.
- **Custom devices** — just name them naturally (`energy meter`, `SPD`, `contactor`). The app renders them as generic symbols and adds them to the CAD legend.
- **Japanese prompts** — write naturally in Japanese. The language detector activates automatically when Japanese characters are present and all labels are output in Japanese.

