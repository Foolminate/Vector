# [PROVISIONAL DRAFT] System Architecture & Design Specification Prompt: Project Vector

**DOCUMENT STATUS: PROVISIONAL / WORKING DRAFT**
*Note: This document is strictly a preliminary guide intended to facilitate discussion. All elements—including architecture, tool selection, and operational constraints—are provisional and will be iteratively improved and finalized during our alignment session.*

**Context for AI:** Act as a Senior Systems Architect and Technical Product Manager. I am providing a high-level, provisional overview of an automated, multi-agent workflow system named "Vector". Use this overview a starting point for a grilling session to align the design. Then then generate a System Design Document (SDD) that we will use as a baseline for development.

## 1. Proposed Project Overview
**Name:** Project Vector
**Proposed Objective:** To build a discreet, highly automated job discovery and evaluation engine. The system aims to leverage deterministic web scraping combined with probabilistic LLM orchestration to identify, evaluate, and structure technical supply chain and analytics roles, filtering out generic management positions. *(Alignment Action: Review weighting criteria for filtering)*.

## 2. Proposed Core Architecture (The "Triage" System)
The system is currently proposed to operate on a dual-stage pipeline to balance computational quality with API cost efficiency.

*   **The Collector (Deterministic Component - To Be Validated):**
    *   Proposed Tech: A Python-based web scraper (e.g., BeautifulSoup/Selenium).
    *   Target: Major job boards (initial discussion focus on Seek).
    *   Function: Extracts raw job description text, title, URL, and metadata based on broad boolean logic (e.g., "Supply Chain" AND "Python").
*   **Agent 1: The Sorter (Cost-Optimized AI - For Review):**
    *   Proposed Model: Lightweight/fast LLM (e.g., GPT-4o-mini or Claude 3 Haiku).
    *   Function: Rapid triage. Evaluates raw text against the Technical Doctrine to assign a score (0-100).
    *   States:
        *   **High-Pass (>=80):** Automatically triggers Agent 2.
        *   **Edge-Case (40-79):** Held for manual human review in the TUI.
        *   **Rejected (<40):** Discarded.
*   **Agent 2: The Evaluator & Synthesizer (Reasoning AI - For Review):**
    *   Proposed Model: Heavyweight LLM (e.g., Claude 3.5 Sonnet or GPT-4o).
    *   Function: Triggered only if Agent 1 returns 'True'. Performs deep qualitative analysis of the job description.
    *   Output: Forces the analysis into a strict, validated JSON schema (schema to be finalized in alignment).

## 3. Finalized JSON Output Schema (Agent 2)
The output from Agent 2 is structured to facilitate rapid human decision-making:
*   `verdict`: String (`shortlisted` | `discarded`)
*   `overlap_score`: Integer (1-10)
*   `role_type`: String (e.g., "Technical PM", "Data Engineer", "Supply Chain Analyst")
*   `technical_depth`: String (2-3 sentence technical summary)
*   `architectural_opportunities`: Array of Strings
*   `key_tech_stack`: Array of Strings
*   `red_flags`: Array of Strings
*   `remote_status`: String (`Verified` | `Likely` | `Unlikely`)

## 4. Provisional Operational Requirements & Constraints
*   **Cost Containment Strategy:** The system must strictly enforce the Agent 1 triage to prevent the heavyweight Agent 2 from processing junk data. Manual "Force Evaluation" in the TUI allows surgical overrides of Agent 1 decisions.
*   **Job Lifecycle (Clean Sweep):** The database serves as a temporary suppression list. Rejected or discarded jobs are retained to prevent re-scraping/re-analysis until their `expiration_date` (default: Scrape Date + 30 days). Expired rejected jobs are automatically purged to keep the database lean.
*   **Error Handling Approach:** The deterministic scraper must include robust exception handling so that UI changes on the target job boards do not crash the downstream pipeline.
*   **Delivery Mechanism Options:** Processed JSON data should be appended to a local database (e.g., SQLite or a CSV) and formatted into a daily automated email or lightweight HTML dashboard for morning review. *(Delivery format to be finalized in session)*.

## 5. Iterative Output Request
Once aligned, we will need a Technical Specification Document, including:
1.  Recommended Python libraries and environment setup.
2.  Draft system prompts (The "Doctrine") for both Agent 1 and Agent 2.
3.  A proposed data flow diagram (in Mermaid.js syntax).
4.  Specific edge cases and rate-limiting strategies to consider for the scraping module.
