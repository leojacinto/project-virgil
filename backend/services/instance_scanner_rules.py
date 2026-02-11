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
ENABLED = False


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
        self.rules: List[Rule] = IT4IT_RULES + INTEGRATION_RULES + HEALTH_RULES
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
                "Best Practices": len(HEALTH_RULES),
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
        Returns structured findings.

        NOTE: Currently returns disabled status. Rule evaluation logic
        will be implemented when the Instance Scanner (Layer 1) is built.
        """
        if not ENABLED:
            logger.info("Rule engine is DISABLED. Skipping evaluation.")
            return {
                "status": "disabled",
                "message": "Rule engine is disabled pending approval from knowledge source authors. "
                           "Set ENABLED = True in instance_scanner_rules.py to activate.",
                "rule_summary": self.get_rule_summary(),
                "findings": [],
            }

        # --- Future: evaluate each rule against instance_model ---
        # findings = []
        # for rule in self.rules:
        #     result = self._evaluate_rule(rule, instance_model)
        #     if result:
        #         findings.append(result)
        # return {
        #     "status": "completed",
        #     "total_findings": len(findings),
        #     "findings": [f.to_dict() for f in findings],
        #     "coverage": self._calculate_it4it_coverage(instance_model),
        # }

        return {
            "status": "disabled",
            "message": "Evaluation logic not yet implemented.",
            "findings": [],
        }

    def get_scanner_queries(self) -> Dict:
        """Return the REST API query templates for the Instance Scanner."""
        return SCANNER_QUERIES
