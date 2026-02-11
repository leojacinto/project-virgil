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

logger = logging.getLogger(__name__)


class InstanceScanner:
    """
    Scans a connected ServiceNow instance and builds an InstanceModel.
    
    Usage:
        scanner = InstanceScanner(sn_utils_service)
        model = scanner.scan()
        engine = RuleEngine()
        findings = engine.evaluate(model)
    """

    def __init__(self, sn_utils_service):
        """
        Args:
            sn_utils_service: An initialized SNUtilsService instance.
        """
        self.sn = sn_utils_service
        self.engine = RuleEngine()

    def scan(self) -> Dict[str, Any]:
        """
        Run a full instance scan and return results.
        
        Returns dict with:
          - instance_model: structured data about the instance
          - rule_summary: what the rule engine contains
          - findings: rule evaluation results (empty if disabled)
          - status: 'disabled' | 'completed'
        """
        logger.info("Starting instance scan...")

        # Layer 1: Build the instance model from REST API data
        model = self._build_instance_model()

        # Layer 2: Evaluate rules against the model
        evaluation = self.engine.evaluate(model)

        # Build the response
        result = {
            "status": evaluation["status"],
            "instance_model": self._model_to_dict(model),
            "rule_summary": self.engine.get_rule_summary(),
            "findings": evaluation.get("findings", []),
            "message": evaluation.get("message", ""),
        }

        logger.info(f"Instance scan complete. Status: {result['status']}, "
                     f"Plugins: {len(model.installed_plugins)}, "
                     f"Flows: {len(model.integration_flows)}")
        return result

    def _build_instance_model(self) -> InstanceModel:
        """Query the instance and populate an InstanceModel."""
        model = InstanceModel()
        model.instance_url = self.sn.instance

        # --- Installed plugins/apps ---
        model.installed_plugins = self._scan_plugins()

        # --- Active tables with record counts ---
        model.active_tables = self._scan_key_tables()

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
        """Scan installed plugins and store apps."""
        plugins = {}
        try:
            # Get store apps
            apps = self.sn.get_installed_applications()
            for app in apps:
                scope = app.get("scope", "")
                if scope:
                    plugins[scope] = {
                        "name": app.get("name", ""),
                        "version": app.get("version", ""),
                        "active": True,
                    }

            # Also try v_plugin for platform plugins
            data = self.sn._make_request(
                "/api/now/table/v_plugin",
                params={
                    "sysparm_fields": "id,name,active",
                    "sysparm_query": "active=true",
                    "sysparm_limit": 500,
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
        except Exception as e:
            logger.warning(f"Plugin scan partial failure: {e}")

        logger.info(f"Scanned {len(plugins)} plugins/apps")
        return plugins

    def _scan_key_tables(self) -> Dict[str, int]:
        """Check record counts for key architectural tables."""
        key_tables = [
            "incident", "problem", "change_request", "sc_request",
            "sn_customerservice_case", "sn_hr_core_case", "cmdb_ci",
            "kb_knowledge", "sn_si_incident", "sn_vul_vulnerability",
            "sys_hub_flow", "wf_workflow", "em_event",
        ]
        counts = {}
        for table in key_tables:
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
