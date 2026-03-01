"""
Plutus Scanner — Workflow Data Fabric credit sizing engine.

Reads the editable plutus_pricing.yaml, scans a live ServiceNow instance
for usage evidence, applies candidate-detection rules, and produces a
credit-consumption estimate with tier recommendation.
"""

import logging
import os
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

PRICING_YAML = Path(__file__).parent / "plutus_pricing.yaml"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CapabilityUsage:
    """Detected or user-supplied usage for a single WDF capability."""
    capability_id: str
    label: str
    detected: bool = False               # True if auto-detected on instance
    usage_value: float = 0.0             # Metered quantity (txns, MB, min …)
    meter_unit: str = ""
    credits_per_unit: float = 0.0
    total_credits: float = 0.0
    pro_only: bool = False
    measurable: bool = True              # False = "Not Measured" section
    measurement_rule: str = ""           # How this capability is measured
    scan_evidence: str = ""              # Human-readable evidence string
    user_override: Optional[float] = None  # Manual override from frontend
    data_days: int = 0                   # Days of log data observed
    is_estimated: bool = False           # True if usage_per_year is extrapolated
    usage_per_year: float = 0.0          # Annualized usage (actual or estimated)


@dataclass
class CandidateFinding:
    """A WDF capability recommendation based on instance behavior."""
    rule_id: str
    name: str
    capability_id: str
    also_recommends: Optional[str] = None
    message: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlutusResult:
    """Complete output of a Plutus pricing scan."""
    # Credit breakdown
    capability_usage: List[CapabilityUsage] = field(default_factory=list)
    total_credits: float = 0.0

    # Tier recommendation
    recommended_tier: str = "standard"
    min_packs: int = 1
    annual_cost: float = 0.0
    credits_per_pack: int = 2_000_000
    price_per_pack: int = 100_000

    # Candidate findings
    candidates: List[CandidateFinding] = field(default_factory=list)

    # Pro-only capabilities detected
    requires_pro: bool = False
    pro_reasons: List[str] = field(default_factory=list)

    # Raw config for frontend editing
    pricing_config: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Pricing config loader
# ---------------------------------------------------------------------------

