"""
ServiceNow Domain Ontology
Graph-based knowledge model of ServiceNow's platform architecture.
Encodes table hierarchy, product modules, plugin dependencies,
CMDB class structure, and architectural constraints.
"""

from typing import Any, Dict, List, Set, Optional, Tuple
import logging
import re

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Graph primitives
# ---------------------------------------------------------------------------

class OntologyNode:
    """A node in the ServiceNow ontology graph."""
    __slots__ = ('id', 'label', 'node_type', 'aliases', 'tables', 'plugins', 'layer', 'it4it_streams')
    
    def __init__(self, id: str, label: str, node_type: str, *,
                 aliases: List[str] = None, tables: List[str] = None,
                 plugin: str = None, plugins: List[str] = None,
                 layer: str = None,
                 it4it_streams: List[str] = None):
        self.id = id
        self.label = label
        self.node_type = node_type        # product | module | table | platform | data | ui | orchestration
        self.aliases = aliases or []
        self.tables = tables or []         # actual SN table names
        # Accept single plugin= or list plugins=; store as list
        if plugins:
            self.plugins = plugins
        elif plugin:
            self.plugins = [plugin]
        else:
            self.plugins = []
        self.layer = layer                 # architecture layer: users | ui | application | orchestration | platform | data
        self.it4it_streams = it4it_streams or []  # IT4IT v3 value streams: S2P | R2D | R2F | D2C
    
    @staticmethod
    def _phrase_match(phrase: str, text: str) -> bool:
        """Match a full phrase in text using word boundaries."""
        return bool(re.search(r'\b' + re.escape(phrase) + r'\b', text))

    def matches(self, text: str) -> bool:
        """Check if free-form text refers to this node (full phrase match)."""
        t = text.lower()
        if self._phrase_match(self.label.lower(), t) or self._phrase_match(self.id.lower(), t):
            return True
        return any(self._phrase_match(a.lower(), t) for a in self.aliases)


class OntologyEdge:
    """A typed, directed edge between two ontology nodes."""
    __slots__ = ('source', 'target', 'rel_type', 'constraint')
    
    def __init__(self, source: str, target: str, rel_type: str, constraint: str = None):
        self.source = source               # source node id
        self.target = target               # target node id
        self.rel_type = rel_type           # runs_on | references | creates | consumes | resolves_using | authenticates_via | extends | depends_on | segregated_from
        self.constraint = constraint       # optional constraint note


# ---------------------------------------------------------------------------
# ServiceNow Ontology
# ---------------------------------------------------------------------------

