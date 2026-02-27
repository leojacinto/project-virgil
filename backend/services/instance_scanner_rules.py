"""
Deterministic Rule Engine for ServiceNow Instance Analysis.

Rules derived from:
  - IT4IT v3 Blueprint (Ian Leu) — Value stream coverage analysis
  - Integration Pattern Decision Tree (Jochen Geist) — Integration best practices
  - ServiceNow architectural best practices — Instance health checks

STATUS: ENABLED — Approved by Ian Leu and Jochen Geist.

Architecture:
  Layer 1: Instance Scanner (REST API) → builds structured instance model
  Layer 2: Rule Engine (this file) → evaluates model against deterministic rules
  Layer 3: LLM (optional) → generates human-readable report from findings
"""

from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import logging
import yaml

logger = logging.getLogger(__name__)

_RULES_YAML = Path(__file__).parent / "rules.yaml"


# ---------------------------------------------------------------------------
# Global kill switch — nothing runs until this is True
# ---------------------------------------------------------------------------
ENABLED = True  # Approved by Ian Leu and Jochen Geist


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
    eval_block: Optional[Dict] = None       # declarative eval logic from YAML
    message_template: str = ""               # finding message (may contain {placeholders})
    recommended_nodes: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        d = {
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
        if self.eval_block:
            d["eval"] = self.eval_block
        return d


_SOURCE_MAP = {
    "it4it": RuleSource.IT4IT,
    "integration": RuleSource.INTEGRATION,
    "best_practice": RuleSource.BEST_PRACTICE,
}

_SEVERITY_MAP = {s.value: s for s in Severity}


def _load_yaml() -> Dict:
    """Load the entire rules.yaml file once."""
    with open(_RULES_YAML, "r") as f:
        return yaml.safe_load(f)


def _parse_rules(data: Dict) -> Dict[str, List[Rule]]:
    """Parse rule entries from the loaded YAML data, grouped by section key."""
    groups: Dict[str, List[Rule]] = {}
    for section_key in ("it4it_rules", "integration_rules", "health_rules",
                        "adoption_rules", "security_rules", "efficiency_rules"):
        rules = []
        for entry in data.get(section_key, []):
            rules.append(Rule(
                id=entry["id"],
                name=entry["name"],
                description=entry.get("description", "").strip(),
                source=_SOURCE_MAP[entry["source"]],
                severity=_SEVERITY_MAP[entry["severity"]],
                category=entry["category"],
                condition_description=entry.get("condition_description", "").strip(),
                recommendation=entry.get("recommendation", "").strip(),
                tags=entry.get("tags", []),
                eval_block=entry.get("eval"),
                message_template=entry.get("message") or "",
                recommended_nodes=entry.get("recommended_nodes") or {},
            ))
        groups[section_key] = rules
    return groups


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
    # Active ontology node IDs (populated after ontology mapping)
    active_node_ids: Set[str] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Load rules + knowledge base metadata from YAML (single source of truth)
# ---------------------------------------------------------------------------
_yaml_data = _load_yaml()
_rule_groups = _parse_rules(_yaml_data)
IT4IT_RULES: List[Rule] = _rule_groups["it4it_rules"]
INTEGRATION_RULES: List[Rule] = _rule_groups["integration_rules"]
HEALTH_RULES: List[Rule] = _rule_groups["health_rules"]
ADOPTION_RULES: List[Rule] = _rule_groups["adoption_rules"]
SECURITY_RULES: List[Rule] = _rule_groups["security_rules"]
EFFICIENCY_RULES: List[Rule] = _rule_groups["efficiency_rules"]
_KB_SOURCES: List[Dict] = _yaml_data.get("knowledge_base", [])

logger.info(f"Loaded {sum(len(v) for v in _rule_groups.values())} rules, "
            f"{len(_KB_SOURCES)} knowledge base sources from {_RULES_YAML.name}")


def reload_rules():
    """Hot-reload rules from YAML after an edit. Updates all module-level lists."""
    global _yaml_data, _rule_groups, _KB_SOURCES
    global IT4IT_RULES, INTEGRATION_RULES, HEALTH_RULES
    global ADOPTION_RULES, SECURITY_RULES, EFFICIENCY_RULES
    _yaml_data = _load_yaml()
    _rule_groups = _parse_rules(_yaml_data)
    IT4IT_RULES = _rule_groups["it4it_rules"]
    INTEGRATION_RULES = _rule_groups["integration_rules"]
    HEALTH_RULES = _rule_groups["health_rules"]
    ADOPTION_RULES = _rule_groups["adoption_rules"]
    SECURITY_RULES = _rule_groups["security_rules"]
    EFFICIENCY_RULES = _rule_groups["efficiency_rules"]
    _KB_SOURCES = _yaml_data.get("knowledge_base", [])
    total = sum(len(v) for v in _rule_groups.values())
    logger.info(f"Hot-reloaded {total} rules from {_RULES_YAML.name}")
    return total


def save_rules_yaml(data: Dict) -> int:
    """Write rule data back to rules.yaml and hot-reload. Returns total rule count."""
    with open(_RULES_YAML, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True, width=120)
    return reload_rules()


def get_full_yaml() -> Dict:
    """Return the full parsed YAML data (for the editor)."""
    return _yaml_data


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

    # ------------------------------------------------------------------
    # Generic YAML-driven evaluator
    # ------------------------------------------------------------------

    def _eval_check(self, check: Dict, model: InstanceModel) -> Tuple[bool, Dict]:
        """Evaluate a single primitive check against the instance model."""
        plugins = set(model.installed_plugins.keys())
        tables = model.active_tables
        cmdb = model.cmdb_stats
        props = model.instance_properties
        ev: Dict[str, Any] = {}

        if "node_absent" in check:
            nid = check["node_absent"]
            return nid not in model.active_node_ids, ev

        if "node_active" in check:
            nid = check["node_active"]
            return nid in model.active_node_ids, ev

        if "plugin_absent" in check:
            pid = check["plugin_absent"]
            return pid not in plugins, ev

        if "plugin_present" in check:
            pid = check["plugin_present"]
            return pid in plugins, ev

        if "table_lte" in check:
            info = check["table_lte"]
            count = tables.get(info["table"], -1)
            ev[f'{info["table"]}_count'] = count
            return count <= info["value"], ev

        if "table_eq" in check:
            info = check["table_eq"]
            count = tables.get(info["table"], -1)
            ev[f'{info["table"]}_count'] = count
            return count == info["value"], ev

        if "table_gt" in check:
            info = check["table_gt"]
            count = tables.get(info["table"], -1)
            ev[f'{info["table"]}_count'] = count
            return count > info["value"], ev

        if "table_between" in check:
            info = check["table_between"]
            count = tables.get(info["table"], -1)
            ev[f'{info["table"]}_count'] = count
            return info["min"] <= count < info["below"], ev

        if "table_exceeds" in check:
            info = check["table_exceeds"]
            ca = tables.get(info["table"], -1)
            cb = tables.get(info["other"], -1)
            ev[f'{info["table"]}_count'] = ca
            ev[f'{info["other"]}_count'] = cb
            return ca > cb, ev

        if "table_ratio_below" in check:
            info = check["table_ratio_below"]
            ca = tables.get(info["table"], -1)
            cb = tables.get(info["other"], -1)
            ev[f'{info["table"]}_count'] = ca
            ev[f'{info["other"]}_count'] = cb
            if cb <= 0:
                return False, ev
            return ca < cb * info["ratio"], ev

        if "cmdb_below" in check:
            info = check["cmdb_below"]
            val = cmdb.get(info["field"], 0)
            ev[info["field"]] = val
            return val < info["value"], ev

        if "cmdb_gt" in check:
            info = check["cmdb_gt"]
            val = cmdb.get(info["field"], 0)
            ev[info["field"]] = val
            return val > info["value"], ev

        if "cmdb_flag_false" in check:
            field = check["cmdb_flag_false"]
            val = cmdb.get(field, False)
            ev[field] = val
            return not val, ev

        if "property_neq" in check:
            info = check["property_neq"]
            actual = props.get(info["property"], "")
            ev[info["property"]] = actual or "(not set)"
            return actual.lower() != info["value"].lower(), ev

        if "property_prefix_absent" in check:
            prefix = check["property_prefix_absent"]
            found = [k for k in props if k.startswith(prefix)]
            ev[f"{prefix}_count"] = len(found)
            return len(found) == 0, ev

        if "mid_server_eq" in check:
            count = len(model.mid_servers)
            ev["mid_servers"] = count
            return count == check["mid_server_eq"], ev

        if "flow_count_eq" in check:
            count = len(model.integration_flows)
            ev["integration_flows"] = count
            return count == check["flow_count_eq"], ev

        # Nested combinators inside a check list
        if "all" in check:
            return self._eval_block({"all": check["all"]}, model)
        if "any" in check:
            return self._eval_block({"any": check["any"]}, model)

        logger.warning(f"Unknown check type: {list(check.keys())}")
        return False, ev

    def _eval_block(self, block: Dict, model: InstanceModel) -> Tuple[bool, Dict]:
        """Evaluate a combinator block (all / any / streams_covered_below)."""
        evidence: Dict[str, Any] = {}

        if "all" in block:
            for check in block["all"]:
                fired, ev = self._eval_check(check, model)
                evidence.update(ev)
                if not fired:
                    return False, evidence
            return True, evidence

        if "any" in block:
            for check in block["any"]:
                fired, ev = self._eval_check(check, model)
                evidence.update(ev)
                if fired:
                    return True, evidence
            return False, evidence

        if "streams_covered_below" in block:
            info = block["streams_covered_below"]
            covered = []
            for stream_name, stream_eval in info["streams"].items():
                stream_ok, _ = self._eval_block(stream_eval, model)
                if stream_ok:
                    covered.append(stream_name)
            evidence["covered_count"] = len(covered)
            evidence["covered_streams"] = ", ".join(covered) if covered else "none"
            return len(covered) < info["threshold"], evidence

        # Single primitive at top level
        return self._eval_check(block, model)

    def evaluate(self, instance_model: InstanceModel) -> Dict:
        """
        Evaluate all rules against the instance model.
        Rules are driven entirely by the YAML eval blocks — no per-rule
        hardcoded logic. Returns structured findings and recommended
        ontology node IDs.
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
        recommended_nodes: Dict[str, str] = {}

        for rule in self.rules:
            if not rule.eval_block:
                continue  # Rule requires scanner data not yet available

            fired, evidence = self._eval_block(rule.eval_block, instance_model)

            if fired:
                # Format message template with evidence values
                try:
                    message = rule.message_template.format(**evidence) if rule.message_template else rule.description
                except (KeyError, IndexError):
                    message = rule.message_template or rule.description

                findings.append(Finding(
                    rule_id=rule.id, rule_name=rule.name, severity=rule.severity,
                    source=rule.source.value, category=rule.category,
                    message=message, recommendation=rule.recommendation,
                    evidence=evidence,
                ))
                if rule.recommended_nodes:
                    recommended_nodes.update(rule.recommended_nodes)

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
        """Return structured summaries of each rule source for display.
        All metadata is loaded from rules.yaml — no hardcoded content here.
        """
        result = []
        for src in _KB_SOURCES:
            rules_key = src.get("rules_key", "")
            rules_list = _rule_groups.get(rules_key, [])
            result.append({
                "id": src["id"],
                "author": src["author"],
                "title": src["title"],
                "description": src.get("description", "").strip(),
                "focus_areas": src.get("focus_areas", []),
                "key_principles": src.get("key_principles", []),
                "rule_count": len(rules_list),
                "rules": [r.to_dict() for r in rules_list],
            })
        return result

    def get_scanner_queries(self) -> Dict:
        """Return the REST API query templates for the Instance Scanner."""
        return SCANNER_QUERIES
