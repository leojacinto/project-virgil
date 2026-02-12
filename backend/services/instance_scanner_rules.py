"""
Deterministic Rule Engine for ServiceNow Instance Analysis.

Rules derived from:
  - IT4IT v3 Blueprint (Ian Leu) — Value stream coverage analysis
  - Integration Pattern Decision Tree (Jochen Geist) — Integration best practices
  - ServiceNow architectural best practices — Instance health checks

STATUS: DISABLED — Pending approval from knowledge source authors.
         Set ENABLED = True once Ian Leu and Jochen Geist approve usage.

Architecture:
  Layer 1: Instance Scanner (REST API) → builds structured instance model
  Layer 2: Rule Engine (this file) → evaluates model against deterministic rules
  Layer 3: LLM (optional) → generates human-readable report from findings
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Global kill switch — nothing runs until this is True
# ---------------------------------------------------------------------------
ENABLED = False  # Flip to True once Ian Leu and Jochen Geist approve usage


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class RuleSource(Enum):
    IT4IT = "IT4IT v3 Blueprint (Ian Leu)"
    INTEGRATION = "Integration Pattern Decision Tree (Jochen Geist)"
    BEST_PRACTICE = "ServiceNow Architectural Best Practices"


@dataclass
class Rule:
    """A single deterministic rule in the engine."""
    id: str
    name: str
    description: str
    source: RuleSource
    severity: Severity
    category: str                       # e.g. "it4it_coverage", "integration_pattern", "health"
    condition_description: str           # human-readable condition
    recommendation: str                  # what to do if rule fires
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "source": self.source.value,
            "severity": self.severity.value,
            "category": self.category,
            "condition": self.condition_description,
            "recommendation": self.recommendation,
            "tags": self.tags,
        }


@dataclass
class Finding:
    """A finding produced when a rule fires against an instance model."""
    rule_id: str
    rule_name: str
    severity: Severity
    source: str
    category: str
    message: str
    recommendation: str
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": self.severity.value,
            "source": self.source,
            "category": self.category,
            "message": self.message,
            "recommendation": self.recommendation,
            "evidence": self.evidence,
        }


@dataclass
class InstanceModel:
    """Structured representation of a scanned ServiceNow instance.
    Built by the Instance Scanner (Layer 1) from REST API queries.
    """
    instance_url: str = ""
    # Installed plugins/apps: plugin_id -> {active: bool, version: str, name: str}
    installed_plugins: Dict[str, Dict] = field(default_factory=dict)
    # Active tables with record counts: table_name -> count
    active_tables: Dict[str, int] = field(default_factory=dict)
    # Table relationships: table_name -> [{field, reference_table}]
    table_relationships: Dict[str, List[Dict]] = field(default_factory=dict)
    # Integration Hub flows: [{name, active, spoke, trigger_type, last_run}]
    integration_flows: List[Dict] = field(default_factory=list)
    # MID Server info: [{name, status, host}]
    mid_servers: List[Dict] = field(default_factory=list)
    # CMDB stats: {total_cis: int, classes_populated: [...], last_discovery: str}
    cmdb_stats: Dict[str, Any] = field(default_factory=dict)
    # Properties: property_name -> value
    instance_properties: Dict[str, str] = field(default_factory=dict)
    # Domain separation enabled
    domain_separation: bool = False
    # Instance version
    instance_version: str = ""


# ---------------------------------------------------------------------------
# IT4IT v3 Value Stream Coverage Rules (Source: Ian Leu)
# ---------------------------------------------------------------------------
# These rules analyze which IT4IT value streams are covered by the
# installed/active plugins and flag gaps in coverage.
# Value Streams: S2P, R2D, R2F, D2C
# ---------------------------------------------------------------------------

IT4IT_RULES: List[Rule] = [
    # --- Strategy to Portfolio (S2P) ---
    Rule(
        id="IT4IT-S2P-001",
        name="No Strategic Portfolio Management",
        description="Instance has no SPM/ITBM capability for Strategy to Portfolio value stream.",
        source=RuleSource.IT4IT,
        severity=Severity.MEDIUM,
        category="it4it_coverage",
        condition_description="SPM plugin (com.snc.project_management) is not installed or inactive",
        recommendation="Consider enabling Strategic Portfolio Management (SPM) to cover the "
                       "Strategy to Portfolio (S2P) value stream. This enables demand management, "
                       "portfolio prioritization, and investment planning.",
        tags=["S2P", "spm", "itbm", "portfolio"],
    ),
    Rule(
        id="IT4IT-S2P-002",
        name="No Governance Risk Compliance",
        description="Instance has no GRC capability. Strategy to Portfolio requires governance oversight.",
        source=RuleSource.IT4IT,
        severity=Severity.MEDIUM,
        category="it4it_coverage",
        condition_description="GRC plugins (com.sn_compliance, com.sn_risk) are not installed or inactive",
        recommendation="Enable GRC (Integrated Risk Management) to provide governance, risk assessment, "
                       "and compliance monitoring as part of the S2P value stream.",
        tags=["S2P", "grc", "compliance", "risk"],
    ),

    # --- Requirement to Deploy (R2D) ---
    Rule(
        id="IT4IT-R2D-001",
        name="No Change Management Process",
        description="Instance has no active Change Management. R2D requires controlled deployment.",
        source=RuleSource.IT4IT,
        severity=Severity.HIGH,
        category="it4it_coverage",
        condition_description="Change Management plugin (com.snc.change_management) is not installed or "
                              "change_request table has zero records",
        recommendation="Enable Change Management to provide controlled release and deployment "
                       "processes as required by the Requirement to Deploy (R2D) value stream.",
        tags=["R2D", "change", "deployment"],
    ),
    Rule(
        id="IT4IT-R2D-002",
        name="No CMDB for Configuration Tracking",
        description="CMDB is not populated. R2D requires configuration item tracking for deployments.",
        source=RuleSource.IT4IT,
        severity=Severity.HIGH,
        category="it4it_coverage",
        condition_description="cmdb_ci table has fewer than 100 records or Discovery is not active",
        recommendation="Populate the CMDB via Discovery or Service Mapping to track configuration items "
                       "that are affected by deployments. A well-maintained CMDB is critical for R2D.",
        tags=["R2D", "cmdb", "discovery", "configuration"],
    ),

    # --- Request to Fulfill (R2F) ---
    Rule(
        id="IT4IT-R2F-001",
        name="No Service Catalog",
        description="Instance has no Service Catalog. R2F requires a request intake mechanism.",
        source=RuleSource.IT4IT,
        severity=Severity.HIGH,
        category="it4it_coverage",
        condition_description="Service Catalog plugin (com.glideapp.servicecatalog) is not installed "
                              "or sc_cat_item table has zero active items",
        recommendation="Enable Service Catalog to provide a structured request intake and fulfillment "
                       "mechanism as required by the Request to Fulfill (R2F) value stream.",
        tags=["R2F", "catalog", "request", "fulfillment"],
    ),
    Rule(
        id="IT4IT-R2F-002",
        name="No Self-Service Portal",
        description="Instance has no portal for self-service. R2F requires user-facing request channel.",
        source=RuleSource.IT4IT,
        severity=Severity.MEDIUM,
        category="it4it_coverage",
        condition_description="Service Portal plugin (com.glide.service-portal) is not installed "
                              "and Employee Center (com.sn_employee_center) is not installed",
        recommendation="Deploy Service Portal or Employee Center to provide end-users with a "
                       "self-service channel for submitting and tracking requests.",
        tags=["R2F", "portal", "self-service"],
    ),
    Rule(
        id="IT4IT-R2F-003",
        name="No Knowledge Base for Self-Resolution",
        description="Knowledge Base is not active. R2F benefits from self-resolution to reduce ticket volume.",
        source=RuleSource.IT4IT,
        severity=Severity.MEDIUM,
        category="it4it_coverage",
        condition_description="Knowledge plugin (com.glideapp.knowledge) is not installed "
                              "or kb_knowledge table has fewer than 10 published articles",
        recommendation="Enable and populate the Knowledge Base to allow end-users to self-resolve "
                       "common issues, reducing ticket volume in the R2F stream.",
        tags=["R2F", "knowledge", "self-service"],
    ),

    # --- Detect to Correct (D2C) ---
    Rule(
        id="IT4IT-D2C-001",
        name="No Incident Management",
        description="Instance has no Incident Management. D2C requires issue detection and resolution.",
        source=RuleSource.IT4IT,
        severity=Severity.CRITICAL,
        category="it4it_coverage",
        condition_description="Incident Management plugin (com.snc.incident) is not installed",
        recommendation="Incident Management is foundational to the Detect to Correct (D2C) value stream. "
                       "Enable it to track, prioritize, and resolve service disruptions.",
        tags=["D2C", "incident", "detection", "resolution"],
    ),
    Rule(
        id="IT4IT-D2C-002",
        name="No Problem Management",
        description="Instance has no Problem Management. D2C requires root cause analysis capability.",
        source=RuleSource.IT4IT,
        severity=Severity.MEDIUM,
        category="it4it_coverage",
        condition_description="Problem Management plugin (com.snc.problem) is not installed "
                              "or problem table has zero records",
        recommendation="Enable Problem Management to perform root cause analysis and prevent "
                       "recurring incidents as part of the D2C value stream.",
        tags=["D2C", "problem", "root-cause"],
    ),
    Rule(
        id="IT4IT-D2C-003",
        name="No Event Management or Monitoring",
        description="Instance has no proactive detection. D2C is reactive without event correlation.",
        source=RuleSource.IT4IT,
        severity=Severity.MEDIUM,
        category="it4it_coverage",
        condition_description="Event Management plugin (com.glide.itom.em) is not installed "
                              "and no active monitoring integrations detected",
        recommendation="Enable ITOM Event Management or integrate with external monitoring tools "
                       "to shift from reactive incident handling to proactive detection.",
        tags=["D2C", "event", "monitoring", "itom", "proactive"],
    ),
    Rule(
        id="IT4IT-D2C-004",
        name="No Discovery or Service Mapping",
        description="CMDB is not automatically populated. D2C requires accurate infrastructure data.",
        source=RuleSource.IT4IT,
        severity=Severity.HIGH,
        category="it4it_coverage",
        condition_description="Discovery (com.snc.discovery) and Service Mapping (com.snc.service_mapping) "
                              "are both not installed or inactive",
        recommendation="Enable Discovery and/or Service Mapping to automatically populate and maintain "
                       "the CMDB. Manual CMDB maintenance leads to stale data and poor D2C outcomes.",
        tags=["D2C", "discovery", "service_mapping", "cmdb"],
    ),

    # --- Cross-stream ---
    Rule(
        id="IT4IT-XS-001",
        name="Single Value Stream Coverage",
        description="Instance only covers one IT4IT value stream. Mature organizations cover all four.",
        source=RuleSource.IT4IT,
        severity=Severity.LOW,
        category="it4it_coverage",
        condition_description="Active plugins only map to a single IT4IT value stream (S2P, R2D, R2F, or D2C)",
        recommendation="Consider expanding ServiceNow usage across additional IT4IT value streams "
                       "to maximize platform ROI and operational maturity.",
        tags=["S2P", "R2D", "R2F", "D2C", "maturity"],
    ),
    Rule(
        id="IT4IT-XS-002",
        name="No Integration Hub for Cross-Stream Orchestration",
        description="Integration Hub is not active. Cross-stream automation requires orchestration capability.",
        source=RuleSource.IT4IT,
        severity=Severity.MEDIUM,
        category="it4it_coverage",
        condition_description="Integration Hub plugin (com.glide.hub.integration_hub) is not installed",
        recommendation="Enable Integration Hub to orchestrate workflows across value streams and "
                       "integrate with external systems without custom scripting.",
        tags=["R2D", "R2F", "D2C", "integration", "orchestration"],
    ),
]


# ---------------------------------------------------------------------------
# Integration Pattern Decision Tree Rules (Source: Jochen Geist)
# ---------------------------------------------------------------------------
# These rules evaluate integration patterns found in an instance and
# recommend better approaches based on the decision tree methodology.
# Categories: Web Service, Data Persistence, Event-Driven, AI Agents,
#             UI-Level, Fallback
# ---------------------------------------------------------------------------

INTEGRATION_RULES: List[Rule] = [
    # --- Pattern Selection ---
    Rule(
        id="INT-PAT-001",
        name="Direct JDBC Instead of REST API",
        description="Instance uses JDBC connections where REST API would be more appropriate.",
        source=RuleSource.INTEGRATION,
        severity=Severity.HIGH,
        category="integration_pattern",
        condition_description="Active JDBC data sources found but target system supports REST API",
        recommendation="Prefer REST API (Scripted REST or Standard REST) over JDBC for real-time "
                       "integrations. JDBC should only be used for bulk data operations where "
                       "REST is not feasible. REST is the preferred Web Service pattern.",
        tags=["web_service", "jdbc", "rest", "pattern_selection"],
    ),
    Rule(
        id="INT-PAT-002",
        name="SOAP When REST Available",
        description="Instance uses SOAP web services where REST endpoints are available.",
        source=RuleSource.INTEGRATION,
        severity=Severity.MEDIUM,
        category="integration_pattern",
        condition_description="Active SOAP message functions found for systems that offer REST APIs",
        recommendation="Migrate SOAP integrations to REST where the target system supports it. "
                       "REST is lighter weight, easier to maintain, and the preferred pattern "
                       "for modern ServiceNow integrations.",
        tags=["web_service", "soap", "rest", "modernization"],
    ),
    Rule(
        id="INT-PAT-003",
        name="No Integration Hub for External Connections",
        description="Instance connects to external systems via custom scripts instead of Integration Hub.",
        source=RuleSource.INTEGRATION,
        severity=Severity.HIGH,
        category="integration_pattern",
        condition_description="Custom REST messages or scripted integrations exist but Integration Hub "
                              "spokes are available for the same target systems",
        recommendation="Use Integration Hub spokes instead of custom scripted integrations. "
                       "Spokes provide built-in error handling, retry logic, connection management, "
                       "and are maintained by ServiceNow or spoke vendors.",
        tags=["integration_hub", "spokes", "custom_script", "best_practice"],
    ),

    # --- Data Flow Direction ---
    Rule(
        id="INT-DIR-001",
        name="Bidirectional Sync Without Conflict Resolution",
        description="Two-way data sync detected without clear master/conflict resolution strategy.",
        source=RuleSource.INTEGRATION,
        severity=Severity.CRITICAL,
        category="integration_pattern",
        condition_description="Import sets and outbound REST/SOAP both exist for the same external "
                              "system, suggesting bidirectional sync without a clear data master",
        recommendation="Define a clear system of record for each data entity. Use coalesce fields "
                       "on import sets and implement conflict resolution rules. Bidirectional sync "
                       "without a defined master leads to data inconsistencies.",
        tags=["data_persistence", "bidirectional", "conflict", "data_master"],
    ),
    Rule(
        id="INT-DIR-002",
        name="Inbound Data Without Transform Maps",
        description="Import sets exist without corresponding transform maps for data cleansing.",
        source=RuleSource.INTEGRATION,
        severity=Severity.MEDIUM,
        category="integration_pattern",
        condition_description="sys_import_set records exist without matching sys_transform_map entries",
        recommendation="Always use transform maps with import sets to validate, cleanse, and "
                       "map incoming data to target tables. Direct table imports bypass data "
                       "quality controls.",
        tags=["data_persistence", "import_set", "transform", "data_quality"],
    ),

    # --- Timing & Volume ---
    Rule(
        id="INT-VOL-001",
        name="High-Volume Real-Time Integration",
        description="Real-time integration pattern used for high-volume data that should be batched.",
        source=RuleSource.INTEGRATION,
        severity=Severity.HIGH,
        category="integration_pattern",
        condition_description="REST API integration processes more than 1000 records per execution "
                              "and runs more than once per hour",
        recommendation="Switch high-volume integrations from real-time REST to scheduled batch "
                       "processing using Import Sets. Real-time should be reserved for low-volume, "
                       "time-sensitive data. Use the Data Persistence pattern for bulk operations.",
        tags=["data_persistence", "batch", "volume", "performance"],
    ),
    Rule(
        id="INT-VOL-002",
        name="Scheduled Job Instead of Event-Driven",
        description="Polling pattern detected where event-driven would be more efficient.",
        source=RuleSource.INTEGRATION,
        severity=Severity.MEDIUM,
        category="integration_pattern",
        condition_description="Scheduled jobs poll external systems for changes instead of using "
                              "webhooks or event-driven triggers",
        recommendation="Replace polling-based integrations with event-driven patterns where possible. "
                       "Use Business Rules, Flow Designer triggers, or inbound webhooks to react "
                       "to changes in real-time without unnecessary polling overhead.",
        tags=["event_driven", "polling", "webhook", "efficiency"],
    ),

    # --- Error Handling ---
    Rule(
        id="INT-ERR-001",
        name="No Error Policy on Integration Hub Flows",
        description="Integration Hub flows lack error handling policies.",
        source=RuleSource.INTEGRATION,
        severity=Severity.HIGH,
        category="integration_pattern",
        condition_description="Active Integration Hub flows found without associated error policies "
                              "or retry configurations",
        recommendation="Configure error policies on all Integration Hub flows. Define retry counts, "
                       "backoff intervals, and error notification recipients. Unhandled integration "
                       "failures cause silent data loss.",
        tags=["integration_hub", "error_handling", "reliability"],
    ),
    Rule(
        id="INT-ERR-002",
        name="No MID Server for On-Premise Integration",
        description="Instance integrates with on-premise systems without a MID Server.",
        source=RuleSource.INTEGRATION,
        severity=Severity.CRITICAL,
        category="integration_pattern",
        condition_description="Outbound integrations target private/internal IP ranges but no active "
                              "MID Server is configured",
        recommendation="Deploy a MID Server for all on-premise integrations. Direct connections "
                       "from cloud to on-premise bypass security controls and are unreliable. "
                       "MID Server provides secure, managed connectivity.",
        tags=["mid_server", "on_premise", "security", "connectivity"],
    ),

    # --- UI-Level (Fallback) ---
    Rule(
        id="INT-UI-001",
        name="UI-Level Integration as Primary Pattern",
        description="iFrame or UI page embedding used as primary integration instead of data-level.",
        source=RuleSource.INTEGRATION,
        severity=Severity.MEDIUM,
        category="integration_pattern",
        condition_description="Service Portal widgets or UI pages embed external systems via iFrame "
                              "as the only integration with that system",
        recommendation="UI-level integration (iFrame, widget embedding) should be a fallback pattern, "
                       "not the primary mechanism. Implement data-level integration (REST, Import Set) "
                       "and use UI embedding only for presentation where API integration is not feasible.",
        tags=["ui_level", "iframe", "fallback", "anti_pattern"],
    ),

    # --- Legacy Patterns ---
    Rule(
        id="INT-LEG-001",
        name="Legacy Workflow Instead of Flow Designer",
        description="Instance uses legacy Workflow Engine where Flow Designer should be used.",
        source=RuleSource.INTEGRATION,
        severity=Severity.MEDIUM,
        category="integration_pattern",
        condition_description="Active legacy workflows (wf_workflow) found that could be migrated "
                              "to Flow Designer",
        recommendation="Migrate legacy workflows to Flow Designer. Flow Designer provides better "
                       "error handling, Integration Hub support, and is ServiceNow's strategic "
                       "direction for process automation. Legacy Workflow is in maintenance mode.",
        tags=["legacy", "workflow", "flow_designer", "modernization"],
    ),
    Rule(
        id="INT-LEG-002",
        name="Email-Based Integration",
        description="Instance uses email as an integration mechanism for structured data exchange.",
        source=RuleSource.INTEGRATION,
        severity=Severity.LOW,
        category="integration_pattern",
        condition_description="Inbound email actions process structured data from external systems "
                              "instead of using REST API or Import Sets",
        recommendation="Email-based integration is a fallback pattern. Replace with REST API "
                       "or Import Set integrations for reliable, structured data exchange. "
                       "Email is fragile, difficult to monitor, and lacks transactional guarantees.",
        tags=["email", "fallback", "legacy", "reliability"],
    ),
]


# ---------------------------------------------------------------------------
# Instance Health & Anti-Pattern Rules
# ---------------------------------------------------------------------------
# General architectural best practices for ServiceNow instances.
# ---------------------------------------------------------------------------

HEALTH_RULES: List[Rule] = [
    Rule(
        id="HEALTH-001",
        name="CMDB Not Populated by Automated Discovery",
        description="CMDB has records but no Discovery or Service Mapping activity detected.",
        source=RuleSource.BEST_PRACTICE,
        severity=Severity.HIGH,
        category="health",
        condition_description="cmdb_ci has records but discovery_status table is empty or "
                              "Discovery plugin is inactive",
        recommendation="CMDB data maintained manually becomes stale quickly. Enable Discovery "
                       "and Service Mapping for automated population and ongoing maintenance.",
        tags=["cmdb", "discovery", "data_quality"],
    ),
    Rule(
        id="HEALTH-002",
        name="Customer Portal Connected to ITSM Directly",
        description="Public-facing Customer Portal creates records in internal ITSM tables.",
        source=RuleSource.BEST_PRACTICE,
        severity=Severity.CRITICAL,
        category="health",
        condition_description="Customer Portal has catalog items or forms that create incident "
                              "or sc_request records directly instead of CSM cases",
        recommendation="Public/customer-facing requests should flow through CSM (Customer Service "
                       "Management), not directly into ITSM. ITSM is for internal IT operations. "
                       "CSM provides customer context, SLA management, and proper segregation.",
        tags=["segregation", "csm", "itsm", "portal", "anti_pattern"],
    ),
    Rule(
        id="HEALTH-003",
        name="No Domain Separation in Multi-Tenant Environment",
        description="Multiple business units or tenants detected but domain separation is not enabled.",
        source=RuleSource.BEST_PRACTICE,
        severity=Severity.HIGH,
        category="health",
        condition_description="Multiple companies or business units in cmn_company but "
                              "glide.sys.domain.enabled is false",
        recommendation="Enable domain separation for multi-tenant environments to enforce data "
                       "isolation between business units. Without it, data leakage across tenants "
                       "is a significant risk.",
        tags=["domain_separation", "multi_tenant", "security"],
    ),
    Rule(
        id="HEALTH-004",
        name="Excessive Custom Tables",
        description="Instance has a high number of custom tables, suggesting platform misuse.",
        source=RuleSource.BEST_PRACTICE,
        severity=Severity.MEDIUM,
        category="health",
        condition_description="More than 50 custom tables (u_ or x_ prefix) exist in the instance",
        recommendation="Review custom tables for consolidation opportunities. Many custom tables "
                       "may indicate that standard ServiceNow modules could replace custom solutions. "
                       "Custom tables increase upgrade complexity and maintenance burden.",
        tags=["custom_tables", "technical_debt", "upgrade"],
    ),
    Rule(
        id="HEALTH-005",
        name="FedRAMP / SPP Without Audit Configuration",
        description="Instance is in a compliance-sensitive environment but audit logging is not fully configured.",
        source=RuleSource.BEST_PRACTICE,
        severity=Severity.CRITICAL,
        category="health",
        condition_description="Instance is FedRAMP/SPP but sys_audit configuration does not cover "
                              "all sensitive tables or audit retention is not configured",
        recommendation="For FedRAMP/SPP compliance, ensure comprehensive audit logging is enabled "
                       "on all sensitive tables, audit retention policies are configured, and "
                       "audit records are protected from deletion.",
        tags=["fedramp", "spp", "compliance", "audit", "security"],
    ),
    Rule(
        id="HEALTH-006",
        name="No Agent Workspace Adoption",
        description="Instance uses legacy list/form UI instead of Agent Workspace for agents.",
        source=RuleSource.BEST_PRACTICE,
        severity=Severity.LOW,
        category="health",
        condition_description="Agent Workspace (com.sn_agent_workspace) is not installed or "
                              "agents primarily use classic UI based on login patterns",
        recommendation="Migrate agents to Agent Workspace for improved productivity. Workspace "
                       "provides contextual side panels, AI-assisted resolution, and is "
                       "ServiceNow's strategic direction for agent experience.",
        tags=["workspace", "agent_experience", "modernization"],
    ),
    Rule(
        id="HEALTH-007",
        name="Legacy Workflow Engine Still Active",
        description="Legacy Workflow Engine has active workflows that should be on Flow Designer.",
        source=RuleSource.BEST_PRACTICE,
        severity=Severity.MEDIUM,
        category="health",
        condition_description="wf_workflow table has active workflows created in the last 12 months",
        recommendation="New automation should use Flow Designer, not Legacy Workflow. Plan migration "
                       "of active legacy workflows to Flow Designer for better maintainability "
                       "and access to Integration Hub capabilities.",
        tags=["workflow", "flow_designer", "modernization", "technical_debt"],
    ),
    Rule(
        id="HEALTH-008",
        name="Single Instance for Public and Internal",
        description="Public-facing and internal services run on same instance without proper segregation.",
        source=RuleSource.BEST_PRACTICE,
        severity=Severity.HIGH,
        category="health",
        condition_description="Customer Portal (public-facing) and Service Portal (internal) both "
                              "active on same instance without domain separation",
        recommendation="For public sector or high-security environments, consider either: "
                       "(1) separate instances for public and internal, or "
                       "(2) domain separation with strict access controls if single instance. "
                       "Evaluate FedRAMP boundary implications.",
        tags=["multi_instance", "segregation", "fedramp", "security"],
    ),
]


# ---------------------------------------------------------------------------
# Wave 2: Product Adoption Maturity Rules
# ---------------------------------------------------------------------------
# These rules detect module pairing gaps — where one product is installed
# but its natural companion is missing. Based on ServiceNow's product
# architecture and recommended adoption paths.
# ---------------------------------------------------------------------------

ADOPTION_RULES: List[Rule] = [
    # --- ITSM Module Pairing ---
    Rule(
        id="ADOPT-001",
        name="Incident Without Problem Management",
        description="Incident Management is active but Problem Management is not used. "
                    "The D2C value stream requires a root cause analysis loop.",
        source=RuleSource.BEST_PRACTICE,
        severity=Severity.MEDIUM,
        category="adoption_maturity",
        condition_description="Incident table has records but Problem plugin is inactive "
                              "or problem table has zero records",
        recommendation="Enable Problem Management to close the reactive-to-proactive loop. "
                       "Without root cause analysis, the same incidents recur. Problem Management "
                       "is included in the ITSM license at no additional cost.",
        tags=["D2C", "itsm", "incident", "problem", "maturity"],
    ),
    Rule(
        id="ADOPT-002",
        name="ITSM Without Knowledge Management",
        description="ITSM is active but Knowledge Base has fewer than 10 articles. "
                    "Knowledge deflection is the highest-ROI self-service investment.",
        source=RuleSource.BEST_PRACTICE,
        severity=Severity.MEDIUM,
        category="adoption_maturity",
        condition_description="ITSM plugins active and incident table has records, but "
                              "Knowledge plugin is inactive or kb_knowledge has < 10 articles",
        recommendation="Build a Knowledge Base from resolved incidents. ServiceNow's Knowledge "
                       "Management allows agents to create KB articles during incident resolution. "
                       "Even 50 well-written articles can deflect 15-20% of ticket volume.",
        tags=["R2F", "D2C", "knowledge", "self_service", "deflection"],
    ),
    Rule(
        id="ADOPT-003",
        name="Service Catalog Without Virtual Agent",
        description="Service Catalog is active but Virtual Agent is not installed. "
                    "VA provides conversational self-service for common requests.",
        source=RuleSource.BEST_PRACTICE,
        severity=Severity.LOW,
        category="adoption_maturity",
        condition_description="Service Catalog plugin is active and sc_cat_item has records, "
                              "but Virtual Agent (com.glide.cs.chatbot) is not installed",
        recommendation="Deploy Virtual Agent to guide users to the right catalog items "
                       "conversationally. VA integrates with Service Catalog and Knowledge Base "
                       "to deflect common requests before they become tickets.",
        tags=["R2F", "virtual_agent", "self_service", "catalog"],
    ),

    # --- HRSD Module Pairing ---
    Rule(
        id="ADOPT-004",
        name="HRSD Without Employee Center",
        description="HR Service Delivery is installed but Employee Center is not. "
                    "Employees lack a unified portal for HR services.",
        source=RuleSource.BEST_PRACTICE,
        severity=Severity.MEDIUM,
        category="adoption_maturity",
        condition_description="HRSD plugin (com.sn_hr_core) is installed but Employee Center "
                              "(com.sn_employee_center) is not installed",
        recommendation="Deploy Employee Center to give employees a single front door for HR "
                       "services, knowledge, and cases. Employee Center is ServiceNow's strategic "
                       "replacement for Service Portal in HR workflows and provides personalized, "
                       "department-specific content delivery.",
        tags=["R2F", "hrsd", "employee_center", "portal", "self_service"],
    ),

    # --- CSM Module Pairing ---
    Rule(
        id="ADOPT-005",
        name="CSM Without Dedicated Customer Portal",
        description="Customer Service Management is installed but no portal is configured "
                    "for external customer self-service.",
        source=RuleSource.BEST_PRACTICE,
        severity=Severity.MEDIUM,
        category="adoption_maturity",
        condition_description="CSM plugin (com.sn_customerservice) is installed but Service Portal "
                              "(com.glide.service-portal) is not installed",
        recommendation="Deploy a Customer Portal (via Service Portal) to provide external customers "
                       "with self-service case management, knowledge search, and request tracking. "
                       "Without a portal, CSM cases can only be created by agents, losing the "
                       "deflection benefits.",
        tags=["R2F", "csm", "customer_portal", "self_service"],
    ),

    # --- ITOM Module Pairing ---
    Rule(
        id="ADOPT-006",
        name="Discovery Without Service Mapping",
        description="Discovery is active but Service Mapping is not. Infrastructure CIs "
                    "are discovered but service context is missing.",
        source=RuleSource.BEST_PRACTICE,
        severity=Severity.MEDIUM,
        category="adoption_maturity",
        condition_description="Discovery plugin (com.snc.discovery) is installed but "
                              "Service Mapping (com.snc.service_mapping) is not installed",
        recommendation="Add Service Mapping to Discovery to build application-level service maps. "
                       "Discovery finds individual CIs but Service Mapping connects them into "
                       "business services, enabling impact analysis during incidents and changes.",
        tags=["D2C", "R2D", "discovery", "service_mapping", "cmdb"],
    ),
    Rule(
        id="ADOPT-007",
        name="CMDB Without Asset Management",
        description="CMDB is populated but Asset Management is not active. "
                    "No lifecycle tracking for hardware and software assets.",
        source=RuleSource.BEST_PRACTICE,
        severity=Severity.MEDIUM,
        category="adoption_maturity",
        condition_description="cmdb_ci has records but Asset Management plugin "
                              "(com.snc.asset_management) is not installed",
        recommendation="Enable IT Asset Management (ITAM) to track asset lifecycle — procurement, "
                       "deployment, maintenance, and retirement. CMDB tells you what you have; "
                       "ITAM tells you what it costs and when to replace it. HAM and SAM provide "
                       "hardware and software license compliance.",
        tags=["R2D", "D2C", "cmdb", "asset", "lifecycle"],
    ),

    # --- SecOps Module Pairing ---
    Rule(
        id="ADOPT-008",
        name="Security Incident Response Without Vulnerability Response",
        description="SIR is installed but Vulnerability Response is not. Reactive-only "
                    "security posture without proactive vulnerability management.",
        source=RuleSource.BEST_PRACTICE,
        severity=Severity.MEDIUM,
        category="adoption_maturity",
        condition_description="Security Incident Response plugin (com.snc.sec_inc_response) "
                              "is installed but Vulnerability Response (com.snc.vul_response) is not",
        recommendation="Add Vulnerability Response to shift from reactive (incident-only) to "
                       "proactive security operations. VR integrates with scanners (Qualys, Tenable, "
                       "Rapid7) to prioritize and track vulnerability remediation before exploitation.",
        tags=["D2C", "secops", "vulnerability", "proactive"],
    ),

    # --- SPM Module Pairing ---
    Rule(
        id="ADOPT-009",
        name="SPM Without GRC",
        description="Strategic Portfolio Management is active but GRC is not. "
                    "Portfolio decisions lack governance and risk oversight.",
        source=RuleSource.BEST_PRACTICE,
        severity=Severity.LOW,
        category="adoption_maturity",
        condition_description="SPM/ITBM plugin (com.snc.project_management) is installed "
                              "but GRC plugins (com.sn_compliance, com.sn_risk) are not installed",
        recommendation="Add Integrated Risk Management (GRC) alongside SPM to incorporate "
                       "risk assessments and compliance requirements into portfolio decisions. "
                       "This ensures investment priorities account for regulatory obligations.",
        tags=["S2P", "spm", "grc", "governance"],
    ),
]


# ---------------------------------------------------------------------------
# Wave 2: Security Posture Rules
# ---------------------------------------------------------------------------
# Security hardening checks based on ServiceNow's platform security
# best practices. These evaluate instance properties and plugin configs.
# ---------------------------------------------------------------------------

SECURITY_RULES: List[Rule] = [
    Rule(
        id="SEC-001",
        name="CSRF Protection Not Enabled",
        description="Cross-Site Request Forgery (CSRF) token validation is not enabled. "
                    "This is a critical security control for web applications.",
        source=RuleSource.BEST_PRACTICE,
        severity=Severity.CRITICAL,
        category="security",
        condition_description="glide.security.use_csrf_token property is not set to 'true'",
        recommendation="Enable CSRF protection by setting glide.security.use_csrf_token = true. "
                       "CSRF attacks can trick authenticated users into performing unintended actions. "
                       "This is a baseline security control recommended by OWASP and required for "
                       "FedRAMP compliance.",
        tags=["security", "csrf", "owasp", "compliance"],
    ),
    Rule(
        id="SEC-002",
        name="No SecOps on Instance With Sensitive Data",
        description="Instance processes sensitive data (ITSM/CSM/HRSD) but has no Security "
                    "Operations capability for threat detection and response.",
        source=RuleSource.BEST_PRACTICE,
        severity=Severity.MEDIUM,
        category="security",
        condition_description="Instance has ITSM, CSM, or HRSD active (processing PII/sensitive data) "
                              "but neither Security Incident Response nor Vulnerability Response is installed",
        recommendation="Consider Security Operations (SecOps) to protect the ServiceNow instance "
                       "and its data. SIR provides security incident workflows, and VR enables "
                       "proactive vulnerability management. Both integrate with SIEM/SOAR tools.",
        tags=["security", "secops", "data_protection"],
    ),
    Rule(
        id="SEC-003",
        name="Audit Logging Not Comprehensively Configured",
        description="Audit logging properties are not set, potentially leaving sensitive "
                    "table changes untracked.",
        source=RuleSource.BEST_PRACTICE,
        severity=Severity.HIGH,
        category="security",
        condition_description="No glide.audit.* properties found in instance configuration",
        recommendation="Configure comprehensive audit logging via glide.audit.* properties. "
                       "At minimum, enable auditing on user tables, CMDB, and any tables "
                       "containing PII. Audit logs are essential for compliance (SOX, HIPAA, "
                       "FedRAMP) and security forensics.",
        tags=["security", "audit", "compliance", "forensics"],
    ),
]


# ---------------------------------------------------------------------------
# Wave 2: Platform Efficiency Rules
# ---------------------------------------------------------------------------
# Rules that detect underutilized licenses, shelfware, and missed
# optimization opportunities.
# ---------------------------------------------------------------------------

EFFICIENCY_RULES: List[Rule] = [
    Rule(
        id="EFF-001",
        name="Potential Shelfware — HRSD Installed But No HR Cases",
        description="HR Service Delivery plugin is installed but hr_core_case table "
                    "has zero records. License may be underutilized.",
        source=RuleSource.BEST_PRACTICE,
        severity=Severity.LOW,
        category="efficiency",
        condition_description="HRSD plugin (com.sn_hr_core) is installed but "
                              "sn_hr_core_case table has zero records",
        recommendation="HRSD is licensed but not producing HR cases. Either onboard HR "
                       "teams to use the platform, or evaluate whether the license is needed. "
                       "Unused licenses represent significant annual cost with zero ROI.",
        tags=["efficiency", "shelfware", "hrsd", "roi"],
    ),
    Rule(
        id="EFF-002",
        name="Potential Shelfware — CSM Installed But No Cases",
        description="Customer Service Management plugin is installed but case table "
                    "has zero records. License may be underutilized.",
        source=RuleSource.BEST_PRACTICE,
        severity=Severity.LOW,
        category="efficiency",
        condition_description="CSM plugin (com.sn_customerservice) is installed but "
                              "sn_customerservice_case table has zero records",
        recommendation="CSM is licensed but not producing customer cases. Either complete the "
                       "CSM implementation (portal, assignment rules, SLAs) or evaluate whether "
                       "the license is still needed.",
        tags=["efficiency", "shelfware", "csm", "roi"],
    ),
    Rule(
        id="EFF-003",
        name="Potential Shelfware — SecOps Installed But No Incidents",
        description="Security Incident Response plugin is installed but SIR table "
                    "has zero records. Security automation not operational.",
        source=RuleSource.BEST_PRACTICE,
        severity=Severity.LOW,
        category="efficiency",
        condition_description="SIR plugin (com.snc.sec_inc_response) is installed but "
                              "sn_si_incident table has zero records",
        recommendation="Security Incident Response is licensed but not ingesting security "
                       "events. Connect SIR to your SIEM (Splunk, Sentinel, etc.) to automate "
                       "security incident creation and response workflows.",
        tags=["efficiency", "shelfware", "secops", "siem"],
    ),
    Rule(
        id="EFF-004",
        name="Flow Designer Underutilized",
        description="Flow Designer is installed but has fewer flows than legacy workflows. "
                    "Modern automation capabilities are underutilized.",
        source=RuleSource.BEST_PRACTICE,
        severity=Severity.LOW,
        category="efficiency",
        condition_description="Flow Designer plugin is active but sys_hub_flow count is less than "
                              "half of wf_workflow count",
        recommendation="Prioritize new automations in Flow Designer over Legacy Workflow. "
                       "Flow Designer supports Integration Hub actions, error policies, and "
                       "parallel execution. Plan a migration roadmap for legacy workflows "
                       "starting with the most frequently triggered ones.",
        tags=["efficiency", "flow_designer", "workflow", "modernization"],
    ),
]


# ---------------------------------------------------------------------------
# REST API Query Templates (for future Instance Scanner)
# ---------------------------------------------------------------------------
# These define the ServiceNow REST API calls needed to populate InstanceModel.
# Not executed — just documented for when the scanner is implemented.
# ---------------------------------------------------------------------------

SCANNER_QUERIES = {
    "installed_plugins": {
        "table": "v_plugin",
        "fields": "id,name,active,version",
        "query": "active=true",
        "description": "List all active plugins to determine installed capabilities",
    },
    "installed_apps": {
        "table": "sys_store_app",
        "fields": "scope,name,version,active",
        "query": "active=true",
        "description": "List all installed store apps",
    },
    "table_record_counts": {
        "table": "sys_db_object",
        "fields": "name,label,super_class,sys_class_name",
        "query": "nameSTARTSWITHu_^ORnameSTARTSWITHx_^ORname=incident^ORname=problem"
                 "^ORname=change_request^ORname=sc_request^ORname=sn_customerservice_case"
                 "^ORname=sn_hr_core_case^ORname=cmdb_ci^ORname=kb_knowledge",
        "description": "Get key tables and their metadata; use stats API for counts",
    },
    "integration_hub_flows": {
        "table": "sys_hub_flow",
        "fields": "name,active,trigger_type,sys_updated_on",
        "query": "active=true",
        "description": "List active Integration Hub flows",
    },
    "mid_servers": {
        "table": "ecc_agent",
        "fields": "name,status,host_name",
        "query": "statusINup,upgrading",
        "description": "List active MID Servers",
    },
    "import_sets": {
        "table": "sys_data_source",
        "fields": "name,type,import_set_table_name,active",
        "query": "active=true",
        "description": "List active data sources for integration analysis",
    },
    "rest_messages": {
        "table": "sys_rest_message",
        "fields": "name,rest_endpoint,authentication_type",
        "query": "",
        "description": "List outbound REST message configurations",
    },
    "soap_messages": {
        "table": "sys_soap_message",
        "fields": "name,endpoint",
        "query": "",
        "description": "List outbound SOAP message configurations",
    },
    "custom_tables": {
        "table": "sys_db_object",
        "fields": "name,label",
        "query": "nameSTARTSWITHu_^ORnameSTARTSWITHx_",
        "description": "Count custom tables to assess technical debt",
    },
    "properties_compliance": {
        "table": "sys_properties",
        "fields": "name,value",
        "query": "name=glide.sys.domain.enabled^ORname=glide.security.use_csrf_token"
                 "^ORnameSTARTSWITHglide.audit",
        "description": "Check compliance-relevant instance properties",
    },
}


# ---------------------------------------------------------------------------
# Rule Engine
# ---------------------------------------------------------------------------

class RuleEngine:
    """
    Deterministic rule engine for ServiceNow instance analysis.

    Evaluates an InstanceModel against IT4IT coverage rules, integration
    pattern rules, and health/anti-pattern rules. Produces structured
    findings that can be displayed directly or fed to an LLM for
    natural language reporting.

    DISABLED by default. Set instance_scanner_rules.ENABLED = True to activate.
    """

    def __init__(self):
        self.rules: List[Rule] = (IT4IT_RULES + INTEGRATION_RULES + HEALTH_RULES
                                  + ADOPTION_RULES + SECURITY_RULES + EFFICIENCY_RULES)
        self._rules_by_id = {r.id: r for r in self.rules}
        self._rules_by_category = {}
        for r in self.rules:
            self._rules_by_category.setdefault(r.category, []).append(r)

    @property
    def is_enabled(self) -> bool:
        return ENABLED

    def get_all_rules(self) -> List[Dict]:
        """Return all rules as dicts (for inspection/display regardless of ENABLED state)."""
        return [r.to_dict() for r in self.rules]

    def get_rules_by_category(self, category: str) -> List[Dict]:
        """Return rules for a specific category."""
        return [r.to_dict() for r in self._rules_by_category.get(category, [])]

    def get_rule_summary(self) -> Dict:
        """Return a summary of the rule engine contents."""
        return {
            "enabled": ENABLED,
            "total_rules": len(self.rules),
            "by_source": {
                "IT4IT v3 (Ian Leu)": len(IT4IT_RULES),
                "Integration Patterns (Jochen Geist)": len(INTEGRATION_RULES),
                "Best Practices": len(HEALTH_RULES) + len(ADOPTION_RULES) + len(SECURITY_RULES) + len(EFFICIENCY_RULES),
            },
            "by_category": {cat: len(rules) for cat, rules in self._rules_by_category.items()},
            "by_severity": {
                s.value: len([r for r in self.rules if r.severity == s])
                for s in Severity
            },
        }

    def evaluate(self, instance_model: InstanceModel) -> Dict:
        """
        Evaluate all rules against the instance model.
        Returns structured findings and recommended ontology node IDs.
        """
        if not ENABLED:
            logger.info("Rule engine is DISABLED. Skipping evaluation.")
            return {
                "status": "disabled",
                "message": "Rule engine is disabled pending approval from knowledge source authors. "
                           "Set ENABLED = True in instance_scanner_rules.py to activate.",
                "rule_summary": self.get_rule_summary(),
                "findings": [],
                "recommended_node_ids": [],
            }

        logger.info("Evaluating rules against instance model...")
        findings: List[Finding] = []
        recommended_nodes: Dict[str, str] = {}  # node_id -> reason

        plugins = set(instance_model.installed_plugins.keys())
        tables = instance_model.active_tables
        mid_servers = instance_model.mid_servers
        flows = instance_model.integration_flows
        cmdb = instance_model.cmdb_stats
        props = instance_model.instance_properties

        def has_plugin(pid: str) -> bool:
            return pid in plugins

        def table_count(tbl: str) -> int:
            return tables.get(tbl, -1)

        def fire(rule: Rule, message: str, evidence: Dict = None,
                 rec_nodes: Dict[str, str] = None):
            findings.append(Finding(
                rule_id=rule.id, rule_name=rule.name, severity=rule.severity,
                source=rule.source.value, category=rule.category,
                message=message, recommendation=rule.recommendation,
                evidence=evidence or {},
            ))
            if rec_nodes:
                recommended_nodes.update(rec_nodes)

        # ============================================================
        # IT4IT Coverage Rules
        # ============================================================

        # IT4IT-S2P-001: No SPM
        r = self._rules_by_id["IT4IT-S2P-001"]
        if not has_plugin("com.snc.project_management"):
            fire(r, "No Strategic Portfolio Management detected. S2P value stream uncovered.",
                 rec_nodes={"spm": "S2P coverage", "ppm": "S2P coverage"})

        # IT4IT-S2P-002: No GRC
        r = self._rules_by_id["IT4IT-S2P-002"]
        if not has_plugin("com.sn_compliance") and not has_plugin("com.sn_risk"):
            fire(r, "No GRC capability detected. Governance oversight missing from S2P.",
                 rec_nodes={"grc": "S2P governance"})

        # IT4IT-R2D-001: No Change Management
        r = self._rules_by_id["IT4IT-R2D-001"]
        if not has_plugin("com.snc.change_management") and table_count("change_request") <= 0:
            fire(r, "No Change Management process detected. R2D value stream at risk.",
                 rec_nodes={"change": "R2D deployment control"})

        # IT4IT-R2D-002: No CMDB for config tracking
        r = self._rules_by_id["IT4IT-R2D-002"]
        ci_count = cmdb.get("total_cis", 0)
        if ci_count < 100 and not cmdb.get("has_discovery", False):
            fire(r, f"CMDB has only {ci_count} CIs and no Discovery. R2D lacks configuration tracking.",
                 evidence={"cmdb_ci_count": ci_count},
                 rec_nodes={"discovery": "R2D config tracking", "service_mapping": "R2D service topology"})

        # IT4IT-R2F-001: No Service Catalog
        r = self._rules_by_id["IT4IT-R2F-001"]
        if not has_plugin("com.glideapp.servicecatalog") and table_count("sc_cat_item") <= 0:
            fire(r, "No Service Catalog detected. R2F has no structured request intake.",
                 rec_nodes={"service_catalog": "R2F request intake"})

        # IT4IT-R2F-002: No Portal
        r = self._rules_by_id["IT4IT-R2F-002"]
        if not has_plugin("com.glide.service-portal") and not has_plugin("com.sn_employee_center"):
            fire(r, "No self-service portal detected. R2F lacks user-facing request channel.",
                 rec_nodes={"service_portal": "R2F self-service"})

        # IT4IT-R2F-003: No Knowledge Base
        r = self._rules_by_id["IT4IT-R2F-003"]
        kb_count = table_count("kb_knowledge")
        if not has_plugin("com.glideapp.knowledge") or (0 <= kb_count < 10):
            fire(r, f"Knowledge Base has {kb_count if kb_count >= 0 else 0} articles. Self-resolution limited.",
                 evidence={"kb_articles": kb_count},
                 rec_nodes={"knowledge_base": "R2F self-resolution"})

        # IT4IT-D2C-001: No Incident Management
        r = self._rules_by_id["IT4IT-D2C-001"]
        if not has_plugin("com.snc.incident") and table_count("incident") <= 0:
            fire(r, "No Incident Management detected. D2C has no issue resolution capability.",
                 rec_nodes={"incident": "D2C issue resolution", "itsm": "D2C foundation"})

        # IT4IT-D2C-002: No Problem Management
        r = self._rules_by_id["IT4IT-D2C-002"]
        if not has_plugin("com.snc.problem") or table_count("problem") == 0:
            fire(r, "No Problem Management activity. Root cause analysis not being performed.",
                 rec_nodes={"problem": "D2C root cause"})

        # IT4IT-D2C-003: No Event Management
        r = self._rules_by_id["IT4IT-D2C-003"]
        if not has_plugin("com.glide.itom.em") and table_count("em_event") <= 0:
            fire(r, "No Event Management or monitoring integration. D2C is purely reactive.",
                 rec_nodes={"event_mgmt": "D2C proactive detection", "itom": "D2C operations"})

        # IT4IT-D2C-004: No Discovery or Service Mapping
        r = self._rules_by_id["IT4IT-D2C-004"]
        if not cmdb.get("has_discovery", False) and not has_plugin("com.snc.service_mapping"):
            fire(r, "No Discovery or Service Mapping. CMDB relies on manual maintenance.",
                 rec_nodes={"discovery": "D2C auto-discovery", "service_mapping": "D2C service topology"})

        # IT4IT-XS-001: Single value stream
        r = self._rules_by_id["IT4IT-XS-001"]
        # Calculate covered streams from what's NOT flagged above
        covered = set()
        if has_plugin("com.snc.project_management") or has_plugin("com.sn_compliance"):
            covered.add("S2P")
        if has_plugin("com.snc.change_management") or table_count("change_request") > 0:
            covered.add("R2D")
        if has_plugin("com.glideapp.servicecatalog") or table_count("sc_request") > 0:
            covered.add("R2F")
        if has_plugin("com.snc.incident") or table_count("incident") > 0:
            covered.add("D2C")
        if len(covered) <= 1:
            fire(r, f"Only {len(covered)} IT4IT value stream(s) covered: {', '.join(covered) or 'none'}.",
                 evidence={"covered_streams": list(covered)})

        # IT4IT-XS-002: No Integration Hub
        r = self._rules_by_id["IT4IT-XS-002"]
        if not has_plugin("com.glide.hub.integration_hub") and table_count("sys_hub_flow") <= 0:
            fire(r, "No Integration Hub detected. Cross-stream orchestration relies on custom scripts.",
                 rec_nodes={"integration_hub": "cross-stream orchestration"})

        # ============================================================
        # Integration Pattern Rules
        # ============================================================

        # INT-PAT-003: No Integration Hub for external connections
        r = self._rules_by_id["INT-PAT-003"]
        if not has_plugin("com.glide.hub.integration_hub") and len(flows) == 0:
            fire(r, "No Integration Hub spokes detected. External integrations likely use custom scripts.",
                 rec_nodes={"integration_hub": "managed integrations"})

        # INT-ERR-002: No MID Server
        r = self._rules_by_id["INT-ERR-002"]
        if len(mid_servers) == 0:
            fire(r, "No active MID Servers detected. On-premise integrations have no secure channel.",
                 evidence={"mid_servers": 0})

        # INT-LEG-001: Legacy Workflows
        r = self._rules_by_id["INT-LEG-001"]
        wf_count = table_count("wf_workflow")
        flow_count = table_count("sys_hub_flow")
        if wf_count > 0 and (flow_count <= 0 or wf_count > flow_count):
            fire(r, f"Legacy Workflow Engine has {wf_count} workflows vs {max(flow_count, 0)} Flow Designer flows. "
                     "Migration recommended.",
                 evidence={"legacy_workflows": wf_count, "flow_designer_flows": max(flow_count, 0)},
                 rec_nodes={"flow_designer": "modern automation"})

        # ============================================================
        # Health Rules
        # ============================================================

        # HEALTH-001: CMDB without Discovery
        r = self._rules_by_id["HEALTH-001"]
        if ci_count > 0 and not cmdb.get("has_discovery", False):
            fire(r, f"CMDB has {ci_count:,} CIs but no automated Discovery. Data staleness risk.",
                 evidence={"cmdb_ci_count": ci_count, "discovery_active": False})

        # HEALTH-002: Customer Portal → ITSM (anti-pattern)
        r = self._rules_by_id["HEALTH-002"]
        has_customer_portal = has_plugin("com.sn_customerservice")
        has_itsm_records = table_count("incident") > 0
        has_csm_records = table_count("sn_customerservice_case") > 0
        if has_customer_portal and has_itsm_records and not has_csm_records:
            fire(r, "Customer Service plugin installed but no CSM cases — customers may be routed to ITSM directly.",
                 rec_nodes={"csm": "customer segregation", "case_mgmt": "customer cases"})

        # HEALTH-006: No Agent Workspace
        r = self._rules_by_id["HEALTH-006"]
        if not has_plugin("com.sn_agent_workspace"):
            fire(r, "No Agent Workspace adoption. Agents using classic UI miss productivity features.",
                 rec_nodes={"workspace": "agent experience"})

        # HEALTH-007: Legacy Workflow still active
        r = self._rules_by_id["HEALTH-007"]
        if wf_count > 10:
            fire(r, f"{wf_count} legacy workflows still active. Flow Designer is the strategic direction.",
                 evidence={"legacy_workflows": wf_count})

        # ============================================================
        # Product Adoption Maturity Rules
        # ============================================================

        # ADOPT-001: Incident without Problem
        r = self._rules_by_id["ADOPT-001"]
        has_incidents = table_count("incident") > 0
        has_problems = has_plugin("com.snc.problem") and table_count("problem") > 0
        if has_incidents and not has_problems:
            fire(r, "Incident Management is active but Problem Management is not in use. "
                     "No root cause analysis loop.",
                 evidence={"incidents": table_count("incident"), "problems": table_count("problem")},
                 rec_nodes={"problem": "D2C root cause analysis"})

        # ADOPT-002: ITSM without Knowledge
        r = self._rules_by_id["ADOPT-002"]
        kb_count = table_count("kb_knowledge")
        if has_incidents and (not has_plugin("com.glideapp.knowledge") or (0 <= kb_count < 10)):
            fire(r, f"ITSM is active but Knowledge Base has only {max(kb_count, 0)} articles. "
                     "Self-service deflection opportunity missed.",
                 evidence={"kb_articles": kb_count, "incidents": table_count("incident")},
                 rec_nodes={"knowledge_base": "R2F self-resolution"})

        # ADOPT-003: Service Catalog without Virtual Agent
        r = self._rules_by_id["ADOPT-003"]
        if has_plugin("com.glideapp.servicecatalog") and not has_plugin("com.glide.cs.chatbot"):
            fire(r, "Service Catalog is active but Virtual Agent is not installed. "
                     "Conversational self-service not available.",
                 rec_nodes={"virtual_agent": "R2F conversational self-service"})

        # ADOPT-004: HRSD without Employee Center
        r = self._rules_by_id["ADOPT-004"]
        if has_plugin("com.sn_hr_core") and not has_plugin("com.sn_employee_center"):
            fire(r, "HRSD is installed but Employee Center is not. Employees lack a "
                     "unified, personalized portal for HR services.",
                 rec_nodes={"employee_center": "R2F employee self-service"})

        # ADOPT-005: CSM without portal
        r = self._rules_by_id["ADOPT-005"]
        if has_plugin("com.sn_customerservice") and not has_plugin("com.glide.service-portal"):
            fire(r, "CSM is installed but no Service Portal for customer self-service. "
                     "Cases can only be created by agents.",
                 rec_nodes={"customer_portal": "R2F customer self-service"})

        # ADOPT-006: Discovery without Service Mapping
        r = self._rules_by_id["ADOPT-006"]
        if has_plugin("com.snc.discovery") and not has_plugin("com.snc.service_mapping"):
            fire(r, "Discovery is active but Service Mapping is not. Infrastructure CIs are "
                     "discovered but service-level topology is missing.",
                 rec_nodes={"service_mapping": "D2C service topology"})

        # ADOPT-007: CMDB without Asset Management
        r = self._rules_by_id["ADOPT-007"]
        if ci_count > 0 and not has_plugin("com.snc.asset_management"):
            fire(r, f"CMDB has {ci_count:,} CIs but Asset Management is not active. "
                     "No lifecycle tracking for hardware and software assets.",
                 evidence={"cmdb_ci_count": ci_count},
                 rec_nodes={"asset": "R2D asset lifecycle"})

        # ADOPT-008: SIR without VR
        r = self._rules_by_id["ADOPT-008"]
        if has_plugin("com.snc.sec_inc_response") and not has_plugin("com.snc.vul_response"):
            fire(r, "Security Incident Response is active but Vulnerability Response is not. "
                     "Reactive-only security posture.",
                 rec_nodes={"vuln_response": "D2C proactive security"})

        # ADOPT-009: SPM without GRC
        r = self._rules_by_id["ADOPT-009"]
        if has_plugin("com.snc.project_management") and not has_plugin("com.sn_compliance") and not has_plugin("com.sn_risk"):
            fire(r, "SPM is active but GRC is not. Portfolio decisions lack governance oversight.",
                 rec_nodes={"grc": "S2P governance", "policy_compliance": "S2P compliance"})

        # ============================================================
        # Security Posture Rules
        # ============================================================

        # SEC-001: CSRF not enabled
        r = self._rules_by_id["SEC-001"]
        csrf = props.get("glide.security.use_csrf_token", "")
        if csrf.lower() != "true":
            fire(r, "CSRF token protection is not enabled. Instance is vulnerable to "
                     "cross-site request forgery attacks.",
                 evidence={"glide.security.use_csrf_token": csrf or "(not set)"})

        # SEC-002: No SecOps on sensitive instance
        r = self._rules_by_id["SEC-002"]
        has_sensitive_data = (has_incidents or has_plugin("com.sn_customerservice")
                              or has_plugin("com.sn_hr_core"))
        has_secops = (has_plugin("com.snc.sec_inc_response")
                      or has_plugin("com.snc.vul_response"))
        if has_sensitive_data and not has_secops:
            fire(r, "Instance processes sensitive data (ITSM/CSM/HRSD) but has no "
                     "Security Operations capability.",
                 rec_nodes={"secops": "security operations", "sec_incident": "security incident response"})

        # SEC-003: No audit properties
        r = self._rules_by_id["SEC-003"]
        audit_props = [k for k in props if k.startswith("glide.audit")]
        if len(audit_props) == 0:
            fire(r, "No audit logging properties detected. Sensitive table changes "
                     "may not be tracked.",
                 evidence={"audit_properties_found": 0})

        # ============================================================
        # Platform Efficiency Rules
        # ============================================================

        # EFF-001: HRSD shelfware
        r = self._rules_by_id["EFF-001"]
        hr_cases = table_count("sn_hr_core_case")
        if has_plugin("com.sn_hr_core") and hr_cases == 0:
            fire(r, "HRSD plugin is installed but sn_hr_core_case has zero records. "
                     "License may be underutilized.",
                 evidence={"hr_cases": 0})

        # EFF-002: CSM shelfware
        r = self._rules_by_id["EFF-002"]
        csm_cases = table_count("sn_customerservice_case")
        if has_plugin("com.sn_customerservice") and csm_cases == 0:
            fire(r, "CSM plugin is installed but sn_customerservice_case has zero records. "
                     "License may be underutilized.",
                 evidence={"csm_cases": 0})

        # EFF-003: SecOps shelfware
        r = self._rules_by_id["EFF-003"]
        sir_incidents = table_count("sn_si_incident")
        if has_plugin("com.snc.sec_inc_response") and sir_incidents == 0:
            fire(r, "Security Incident Response is installed but sn_si_incident has zero records. "
                     "SIEM integration not connected.",
                 evidence={"security_incidents": 0})

        # EFF-004: Flow Designer underutilized
        r = self._rules_by_id["EFF-004"]
        if (has_plugin("com.glide.hub.flow_designer") and flow_count > 0
                and wf_count > 0 and flow_count < wf_count // 2):
            fire(r, f"Flow Designer has {flow_count} flows vs {wf_count} legacy workflows. "
                     "Modern automation underutilized.",
                 evidence={"flow_designer_flows": flow_count, "legacy_workflows": wf_count},
                 rec_nodes={"flow_designer": "modern automation"})

        # ============================================================
        # Results
        # ============================================================

        findings.sort(key=lambda f: list(Severity).index(f.severity))

        logger.info(f"Evaluation complete: {len(findings)} findings, "
                     f"{len(recommended_nodes)} recommended nodes")

        return {
            "status": "completed",
            "total_findings": len(findings),
            "findings": [f.to_dict() for f in findings],
            "recommended_node_ids": recommended_nodes,
            "rule_summary": self.get_rule_summary(),
        }

    def get_knowledge_base(self) -> List[Dict]:
        """Return structured summaries of each rule source for display."""
        return [
            {
                "id": "ian_leu",
                "author": "Ian Leu",
                "title": "IT4IT v3 Blueprint",
                "description": (
                    "Deterministic rules derived from the IT4IT Reference Architecture v3. "
                    "Evaluates which of the four IT value streams — Strategy to Portfolio (S2P), "
                    "Requirement to Deploy (R2D), Request to Fulfill (R2F), and Detect to Correct "
                    "(D2C) — are covered by the instance's installed capabilities."
                ),
                "focus_areas": [
                    {"key": "S2P", "label": "Strategy to Portfolio",
                     "description": "Demand management, portfolio prioritization, investment planning, and governance."},
                    {"key": "R2D", "label": "Requirement to Deploy",
                     "description": "Change management, configuration tracking, and controlled deployment processes."},
                    {"key": "R2F", "label": "Request to Fulfill",
                     "description": "Service catalog, self-service portal, knowledge base, and fulfillment workflows."},
                    {"key": "D2C", "label": "Detect to Correct",
                     "description": "Incident, problem, event management, discovery, and proactive monitoring."},
                ],
                "key_principles": [
                    "Every IT organization should cover all four value streams for operational maturity.",
                    "Gaps in a value stream create blind spots — e.g., no D2C means purely reactive operations.",
                    "Cross-stream orchestration (Integration Hub) multiplies the value of individual streams.",
                    "CMDB is foundational to both R2D (config tracking) and D2C (impact analysis).",
                ],
                "rule_count": len(IT4IT_RULES),
                "rules": [r.to_dict() for r in IT4IT_RULES],
            },
            {
                "id": "jochen_geist",
                "author": "Jochen Geist",
                "title": "Integration Pattern Decision Tree",
                "description": (
                    "Rules based on Jochen Geist's integration pattern decision tree methodology. "
                    "Evaluates integration patterns found in the instance and recommends approaches "
                    "based on data flow direction, volume, timing, and error handling requirements."
                ),
                "focus_areas": [
                    {"key": "web_service", "label": "Web Service Patterns",
                     "description": "REST vs SOAP vs JDBC pattern selection for real-time integrations."},
                    {"key": "data_persistence", "label": "Data Persistence Patterns",
                     "description": "Import sets, transform maps, batch processing for bulk data operations."},
                    {"key": "event_driven", "label": "Event-Driven Patterns",
                     "description": "Webhooks, business rules, and Flow Designer triggers vs polling."},
                    {"key": "error_handling", "label": "Error Handling & Reliability",
                     "description": "MID Servers, error policies, retry logic, and connection management."},
                    {"key": "legacy", "label": "Legacy & Anti-Patterns",
                     "description": "Workflow Engine migration, email-based integrations, UI-level fallbacks."},
                ],
                "key_principles": [
                    "Choose the integration pattern based on data volume, timing, and direction — not convenience.",
                    "Integration Hub spokes are preferred over custom scripted integrations for maintainability.",
                    "MID Server is required for any on-premise integration — never expose internal endpoints directly.",
                    "Legacy Workflow Engine is in maintenance mode — new automations should use Flow Designer.",
                    "UI-level integration (iFrame) is a fallback, not a primary integration pattern.",
                ],
                "rule_count": len(INTEGRATION_RULES),
                "rules": [r.to_dict() for r in INTEGRATION_RULES],
            },
            {
                "id": "best_practices",
                "author": "ServiceNow",
                "title": "Architectural Health",
                "description": (
                    "General architectural health checks derived from ServiceNow platform best "
                    "practices. Evaluates CMDB hygiene, domain separation, custom table sprawl, "
                    "compliance posture, and modernization of agent experience."
                ),
                "focus_areas": [
                    {"key": "cmdb", "label": "CMDB Hygiene",
                     "description": "Automated discovery, data freshness, and CI accuracy."},
                    {"key": "segregation", "label": "Tenant & Data Segregation",
                     "description": "Domain separation, public vs internal workloads, FedRAMP boundaries."},
                    {"key": "modernization", "label": "Platform Modernization",
                     "description": "Agent Workspace adoption, Flow Designer migration, custom table reduction."},
                    {"key": "compliance", "label": "Compliance & Audit",
                     "description": "Audit logging, FedRAMP/SPP configuration, security properties."},
                ],
                "key_principles": [
                    "CMDB without Discovery is a liability — manual maintenance leads to stale data.",
                    "Public-facing requests should flow through CSM, not directly into ITSM tables.",
                    "Custom table sprawl increases upgrade complexity — prefer extending standard tables.",
                    "Agent Workspace is the strategic direction — classic UI misses AI-assisted features.",
                ],
                "rule_count": len(HEALTH_RULES),
                "rules": [r.to_dict() for r in HEALTH_RULES],
            },
            {
                "id": "adoption_maturity",
                "author": "ServiceNow",
                "title": "Product Adoption Maturity",
                "description": (
                    "Rules that detect module pairing gaps — where one product is installed "
                    "but its natural companion is missing. Based on ServiceNow's product "
                    "architecture and recommended adoption paths. Each pairing represents a "
                    "well-documented best practice for maximizing platform value."
                ),
                "focus_areas": [
                    {"key": "itsm_pairing", "label": "ITSM Module Pairing",
                     "description": "Incident + Problem, ITSM + Knowledge Base, Catalog + Virtual Agent."},
                    {"key": "hrsd_pairing", "label": "HRSD Module Pairing",
                     "description": "HR Service Delivery + Employee Center for unified employee experience."},
                    {"key": "itom_pairing", "label": "ITOM Module Pairing",
                     "description": "Discovery + Service Mapping, CMDB + Asset Management for full lifecycle."},
                    {"key": "secops_pairing", "label": "SecOps Module Pairing",
                     "description": "Security Incident Response + Vulnerability Response for proactive security."},
                ],
                "key_principles": [
                    "Each ServiceNow product has natural companions — deploying one without the other leaves gaps.",
                    "Incident without Problem means reactive-only operations — no root cause analysis loop.",
                    "Discovery without Service Mapping finds CIs but misses the service context needed for impact analysis.",
                    "CMDB without Asset Management tracks what you have but not what it costs or when to replace it.",
                    "Every portal product (CSM, HRSD) needs a self-service channel to achieve deflection ROI.",
                ],
                "rule_count": len(ADOPTION_RULES),
                "rules": [r.to_dict() for r in ADOPTION_RULES],
            },
            {
                "id": "security_posture",
                "author": "ServiceNow",
                "title": "Security Posture",
                "description": (
                    "Security hardening checks based on ServiceNow's platform security "
                    "best practices and OWASP guidelines. Evaluates CSRF protection, audit "
                    "logging configuration, and security operations coverage for instances "
                    "processing sensitive data."
                ),
                "focus_areas": [
                    {"key": "web_security", "label": "Web Application Security",
                     "description": "CSRF protection, session management, and input validation."},
                    {"key": "audit_forensics", "label": "Audit & Forensics",
                     "description": "Comprehensive audit logging for compliance and incident investigation."},
                    {"key": "data_protection", "label": "Data Protection",
                     "description": "SecOps coverage for instances processing PII and sensitive data."},
                ],
                "key_principles": [
                    "CSRF protection is a baseline security control — required for FedRAMP and recommended by OWASP.",
                    "Audit logging must cover all sensitive tables — without it, compliance is impossible.",
                    "Instances processing PII (ITSM, CSM, HRSD) should have Security Operations for threat detection.",
                ],
                "rule_count": len(SECURITY_RULES),
                "rules": [r.to_dict() for r in SECURITY_RULES],
            },
            {
                "id": "efficiency",
                "author": "ServiceNow",
                "title": "Platform Efficiency",
                "description": (
                    "Rules that detect underutilized licenses (shelfware), missed optimization "
                    "opportunities, and modern automation gaps. Helps identify where licensed "
                    "capabilities are not generating ROI."
                ),
                "focus_areas": [
                    {"key": "shelfware", "label": "License Utilization (Shelfware)",
                     "description": "Plugins installed but not producing records — potential wasted spend."},
                    {"key": "automation", "label": "Automation Modernization",
                     "description": "Flow Designer adoption vs legacy Workflow Engine usage ratio."},
                ],
                "key_principles": [
                    "A licensed plugin with zero records is shelfware — significant annual cost with zero ROI.",
                    "Flow Designer is ServiceNow's strategic automation platform — legacy Workflow is maintenance-only.",
                    "Shelfware detection should trigger either onboarding (use it) or decommissioning (stop paying).",
                ],
                "rule_count": len(EFFICIENCY_RULES),
                "rules": [r.to_dict() for r in EFFICIENCY_RULES],
            },
        ]

    def get_scanner_queries(self) -> Dict:
        """Return the REST API query templates for the Instance Scanner."""
        return SCANNER_QUERIES
