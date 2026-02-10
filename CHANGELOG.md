# Changelog

All notable changes to Project Virgil are documented here. Only the latest release is shown in [README.md](README.md).

---

## v1.4.0 (Backend + Frontend) - February 2026

**Diagram Pipeline Overhaul:**
- ✅ **Baseline Stage**: Unconstrained LLM call (no guardrails) as first pipeline stage — demonstrates raw output quality without ontology, hard limits, or vocabulary enforcement
- ✅ **Query-Aware Subgraph**: `get_relevant_subgraph()` extracts ontology nodes/edges relevant to the user query with 1-hop expansion, shown in pipeline with color-coded layer badges
- ✅ **Label Replacement Mapping**: 32 vague→standard label rules (e.g., leverages→references, manages→depends on, hosts→runs on, triggers→creates) displayed as a visible mapping grid in the pipeline
- ✅ **Reference Example Diagram**: Auto-generated from the query-relevant ontology subgraph, renderable directly in the constraints panel
- ✅ **Expanded Blocked Labels**: From 9 to 32 rules — added handles, triggers, sends to, links to, powered by, drives, facilitates, enables, orchestrates, maintains, governs, oversees, etc.
- ✅ **Validator Fix**: `ArchitectureValidator` was never instantiated on `LLMService` — stage 4 always crashed silently, showing a duplicate of stage 3. Now properly imported and initialized.
- ✅ **Validator Always Visible**: Ontology Validator stage now always appears in pipeline even when validation throws an exception
- ✅ **Clean Validator Message**: Shows "Ontology rules already satisfied — prompt constraints prevented issues pre-generation" when no corrections needed

**Frontend (DiagramLog.js) Rewrite:**
- ✅ Baseline stage with red theme, code-only view, "No guardrails" badge
- ✅ Label replacement mapping grid (vague → standard) in Ontology Constraints panel
- ✅ Query-relevant subgraph display with color-coded nodes by architecture layer
- ✅ Segregation rules shown when applicable
- ✅ Reference diagram with render/code toggle
- ✅ Full ontology stats labeled "Full Ontology Graph"
- ✅ Baseline stage is permanently code-only (no render toggle) to prevent mermaid error spam

**Pipeline Stages (5 stages):**

| # | Stage | Purpose |
|---|-------|---------|
| 0 | Baseline (red) | Raw LLM output — no rules, no limits, no vocabulary |
| 1 | Ontology Constraints (purple) | Hard limits, allowed labels, 32 replacement rules, subgraph, reference diagram |
| 2 | LLM Output (blue) | Guided LLM response with all constraints applied |
| 3 | Syntax Sanitizer (amber) | Mermaid syntax auto-fix (special chars, arrow format, node IDs) |
| 4 | Ontology Validator (green) | Post-generation enforcement — removes invalid arrows, normalizes labels |

---

## v1.3.0 (Backend) - February 2026

**Ontology Refactor:**
- ✅ Replaced flat dict/list ontology with graph-based knowledge model (40 nodes, 65 typed edges)
- ✅ OntologyNode: id, label, node_type, aliases, actual SN table names, plugin IDs, architecture layer
- ✅ OntologyEdge: typed relationships (extends, depends_on, runs_on, references, creates, consumes, resolves_using, authenticates_via, segregated_from)
- ✅ Table hierarchy: incident/problem/change/case/hr_case/sec_incident/service_catalog all extend task
- ✅ Graph traversal: find_node(), what_depends_on(), what_does_it_need(), get_children()
- ✅ Coverage: ITSM, CSM, HRSD, ITOM, SecOps, GRC, SPM products and all major modules

**Validator Enforcement:**
- ✅ Validator now REMOVES invalid arrows and returns corrected diagrams (was only logging warnings)
- ✅ Parses node ID→label mappings for accurate anti-pattern detection
- ✅ Arrow count enforcement: prunes lowest-priority connections when over limit
- ✅ Priority system: keeps runs_on/creates/references, drops manages/connects/uses
- ✅ Bidirectional arrow detection and circular dependency checking
- ✅ Label vocabulary enforcement: auto-replaces vague labels
- ✅ Missing relationship detection: flags when ITSM/CSM nodes lack required `runs on` → Platform

**Prompt Hardening:**
- ✅ Hard limits: max 15 arrows, max 10 nodes, max 4 subgraphs, max 3 outgoing per node
- ✅ Explicit ALLOWED RELATIONSHIP LABELS whitelist
- ✅ REQUIRED RELATIONSHIPS: apps must `runs on` Platform, portals must `authenticates via` Identity
- ✅ Orchestration components inside Application layer subgraph
- ✅ Group related modules into single nodes

---

## v1.2.4 (Backend) - February 2026

**Backend Fixes:**
- ✅ Fixed Mermaid syntax errors caused by `&` in subgraph names
- ✅ Fixed Mermaid syntax errors caused by `/` and `()` in edge labels
- ✅ Fixed Mermaid syntax errors caused by numbered subgraph prefixes
- ✅ Mermaid sanitizer now applied to both structured output and fallback JSON parsing paths
- ✅ JSON parsing now uses `strict=False` to tolerate literal newlines in LLM responses
- ✅ Added detailed JSONDecodeError logging with position and raw text dump
- ✅ Added ServiceNow JDBC user role/ACL documentation

---

## v1.2.3 (Frontend) + v1.2.1 (Backend) - February 2026

**Frontend Fixes (v1.2.3):**
- ✅ Fixed setup wizard navigation — Continue button now properly advances to ServiceNow configuration
- ✅ Configured axios to use correct backend URL in Docker deployments
- ✅ Added click prevention to avoid multiple rapid API calls
- ✅ Resolved browser caching issues with hard refresh recommendations

**Backend Fixes (v1.2.1):**
- ✅ Fixed Mermaid syntax errors caused by parentheses in node labels
- ✅ Auto-fix now converts `Platform (FedRAMP/SPP)` to `Platform - FedRAMP/SPP`
- ✅ Improved diagram rendering reliability across all deployment methods

**Infrastructure:**
- ✅ ARM64 (Apple Silicon) compatible Docker images
- ✅ OpenJDK 21 for Debian Trixie compatibility
- ✅ Both local and Docker deployments fully tested and working

**Docker Hub Images:**
- Backend: `leofrancia08489/project-virgil-backend:v1.2.1`
- Frontend: `leofrancia08489/project-virgil-frontend:v1.2.3`
