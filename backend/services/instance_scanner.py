"""
Instance Scanner (Layer 1) — Scans a ServiceNow instance via REST API
to build a structured InstanceModel for rule engine evaluation.

Uses the existing SNUtilsService for API calls and maps results into
the InstanceModel dataclass consumed by the RuleEngine.

STATUS: SCAFFOLDED — Scanner logic is implemented but the RuleEngine
        evaluation is disabled pending approval from knowledge source authors.
"""

from typing import Dict, List, Any, Optional
import logging

from services.instance_scanner_rules import (
    InstanceModel, RuleEngine, ENABLED as RULES_ENABLED
)
from services.servicenow_ontology import ServiceNowOntology

logger = logging.getLogger(__name__)


class InstanceScanner:
    """
    Scans a connected ServiceNow instance and builds an InstanceModel.
    
    Usage:
        scanner = InstanceScanner(sn_utils_service)
        result = scanner.scan()  # includes as-is + recommended diagrams
    """

    def __init__(self, sn_utils_service):
        """
        Args:
            sn_utils_service: An initialized SNUtilsService instance.
        """
        self.sn = sn_utils_service
        self.engine = RuleEngine()
        self.ontology = ServiceNowOntology()

    def scan(self) -> Dict[str, Any]:
        """
        Run a full instance scan and return results.
        
        Returns dict with:
          - instance_model: structured data about the instance
          - rule_summary: what the rule engine contains
          - findings: rule evaluation results (empty if disabled)
          - as_is_diagram: Mermaid diagram of current architecture
          - recommended_diagram: Mermaid diagram with recommendations overlaid
          - it4it_coverage: {S2P, R2D, R2F, D2C} booleans
          - status: 'disabled' | 'completed'
        """
        logger.info("Starting instance scan...")

        # Layer 1: Build the instance model from REST API data
        model = self._build_instance_model()

        # Layer 2: Map scanner data to ontology nodes
        mapping = self.ontology.map_instance_to_nodes(
            model.installed_plugins, model.active_tables
        )
        active_ids = mapping["active_node_ids"]

        # Inject ontology-resolved nodes into the model so rules can use node_active/node_absent
        model.active_node_ids = active_ids

        # Layer 3: Evaluate rules against the model
        evaluation = self.engine.evaluate(model)

        # Layer 4: Generate architecture diagrams
        recommended_nodes = evaluation.get("recommended_node_ids", {})
        recommended_ids = set(recommended_nodes.keys()) if isinstance(recommended_nodes, dict) else set()

        as_is_diagram = self.ontology.generate_architecture_mermaid(active_ids)
        recommended_diagram = self.ontology.generate_architecture_mermaid(
            active_ids, recommended_ids, recommended_nodes
        ) if recommended_ids else as_is_diagram

        # Build active nodes list for frontend display
        active_nodes = []
        for nid in sorted(active_ids):
            node = self.ontology._nodes.get(nid)
            if node:
                active_nodes.append({
                    "id": nid,
                    "label": node.label,
                    "layer": node.layer,
                    "it4it_streams": node.it4it_streams,
                    "evidence": mapping["node_evidence"].get(nid, ""),
                })

        recommended_node_list = []
        for nid, reason in recommended_nodes.items():
            node = self.ontology._nodes.get(nid)
            if node and nid not in active_ids:
                recommended_node_list.append({
                    "id": nid,
                    "label": node.label,
                    "layer": node.layer,
                    "reason": reason,
                })

        # Layer 5: Build gap analysis
        gap_analysis = self._build_gap_analysis(
            active_nodes, recommended_node_list,
            evaluation.get("findings", []),
            mapping["it4it_coverage"],
        )

        # Build the response
        result = {
            "status": evaluation["status"],
            "instance_model": self._model_to_dict(model),
            "rule_summary": self.engine.get_rule_summary(),
            "findings": evaluation.get("findings", []),
            "message": evaluation.get("message", ""),
            "as_is_diagram": as_is_diagram,
            "recommended_diagram": recommended_diagram,
            "active_nodes": active_nodes,
            "recommended_nodes": recommended_node_list,
            "it4it_coverage": mapping["it4it_coverage"],
            "active_node_count": len(active_ids),
            "recommended_node_count": len(recommended_node_list),
            "total_findings": len(evaluation.get("findings", [])),
            "gap_analysis": gap_analysis,
        }

        logger.info(f"Instance scan complete. Status: {result['status']}, "
                     f"Plugins: {len(model.installed_plugins)}, "
                     f"Active nodes: {len(active_ids)}, "
                     f"Recommendations: {len(recommended_node_list)}, "
                     f"Findings: {len(result['findings'])}")
        return result

    def _build_gap_analysis(
        self,
        active_nodes: List[Dict],
        recommended_nodes: List[Dict],
        findings: List[Dict],
        it4it_coverage: Dict[str, bool],
    ) -> Dict[str, Any]:
        """
        Build a deterministic gap analysis grouped by IT4IT value stream,
        integration patterns, and health. Each section shows what's present,
        what's missing, and the rules that flagged each gap.
        """
        # Map active nodes to their IT4IT streams
        stream_active = {"S2P": [], "R2D": [], "R2F": [], "D2C": []}
        for n in active_nodes:
            for s in (n.get("it4it_streams") or []):
                if s in stream_active:
                    stream_active[s].append(n["label"])

        # Map recommended nodes to streams
        stream_recommended = {"S2P": [], "R2D": [], "R2F": [], "D2C": []}
        for n in recommended_nodes:
            node_obj = self.ontology._nodes.get(n["id"])
            if node_obj:
                for s in (node_obj.it4it_streams or []):
                    if s in stream_recommended:
                        stream_recommended[s].append({
                            "label": n["label"],
                            "reason": n.get("reason", ""),
                        })

        # Map findings to streams based on rule tags
        stream_findings = {"S2P": [], "R2D": [], "R2F": [], "D2C": []}
        integration_findings = []
        health_findings = []
        security_findings = []
        efficiency_findings = []

        def _finding_summary(f):
            return {
                "rule_id": f["rule_id"],
                "rule_name": f["rule_name"],
                "severity": f["severity"],
                "message": f["message"],
                "recommendation": f["recommendation"],
            }

        for f in findings:
            cat = f.get("category", "")
            # IT4IT coverage and adoption maturity both map to streams via tags
            if cat in ("it4it_coverage", "adoption_maturity"):
                rule = self.engine._rules_by_id.get(f.get("rule_id", ""))
                if rule:
                    for tag in rule.tags:
                        if tag in stream_findings:
                            stream_findings[tag].append(_finding_summary(f))
            elif cat == "integration_pattern":
                integration_findings.append(_finding_summary(f))
            elif cat == "health":
                health_findings.append(_finding_summary(f))
            elif cat == "security":
                security_findings.append(_finding_summary(f))
            elif cat == "efficiency":
                efficiency_findings.append(_finding_summary(f))

        STREAM_META = {
            "S2P": {"label": "Strategy to Portfolio", "description": "Demand management, portfolio prioritization, and governance."},
            "R2D": {"label": "Requirement to Deploy", "description": "Change management, configuration tracking, and controlled releases."},
            "R2F": {"label": "Request to Fulfill", "description": "Service catalog, self-service portal, and fulfillment workflows."},
            "D2C": {"label": "Detect to Correct", "description": "Incident, problem, event management, and proactive monitoring."},
        }

        streams = []
        for key in ["S2P", "R2D", "R2F", "D2C"]:
            meta = STREAM_META[key]
            active_caps = sorted(set(stream_active[key]))
            missing = stream_recommended[key]
            gap_findings = stream_findings[key]
            covered = it4it_coverage.get(key, False)
            # Determine health: green if covered + no findings, yellow if covered + findings, red if not covered
            if covered and len(gap_findings) == 0:
                health = "healthy"
            elif covered:
                health = "gaps"
            else:
                health = "uncovered"
            streams.append({
                "key": key,
                "label": meta["label"],
                "description": meta["description"],
                "covered": covered,
                "health": health,
                "active_capabilities": active_caps,
                "missing_capabilities": missing,
                "findings": gap_findings,
                "finding_count": len(gap_findings),
            })

        return {
            "streams": streams,
            "integration": {
                "findings": integration_findings,
                "finding_count": len(integration_findings),
                "has_issues": len(integration_findings) > 0,
            },
            "health": {
                "findings": health_findings,
                "finding_count": len(health_findings),
                "has_issues": len(health_findings) > 0,
            },
            "security": {
                "findings": security_findings,
                "finding_count": len(security_findings),
                "has_issues": len(security_findings) > 0,
            },
            "efficiency": {
                "findings": efficiency_findings,
                "finding_count": len(efficiency_findings),
                "has_issues": len(efficiency_findings) > 0,
            },
            "summary": {
                "streams_covered": sum(1 for s in streams if s["covered"]),
                "streams_total": 4,
                "total_gaps": sum(s["finding_count"] for s in streams),
                "integration_issues": len(integration_findings),
                "health_issues": len(health_findings),
                "security_issues": len(security_findings),
                "efficiency_issues": len(efficiency_findings),
            },
        }

    def _build_instance_model(self) -> InstanceModel:
        """Query the instance and populate an InstanceModel."""
        model = InstanceModel()
        model.instance_url = self.sn.instance

        # --- Installed plugins/apps ---
        model.installed_plugins = self._scan_plugins()

        # --- Active tables with record counts ---
        model.active_tables = self._scan_key_tables()

        # --- Custom table count (u_* and x_* prefixed tables) ---
        try:
            custom_count = self.sn.get_record_count(
                'sys_db_object',
                query='nameSTARTSWITHu_^ORnameSTARTSWITHx_'
            )
            model.active_tables['_custom_tables'] = custom_count
            logger.info(f"Custom tables (u_/x_ prefix): {custom_count}")
        except Exception:
            model.active_tables['_custom_tables'] = -1

        # --- Integration Hub flows ---
        model.integration_flows = self._scan_integration_flows()

        # --- MID Servers ---
        model.mid_servers = self._scan_mid_servers()

        # --- CMDB stats ---
        model.cmdb_stats = self._scan_cmdb_stats()

        # --- Instance properties ---
        model.instance_properties = self._scan_properties()
        model.domain_separation = (
            model.instance_properties.get("glide.sys.domain.enabled", "false").lower() == "true"
        )

        return model

    # ------------------------------------------------------------------
    # Individual scan methods
    # ------------------------------------------------------------------

    def _scan_plugins(self) -> Dict[str, Dict]:
        """Scan installed plugins, store apps, and sys_store_app."""
        plugins = {}
        try:
            # 1) sys_app — custom & scoped apps
            apps = self.sn.get_installed_applications()
            for app in apps:
                scope = app.get("scope", "")
                if scope:
                    plugins[scope] = {
                        "name": app.get("name", ""),
                        "version": app.get("version", ""),
                        "active": True,
                    }

            # 2) v_plugin — platform plugins (increased limit for large instances)
            data = self.sn._make_request(
                "/api/now/table/v_plugin",
                params={
                    "sysparm_fields": "id,name,active",
                    "sysparm_query": "active=true",
                    "sysparm_limit": 2000,
                },
                cache_key="v_plugin_active",
            )
            if data:
                for p in data.get("result", []):
                    pid = p.get("id", "")
                    if pid and pid not in plugins:
                        plugins[pid] = {
                            "name": p.get("name", ""),
                            "version": "",
                            "active": p.get("active", "") == "true",
                        }

            # 3) sys_store_app — store-installed apps (scope may differ from sys_app)
            store_data = self.sn._make_request(
                "/api/now/table/sys_store_app",
                params={
                    "sysparm_fields": "scope,name,version",
                    "sysparm_limit": 1000,
                },
                cache_key="sys_store_app",
            )
            if store_data:
                for sa in store_data.get("result", []):
                    scope = sa.get("scope", "")
                    if scope and scope not in plugins:
                        plugins[scope] = {
                            "name": sa.get("name", ""),
                            "version": sa.get("version", ""),
                            "active": True,
                        }
        except Exception as e:
            logger.warning(f"Plugin scan partial failure: {e}")

        logger.info(f"Scanned {len(plugins)} plugins/apps")
        return plugins

    def _scan_key_tables(self) -> Dict[str, int]:
        """Check record counts for ontology-referenced + integration/health tables."""
        # Start with all tables the ontology cares about (ensures detection works)
        key_tables = set(self.ontology.get_all_referenced_tables())
        # Add integration pattern detection tables
        key_tables.update([
            "sys_data_source", "sys_soap_message", "sys_rest_message",
            "sys_import_set", "sys_transform_map", "sysauto_script",
            "sysevent_email_action",
            # Tier 2 integration evidence (Jochen Geist decision tree)
            "sys_script",          # business rules — custom scripting volume
            "sys_ws_operation",    # scripted REST API definitions — custom API surface
            "sys_remote_table",    # remote tables — Zero Copy / data residency pattern
        ])
        # Add health detection tables (may already be in ontology set)
        key_tables.update(["sys_audit", "sc_cat_item"])

        counts = {}
        for table in sorted(key_tables):
            try:
                data = self.sn._make_request(
                    f"/api/now/stats/{table}",
                    params={"sysparm_count": "true"},
                    cache_key=f"count_{table}",
                )
                if data:
                    count = int(data.get("result", {}).get("stats", {}).get("count", 0))
                    counts[table] = count
                else:
                    counts[table] = -1  # table may not exist or no access
            except Exception:
                counts[table] = -1
        logger.info(f"Scanned record counts for {len(counts)} tables")
        return counts

    def _scan_integration_flows(self) -> List[Dict]:
        """Scan Integration Hub flows."""
        flows = []
        try:
            data = self.sn._make_request(
                "/api/now/table/sys_hub_flow",
                params={
                    "sysparm_fields": "name,active,trigger_type,sys_updated_on",
                    "sysparm_query": "active=true",
                    "sysparm_limit": 200,
                },
                cache_key="hub_flows_active",
            )
            if data:
                for f in data.get("result", []):
                    flows.append({
                        "name": f.get("name", ""),
                        "active": True,
                        "trigger_type": f.get("trigger_type", ""),
                        "last_updated": f.get("sys_updated_on", ""),
                    })
        except Exception as e:
            logger.warning(f"Integration flow scan failed: {e}")
        logger.info(f"Scanned {len(flows)} active Integration Hub flows")
        return flows

    def _scan_mid_servers(self) -> List[Dict]:
        """Scan MID Server status."""
        servers = []
        try:
            data = self.sn._make_request(
                "/api/now/table/ecc_agent",
                params={
                    "sysparm_fields": "name,status,host_name",
                    "sysparm_query": "statusINup,upgrading",
                    "sysparm_limit": 50,
                },
                cache_key="mid_servers",
            )
            if data:
                for s in data.get("result", []):
                    servers.append({
                        "name": s.get("name", ""),
                        "status": s.get("status", ""),
                        "host": s.get("host_name", ""),
                    })
        except Exception as e:
            logger.warning(f"MID Server scan failed: {e}")
        logger.info(f"Scanned {len(servers)} active MID Servers")
        return servers

    def _scan_cmdb_stats(self) -> Dict[str, Any]:
        """Scan CMDB population stats."""
        stats = {"total_cis": 0, "classes_populated": [], "has_discovery": False}
        try:
            # Total CI count
            data = self.sn._make_request(
                "/api/now/stats/cmdb_ci",
                params={"sysparm_count": "true"},
                cache_key="cmdb_ci_count",
            )
            if data:
                stats["total_cis"] = int(
                    data.get("result", {}).get("stats", {}).get("count", 0)
                )

            # Check if Discovery plugin is active
            disc = self.sn._make_request(
                "/api/now/table/v_plugin",
                params={
                    "sysparm_query": "id=com.snc.discovery^active=true",
                    "sysparm_limit": 1,
                },
                cache_key="discovery_active",
            )
            if disc and len(disc.get("result", [])) > 0:
                stats["has_discovery"] = True

        except Exception as e:
            logger.warning(f"CMDB stats scan failed: {e}")
        return stats

    def _scan_properties(self) -> Dict[str, str]:
        """Scan compliance-relevant instance properties."""
        props = {}
        try:
            data = self.sn._make_request(
                "/api/now/table/sys_properties",
                params={
                    "sysparm_fields": "name,value",
                    "sysparm_query": (
                        "name=glide.sys.domain.enabled"
                        "^ORname=glide.security.use_csrf_token"
                        "^ORnameSTARTSWITHglide.audit"
                    ),
                    "sysparm_limit": 50,
                },
                cache_key="sys_properties_compliance",
            )
            if data:
                for p in data.get("result", []):
                    props[p.get("name", "")] = p.get("value", "")
        except Exception as e:
            logger.warning(f"Properties scan failed: {e}")
        return props

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    @staticmethod
    def _model_to_dict(model: InstanceModel) -> Dict:
        """Convert InstanceModel to a JSON-serializable dict."""
        return {
            "instance_url": model.instance_url,
            "installed_plugins": model.installed_plugins,
            "active_tables": model.active_tables,
            "integration_flows_count": len(model.integration_flows),
            "mid_servers": model.mid_servers,
            "cmdb_stats": model.cmdb_stats,
            "domain_separation": model.domain_separation,
            "properties_scanned": len(model.instance_properties),
        }