class ServiceNowOntology:
    """
    Graph-based ServiceNow domain ontology.
    Nodes represent platform components; edges represent typed relationships.
    """
    
    def __init__(self):
        self._nodes: Dict[str, OntologyNode] = {}
        self._edges: List[OntologyEdge] = []
        self._build_graph()
        
        # Indexes built after graph construction
        self._children: Dict[str, List[str]] = {}       # parent -> [child] (extends)
        self._outgoing: Dict[str, List[OntologyEdge]] = {}
        self._incoming: Dict[str, List[OntologyEdge]] = {}
        self._build_indexes()
        
        # Backward-compat: flat sets/dicts used by existing code
        self.foundational_components = self._foundational_aliases()
        self.relationship_types = {
            "runs_on": "Component runs on/is hosted by another",
            "consumes": "Component consumes data from another",
            "references": "Component references data in another",
            "creates": "Component creates records in another",
            "resolves_using": "Component uses another to resolve issues",
            "authenticates_via": "Component uses another for authentication",
            "extends": "Table/class extends another (inheritance)",
            "depends_on": "Component depends on another to function",
            "segregated_from": "Components must NOT cross-connect",
        }
        self.semantic_relationships = [
            (e.source, e.target, e.rel_type)
            for e in self._edges
            if e.rel_type not in ("extends", "depends_on")
        ]
        self.dependencies = self._build_dependency_dict()
        self.cannot_be_downstream = {
            "CMDB": ["Knowledge Base", "Service Portal", "Customer Portal"],
            "User Management": ["Service Portal", "Customer Portal", "Case Management"],
            "Platform": ["any"],
        }
        self.product_components = self._build_product_components()
        self.query_patterns = {
            "integration": ["integrate", "integration", "connect", "sync", "api", "webhook", "spoke"],
            "itsm": ["incident", "problem", "change", "itsm", "it service", "service desk"],
            "csm": ["csm", "customer service", "contact center", "case management"],
            "data_flow": ["data", "flow", "sync", "transfer", "master data", "etl"],
            "portal": ["portal", "self-service", "customer portal", "service portal", "employee center"],
            "automation": ["automate", "workflow", "flow", "orchestration", "playbook"],
            "compliance": ["compliance", "fedramp", "spp", "security", "audit", "grc"],
            "hrsd": ["hr", "human resources", "hrsd", "onboarding", "lifecycle", "employee onboarding", "employee lifecycle"],
            "itom": ["discovery", "service mapping", "event management", "cloud", "itom"],
            "secops": ["security incident", "vulnerability", "threat", "secops", "siem"],
        }
    
    # -------------------------------------------------------------------
    # Graph construction
    # -------------------------------------------------------------------
    
    def _add_node(self, node: OntologyNode):
        self._nodes[node.id] = node
    
    def _add_edge(self, source: str, target: str, rel_type: str, constraint: str = None):
        self._edges.append(OntologyEdge(source, target, rel_type, constraint))
    
    def _build_graph(self):
        """Construct the full ServiceNow ontology graph."""
        
        # === PLATFORM / FOUNDATIONAL LAYER ===
        self._add_node(OntologyNode("platform", "ServiceNow Platform", "platform",
            aliases=["Platform", "Now Platform", "ServiceNow"],
            layer="platform", it4it_streams=["S2P", "R2D", "R2F", "D2C"]))
        self._add_node(OntologyNode("cmdb", "CMDB", "data",
            aliases=["Configuration Management Database", "CMDB", "Configuration Management"],
            tables=["cmdb_ci", "cmdb_ci_server", "cmdb_ci_service", "cmdb_ci_app_server",
                    "cmdb_ci_database", "cmdb_ci_hardware", "cmdb_ci_netgear",
                    "cmdb_ci_vm", "cmdb_ci_linux_server", "cmdb_ci_win_server"],
            plugin="com.snc.cmdb", layer="data", it4it_streams=["R2D", "R2F", "D2C"]))
        self._add_node(OntologyNode("user_mgmt", "User Management", "data",
            aliases=["User Management", "Users", "Authentication", "Identity"],
            tables=["sys_user", "sys_user_group", "sys_user_role", "sys_user_has_role",
                    "sys_user_grmember"],
            layer="data", it4it_streams=["R2F", "D2C"]))
        self._add_node(OntologyNode("knowledge_base", "Knowledge Base", "data",
            aliases=["Knowledge Base", "KB", "Knowledge Management", "Knowledge"],
            tables=["kb_knowledge", "kb_knowledge_base", "kb_category", "kb_use"],
            plugin="com.glideapp.knowledge", layer="data", it4it_streams=["R2F", "D2C"]))
        self._add_node(OntologyNode("audit", "Audit Logging", "data",
            aliases=["Audit", "Audit Logs", "System Logs"],
            tables=["sys_audit", "sys_audit_delete", "syslog"],
            layer="data", it4it_streams=["S2P", "D2C"]))
        
        # === TABLE HIERARCHY (task-based) ===
        self._add_node(OntologyNode("task", "Task", "table",
            aliases=["Task", "Work Item"],
            tables=["task"], layer="data"))
        
        # === ITSM MODULES ===
        self._add_node(OntologyNode("itsm", "ITSM", "product",
            aliases=["IT Service Management", "ITSM", "IT Service"],
            plugins=["com.snc.itsm", "com.snc.itsm.workspace"],
            layer="application", it4it_streams=["R2F", "D2C"]))
        self._add_node(OntologyNode("incident", "Incident Management", "module",
            aliases=["Incident", "Incident Management"],
            tables=["incident", "incident_task"],
            plugin="com.snc.incident", layer="application", it4it_streams=["D2C"]))
        self._add_node(OntologyNode("problem", "Problem Management", "module",
            aliases=["Problem", "Problem Management"],
            tables=["problem", "problem_task"],
            plugin="com.snc.problem", layer="application", it4it_streams=["D2C"]))
        self._add_node(OntologyNode("change", "Change Management", "module",
            aliases=["Change", "Change Management", "Change Request"],
            tables=["change_request", "change_task"],
            plugins=["com.snc.change_management", "com.snc.change_management.standard_change_catalog"],
            layer="application", it4it_streams=["R2D"]))
        self._add_node(OntologyNode("service_catalog", "Service Catalog", "module",
            aliases=["Service Catalog", "Catalog", "Request Management"],
            tables=["sc_catalog", "sc_cat_item", "sc_request", "sc_req_item", "sc_task"],
            plugin="com.glideapp.servicecatalog", layer="application", it4it_streams=["R2F"]))
        self._add_node(OntologyNode("asset", "Asset Management", "module",
            aliases=["Asset", "Asset Management", "IT Asset Management", "ITAM", "HAM", "SAM"],
            tables=["alm_asset", "alm_hardware", "alm_license"],
            plugins=["com.snc.asset_management", "com.snc.ham", "com.snc.sam"],
            layer="application", it4it_streams=["R2D", "D2C"]))
        
        # === CSM MODULES ===
        self._add_node(OntologyNode("csm", "CSM", "product",
            aliases=["Customer Service Management", "CSM", "Customer Service"],
            plugin="com.sn_customerservice", layer="application", it4it_streams=["R2F"]))
        self._add_node(OntologyNode("case_mgmt", "Case Management", "module",
            aliases=["Case Management", "Case", "CSM Case"],
            tables=["sn_customerservice_case", "sn_customerservice_task"],
            plugin="com.sn_customerservice", layer="application", it4it_streams=["R2F"]))
        self._add_node(OntologyNode("customer_accounts", "Customer Accounts", "module",
            aliases=["Customer Accounts", "CSM Accounts"],
            tables=["customer_account", "customer_contact", "csm_consumer"],
            plugin="com.sn_customerservice", layer="application", it4it_streams=["R2F"]))
        
        # === HRSD MODULES ===
        self._add_node(OntologyNode("hrsd", "HR Service Delivery", "product",
            aliases=["HRSD", "HR Service Delivery", "HR", "Human Resources"],
            plugin="com.sn_hr_core", layer="application", it4it_streams=["R2F"]))
        self._add_node(OntologyNode("hr_case", "HR Case Management", "module",
            aliases=["HR Case", "HR Case Management"],
            tables=["sn_hr_core_case", "sn_hr_core_task"],
            plugin="com.sn_hr_core", layer="application", it4it_streams=["R2F"]))
        
        # === ITOM MODULES ===
        self._add_node(OntologyNode("itom", "ITOM", "product",
            aliases=["IT Operations Management", "ITOM"],
            layer="application", it4it_streams=["D2C"]))
        self._add_node(OntologyNode("discovery", "Discovery", "module",
            aliases=["Discovery", "Network Discovery"],
            tables=["discovery_status"],
            plugins=["com.snc.discovery", "com.snc.itom.discovery"],
            layer="application", it4it_streams=["D2C"]))
        self._add_node(OntologyNode("service_mapping", "Service Mapping", "module",
            aliases=["Service Mapping"],
            tables=["svc_ci_assoc"],
            plugins=["com.snc.service_mapping", "com.snc.service-mapping"],
            layer="application", it4it_streams=["D2C"]))
        self._add_node(OntologyNode("event_mgmt", "Event Management", "module",
            aliases=["Event Management", "Event"],
            tables=["em_event", "em_alert"],
            plugin="com.glide.itom.em", layer="application", it4it_streams=["D2C"]))
        
        # === SECOPS ===
        self._add_node(OntologyNode("secops", "Security Operations", "product",
            aliases=["SecOps", "Security Operations"],
            layer="application", it4it_streams=["D2C"]))
        self._add_node(OntologyNode("sec_incident", "Security Incident Response", "module",
            aliases=["Security Incident", "SIR"],
            tables=["sn_si_incident", "sn_si_task"],
            plugin="com.snc.sec_inc_response", layer="application", it4it_streams=["D2C"]))
        self._add_node(OntologyNode("vuln_response", "Vulnerability Response", "module",
            aliases=["Vulnerability Response", "VR"],
            tables=["sn_vul_vulnerability", "sn_vul_entry"],
            plugin="com.snc.vul_response", layer="application", it4it_streams=["D2C"]))
        
        # === GRC ===
        self._add_node(OntologyNode("grc", "GRC", "product",
            aliases=["Governance Risk Compliance", "GRC", "Risk Management",
                     "Integrated Risk Management", "IRM"],
            plugins=["com.sn_grc", "com.sn_audit"],
            layer="application", it4it_streams=["S2P"]))
        self._add_node(OntologyNode("policy_compliance", "Policy and Compliance", "module",
            aliases=["Policy", "Compliance"],
            tables=["sn_compliance_policy", "sn_compliance_policy_statement"],
            plugin="com.sn_compliance", layer="application", it4it_streams=["S2P"]))
        self._add_node(OntologyNode("risk_mgmt", "Risk Management", "module",
            aliases=["Risk"],
            tables=["sn_risk_risk", "sn_risk_definition"],
            plugin="com.sn_risk", layer="application", it4it_streams=["S2P"]))
        
        # === SPM / ITBM ===
        self._add_node(OntologyNode("spm", "Strategic Portfolio Management", "product",
            aliases=["SPM", "ITBM", "IT Business Management", "Portfolio Management"],
            plugins=["com.snc.it_business_management", "com.snc.financial_planning_pmo",
                     "com.snc.alignment", "com.snc.sdlc"],
            tables=["pm_project", "pm_portfolio", "planned_task"],
            layer="application", it4it_streams=["S2P"]))
        self._add_node(OntologyNode("ppm", "Project Portfolio Management", "module",
            aliases=["PPM", "Project Management"],
            tables=["pm_project", "pm_portfolio", "pm_project_task", "pm_program"],
            plugins=["com.snc.project_management", "com.snc.it_business_management"],
            layer="application", it4it_streams=["S2P"]))
        
        # === ORCHESTRATION LAYER ===
        self._add_node(OntologyNode("integration_hub", "Integration Hub", "orchestration",
            aliases=["Integration Hub", "IntegrationHub", "Spokes"],
            tables=["sys_hub_flow", "sys_hub_action_type_definition"],
            plugin="com.glide.hub.integration_hub", layer="orchestration", it4it_streams=["R2D", "R2F", "D2C"]))
        self._add_node(OntologyNode("flow_designer", "Flow Designer", "orchestration",
            aliases=["Flow Designer", "Flows", "Subflows"],
            tables=["sys_hub_flow"],
            plugin="com.glide.hub.flow_designer", layer="orchestration", it4it_streams=["R2F", "D2C"]))
        self._add_node(OntologyNode("workflow", "Workflow Engine", "orchestration",
            aliases=["Workflow", "Workflow Engine", "Legacy Workflow"],
            tables=["wf_workflow", "wf_workflow_version", "wf_activity"],
            layer="orchestration", it4it_streams=["R2F", "D2C"]))
        self._add_node(OntologyNode("virtual_agent", "Virtual Agent", "orchestration",
            aliases=["Virtual Agent", "VA", "Chatbot"],
            tables=["cb_topic", "cb_topic_goal"],
            plugin="com.glide.cs.chatbot", layer="orchestration", it4it_streams=["R2F"]))
        self._add_node(OntologyNode("notifications", "Notifications", "orchestration",
            aliases=["Notifications", "Email", "Push Notifications"],
            tables=["sysevent_email_action", "sys_email"],
            layer="orchestration", it4it_streams=["R2F", "D2C"]))
        
        # === UI LAYER ===
        self._add_node(OntologyNode("service_portal", "Service Portal", "ui",
            aliases=["Service Portal", "Employee Portal", "Internal Portal", "SP"],
            tables=["sp_portal", "sp_page", "sp_widget"],
            plugin="com.glide.service-portal", layer="ui", it4it_streams=["R2F"]))
        self._add_node(OntologyNode("customer_portal", "Customer Portal", "ui",
            aliases=["Customer Portal", "Customer Service Portal", "Public Portal", "CSP"],
            tables=["sp_portal"],
            plugin="com.sn_customerservice", layer="ui", it4it_streams=["R2F"]))
        self._add_node(OntologyNode("employee_center", "Employee Center", "ui",
            aliases=["Employee Center", "EC"],
            tables=["sn_ec_content", "sn_ec_taxonomy_topic"],
            plugin="com.sn_employee_center", layer="ui", it4it_streams=["R2F"]))
        self._add_node(OntologyNode("now_mobile", "Now Mobile", "ui",
            aliases=["Now Mobile", "Mobile", "Mobile App"],
            layer="ui", it4it_streams=["R2F", "D2C"]))
        self._add_node(OntologyNode("workspace", "Agent Workspace", "ui",
            aliases=["Agent Workspace", "Workspace", "CSM Workspace", "ITSM Workspace"],
            layer="ui", it4it_streams=["R2F", "D2C"]))
        
        # === EXTERNAL ===
        self._add_node(OntologyNode("external", "External Systems", "external",
            aliases=["External Systems", "Third Party", "External"],
            layer="external"))
        
        # ---------------------------------------------------------------
        # EDGES: Table hierarchy (extends)
        # ---------------------------------------------------------------
        for child, parent in [
            ("incident", "task"), ("problem", "task"), ("change", "task"),
            ("case_mgmt", "task"), ("hr_case", "task"), ("sec_incident", "task"),
            ("service_catalog", "task"),  # sc_request / sc_task extend task
        ]:
            self._add_edge(child, parent, "extends")
        
        # ---------------------------------------------------------------
        # EDGES: Product -> module composition (depends_on)
        # ---------------------------------------------------------------
        for module in ["incident", "problem", "change", "service_catalog"]:
            self._add_edge("itsm", module, "depends_on")
        for module in ["case_mgmt", "customer_accounts"]:
            self._add_edge("csm", module, "depends_on")
        self._add_edge("hrsd", "hr_case", "depends_on")
        for module in ["discovery", "service_mapping", "event_mgmt"]:
            self._add_edge("itom", module, "depends_on")
        for module in ["sec_incident", "vuln_response"]:
            self._add_edge("secops", module, "depends_on")
        for module in ["policy_compliance", "risk_mgmt"]:
            self._add_edge("grc", module, "depends_on")
        self._add_edge("spm", "ppm", "depends_on")
        
        # ---------------------------------------------------------------
        # EDGES: Architectural relationships
        # ---------------------------------------------------------------
        # runs_on (applications -> platform)
        for app in ["itsm", "csm", "hrsd", "itom", "secops", "grc", "spm",
                     "service_portal", "customer_portal", "employee_center"]:
            self._add_edge(app, "platform", "runs_on")
        
        # references (applications -> CMDB)
        for app in ["incident", "problem", "change", "case_mgmt", "asset",
                     "discovery", "service_mapping", "event_mgmt", "sec_incident"]:
            self._add_edge(app, "cmdb", "references")
        
        # resolves_using (applications -> KB)
        for app in ["incident", "problem", "case_mgmt", "hr_case"]:
            self._add_edge(app, "knowledge_base", "resolves_using")
        
        # consumes (portals -> KB)
        for portal in ["service_portal", "customer_portal", "employee_center"]:
            self._add_edge(portal, "knowledge_base", "consumes")
        
        # creates (portals -> applications)
        self._add_edge("customer_portal", "csm", "creates", "Portal creates cases in CSM")
        self._add_edge("service_portal", "itsm", "creates", "Portal creates tickets in ITSM")
        self._add_edge("service_portal", "service_catalog", "creates", "Portal creates catalog requests")
        self._add_edge("employee_center", "hrsd", "creates", "Employee Center creates HR cases")
        
        # authenticates_via
        for portal in ["service_portal", "customer_portal", "employee_center", "now_mobile"]:
            self._add_edge(portal, "user_mgmt", "authenticates_via")
        
        # orchestration relationships
        self._add_edge("flow_designer", "platform", "runs_on")
        self._add_edge("integration_hub", "platform", "runs_on")
        self._add_edge("flow_designer", "integration_hub", "depends_on")
        self._add_edge("integration_hub", "external", "creates", "Connects to external systems")
        self._add_edge("virtual_agent", "knowledge_base", "consumes")
        
        # CMDB population
        self._add_edge("discovery", "cmdb", "creates", "Discovery populates CMDB")
        self._add_edge("service_mapping", "cmdb", "creates", "Service Mapping maps services in CMDB")
        
        # Segregation rules (anti-patterns)
        self._add_edge("customer_portal", "itsm", "segregated_from", "Public portal must not connect to internal ITSM")
        self._add_edge("service_portal", "csm", "segregated_from", "Internal portal must not connect to external CSM")
    
    def _build_indexes(self):
        """Build lookup indexes from the edge list."""
        for edge in self._edges:
            self._outgoing.setdefault(edge.source, []).append(edge)
            self._incoming.setdefault(edge.target, []).append(edge)
            if edge.rel_type == "extends":
                self._children.setdefault(edge.target, []).append(edge.source)
    
    def _foundational_aliases(self) -> Set[str]:
        """Build the flat set of foundational component names for backward compat."""
        result = set()
        for nid in ["cmdb", "user_mgmt", "platform", "knowledge_base"]:
            node = self._nodes.get(nid)
            if node:
                result.add(node.label)
                result.update(node.aliases)
                result.update(node.tables)
        return result
    
    def _build_dependency_dict(self) -> Dict[str, List[str]]:
        """Build backward-compat dependency dict from edges."""
        deps = {}
        for edge in self._edges:
            if edge.rel_type in ("depends_on", "references", "resolves_using", "authenticates_via"):
                src = self._nodes[edge.source].label if edge.source in self._nodes else edge.source
                tgt = self._nodes[edge.target].label if edge.target in self._nodes else edge.target
                deps.setdefault(src, []).append(tgt)
        return deps
    
    def _build_product_components(self) -> Dict[str, List[str]]:
        """Build backward-compat product_components dict from edges."""
        products = {}
        for edge in self._edges:
            if edge.rel_type == "depends_on" and edge.source in self._nodes:
                src_node = self._nodes[edge.source]
                if src_node.node_type == "product":
                    tgt_node = self._nodes.get(edge.target)
                    tgt_label = tgt_node.label if tgt_node else edge.target
                    products.setdefault(src_node.label, []).append(tgt_label)
        return products
    
    # -------------------------------------------------------------------
    # Graph query methods
    # -------------------------------------------------------------------
    
    def find_node(self, text: str) -> Optional[OntologyNode]:
        """Find an ontology node by free-text match against id, label, or aliases."""
        text_lower = text.lower()
        # Exact id match first
        if text_lower in self._nodes:
            return self._nodes[text_lower]
        # Label/alias match
        for node in self._nodes.values():
            if node.matches(text):
                return node
        return None
    
    def get_tables_for(self, node_id: str) -> List[str]:
        """Get all actual SN table names associated with a node."""
        node = self._nodes.get(node_id)
        return node.tables if node else []
    
    def what_depends_on(self, node_id: str) -> List[str]:
        """Return IDs of all nodes that depend on / reference / consume the given node."""
        return [e.source for e in self._incoming.get(node_id, [])
                if e.rel_type in ("depends_on", "references", "resolves_using", "consumes")]
    
    def what_does_it_need(self, node_id: str) -> List[str]:
        """Return IDs of all nodes that a given node depends on."""
        return [e.target for e in self._outgoing.get(node_id, [])
                if e.rel_type in ("depends_on", "references", "resolves_using", "authenticates_via")]
    
    def get_layer(self, node_id: str) -> Optional[str]:
        """Get the architecture layer for a node."""
        node = self._nodes.get(node_id)
        return node.layer if node else None
    
    def get_plugin(self, node_id: str) -> Optional[str]:
        """Get the primary ServiceNow plugin id for a node."""
        node = self._nodes.get(node_id)
        return node.plugins[0] if (node and node.plugins) else None
    
    def get_children(self, node_id: str) -> List[str]:
        """Get nodes that extend this node (table inheritance)."""
        return self._children.get(node_id, [])
    
    def get_segregation_rules(self) -> List[Tuple[str, str, str]]:
        """Get all segregation (anti-pattern) rules."""
        return [
            (e.source, e.target, e.constraint or "")
            for e in self._edges if e.rel_type == "segregated_from"
        ]

    def get_all_referenced_tables(self) -> Set[str]:
        """Return every table name referenced by any ontology node."""
        tables: Set[str] = set()
        for node in self._nodes.values():
            tables.update(node.tables)
        return tables
    
    # -------------------------------------------------------------------
    # Instance Assessment (Minos) methods
    # -------------------------------------------------------------------

    def map_instance_to_nodes(self, installed_plugins: Dict[str, Dict],
                               active_tables: Dict[str, int]) -> Dict[str, Any]:
        """
        Map scanner results to active ontology nodes.
        
        Args:
            installed_plugins: {plugin_id: {name, version, active}} from scanner
            active_tables: {table_name: record_count} from scanner
        
        Returns:
            Dict with active_node_ids, inactive_node_ids, coverage details
        """
        plugin_ids = set(installed_plugins.keys())
        active_node_ids = set()
        inactive_node_ids = set()
        node_evidence = {}  # node_id -> why it's active

        for nid, node in self._nodes.items():
            # Skip abstract/foundational — they're always included
            if nid in ("platform", "task"):
                active_node_ids.add(nid)
                node_evidence[nid] = "foundational"
                continue

            matched = False
            evidence = []

            # Check by plugin (any of the node's plugin IDs)
            for pid in node.plugins:
                if pid in plugin_ids:
                    matched = True
                    evidence.append(f"plugin: {pid}")
                    break

            # Check by table activity (records > 0)
            if node.tables:
                for tbl in node.tables:
                    count = active_tables.get(tbl, -1)
                    if count > 0:
                        matched = True
                        evidence.append(f"table: {tbl} ({count:,} records)")

            if matched:
                active_node_ids.add(nid)
                node_evidence[nid] = "; ".join(evidence)
            else:
                inactive_node_ids.add(nid)

        # Promote product nodes if any of their modules are active
        for edge in self._edges:
            if edge.rel_type == "depends_on":
                if edge.target in active_node_ids and edge.source in inactive_node_ids:
                    src_node = self._nodes.get(edge.source)
                    if src_node and src_node.node_type == "product":
                        active_node_ids.add(edge.source)
                        inactive_node_ids.discard(edge.source)
                        node_evidence[edge.source] = f"has active module: {edge.target}"

        # Foundational data nodes are active if any app is active
        app_active = any(
            self._nodes[nid].node_type in ("product", "module") and self._nodes[nid].layer == "application"
            for nid in active_node_ids if nid in self._nodes
        )
        if app_active:
            for fid in ("cmdb", "user_mgmt", "knowledge_base", "audit"):
                if fid in self._nodes:
                    active_node_ids.add(fid)
                    inactive_node_ids.discard(fid)
                    if fid not in node_evidence:
                        node_evidence[fid] = "foundational (apps active)"

        # IT4IT coverage
        active_streams = set()
        for nid in active_node_ids:
            node = self._nodes.get(nid)
            if node:
                active_streams.update(node.it4it_streams)

        return {
            "active_node_ids": active_node_ids,
            "inactive_node_ids": inactive_node_ids,
            "node_evidence": node_evidence,
            "it4it_coverage": {
                "S2P": "S2P" in active_streams,
                "R2D": "R2D" in active_streams,
                "R2F": "R2F" in active_streams,
                "D2C": "D2C" in active_streams,
            },
            "active_streams": sorted(active_streams),
        }

    def generate_architecture_mermaid(self, active_ids: set,
                                       recommended_ids: set = None,
                                       recommendations: Dict[str, str] = None) -> str:
        """
        Generate a Mermaid diagram showing active and optionally recommended nodes.
        
        Args:
            active_ids: set of node IDs currently active in the instance
            recommended_ids: optional set of node IDs to add as recommendations
            recommendations: optional {node_id: reason} for annotations
        
        Returns:
            Mermaid diagram string
        """
        recommended_ids = recommended_ids or set()
        recommendations = recommendations or {}
        all_ids = active_ids | recommended_ids

        # Filter to nodes that exist
        all_ids = {nid for nid in all_ids if nid in self._nodes}

        if not all_ids:
            return "graph TD\n    EMPTY[No components detected]"

        # Assign short IDs
        id_map = {}
        counter = 0
        for nid in sorted(all_ids):
            id_map[nid] = chr(65 + counter) if counter < 26 else f"N{counter}"
            counter += 1

        # Group by layer
        layers = {}
        for nid in sorted(all_ids):
            node = self._nodes[nid]
            layer = node.layer or "other"
            layers.setdefault(layer, []).append(nid)

        layer_order = ["ui", "application", "orchestration", "platform", "data", "external", "other"]
        layer_labels = {
            "ui": "Portals & UI",
            "application": "Applications",
            "orchestration": "Orchestration",
            "platform": "Platform",
            "data": "Foundation & Data",
            "external": "External",
            "other": "Other",
        }

        lines = ["graph TD"]

        # Style classes
        lines.append("    classDef active fill:#dbeafe,stroke:#3b82f6,stroke-width:2px,color:#1e40af")
        lines.append("    classDef recommended fill:#fef3c7,stroke:#f59e0b,stroke-width:2px,stroke-dasharray:5 5,color:#92400e")
        lines.append("    classDef foundational fill:#d1fae5,stroke:#10b981,stroke-width:2px,color:#065f46")

        foundational_ids = {"platform", "cmdb", "user_mgmt", "knowledge_base", "audit", "task"}

        for layer in layer_order:
            nids = layers.get(layer, [])
            if not nids:
                continue
            label = layer_labels.get(layer, layer.title())
            lines.append(f"    subgraph {label}")
            for nid in nids:
                short = id_map[nid]
                node_label = self._nodes[nid].label
                if nid in recommended_ids and nid not in active_ids:
                    node_label += " ⊕"
                lines.append(f"        {short}[{node_label}]")
            lines.append("    end")

        # Edges — only between nodes in our set
        rel_label_map = {
            "runs_on": "runs on", "creates": "creates", "references": "refs",
            "resolves_using": "resolves via", "consumes": "consumes",
            "authenticates_via": "auth", "depends_on": "depends on",
        }
        edge_count = 0
        for e in self._edges:
            if e.source in all_ids and e.target in all_ids and e.rel_type != "segregated_from" and e.rel_type != "extends":
                src = id_map.get(e.source)
                tgt = id_map.get(e.target)
                if src and tgt and edge_count < 20:
                    lbl = rel_label_map.get(e.rel_type, e.rel_type.replace("_", " "))
                    # Dashed edge if either end is recommended
                    if (e.source in recommended_ids and e.source not in active_ids) or \
                       (e.target in recommended_ids and e.target not in active_ids):
                        lines.append(f"    {src} -.->|{lbl}| {tgt}")
                    else:
                        lines.append(f"    {src} -->|{lbl}| {tgt}")
                    edge_count += 1

        # Apply style classes
        for nid in sorted(all_ids):
            short = id_map[nid]
            if nid in recommended_ids and nid not in active_ids:
                lines.append(f"    class {short} recommended")
            elif nid in foundational_ids:
                lines.append(f"    class {short} foundational")
            else:
                lines.append(f"    class {short} active")

        return "\n".join(lines)

    def get_relevant_subgraph(self, query: str, query_types: List[str]) -> Dict:
        """
        Extract the ontology subgraph relevant to a specific query.
        Returns relevant nodes, edges, and a query-specific example diagram.
        """
        query_lower = query.lower()
        relevant_ids = set()

        # 1. Find directly mentioned nodes
        for node_id, node in self._nodes.items():
            if node.matches(query_lower):
                relevant_ids.add(node_id)

        # 2. Map query_types to seed nodes
        type_to_seeds = {
            "itsm": ["itsm", "incident", "problem", "change"],
            "csm": ["csm", "case_mgmt", "customer_portal"],
            "hrsd": ["hrsd"],
            "itom": ["itom", "discovery", "service_mapping", "event_mgmt"],
            "secops": ["secops"],
            "compliance": ["grc", "audit"],
            "portal": ["service_portal", "customer_portal", "employee_center"],
            "automation": ["integration_hub", "flow_designer"],
            "integration": ["integration_hub", "mid_server", "external_systems"],
            "data_flow": ["cmdb", "knowledge_base"],
        }
        for qt in query_types:
            for seed in type_to_seeds.get(qt, []):
                if seed in self._nodes:
                    relevant_ids.add(seed)

        # 3. Expand outgoing edges only from non-foundational seeds.
        #    Outgoing = what the seed depends on / runs on / references.
        #    Skip incoming = prevents "everything that references CMDB" from
        #    pulling in the entire graph. Skip foundational seeds because
        #    they connect to almost everything.
        foundational_ids = {"platform", "cmdb", "user_mgmt", "knowledge_base", "audit", "task"}
        structural_rels = {"depends_on", "runs_on", "extends"}
        expansion_seeds = relevant_ids - foundational_ids
        expanded = set(relevant_ids)
        for nid in expansion_seeds:
            for e in self._outgoing.get(nid, []):
                if e.rel_type in structural_rels:
                    expanded.add(e.target)
        relevant_ids = expanded

        # 4. Always include foundational nodes
        for fid in ["platform", "cmdb", "user_mgmt", "knowledge_base"]:
            if fid in self._nodes:
                relevant_ids.add(fid)

        # 5. Collect relevant edges
        relevant_edges = [
            e for e in self._edges
            if e.source in relevant_ids and e.target in relevant_ids
            and e.rel_type != "segregated_from"
        ]

        # 6. Build nodes list
        relevant_nodes = [
            {"id": nid, "label": self._nodes[nid].label,
             "type": self._nodes[nid].node_type, "layer": self._nodes[nid].layer}
            for nid in sorted(relevant_ids) if nid in self._nodes
        ]

        # 7. Build edges list
        edges_list = [
            {"source": self._nodes[e.source].label,
             "target": self._nodes[e.target].label,
             "type": e.rel_type}
            for e in relevant_edges
            if e.source in self._nodes and e.target in self._nodes
        ]

        # 8. Build a reference example diagram from this subgraph
        example_diagram = self._build_example_diagram(relevant_ids, relevant_edges)

        # 9. Get segregation rules relevant to these nodes
        segregation = [
            f"{self._nodes[e.source].label} must NOT connect to {self._nodes[e.target].label}"
            for e in self._edges
            if e.rel_type == "segregated_from"
            and e.source in relevant_ids and e.target in relevant_ids
            and e.source in self._nodes and e.target in self._nodes
        ]

        return {
            "nodes": relevant_nodes,
            "edges": edges_list,
            "example_diagram": example_diagram,
            "segregation_rules": segregation,
            "total_nodes": len(relevant_nodes),
            "total_edges": len(edges_list),
        }

    def _build_example_diagram(self, node_ids: set, edges: list) -> str:
        """Build a Mermaid reference diagram from relevant ontology nodes/edges."""
        if not edges:
            return ""

        # Assign short IDs
        id_map = {}
        counter = 0
        for nid in sorted(node_ids):
            if nid in self._nodes:
                id_map[nid] = chr(65 + counter) if counter < 26 else f"N{counter}"
                counter += 1

        # Group by layer
        layers = {}
        for nid in sorted(node_ids):
            if nid not in self._nodes:
                continue
            node = self._nodes[nid]
            layer = node.layer or "other"
            layers.setdefault(layer, []).append(nid)

        layer_order = ["ui", "product", "orchestration", "platform", "data", "other"]
        layer_labels = {
            "ui": "Portals", "product": "Applications", "orchestration": "Orchestration",
            "platform": "Platform", "data": "Foundation", "other": "Other"
        }

        lines = ["graph TD"]
        for layer in layer_order:
            nids = layers.get(layer, [])
            if not nids:
                continue
            label = layer_labels.get(layer, layer.title())
            lines.append(f"    subgraph {label}")
            for nid in nids:
                short = id_map.get(nid, nid)
                lines.append(f"        {short}[{self._nodes[nid].label}]")
            lines.append("    end")

        # Add edges (limit to 15)
        rel_label_map = {
            "runs_on": "runs on", "creates": "creates", "references": "references",
            "resolves_using": "resolves using", "consumes": "consumes",
            "authenticates_via": "authenticates via", "depends_on": "depends on",
            "populates": "populates",
        }
        edge_lines = []
        for e in edges[:15]:
            src = id_map.get(e.source)
            tgt = id_map.get(e.target)
            if src and tgt:
                lbl = rel_label_map.get(e.rel_type, e.rel_type.replace("_", " "))
                edge_lines.append(f"    {src} -->|{lbl}| {tgt}")
        lines.extend(edge_lines)

        return "\n".join(lines)

    def get_component_dependencies(self, component: str) -> List[str]:
        """Get required dependencies for a component."""
        return self.dependencies.get(component, [])
    
    def get_relationship_type(self, source: str, target: str) -> str:
        """
        Get the semantic relationship type between two components.
        Returns the relationship type or 'connects_to' as default.
        """
        # Check semantic relationships
        for src, tgt, rel_type in self.semantic_relationships:
            if src.lower() in source.lower() and tgt.lower() in target.lower():
                return rel_type
            # Check reverse direction for bidirectional relationships
            if tgt.lower() in source.lower() and src.lower() in target.lower():
                if rel_type == "segregated_from":
                    return rel_type
        
        # Check if target is foundational (should be referenced, not consumed)
        if self.is_foundational(target):
            return "references"
        
        return "connects_to"
    
    def should_be_bidirectional(self, source: str, target: str) -> bool:
        """
        Check if a relationship should be bidirectional.
        Most ServiceNow relationships are unidirectional.
        """
        # Bidirectional relationships are rare - only for peer-to-peer integrations
        bidirectional_patterns = [
            ("Integration Hub", "External System"),
            ("API", "External System")
        ]
        
        for pattern1, pattern2 in bidirectional_patterns:
            if (pattern1.lower() in source.lower() and pattern2.lower() in target.lower()) or \
               (pattern2.lower() in source.lower() and pattern1.lower() in target.lower()):
                return True
        
        return False
    
    def is_foundational(self, component: str) -> bool:
        """Check if a component is foundational (should not depend on others)."""
        return any(found in component for found in self.foundational_components)
    
    def validate_relationship(self, upstream: str, downstream: str) -> Dict:
        """
        Validate if a component relationship makes sense.
        Returns dict with 'valid' boolean and 'reason' string.
        """
        # Check if downstream component cannot be downstream of upstream
        for component, forbidden_upstreams in self.cannot_be_downstream.items():
            if component in downstream:
                if "any" in forbidden_upstreams:
                    return {
                        "valid": False,
                        "reason": f"{downstream} is foundational and should not depend on {upstream}"
                    }
                if any(forbidden in upstream for forbidden in forbidden_upstreams):
                    return {
                        "valid": False,
                        "reason": f"{downstream} should not depend on {upstream}. Reverse this relationship."
                    }
        
        # Check if upstream should actually be downstream
        if upstream in self.dependencies:
            required_deps = self.dependencies[upstream]
            if any(dep in downstream for dep in required_deps):
                return {
                    "valid": False,
                    "reason": f"{upstream} depends on {downstream}, not the other way around"
                }
        
        return {"valid": True, "reason": ""}
    
    def detect_query_type(self, query: str) -> List[str]:
        """Detect the type of architecture query for specialized handling."""
        query_lower = query.lower()
        detected_types = []
        
        for query_type, patterns in self.query_patterns.items():
            for pattern in patterns:
                if len(pattern) <= 4:
                    if re.search(r'\b' + re.escape(pattern) + r'\b', query_lower):
                        detected_types.append(query_type)
                        break
                else:
                    if pattern in query_lower:
                        detected_types.append(query_type)
                        break
        
        return detected_types if detected_types else ["general"]
    
    def get_specialized_constraints(self, query_types: List[str]) -> str:
        """Get specialized architectural constraints based on query type."""
        constraints = []
        
        if "integration" in query_types:
            constraints.append(
                "Integration Architecture Constraints:\n"
                "- Use Integration Hub or REST APIs for external connections\n"
                "- CMDB should be central for service mapping\n"
                "- Consider data synchronization patterns (real-time vs batch)\n"
                "- Include authentication and error handling components"
            )
        
        if "itsm" in query_types:
            constraints.append(
                "ITSM Architecture Constraints:\n"
                "- CMDB is foundational for all ITSM processes — CI relationships drive impact analysis\n"
                "- Incident → Problem → Change is the standard escalation flow\n"
                "- Knowledge Base should feed into all ITSM modules for resolution guidance\n"
                "- Service Catalog requires workflow engine (Flow Designer or legacy Workflow)\n"
                "- Key tables: incident, problem, change_request, sc_request, sc_req_item, kb_knowledge\n"
                "- Key plugins: com.snc.incident, com.snc.problem, com.snc.change_management\n"
                "- Service Portal (sp_portal) is the internal self-service entry point for IT requests\n"
                "- If ITSM data volumes are high (millions of records), consider archiving strategy and performance indexing"
            )
        
        if "csm" in query_types:
            constraints.append(
                "CSM Architecture Constraints:\n"
                "- Customer Portal (sn_csm_portal) is the public-facing entry point — separate from Service Portal\n"
                "- Case Management (sn_customerservice_case) is core, NOT Incident Management\n"
                "- Customer Accounts (customer_account) and Contacts (customer_contact) are separate from internal Users (sys_user)\n"
                "- Knowledge Base should be accessible to customers via portal with ACL-controlled visibility\n"
                "- CSM uses Account-Contact-Case model, not ITSM's User-Incident model\n"
                "- Key plugins: com.sn_customerservice, com.sn_csm_portal\n"
                "- If CSM coexists with ITSM: cases can escalate to internal incidents via escalation rules\n"
                "- Agent Workspace (sn_csm_workspace) provides unified agent experience for case management"
            )
        
        if "compliance" in query_types:
            constraints.append(
                "Compliance / FedRAMP / SPP Architecture Constraints:\n"
                "- All components processing government data MUST reside in a FedRAMP-authorized instance (IL2/IL4/IL5 as applicable)\n"
                "- ServiceNow Government Community Cloud (GCC) or SPP instances are required for FedRAMP compliance\n"
                "- CRITICAL DECISION: Single instance with domain separation vs. dual instance — analyze both options:\n"
                "  * Single instance: easier integration, shared CMDB, lower cost, but requires strict ACLs and domain separation\n"
                "  * Dual instance: stronger isolation for public vs internal, but requires integration middleware and data sync\n"
                "- Domain Separation: if single instance, enable glide.sys.domain for data partitioning between public-facing and internal data\n"
                "- ACL requirements: row-level and field-level ACLs to enforce least-privilege across CSM (public) and ITSM (internal) data\n"
                "- Audit and logging: sys_audit, sys_journal_field, and transaction logs must be enabled for all sensitive operations\n"
                "- Encryption: column-level encryption for PII/PHI fields, TLS 1.2+ for all integrations\n"
                "- MID Server placement: MID Servers connecting to on-premise systems must reside in the agency's security boundary\n"
                "- User segregation: external customer accounts (sys_user with appropriate roles) must be isolated from internal agent accounts\n"
                "- Portal segregation: Customer Portal (public-facing) must be separate from Service Portal (internal) with independent authentication flows"
            )
        
        if "data_flow" in query_types:
            constraints.append(
                "Data Flow Architecture Constraints:\n"
                "- CMDB is the single source of truth\n"
                "- Define clear data ownership and master systems\n"
                "- Consider data synchronization frequency and direction\n"
                "- Include data validation and transformation layers"
            )
        
        return "\n\n".join(constraints) if constraints else ""
    
    def validate_architecture(self, components: List[Dict]) -> Dict:
        """
        Validate an entire architecture for ServiceNow best practices.
        Returns validation results with errors and warnings.
        """
        errors = []
        warnings = []
        
        # Check for foundational components
        has_cmdb = any("cmdb" in comp.get("name", "").lower() or 
                      "configuration" in comp.get("name", "").lower() 
                      for comp in components)
        
        has_user_mgmt = any("user" in comp.get("name", "").lower() or
                           "authentication" in comp.get("name", "").lower()
                           for comp in components)
        
        if not has_cmdb:
            warnings.append("CMDB not found. Most ServiceNow architectures require CMDB as foundation.")
        
        if not has_user_mgmt:
            warnings.append("User Management not found. Required for authentication and authorization.")
        
        # Validate component relationships
        for component in components:
            name = component.get("name", "")
            connections = component.get("connections", [])
            
            for connected_comp in connections:
                # Find the connected component details
                connected_details = next(
                    (c for c in components if c.get("name") == connected_comp),
                    None
                )
                
                if connected_details:
                    validation = self.validate_relationship(name, connected_comp)
                    if not validation["valid"]:
                        errors.append(f"{name} → {connected_comp}: {validation['reason']}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "has_foundational_components": has_cmdb and has_user_mgmt
        }
    
    def get_instance_aware_recommendations(self, 
                                          installed_apps: List[str],
                                          query_type: List[str]) -> List[str]:
        """
        Generate recommendations based on what's already installed in the instance.
        """
        recommendations = []
        
        # Check for common product combinations
        has_itsm = any("itsm" in app.lower() or "incident" in app.lower() 
                      for app in installed_apps)
        has_csm = any("csm" in app.lower() or "customer service" in app.lower() 
                     for app in installed_apps)
        has_itom = any("itom" in app.lower() or "discovery" in app.lower() 
                      for app in installed_apps)
        
        if "itsm" in query_type and not has_itsm:
            recommendations.append(
                "Your instance does not have ITSM installed. "
                "You'll need to install ITSM applications (Incident, Problem, Change Management)."
            )
        
        if "csm" in query_type and not has_csm:
            recommendations.append(
                "Your instance does not have CSM installed. "
                "You'll need the Customer Service Management plugin."
            )
        
        if has_itsm and has_csm:
            recommendations.append(
                "Your instance has both ITSM and CSM. "
                "Consider integrating Case-to-Incident escalation for IT-related customer issues."
            )
        
        if "integration" in query_type and not has_itom:
            recommendations.append(
                "For complex integrations, consider ITOM Discovery and Service Mapping "
                "to automatically populate your CMDB."
            )
        
        return recommendations
    
    def get_mermaid_guidance(self, query_types: List[str]) -> str:
        """
        Get specialized Mermaid diagram guidance based on query type.
        Includes relationship semantics and architectural patterns.
        """
        guidance = """
CRITICAL MERMAID DIAGRAM RULES:

1. RELATIONSHIP SEMANTICS - Use labels to show HOW components relate:
   - Portal -->|creates| CSM (Portal creates cases in CSM)
   - CSM -->|runs on| Platform (CSM runs on Platform)
   - Incident -->|references| CMDB (Incident references CMDB data)
   - Case -->|resolves using| KB (Case resolves using Knowledge Base)

2. FOUNDATIONAL COMPONENTS (CMDB, Platform, User Mgmt):
   - Place at BOTTOM or as separate layer
   - Other components point TO them (references)
   - They do NOT point to other components
   - Use subgraph to show they're foundational

3. NO BIDIRECTIONAL ARROWS unless it's peer-to-peer integration:
   - WRONG: Portal <--> CSM
   - RIGHT: Portal -->|creates| CSM

4. SEGREGATION PATTERNS (CSM vs ITSM):
   - Public Portal should ONLY connect to CSM
   - Internal Portal should ONLY connect to ITSM
   - NO cross-connections between public and internal paths

5. LAYERED ARCHITECTURE:
   - Layer 1 (Top): Users/Personas
   - Layer 2: Portals/UI
   - Layer 3: Applications (CSM, ITSM)
   - Layer 4: Platform
   - Layer 5 (Bottom): Foundational Data (CMDB, KB)

CORRECT Example with Semantics:
graph TD
    subgraph Users
        A[Public Customer]
        B[Internal Employee]
    end
    subgraph Portals
        C[Customer Portal]
        D[Service Portal]
    end
    subgraph Applications
        E[CSM]
        F[ITSM]
    end
    subgraph Foundation
        G[Platform]
        H[CMDB]
        I[Knowledge Base]
    end
    
    A -->|accesses| C
    B -->|accesses| D
    C -->|creates cases| E
    D -->|creates tickets| F
    E -->|runs on| G
    F -->|runs on| G
    E -->|references| H
    F -->|references| H
    E -->|resolves using| I
    F -->|resolves using| I

WRONG Example (DO NOT DO):
graph TD
    A[Portal] <--> B[CSM]  ❌ Bidirectional
    B --> C[CMDB]  ❌ CMDB at bottom implies it's downstream
    A --> D[ITSM]  ❌ Public portal connecting to ITSM
    C --> E[KB]  ❌ CMDB feeding KB (backwards)
"""
        
        # Add query-specific guidance
        if "csm" in query_types and "itsm" in query_types:
            guidance += """
SPECIFIC TO CSM + ITSM ARCHITECTURE:
- Show TWO SEPARATE PATHS: Public → CSM and Internal → ITSM
- NO arrows between Customer Portal and ITSM
- NO arrows between Service Portal and CSM
- Both CSM and ITSM reference CMDB (not consume it)
- Use subgraphs to show segregation
"""
        
        return guidance