class PlutusPricingConfig:
    """Loads and provides access to the editable pricing YAML."""

    def __init__(self, yaml_path: Optional[str] = None):
        self._path = Path(yaml_path) if yaml_path else PRICING_YAML
        self._data: Dict[str, Any] = {}
        self.reload()

    def reload(self):
        with open(self._path, "r") as f:
            self._data = yaml.safe_load(f)
        logger.info(f"Plutus pricing config loaded from {self._path}")

    def save(self, data: Dict[str, Any]):
        """Write updated config back to YAML."""
        self._data = data
        with open(self._path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False,
                      allow_unicode=True, width=120)
        logger.info(f"Plutus pricing config saved to {self._path}")

    @property
    def raw(self) -> Dict[str, Any]:
        return self._data

    @property
    def packs(self) -> Dict[str, Any]:
        return self._data.get("packs", {})

    @property
    def tiers(self) -> Dict[str, Any]:
        return self._data.get("tiers", {})

    @property
    def rate_card(self) -> List[Dict[str, Any]]:
        return self._data.get("rate_card", [])

    @property
    def zcc_databases(self) -> List[Dict[str, Any]]:
        return self._data.get("zcc_supported_databases", [])

    @property
    def candidate_rules(self) -> List[Dict[str, Any]]:
        return self._data.get("candidate_rules", [])

    def get_capability(self, cap_id: str) -> Optional[Dict[str, Any]]:
        for cap in self.rate_card:
            if cap["id"] == cap_id:
                return cap
        return None


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class PlutusScanner:
    """
    Scans a ServiceNow instance for WDF-relevant usage data and produces
    a credit-sizing estimate.
    """

    def __init__(self, sn_utils_service, pricing_config: Optional[PlutusPricingConfig] = None):
        self.sn = sn_utils_service
        self.config = pricing_config or PlutusPricingConfig()

    # ----- public API -----

    def scan(self, active_node_ids: Set[str] = None,
             active_tables: Dict[str, int] = None,
             user_overrides: Dict[str, float] = None) -> PlutusResult:
        """
        Run a full Plutus pricing scan.

        Args:
            active_node_ids: Ontology node IDs already detected by Minos scanner
            active_tables:   Table record counts already collected
            user_overrides:  Manual usage values keyed by capability_id
        """
        active_node_ids = active_node_ids or set()
        active_tables = active_tables or {}
        user_overrides = user_overrides or {}

        result = PlutusResult()
        result.pricing_config = self.config.raw
        result.credits_per_pack = self.config.packs.get("credits_per_pack", 2_000_000)
        result.price_per_pack = self.config.packs.get("price_per_pack_yearly", 100_000)

        # 1. Scan usage for each capability on the rate card
        instance_data = self._gather_instance_data(active_tables)
        for cap in self.config.rate_card:
            if cap.get("hidden", False):
                continue
            usage = self._assess_capability(cap, active_node_ids, instance_data, user_overrides)
            result.capability_usage.append(usage)
            result.total_credits += usage.total_credits

            if usage.pro_only and (usage.detected or usage.usage_value > 0):
                result.requires_pro = True
                result.pro_reasons.append(f"{usage.label} requires Professional tier")

        # 2. Detect candidates (ZCC, Stream Connect, Data Catalog, etc.)
        result.candidates = self._evaluate_candidates(instance_data, active_node_ids)

        # 3. Determine tier and cost
        self._calculate_tier(result)

        return result

    # ----- instance data gathering -----

    def _gather_instance_data(self, active_tables: Dict[str, int]) -> Dict[str, Any]:
        """Collect instance metrics relevant to WDF pricing.

        Scans EXECUTION tables (not definitions) so numbers reflect
        actual usage, not configured assets.
        """
        data: Dict[str, Any] = {
            "active_tables": active_tables,
            "data_sources": [],
            "jdbc_data_sources": [],
            "rest_messages": [],
            "outbound_http_logs": [],
            # ---- execution counts (the real metrics) ----
            "ihub_execution_count": 0,
            "outbound_http_count": 0,
            "outbound_http_total_request_bytes": 0,
            "outbound_http_total_response_bytes": 0,
            "import_run_count": 0,
            "import_row_count": 0,
            "reports_count": 0,
            "custom_table_count": active_tables.get("_custom_tables", 0),
            "rpa_execution_minutes": 0,
        }

        # ------------------------------------------------------------------
        # 1. IHub / outbound HTTP execution count (sys_outbound_http_log)
        #    Each row = one real outbound call.  source_table tells us if it
        #    came from a hub flow step.
        # ------------------------------------------------------------------
        try:
            total_outbound = self.sn.get_record_count("sys_outbound_http_log")
            data["outbound_http_count"] = total_outbound or 0

            # IHub-originated subset
            ihub_count = self.sn.get_record_count(
                "sys_outbound_http_log",
                query="source_table=sys_hub_step_instance"
            )
            data["ihub_execution_count"] = ihub_count or 0
            logger.info(f"Plutus: {data['ihub_execution_count']} IHub executions, "
                        f"{data['outbound_http_count']} total outbound HTTP calls")

            # Sample outbound logs for ZCC candidate URL matching
            http_samples = self.sn.get_table_data(
                "sys_outbound_http_log",
                fields="url,hostname,method,request_length,response_length,source_table",
                limit=200
            )
            if http_samples:
                data["outbound_http_logs"] = http_samples
                # Estimate total bytes from sample average
                req_bytes = sum(int(r.get("request_length", 0) or 0) for r in http_samples)
                resp_bytes = sum(int(r.get("response_length", 0) or 0) for r in http_samples)
                if http_samples:
                    avg_req = req_bytes / len(http_samples)
                    avg_resp = resp_bytes / len(http_samples)
                    data["outbound_http_total_request_bytes"] = int(avg_req * total_outbound)
                    data["outbound_http_total_response_bytes"] = int(avg_resp * total_outbound)
        except Exception as e:
            logger.warning(f"Plutus: Could not scan sys_outbound_http_log: {e}")

        # ------------------------------------------------------------------
        # 2. JDBC data sources (for ZCC candidate detection)
        # ------------------------------------------------------------------
        try:
            ds_resp = self.sn.get_table_data(
                "sys_data_source",
                query="type=JDBC",
                fields="name,type,connection_url,format",
                limit=500
            )
            if ds_resp:
                data["jdbc_data_sources"] = ds_resp
                data["data_sources"] = ds_resp
                logger.info(f"Plutus: Found {len(ds_resp)} JDBC data sources")
        except Exception as e:
            logger.warning(f"Plutus: Could not scan sys_data_source: {e}")

        # ------------------------------------------------------------------
        # 3. REST message definitions (for ZCC candidate URL matching)
        # ------------------------------------------------------------------
        try:
            rest_resp = self.sn.get_table_data(
                "sys_rest_message",
                fields="name,rest_endpoint",
                limit=500
            )
            if rest_resp:
                data["rest_messages"] = rest_resp
                logger.info(f"Plutus: Found {len(rest_resp)} REST message definitions")
        except Exception as e:
            logger.warning(f"Plutus: Could not scan sys_rest_message: {e}")

        # ------------------------------------------------------------------
        # 4. Import set EXECUTIONS (sys_import_set_run + sys_import_set_row)
        # ------------------------------------------------------------------
        try:
            run_count = self.sn.get_record_count("sys_import_set_run")
            row_count = self.sn.get_record_count("sys_import_set_row")
            data["import_run_count"] = run_count or 0
            data["import_row_count"] = row_count or 0
            logger.info(f"Plutus: {data['import_run_count']} import runs, "
                        f"{data['import_row_count']} imported rows")
        except Exception as e:
            logger.warning(f"Plutus: Could not scan import set runs: {e}")

        # ------------------------------------------------------------------
        # 5. Reports / dashboards (definitions — no exec log available)
        # ------------------------------------------------------------------
        try:
            report_count = self.sn.get_record_count("sys_report")
            pa_count = self.sn.get_record_count("pa_dashboards")
            data["reports_count"] = (report_count or 0) + (pa_count or 0)
            logger.info(f"Plutus: {data['reports_count']} report/dashboard definitions")
        except Exception as e:
            logger.warning(f"Plutus: Could not scan reports: {e}")

        # ------------------------------------------------------------------
        # 6. RPA execution minutes
        #    Try sn_rpa_execution first; fall back to sn_rpa_robot count
        # ------------------------------------------------------------------
        try:
            rpa_exec_count = self.sn.get_record_count("sn_rpa_execution")
            if rpa_exec_count and rpa_exec_count > 0:
                data["rpa_execution_minutes"] = rpa_exec_count  # placeholder; refine with duration field
                logger.info(f"Plutus: {rpa_exec_count} RPA execution records")
            else:
                rpa_robot_count = self.sn.get_record_count("sn_rpa_robot")
                if rpa_robot_count and rpa_robot_count > 0:
                    data["rpa_execution_minutes"] = 0  # robots exist but no executions
                    logger.info(f"Plutus: {rpa_robot_count} RPA robots, no execution data")
        except Exception as e:
            logger.debug(f"Plutus: No RPA tables accessible: {e}")

        # ------------------------------------------------------------------
        # 7. Data span detection — how many days of data each log table holds
        #    Query oldest record (ORDER BY sys_created_on ASC, limit 1).
        # ------------------------------------------------------------------
        from datetime import datetime, timezone
        data["data_spans"] = {}  # table_name -> days of data
        span_tables = [
            "sys_outbound_http_log",
            "sys_import_set_run",
            "sn_rpa_execution",
        ]
        now = datetime.now(timezone.utc)
        for tbl in span_tables:
            try:
                oldest = self.sn.get_table_data(
                    tbl,
                    query="ORDERBYsys_created_on",
                    fields="sys_created_on",
                    limit=1
                )
                if oldest and oldest[0].get("sys_created_on"):
                    dt_str = oldest[0]["sys_created_on"]
                    # ServiceNow format: "2024-06-15 08:23:11"
                    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    span_days = max((now - dt).days, 1)
                    data["data_spans"][tbl] = span_days
                    logger.info(f"Plutus: {tbl} data spans {span_days} days")
            except Exception as e:
                logger.debug(f"Plutus: Could not determine data span for {tbl}: {e}")

        return data

    # ----- capability assessment -----

    def _assess_capability(self, cap: Dict, active_node_ids: Set[str],
                           instance_data: Dict, user_overrides: Dict) -> CapabilityUsage:
        """Assess usage of a single WDF capability."""
        cap_id = cap["id"]
        usage = CapabilityUsage(
            capability_id=cap_id,
            label=cap.get("label", cap_id),
            meter_unit=cap.get("meter_unit", ""),
            credits_per_unit=cap.get("credits", 0),
            pro_only=cap.get("pro_only", False),
            measurable=cap.get("measurable", True),
            measurement_rule=cap.get("measurement_rule", "").strip(),
        )

        # Map capabilities to their primary execution log table for date span
        CAP_TABLE_MAP = {
            "integration_hub": "sys_outbound_http_log",
            "stream_connect": "sys_outbound_http_log",
            "api_access_volume": "sys_outbound_http_log",
            "rpa_bots": "sn_rpa_execution",
        }

        # Check if user provided a manual override
        if cap_id in user_overrides:
            usage.user_override = user_overrides[cap_id]
            usage.usage_value = user_overrides[cap_id]
            usage.usage_per_year = user_overrides[cap_id]
            usage.detected = True
            usage.scan_evidence = "User-provided value"
        else:
            # Auto-detect based on capability
            self._auto_detect(cap_id, usage, instance_data, active_node_ids)

        # Annualize: if we have a time-based table, extrapolate or confirm
        data_spans = instance_data.get("data_spans", {})
        primary_table = CAP_TABLE_MAP.get(cap_id)

        if usage.detected and primary_table and primary_table in data_spans:
            span_days = data_spans[primary_table]
            usage.data_days = span_days
            if span_days >= 365:
                # Full year of data — usage_value IS the yearly value
                usage.usage_per_year = usage.usage_value
                usage.is_estimated = False
            else:
                # Extrapolate: average daily rate × 365
                daily_rate = usage.usage_value / span_days
                usage.usage_per_year = round(daily_rate * 365, 1)
                usage.is_estimated = True
                usage.scan_evidence += (
                    f" [Observed {usage.usage_value:,.0f} over {span_days} days → "
                    f"est. {usage.usage_per_year:,.0f}/yr via avg daily rate]"
                )
        elif usage.detected:
            # Non-time-based capability (ZCC db count, report count, etc.)
            # or no span data available — treat raw value as yearly
            usage.usage_per_year = usage.usage_value
            usage.is_estimated = False

        # Calculate credits from annualized value
        usage.total_credits = usage.usage_per_year * usage.credits_per_unit

        return usage

    def _auto_detect(self, cap_id: str, usage: CapabilityUsage,
                     data: Dict, active_node_ids: Set[str]):
        """Try to auto-detect usage for a capability from instance data.

        Uses EXECUTION counts, not asset/definition counts.
        """

        if cap_id == "integration_hub":
            # Real execution count from sys_outbound_http_log
            # filtered to source_table=sys_hub_step_instance
            count = data.get("ihub_execution_count", 0)
            if count > 0 or "integration_hub" in active_node_ids:
                usage.detected = True
                usage.usage_value = count
                usage.scan_evidence = (
                    f"{count:,} IHub outbound executions "
                    f"(from sys_outbound_http_log, source=sys_hub_step_instance)"
                )

        elif cap_id == "rpa_hub":
            minutes = data.get("rpa_execution_minutes", 0)
            if minutes > 0:
                usage.detected = True
                usage.usage_value = minutes
                usage.scan_evidence = f"{minutes:,} RPA execution records (from sn_rpa_execution)"
            # If 0, RPA not active — leave as not detected

        elif cap_id == "api_access_volume":
            # Estimate MB from outbound HTTP log response sizes
            resp_bytes = data.get("outbound_http_total_response_bytes", 0)
            total_calls = data.get("outbound_http_count", 0)
            if resp_bytes > 0:
                mb_egressed = resp_bytes / (1024 * 1024)
                usage.detected = True
                usage.usage_value = round(mb_egressed, 1)
                usage.scan_evidence = (
                    f"{mb_egressed:,.1f} MB estimated egress from "
                    f"{total_calls:,} outbound HTTP calls (sampled avg × total)"
                )
            elif total_calls > 0:
                usage.detected = True
                usage.usage_value = 0
                usage.scan_evidence = (
                    f"{total_calls:,} outbound HTTP calls detected but "
                    f"payload sizes not available — enter MB manually"
                )

        elif cap_id == "orchestration":
            # Orchestration is included (0 credits) — just report activity
            ihub = data.get("ihub_execution_count", 0)
            total_outbound = data.get("outbound_http_count", 0)
            if ihub > 0 or total_outbound > 0:
                usage.detected = True
                usage.usage_value = total_outbound
                usage.scan_evidence = (
                    f"{total_outbound:,} total outbound calls "
                    f"({ihub:,} from IHub) — orchestration included in tier"
                )

        elif cap_id == "zero_copy_connectors":
            # Detect connections to ZCC-supported databases via 3 sources:
            # 1. JDBC data sources (connection_url patterns)
            # 2. REST message definitions (spoke names)
            # 3. Outbound HTTP log URLs (hostname patterns)
            matched_dbs = set()
            jdbc_count = 0

            for ds in data.get("jdbc_data_sources", []):
                conn_url = (ds.get("connection_url", "") or "").lower()
                ds_name = (ds.get("name", "") or "").lower()
                for db in self.config.zcc_databases:
                    for pattern in db.get("jdbc_patterns", []):
                        if pattern.lower() in conn_url or pattern.lower() in ds_name:
                            matched_dbs.add(db["name"])
                            jdbc_count += 1

            for msg in data.get("rest_messages", []):
                endpoint = (msg.get("rest_endpoint", "") or "").lower()
                name = (msg.get("name", "") or "").lower()
                for db in self.config.zcc_databases:
                    for spoke_name in db.get("spoke_names", []):
                        if spoke_name.lower() in name or spoke_name.lower() in endpoint:
                            matched_dbs.add(db["name"])

            for log in data.get("outbound_http_logs", []):
                url = (log.get("url", "") or "").lower()
                hostname = (log.get("hostname", "") or "").lower()
                for db in self.config.zcc_databases:
                    for pattern in db.get("jdbc_patterns", []):
                        if pattern.lower() in url or pattern.lower() in hostname:
                            matched_dbs.add(db["name"])

            if matched_dbs:
                usage.detected = True
                db_str = ", ".join(sorted(matched_dbs))

                # Estimate MB: count outbound HTTP bytes going to matched DB hosts
                matched_bytes = 0
                matched_calls = 0
                for log in data.get("outbound_http_logs", []):
                    url = (log.get("url", "") or "").lower()
                    hostname = (log.get("hostname", "") or "").lower()
                    for db in self.config.zcc_databases:
                        if db["name"] not in matched_dbs:
                            continue
                        for pattern in db.get("jdbc_patterns", []):
                            if pattern.lower() in url or pattern.lower() in hostname:
                                matched_bytes += int(log.get("response_length", 0) or 0)
                                matched_bytes += int(log.get("request_length", 0) or 0)
                                matched_calls += 1
                                break

                # Scale sample to full population
                total_outbound = data.get("outbound_http_count", 0)
                sample_size = len(data.get("outbound_http_logs", []))
                if sample_size > 0 and matched_calls > 0:
                    ratio = matched_calls / sample_size
                    estimated_total_calls = int(total_outbound * ratio)
                    avg_bytes_per_call = matched_bytes / matched_calls
                    estimated_mb = round((avg_bytes_per_call * estimated_total_calls) / (1024 * 1024), 1)
                else:
                    estimated_mb = 0
                    estimated_total_calls = 0

                usage.usage_value = max(estimated_mb, 0)
                usage.scan_evidence = (
                    f"Proposed — connections to {len(matched_dbs)} ZCC-supported DB(s) detected: {db_str} "
                    f"({jdbc_count} JDBC source(s)). Usage patterns suggest this instance may benefit from Zero Copy Connectors. "
                    f"Est. {usage.usage_value:,.1f} MB from ~{estimated_total_calls:,} DB-bound calls."
                )

        elif cap_id == "stream_connect":
            # Detect high-frequency messaging from a SINGLE source/endpoint.
            # Logic: group outbound HTTP logs by hostname, find the top talker.
            # Only qualifies if one host has high call concentration.
            total_outbound = data.get("outbound_http_count", 0)
            sample_size = len(data.get("outbound_http_logs", []))
            indicators = []

            # Group sampled calls by hostname
            host_stats = {}  # hostname -> {calls, bytes}
            for log in data.get("outbound_http_logs", []):
                host = (log.get("hostname", "") or "").lower().strip()
                if not host:
                    host = "(unknown)"
                if host not in host_stats:
                    host_stats[host] = {"calls": 0, "bytes": 0}
                host_stats[host]["calls"] += 1
                host_stats[host]["bytes"] += int(log.get("response_length", 0) or 0)
                host_stats[host]["bytes"] += int(log.get("request_length", 0) or 0)

            # Find top single-source talker and scale to full population
            top_host = None
            top_calls_estimated = 0
            top_mb_estimated = 0
            if sample_size > 0 and host_stats:
                for host, stats in host_stats.items():
                    ratio = stats["calls"] / sample_size
                    est_calls = int(total_outbound * ratio)
                    avg_bytes = stats["bytes"] / stats["calls"] if stats["calls"] > 0 else 0
                    est_mb = round((avg_bytes * est_calls) / (1024 * 1024), 1)
                    if est_calls > top_calls_estimated:
                        top_host = host
                        top_calls_estimated = est_calls
                        top_mb_estimated = est_mb

            # Threshold: single source must have >1000 estimated calls
            if top_host and top_calls_estimated > 1000:
                indicators.append(
                    f"~{top_calls_estimated:,} calls to single host '{top_host}' "
                    f"(~{top_mb_estimated:,.1f} MB)"
                )

            # Also check import sets: single import source with high row count
            import_runs = data.get("import_run_count", 0)
            import_rows = data.get("import_row_count", 0)
            if import_runs > 0 and import_rows > 10000:
                avg_rows_per_run = import_rows / import_runs
                if avg_rows_per_run > 100:  # high-volume per run = batch pattern
                    indicators.append(
                        f"{import_runs:,} import runs averaging "
                        f"{avg_rows_per_run:,.0f} rows/run ({import_rows:,} total rows)"
                    )

            if indicators:
                usage.detected = True
                usage.usage_value = max(top_mb_estimated, 0)
                usage.scan_evidence = (
                    f"Proposed — usage patterns suggest this instance may benefit from Stream Connect. "
                    f"Single-source indicators: {'; '.join(indicators)}. "
                    f"Est. {usage.usage_value:,.1f} MB throughput from top source."
                )

        elif cap_id == "ai_data_explorer":
            # Detect high report/dashboard count as signal for AI Data Explorer.
            # Many reports = many narrow data views = strong candidate.
            # Estimate: ~10% of reports would translate to explorations.
            report_count = data.get("reports_count", 0)
            if report_count > 0:
                usage.detected = True
                estimated_explorations = max(1, int(report_count * 0.10))
                usage.usage_value = estimated_explorations
                usage.scan_evidence = (
                    f"Proposed — {report_count:,} reports/dashboards on instance suggest this instance may benefit from AI Data Explorer. "
                    f"Est. {estimated_explorations:,} explorations (~10% of reports)."
                )

        # Not-measured capabilities: skip auto-detect entirely
        # (handled by measurable=false in YAML, frontend shows in Not Measured section)

    # ----- candidate detection -----

    def _evaluate_candidates(self, data: Dict, active_node_ids: Set[str]) -> List[CandidateFinding]:
        """Evaluate candidate rules to recommend WDF capabilities."""
        candidates = []

        for rule in self.config.candidate_rules:
            check = rule.get("check", "")
            finding = None

            if check == "jdbc_to_supported_db":
                finding = self._check_jdbc_to_supported_db(rule, data)
            elif check == "ihub_spoke_to_supported_db":
                finding = self._check_ihub_spoke_to_supported_db(rule, data, active_node_ids)
            elif check == "high_frequency_imports":
                finding = self._check_high_frequency_imports(rule, data)
            elif check == "large_outbound_volume":
                finding = self._check_large_outbound_volume(rule, data)
            elif check == "high_report_usage":
                finding = self._check_high_report_usage(rule, data)
            elif check == "large_table_estate":
                finding = self._check_large_table_estate(rule, data)

            if finding:
                candidates.append(finding)

        return candidates

    def _check_jdbc_to_supported_db(self, rule: Dict, data: Dict) -> Optional[CandidateFinding]:
        """Check if JDBC data sources connect to ZCC-supported databases."""
        jdbc_sources = data.get("jdbc_data_sources", [])
        min_ds = rule.get("min_data_sources", 1)
        if len(jdbc_sources) < min_ds:
            return None

        matched_dbs = set()
        for ds in jdbc_sources:
            conn_url = (ds.get("connection_url", "") or "").lower()
            ds_name = (ds.get("name", "") or "").lower()
            for db in self.config.zcc_databases:
                for pattern in db.get("jdbc_patterns", []):
                    if pattern.lower() in conn_url or pattern.lower() in ds_name:
                        matched_dbs.add(db["name"])

        if not matched_dbs:
            return None

        msg = rule.get("message", "").format(
            count=len(jdbc_sources),
            databases=", ".join(sorted(matched_dbs))
        )
        return CandidateFinding(
            rule_id=rule["id"],
            name=rule["name"],
            capability_id=rule.get("recommends", "zero_copy_connectors"),
            message=msg,
            evidence={"jdbc_count": len(jdbc_sources), "databases": list(matched_dbs)}
        )

    def _check_ihub_spoke_to_supported_db(self, rule: Dict, data: Dict,
                                           active_node_ids: Set[str]) -> Optional[CandidateFinding]:
        """Check if IHub spokes or outbound HTTP calls target ZCC-supported databases."""
        if "integration_hub" not in active_node_ids:
            return None

        matched_dbs = set()

        # Check REST message definitions for database-related endpoints
        for msg in data.get("rest_messages", []):
            endpoint = (msg.get("rest_endpoint", "") or "").lower()
            name = (msg.get("name", "") or "").lower()
            for db in self.config.zcc_databases:
                for spoke_name in db.get("spoke_names", []):
                    if spoke_name.lower() in name or spoke_name.lower() in endpoint:
                        matched_dbs.add(db["name"])

        # Also check actual outbound HTTP log URLs for database patterns
        for log in data.get("outbound_http_logs", []):
            url = (log.get("url", "") or "").lower()
            hostname = (log.get("hostname", "") or "").lower()
            for db in self.config.zcc_databases:
                for pattern in db.get("jdbc_patterns", []):
                    if pattern.lower() in url or pattern.lower() in hostname:
                        matched_dbs.add(db["name"])

        if not matched_dbs:
            return None

        msg_text = rule.get("message", "").format(databases=", ".join(sorted(matched_dbs)))
        return CandidateFinding(
            rule_id=rule["id"],
            name=rule["name"],
            capability_id=rule.get("recommends", "zero_copy_connectors"),
            message=msg_text,
            evidence={"databases": list(matched_dbs)}
        )

    def _check_high_frequency_imports(self, rule: Dict, data: Dict) -> Optional[CandidateFinding]:
        """Check for high-frequency import patterns → Stream Connect candidate.

        Uses actual import run count and imported row count, not definitions.
        """
        run_count = data.get("import_run_count", 0)
        row_count = data.get("import_row_count", 0)
        min_imports = rule.get("min_import_sets", 50)

        if run_count < min_imports and row_count < 1000:
            return None

        msg = rule.get("message", "").format(
            import_count=run_count,
            ds_count=row_count
        )
        return CandidateFinding(
            rule_id=rule["id"],
            name=rule["name"],
            capability_id=rule.get("recommends", "stream_connect"),
            message=msg,
            evidence={"import_runs": run_count, "imported_rows": row_count}
        )

    def _check_large_outbound_volume(self, rule: Dict, data: Dict) -> Optional[CandidateFinding]:
        """Check for large outbound HTTP volume → Stream Connect candidate.

        Uses actual outbound HTTP execution count, not REST message definitions.
        """
        outbound_count = data.get("outbound_http_count", 0)
        min_calls = rule.get("min_rest_messages", 30) * 100  # scale threshold for executions

        if outbound_count < min_calls:
            return None

        msg = rule.get("message", "").format(rest_count=outbound_count)
        return CandidateFinding(
            rule_id=rule["id"],
            name=rule["name"],
            capability_id=rule.get("recommends", "stream_connect"),
            message=msg,
            evidence={"outbound_http_executions": outbound_count}
        )

    def _check_high_report_usage(self, rule: Dict, data: Dict) -> Optional[CandidateFinding]:
        """Check for high report usage → Data Catalog / AI Data Explorer candidate."""
        report_count = data.get("reports_count", 0)
        min_reports = rule.get("min_reports", 100)

        if report_count < min_reports:
            return None

        msg = rule.get("message", "").format(report_count=report_count)
        return CandidateFinding(
            rule_id=rule["id"],
            name=rule["name"],
            capability_id=rule.get("recommends", "data_catalog"),
            also_recommends=rule.get("also_recommends"),
            message=msg,
            evidence={"reports": report_count}
        )

    def _check_large_table_estate(self, rule: Dict, data: Dict) -> Optional[CandidateFinding]:
        """Check for large custom table estate → Data Catalog candidate."""
        table_count = data.get("custom_table_count", 0)
        min_tables = rule.get("min_custom_tables", 50)

        if table_count < min_tables:
            return None

        msg = rule.get("message", "").format(table_count=table_count)
        return CandidateFinding(
            rule_id=rule["id"],
            name=rule["name"],
            capability_id=rule.get("recommends", "data_catalog"),
            message=msg,
            evidence={"custom_tables": table_count}
        )

    # ----- tier calculation -----

    def _calculate_tier(self, result: PlutusResult):
        """Determine recommended tier, packs, and annual cost."""
        tiers = self.config.tiers

        # Check if any Pro-only capability is needed
        if result.requires_pro:
            tier_key = "professional"
        else:
            tier_key = "standard"

        # Also upgrade to Pro if candidates suggest Pro-only capabilities
        pro_capabilities = set()
        pro_tier = tiers.get("professional", {})
        std_tier = tiers.get("standard", {})
        pro_only_caps = set(pro_tier.get("capabilities", [])) - set(std_tier.get("capabilities", []))

        for candidate in result.candidates:
            if candidate.capability_id in pro_only_caps:
                tier_key = "professional"
                result.requires_pro = True
                result.pro_reasons.append(
                    f"Candidate: {candidate.name} recommends {candidate.capability_id}"
                )

        tier = tiers.get(tier_key, tiers.get("standard", {}))
        result.recommended_tier = tier.get("label", tier_key)
        result.min_packs = tier.get("min_packs", 1)

        # Calculate packs needed based on credit consumption
        credits_per_pack = result.credits_per_pack
        if result.total_credits > 0:
            packs_for_credits = max(1, -(-int(result.total_credits) // credits_per_pack))  # ceil div
            result.min_packs = max(result.min_packs, packs_for_credits)

        result.annual_cost = result.min_packs * result.price_per_pack

    # ----- serialization -----

    def result_to_dict(self, result: PlutusResult) -> Dict[str, Any]:
        """Convert PlutusResult to JSON-serializable dict."""
        return {
            "total_credits": result.total_credits,
            "recommended_tier": result.recommended_tier,
            "requires_pro": result.requires_pro,
            "pro_reasons": result.pro_reasons,
            "min_packs": result.min_packs,
            "annual_cost": result.annual_cost,
            "credits_per_pack": result.credits_per_pack,
            "price_per_pack": result.price_per_pack,
            "capability_usage": [
                {
                    "capability_id": u.capability_id,
                    "label": u.label,
                    "detected": u.detected,
                    "usage_value": u.usage_value,
                    "meter_unit": u.meter_unit,
                    "credits_per_unit": u.credits_per_unit,
                    "total_credits": u.total_credits,
                    "pro_only": u.pro_only,
                    "measurable": u.measurable,
                    "measurement_rule": u.measurement_rule,
                    "scan_evidence": u.scan_evidence,
                    "user_override": u.user_override,
                    "data_days": u.data_days,
                    "is_estimated": u.is_estimated,
                    "usage_per_year": u.usage_per_year,
                }
                for u in result.capability_usage
            ],
            "candidates": [
                {
                    "rule_id": c.rule_id,
                    "name": c.name,
                    "capability_id": c.capability_id,
                    "also_recommends": c.also_recommends,
                    "message": c.message,
                    "evidence": c.evidence,
                }
                for c in result.candidates
            ],
            "pricing_config": result.pricing_config,
        }
