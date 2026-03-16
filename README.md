# §121 GraphDB Pipeline Version 1.0

A proof of concept knowledge graph–driven application for evaluating **IRC §121 home sale exclusion** scenarios (**Note - Version 1.0 only implements the following sections of IRC §121: `121(a), 121(b)(1), 121(b)(2)(A), 121(b)(2)(B), 121(b)(3), 121(c), 121(d)(1)`). The system converts plain-English taxpayer descriptions into RDF/Turtle (`.ttl`) facts according to a predefined ontology via a large language model, validates and stores the information in a GraphDB knowledge graph, runs a chain of SPARQL queries to calculate results, and finally produces a readable determination of the taxpayer's exclusion.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture & Pipeline](#2-architecture--pipeline)
3. [Repository Structure](#3-repository-structure)
4. [Prerequisites](#4-prerequisites)
5. [Installation & Setup](#5-installation--setup)
6. [Configuration](#6-configuration)
7. [Running the Application](#7-running-the-application)
8. [Using the Application](#8-using-the-application)
   - [Tab 1 — TTL Editor](#tab-1--ttl-editor)
   - [Tab 2 — Prompt Builder](#tab-2--prompt-builder)
   - [Tab 3 — How to Use](#tab-3--how-to-use)
9. [Knowledge Graph Components](#9-knowledge-graph-components)
   - [Ontology](#ontology)
   - [SHACL Shapes](#shacl-shapes)
   - [SPARQL Queries](#sparql-queries)
10. [LLM Prompting System](#10-llm-prompting-system)
11. [Output Format & Interpretation](#11-output-format--interpretation)
12. [Evaluation & Testing](#12-evaluation--testing)
13. [Module Reference](#13-module-reference)
14. [Keyboard Shortcuts](#14-keyboard-shortcuts)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Project Overview

IRC §121 permits taxpayers to exclude up to $250,000 (single) or $500,000 (joint) of gain realized on the sale of a principal residence, contingent on satisfaction of ownership and use tests, frequency limitations, and partial-exclusion provisions. Consistent application of these rules across complex fact patterns — co-ownership arrangements, multiple dispositions, partial exclusions, and cross-property loss offsets — is often difficult to achieve manually due to the density and interdependence of the statutory language.

This project encodes §121 as a **formal knowledge graph** and automates the evaluation and calculation of property sale exclusions using the following:

- A **custom OWL ontology** represents taxpayer facts (ownership intervals, residence intervals, dispositions, returns, etc).
- **SHACL shapes** to help enforce the structural validity of the formatted data before any query-based reasoning is applied.
- **SPARQL UPDATE** queries encode the §121 rule application (of the implemented subset), using named subgraphs to keep each reasoning step isolated and independently verifiable.
- A **Python/tkinter desktop GUI** orchestrates the entire pipeline and displays results back to the user.
- A **structured prompting system** guides an LLM (ChatGPT / Claude / Gemini) to convert natural-language scenarios into syntactically correct Turtle files through constrained generation, role assignment, and iterative error correction.




---

## 2. Architecture & Pipeline

```
Plain-English Scenario
        │
        ▼
┌───────────────────┐
│  Prompt Builder   │  Assembles pre-prompt + ontology + SHACL + user scenario
│  (Tab 2 in GUI)   │
└────────┬──────────┘
         │  Full prompt copied to clipboard
         ▼
┌───────────────────┐
│   LLM of Choice   │  ChatGPT / Claude / Gemini
│  (external)       │  Returns RDF/Turtle inside a code block
└────────┬──────────┘
         │  TTL pasted / loaded into editor
         ▼
┌───────────────────────────────────────────────────────┐
│                  §121 Pipeline  (controller.py)       │
│                                                       │
│  Step 1  Upload TTL ────────►  GraphDB default graph  |
│                                                       │
│  Step 2  SHACL Validation ──► violations? ──► Error   │
│                                                       │
│  Step 3  NYI Check (NYICheck.sparql) ─── warnings?    │
│                                                       │
│  Step 4  DerivedInfoQuery.sparql  (SPARQL UPDATE)     │
│          InterpretationQuery.sparql (SPARQL UPDATE)   │
│                                                       │
│  Step 5  ResultsQuery.sparql (SPARQL SELECT)          │
│          │                                            │
│          ▼                                            │
│      formatter.py ──► Human-readable exclusion output │
└───────────────────────────────────────────────────────┘
```

**Key design decisions:**

- All legal reasoning lives in SPARQL — the LLM only converts facts into Turtle; it never applies tax law.
- SHACL validation acts as a hard gate; a violation prevents any reasoning from running.
- The NYI (Not-Yet-Implemented) check flags entities that are not defined in the ontology, producing warnings without hard-stopping the pipeline. These warnings are meant to act as caution signs for the user when viewing the proposed results.
- The formatter applies the §121(b)(1) $250k / $500k cap correctly at the taxpayer portfolio level, not per-property, allowing for the handling of loss offsets.

---

## 3. Repository Structure

```
§121-GraphDB-Pipeline/
│
├── App/                                 # Python application package
│   ├── __init__.py
│   ├── main.py                          # Entry point; GUI assembly (tkinter)
│   ├── controller.py                    # Backend logic; pipeline orchestration
│   ├── formatter.py                     # Result formatting; cap & offset logic
│   ├── graphdb_client.py                # HTTP calls to GraphDB REST API
│   ├── config.py                        # GraphDB URL & named-graph constants
│   ├── theme.py                         # UI color & font constants
│   └── widgets.py                       # Reusable styled tkinter widget factories
│
├── Prompting_Files/
│   ├── Combined_Prompting_File          # Full LLM system prompt (instructions + ontology + SHACL)
│   ├── Taxpayer_TTL_LLM_Instructions    # Standalone LLM instructions (subset of Combined)
│   ├── Section_121_Taxpayer_Ontology.ttl
│   └── Section_121_SHACL_Shapes.ttl
│
├── Resources/
│   └── SPARQL_Queries/
│       ├── DerivedInfoQuery.sparql      # SPARQL UPDATE — computes derived ownership/use facts
│       ├── InterpretationQuery.sparql   # SPARQL UPDATE — applies §121 rule logic
│       ├── NYICheck.sparql              # SPARQL SELECT — checks for undefined entities
│       └── ResultsQuery.sparql          # SPARQL SELECT — retrieves final exclusion results
│
└── Testing/
    ├── Accuracy_Validation_Cases/       # 77 hand-verified test cases (SPARQL pipeline accuracy)
    ├── Evaluation_Cases/                # 231 cases (77 × 3 runs) for full NL→Output evaluation
    │   └── Section_121_Evaluation_Cases.xlsx
    ├── Test_Cases/                      # Original prototype test cases
    └── Incorrect_Example_Cases/         # Annotated examples of typical LLM/pipeline errors
```

> **Note:** `Combined_Prompting_File` is automatically read by `main.py` at startup and pre-loaded into the Prompt Builder. Do not move or rename it without updating the path in `main.py`.

---

## 4. Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.9 + | 3.11+ recommended |
| tkinter | bundled with Python | Confirm with `python -m tkinter` |
| GraphDB Free | 10.x | [Download](https://graphdb.ontotext.com/) |
| requests | ≥ 2.28 | `pip install requests` |

No other third-party Python libraries are required.

You will also need access to at least one LLM (ChatGPT, Claude, or Gemini) through your browser — direct links are provided inside the application.

---

## 5. Installation & Setup

### 5.1 Clone the Repository

```bash
git clone https://github.com/AndrewCSAllison/Section121TaxLaw.git
cd Section121TaxLaw
```

### 5.2 Install Python Dependencies

```bash
pip install -r App/requirements.txt
```

### 5.3 Install & Configure GraphDB

1. Download and install **GraphDB Free** from [https://graphdb.ontotext.com/](https://graphdb.ontotext.com/).
2. Start the GraphDB server (default port: `7200`).
3. Open the GraphDB Workbench at `http://localhost:7200`.
4. Create a new repository:
   - Navigate to **Setup → Repositories → Create new repository**.
   - Repository type: **GraphDB Repository**.
   - Repository ID: `Section121TaxLaw` *(must match `config.py`)*.
   - Enable the **SHACL** plugin: under the "Validation" section, set **SHACL validation** to **enabled**.
   - Leave all other settings at their defaults and click **Create**.

### 5.4 Load Base Ontology & SHACL Shapes

The application can reload these automatically via the **⟳ Reset Repository** button, but for first-time setup you can also load them manually through the GraphDB Workbench:

1. Import `Prompting_Files/Section_121_Taxpayer_Ontology.ttl` into the named graph:
   `http://example.org/section121/Ontology`
2. Import `Prompting_Files/Section_121_SHACL_Shapes.ttl` into the named graph:
   `http://rdf4j.org/schema/rdf4j#SHACLShapeGraph`

Once loaded, the repository is ready for use. The application will preserve these graphs across resets.

---

## 6. Configuration

All connection settings are in `App/config.py`:

```python
GRAPHDB_REPO  = "http://localhost:7200/repositories/Section121TaxLaw"
SHACL_GRAPH   = "http://rdf4j.org/schema/rdf4j#SHACLShapeGraph"
ONTOLOGY_GRAPH = "http://example.org/section121/Ontology"
```

| Variable | Purpose |
|---|---|
| `GRAPHDB_REPO` | Full URL of the GraphDB repository endpoint |
| `SHACL_GRAPH` | Named graph where SHACL shapes are stored |
| `ONTOLOGY_GRAPH` | Named graph where the OWL ontology is stored |

If you use a different port, host, or repository name, update `GRAPHDB_REPO` accordingly. The SHACL and ontology graph URIs should not normally need to change.

---

## 7. Running the Application

```bash
# From the repository root
python -m App.main
```

The application window opens at 1100 × 700 px (minimum 900 × 600). It consists of three tabs: **TTL Editor**, **Prompt Builder**, and **How to Use**.

---

## 8. Using the Application

### Recommended Workflow

```
Prompt Builder tab  →  External LLM  →  TTL Editor tab  →  View Results
```

---

### Tab 1 — TTL Editor

The primary working tab. Split into two panels:

**Left panel — Turtle Input**

| Control | Action |
|---|---|
| Text area | Paste or type the TTL content generated by the LLM |
| 📂 Load File | Opens a file picker to load a `.ttl` file from disk |
| ✕ Clear | Clears the editor |
| ▶ Submit & Run Rules | Uploads the TTL and runs the full §121 pipeline |
| ⟳ Reset Repository | Clears all triples from GraphDB and reloads the base ontology + SHACL shapes |
| Char counter | Live character count shown below the editor |

**Right panel — Pipeline Output**

Displays timestamped, color-coded pipeline progress:

| Color | Symbol | Meaning |
|---|---|---|
| Green | ✔ | Step completed successfully |
| Red | ✘ | Error — pipeline halted; review message and fix TTL |
| Yellow | ⚠ | Warning — undefined entities detected; pipeline continues |
| Blue (bold) | — | Section heading / submission timestamp |
| White | — | Final exclusion results |

The **Copy** button copies all output text to the clipboard. The **Clear** button resets the output panel.

**Important:** Before submitting a *new* scenario, always click **⟳ Reset Repository** to prevent data from a previous scenario from interfering with the current one. If unexpected errors occur, usually clicking **⟳ Reset Repository** fixes it by restoring the GraphDB setup to its original state with no uploaded TTL files. 

---

### Tab 2 — Prompt Builder

Assembles the complete LLM prompt from your scenario description.

**Left panel — Your Scenario**

1. Click **▶ What to include in your scenario** to expand the checklist of required facts.
2. Write a plain-English description of the taxpayer scenario in the text box. Include:
   - Taxpayer name(s) and marital/filing status
   - Property name(s)
   - Ownership start/end date per taxpayer per property, and percentage owned if split
   - Residence start/end date per taxpayer per property
   - Sale date and realized gain (positive) or loss (negative) per property
   - Return type (Single or Joint) and which taxpayers / dispositions belong to it
   - Partial exclusion reason, if applicable: Employment-related, Health-related, Unforeseen circumstance, or Non-qualifying

   > **Tip:** Dates and amounts can be written naturally — `"January 2001"`, `"$300k"`, `"three hundred thousand dollars"` — the LLM will convert them to the correct XSD datatypes.
   >
   > **Do not** compute or include exclusion amounts; those are calculated automatically by the SPARQL pipeline.

3. Click **⚙ Build Prompt** to assemble the full prompt in the right panel.

**Right panel — Assembled Prompt**

The pre-loaded system instructions (from `Combined_Prompting_File`) are shown first, followed by your scenario text after clicking Build Prompt.

| Control | Action |
|---|---|
| ⚙ Build Prompt | Concatenates pre-prompt + scenario; populates right panel |
| 📋 Copy Full Prompt | Copies the assembled prompt to clipboard |
| ↗ ChatGPT | Opens `https://chat.openai.com/` in your browser |
| ↗ Claude | Opens `https://claude.ai/new` in your browser |
| ↗ Gemini | Opens `https://gemini.google.com/app` in your browser |

After copying the prompt, paste it into the LLM of your choice. The LLM will either return a Turtle file inside a Markdown code block or ask you to clarify information. Follow it as instructed and then copy the full TTL output (including all `@prefix` lines) and paste it into the TTL Editor.

---

### Tab 3 — How to Use

A scrollable, step-by-step in-app guide that mirrors the workflow above. Useful as a quick reference while working.

---

## 9. Knowledge Graph Components

### Ontology

**File:** `Prompting_Files/Section_121_Taxpayer_Ontology.ttl`  
**Named graph:** `http://example.org/section121/Ontology`  
**Namespace prefix:** `:` → `http://example.org/section121#`

The ontology declares the following OWL classes:

| Class | Description |
|---|---|
| `:Taxpayer` | An individual taxpayer |
| `:Property` | A real property asset |
| `:OwnershipUseInterval` | A contiguous period during which a taxpayer owned a property |
| `:ResidenceUseInterval` | A contiguous period during which a taxpayer used a property as a principal residence |
| `:Disposition` | A sale or other disposition of a property |
| `:Return` | A tax return (superclass) |
| `:SingleReturn` | A single-filer return (exclusion cap: $250,000) |
| `:JointReturn` | A joint-filer return (exclusion cap: $500,000) |
| `:DerivedInfo` | Computed facts populated by SPARQL (do not assert manually) |
| `:Interpretation` | Rule conclusions populated by SPARQL (do not assert manually) |
| `:ReasonType` | A §121(c) partial exclusion reason type |

Key individuals of `:ReasonType`:

| Individual | Meaning |
|---|---|
| `:EmploymentRelatedReason` | Job change, reassignment, ≥ 50-mile distance requirement |
| `:HealthRelatedReason` | Illness, injury, or care for a family member |
| `:UnforeseenCircumstanceReason` | Divorce, death, financial hardship, etc. |
| `:NonQualifyingReason` | Explicitly does not qualify for partial exclusion |

Key datatype properties:

| Property | Domain | Range | Required |
|---|---|---|---|
| `:ownershipStart` | `:OwnershipUseInterval` | `xsd:date` | Yes |
| `:ownershipEnd` | `:OwnershipUseInterval` | `xsd:date` | Yes |
| `:percentageOwned` | `:OwnershipUseInterval` | `xsd:decimal` | No (0–1) |
| `:residenceStart` | `:ResidenceUseInterval` | `xsd:date` | Yes |
| `:residenceEnd` | `:ResidenceUseInterval` | `xsd:date` | Yes |
| `:sellDate` | `:Disposition` | `xsd:date` | Yes |
| `:potentialGain` | `:Disposition` | `xsd:integer` | Yes |
| `:exclusionCap` | `:Return` | `xsd:integer` | Yes |

Key object properties:

| Property | Domain | Range |
|---|---|---|
| `:owns` | `:Taxpayer` | `:OwnershipUseInterval` |
| `:uses` | `:Taxpayer` | `:ResidenceUseInterval` |
| `:disposesOf` | `:Taxpayer` | `:Disposition` |
| `:hasOwnershipOf` | `:OwnershipUseInterval` | `:Property` |
| `:hasResidenceOf` | `:ResidenceUseInterval` | `:Property` |
| `:involves` | `:Disposition` | `:Property` |
| `:associates` | `:Return` | `:Taxpayer` |
| `:linkedTo` | `:Return` | `:Disposition` |
| `:partialExclusionReason` | `:Disposition` | `:ReasonType` |

---

### SHACL Shapes

**File:** `Prompting_Files/Section_121_SHACL_Shapes.ttl`  
**Named graph:** `http://rdf4j.org/schema/rdf4j#SHACLShapeGraph`

SHACL validation is run before any SPARQL reasoning. Violations halt the pipeline. The shapes enforce:

| Shape | Key constraints |
|---|---|
| `:TaxpayerShape` | Ensures `:owns`, `:uses`, `:disposesOf` point to correct classes |
| `:OwnershipUseIntervalShape` | Exactly one `:hasOwnershipOf` (Property); exactly one `:ownershipStart` and `:ownershipEnd`; optional `:percentageOwned` in [0, 1] |
| `:ResidenceUseIntervalShape` | Exactly one `:hasResidenceOf`; exactly one `:residenceStart` and `:residenceEnd` |
| `:DispositionShape` | Exactly one `:involves` (Property); exactly one `:sellDate`; exactly one `:potentialGain`; optional `:partialExclusionReason` from the four valid individuals |
| `:ReturnShape` | At least one `:associates` (Taxpayer); at least one `:linkedTo` (Disposition) |
| `:SingleReturnShape` | `:exclusionCap` must be exactly 250,000 |
| `:JointReturnShape` | `:exclusionCap` must be exactly 500,000 |

---

### SPARQL Queries

All SPARQL files live in `Resources/SPARQL_Queries/`.

#### `NYICheck.sparql` — Undefined Entity Check (SELECT)

Scans the base data graph for any classes or properties not declared in the ontology named graph. Returns a table of `(?s, ?undefined, ?type)` bindings. Results are shown as warnings (yellow) and do not halt the pipeline.

#### `DerivedInfoQuery.sparql` — Derived Facts (UPDATE)

Computes intermediate facts and writes them to `:DerivedInfo` instances in the triplestore. This includes aggregated ownership duration, residence duration, and other facts needed by the interpretation step.

#### `InterpretationQuery.sparql` — Rule Application (UPDATE)

Applies the §121 rule logic and writes conclusions to `:Interpretation` instances. Covers:

- **§121(a)** — principal residence ownership and use tests (2-of-5 year rules)
- **§121(b)(1)** — single-return exclusion cap ($250,000)
- **§121(b)(2)(A)** — joint-return exclusion, both spouses qualify
- **§121(b)(2)(B)** — joint-return exclusion, one spouse qualifies
- **§121(b)(3)** — frequency limitation (not more than once every 2 years)
- **§121(c)** — reduced maximum exclusion (partial exclusion) for employment, health, or unforeseen circumstance
- **§121(d)(1)** — surviving spouse rule (2-year window after death of a spouse)

#### `ResultsQuery.sparql` — Final Results (SELECT)

Retrieves all `:Interpretation` bindings and joins them with taxpayer, property, sale date, realized gain, and excluded gain values for display.

---

## 10. LLM Prompting System

The **Combined Prompting File** (`Prompting_Files/Combined_Prompting_File`) is the single document sent to the LLM. It contains, in order:

1. **Role and scope instructions** — The LLM's sole task is Turtle generation and repair. It must not interpret tax law, apply legal reasoning, compute exclusions, or infer missing facts.
2. **Allowed tasks** — Convert NL to Turtle; repair Turtle given SHACL/NYI error messages; ask clarifying questions for missing facts.
3. **Output requirements** — Valid Turtle syntax only, inside a Markdown code block, no prose outside the code block.
4. **Ontology compliance rules** — Use only declared classes, properties, and individuals; correct XSD datatypes; no `:DerivedInfo` or `:Interpretation` triples.
5. **Specific §121 modeling rules** — Property linking requirement, instantiation requirement, co-owner splitting logic, non-continuous interval modeling.
6. **Error handling instructions** — How to respond to SHACL violations and NYI warnings pasted back from the pipeline output.
7. **The full ontology** — Embedded directly so the LLM knows every valid class, property, and individual.
8. **The full SHACL shapes** — Embedded so the LLM can self-validate before generating output.

**Error correction loop:** If the pipeline returns a red error message (SHACL violation or upload failure), copy the error text from the Pipeline Output panel, paste it back into the LLM conversation, and the LLM will repair the affected triples and return a corrected Turtle file. Repeat this step until errors stop persisting.

---

## 11. Output Format & Interpretation

After a successful pipeline run, the results panel displays one block per taxpayer / disposition:

```
Taxpayer TaxpayerA sold property MainResidence on 2024-06-01.
- §121(a) applies
- §121(b)(1) exclusion
Realized gain: 300000.0, Excluded gain: 250000.0, Taxable gain: 50000.0
```

**Multi-property scenarios (single taxpayer, §121(b)(1) only):**

The formatter aggregates gains and losses across all properties before applying the $250k cap, showing a per-property breakdown and a portfolio-level total:

```
Taxpayer TaxpayerA sold multiple properties:
  PropertyOne (sold 2024-06-01): realized 350000.0, excluded 250000.0, taxable 100000.0
  PropertyTwo (sold 2024-08-01): realized -50000.0  [loss — not excludable]
  ($250,000 exclusion cap applies across all properties)
- §121(a) applies
- §121(b)(1) exclusion
Total realized gain: 300000.0, Total excluded: 250000.0, Total taxable: 50000.0
```

**Joint-return / surviving-spouse scenarios:**

Taxpayers on the same disposition are aggregated together with the combined $500k cap:

```
Taxpayers TaxpayerA, TaxpayerB sold property MainResidence on 2024-06-01.
- §121(b)(2)(A) exclusion
Realized gain: 600000.0, Excluded gain: 500000.0, Taxable gain: 100000.0
```

---

## 12. Evaluation & Testing

The `Testing/` directory contains four suites of cases:

### Federal Regulations Test Cases (30 cases)
Initial prototype cases directly taken from [ecfr.gov](ecfr.gov) used to verify that the NL → Turtle → SPARQL pipeline worked end-to-end. These served as proof-of-concept before systematic accuracy evaluation. 

[Section §1.121-1](https://www.ecfr.gov/current/title-26/chapter-I/subchapter-A/part-1/subject-group-ECFRb467872627553f1/section-1.121-1)\
[Section §1.121-2](https://www.ecfr.gov/current/title-26/chapter-I/subchapter-A/part-1/subject-group-ECFRb467872627553f1/section-1.121-2)\
[Section §1.121-3](https://www.ecfr.gov/current/title-26/chapter-I/subchapter-A/part-1/subject-group-ECFRb467872627553f1/section-1.121-3)

### Accuracy Validation Cases (77 cases)
A curated set of 77 scenarios with hand-verified expected outputs. These test the accuracy of the **SPARQL pipeline in isolation** — they assume a correct Turtle file is already provided and measure whether the SPARQL rules produce the correct exclusion determination.

### Evaluation Cases (231 cases) — primary benchmark
**File:** `Section_121_Evaluation_Cases.xlsx`

The 77 Accuracy Validation Cases run **three times each** (231 total runs). Each run puts a different LLM-generated Turtle file through the full pipeline, measuring:

- **LLM reproducibility** — does the LLM generate equivalent Turtle across runs for the same scenario?
- **End-to-end accuracy** — does the full NL → LLM → TTL → SPARQL → Output pipeline produce the correct final answer?

This is the primary benchmark for overall system performance.

### Incorrect Example Cases
Annotated examples of the most common failure modes, including:
- Incorrect XSD datatypes (e.g., using `xsd:string` for a date)
- Missing property links (e.g., omitting `:hasOwnershipOf`)
- Hallucinated predicates not in the ontology
- Incorrect co-owner modeling (wrong `:percentageOwned`, wrong return type)
- Applying partial exclusion reasons that were not mentioned in the scenario

These are useful for understanding the kinds of errors the LLM makes and for improving the prompting system.

---

## 13. Module Reference

### `config.py`
Defines the three string constants (`GRAPHDB_REPO`, `SHACL_GRAPH`, `ONTOLOGY_GRAPH`) used throughout the application. Edit this file to point to a different GraphDB instance.

### `graphdb_client.py`
All HTTP communication with GraphDB. Functions:

| Function | Description |
|---|---|
| `upload_ttl(ttl_content, target_graph=None)` | POST Turtle content to the default or a named graph |
| `run_shacl_validation()` | CONSTRUCT query to retrieve current SHACL violations; returns empty string if none |
| `run_update_query(query, from_file=True)` | Execute a SPARQL UPDATE; if `from_file=True`, loads from `SPARQL_DIR` |
| `run_select_query(filename)` | Execute a SPARQL SELECT from a file; returns parsed JSON |
| `load_query_file(filename)` | Read a `.sparql` file from `Resources/SPARQL_Queries/` |

### `controller.py`
Business logic layer. Functions:

| Function | Description |
|---|---|
| `submit_with_callback(ttl_content, log)` | Runs the full 5-step pipeline; routes all messages through the `log(msg, tag)` callback |
| `clear_repository()` | CLEAR ALL, then reload ontology and SHACL shapes |
| `load_file(ttl_text_widget)` | Opens a file dialog and populates a tkinter Text widget |
| `load_file_contents(path)` | Read a file and return its text content |
| `submit(ttl_text_widget, output_text_widget)` | Legacy entry point; kept for backwards compatibility |

Pipeline steps in `submit_with_callback`:
1. Upload TTL
2. Run SHACL validation (halt on violations)
3. Run NYI check (warn, continue)
4. Run `DerivedInfoQuery.sparql` and `InterpretationQuery.sparql`
5. Run `ResultsQuery.sparql` and format output

### `formatter.py`
Converts the SPARQL SELECT JSON result into human-readable text. Implements:
- Grouping by taxpayer and (property, sell-date) key
- Joint-rule detection for §121(b)(2)(A/B) and §121(d)(1)
- Cross-property gain aggregation and loss-offset logic for §121(b)(1) single-return scenarios
- $250k / $500k cap enforcement at the correct level of aggregation

### `main.py`
Application entry point. Assembles three tabbed panels with tkinter/ttk. Reads `Combined_Prompting_File` at startup. Runs pipeline submissions on a background thread to keep the UI responsive.

### `theme.py`
Color and font constants for the dark UI theme. Import these in any new widget module rather than hard-coding color strings.

### `widgets.py`
Reusable themed widget factories:
- `styled_text(parent)` — dark-themed `tk.Text`
- `styled_scrolled(parent)` — bordered frame with text + scrollbar
- `pill_button(parent, text, command, color)` — flat button with hover effect
- `section_label(parent, text)` — small uppercase section header

---

## 14. Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+Enter` | Submit & Run Rules (TTL Editor) |
| `Ctrl+O` | Load TTL file from disk |

---

## 15. Troubleshooting

**"Connection refused" or HTTP error on submission**
- Confirm GraphDB is running: open `http://localhost:7200` in a browser.
- Verify the repository ID matches `GRAPHDB_REPO` in `config.py`.
- Check that the SHACL plugin is enabled for the repository.

**SHACL violations on upload**
- Copy the red error text from the Pipeline Output panel.
- Paste it back into your LLM conversation.
- The LLM will identify and repair only the offending triples.
- Copy the corrected TTL and re-submit.

**NYI warnings (yellow) in output**
- The pipeline will continue, but the TTL contains classes or properties not declared in the ontology.
- Common cause: LLM invented a predicate not in the ontology, e.g. `:hasSalePrice` instead of `:potentialGain`.
- Fix by pasting the warning back to the LLM and asking it to map undefined terms to ontology-defined ones.

**Results panel shows "(no results returned)"**
- This usually means SPARQL could not find a matching `:Interpretation` instance.
- Check that the TTL contains all required facts (ownership, residence, disposition, return).
- Re-run the NYI check manually if needed.

**Application crashes on startup with `FileNotFoundError`**
- `main.py` reads `Prompting_Files/Combined_Prompting_File` relative to the working directory.
- Always launch the application from the repository root, not from inside `App/`.

**"Module not found" errors**
- Run the app as a module from the root: `python -m App.main`
- The fallback `except ModuleNotFoundError` imports in `controller.py` and `graphdb_client.py` handle direct-script execution, but running as a package is the recommended approach.

**Previous scenario data affecting results**
- Always click **⟳ Reset Repository** before submitting a new scenario.
- Confirm the reset dialog when prompted.

---

*Built for proof-of-concept research into knowledge-graph–driven tax law reasoning under the **Loyola University Chicago Lab for Applied AI**. All legal conclusions should be verified by a qualified tax professional.*