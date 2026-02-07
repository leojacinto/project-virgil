"""
ServiceNow Domain Knowledge and Ontology
Provides structured knowledge about ServiceNow component relationships,
dependencies, and architectural constraints.
"""

from typing import Dict, List, Set
import logging

logger = logging.getLogger(__name__)

class ServiceNowOntology:
    """
    ServiceNow domain knowledge graph and validation rules.
    Ensures architectures follow ServiceNow best practices and constraints.
    """
    
    def __init__(self):
        # Core foundational components that other components depend on
        self.foundational_components = {
            "CMDB", "Configuration Management Database", "cmdb_ci",
            "User Management", "sys_user", "Groups", "sys_user_group",
            "Platform", "ServiceNow Platform"
        }
        
        # Relationship types with semantic meaning
        self.relationship_types = {
            "runs_on": "Component runs on/is hosted by another (e.g., CSM runs on Platform)",
            "consumes": "Component consumes data from another (e.g., Portal consumes Knowledge Base)",
            "references": "Component references data in another (e.g., Incident references CMDB)",
            "creates": "Component creates records in another (e.g., Portal creates Cases)",
            "resolves_using": "Component uses another to resolve issues (e.g., Case resolves using KB)",
            "authenticates_via": "Component uses another for authentication (e.g., Portal authenticates via User Mgmt)",
            "segregated_from": "Components should NOT cross-connect (e.g., Public Portal ≠ ITSM)"
        }
        
        # Semantic relationships: (source, target, relationship_type)
        self.semantic_relationships = [
            # Platform relationships (runs-on)
            ("CSM", "Platform", "runs_on"),
            ("ITSM", "Platform", "runs_on"),
            ("Service Portal", "Platform", "runs_on"),
            ("Customer Portal", "Platform", "runs_on"),
            
            # CMDB relationships (references - CMDB is lateral/foundational)
            ("Incident Management", "CMDB", "references"),
            ("Problem Management", "CMDB", "references"),
            ("Change Management", "CMDB", "references"),
            ("Case Management", "CMDB", "references"),
            ("Asset Management", "CMDB", "references"),
            
            # Knowledge Base relationships (consumes)
            ("Incident Management", "Knowledge Base", "resolves_using"),
            ("Case Management", "Knowledge Base", "resolves_using"),
            ("Service Portal", "Knowledge Base", "consumes"),
            ("Customer Portal", "Knowledge Base", "consumes"),
            
            # Portal to App relationships (creates)
            ("Customer Portal", "CSM", "creates"),
            ("Service Portal", "ITSM", "creates"),
            
            # Authentication relationships
            ("Customer Portal", "User Management", "authenticates_via"),
            ("Service Portal", "User Management", "authenticates_via"),
            
            # Segregation rules (anti-patterns)
            ("Customer Portal", "ITSM", "segregated_from"),
            ("Service Portal", "CSM", "segregated_from"),
        ]
        
        # Component dependency rules: component -> list of dependencies
        self.dependencies = {
            "Incident Management": ["CMDB", "User Management", "Assignment Groups"],
            "Problem Management": ["Incident Management", "CMDB", "Knowledge Base"],
            "Change Management": ["CMDB", "Incident Management", "Approval Workflows"],
            "Service Catalog": ["CMDB", "Workflows", "User Management"],
            "Knowledge Base": ["User Management"],
            "CSM": ["Customer Portal", "Case Management", "Knowledge Base"],
            "Case Management": ["Knowledge Base", "User Management"],
            "ITSM": ["Incident Management", "Problem Management", "Change Management"],
            "Asset Management": ["CMDB"],
            "Service Portal": ["User Management", "Knowledge Base"],
            "Customer Portal": ["User Management", "Knowledge Base"],
            "Integration Hub": ["Platform"],
            "Flow Designer": ["Platform"],
            "Virtual Agent": ["Knowledge Base", "NLU"],
        }
        
        # Components that should NOT be downstream of others
        self.cannot_be_downstream = {
            "CMDB": ["Knowledge Base", "Service Portal", "Customer Portal"],
            "User Management": ["Service Portal", "Customer Portal", "Case Management"],
            "Platform": ["any"]  # Platform is always foundational
        }
        
        # Common ServiceNow products and their core components
        self.product_components = {
            "ITSM": ["Incident Management", "Problem Management", "Change Management", 
                    "Service Catalog", "Knowledge Base", "CMDB"],
            "CSM": ["Customer Service Portal", "Case Management", "Customer Accounts",
                   "Knowledge Base", "Playbooks"],
            "ITOM": ["Discovery", "Service Mapping", "Event Management", "CMDB"],
            "ITBM": ["Project Portfolio Management", "Agile Development", "Resource Management"],
            "SecOps": ["Security Incident Response", "Vulnerability Response", "Threat Intelligence"],
            "HR Service Delivery": ["HR Case Management", "Employee Portal", "Knowledge Base"],
            "GRC": ["Policy and Compliance", "Risk Management", "Audit Management"],
        }
        
        # Query type patterns for specialized handling
        self.query_patterns = {
            "integration": ["integrate", "integration", "connect", "sync", "api", "webhook"],
            "itsm": ["incident", "problem", "change", "itsm", "it service"],
            "csm": ["customer", "case", "csm", "customer service"],
            "data_flow": ["data", "flow", "sync", "transfer", "master data"],
            "portal": ["portal", "self-service", "employee", "customer"],
            "automation": ["automate", "workflow", "flow", "orchestration"],
            "compliance": ["compliance", "fedramp", "spp", "security", "audit"],
        }
    
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
            if any(pattern in query_lower for pattern in patterns):
                detected_types.append(query_type)
        
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
                "- CMDB is foundational for all ITSM processes\n"
                "- Incident → Problem → Change is the standard escalation flow\n"
                "- Knowledge Base should feed into all ITSM modules\n"
                "- Service Catalog requires workflow engine"
            )
        
        if "csm" in query_types:
            constraints.append(
                "CSM Architecture Constraints:\n"
                "- Customer Portal is the public-facing entry point\n"
                "- Case Management is core, not Incident Management\n"
                "- Customer Accounts separate from internal Users\n"
                "- Knowledge Base should be accessible to customers"
            )
        
        if "compliance" in query_types:
            constraints.append(
                "Compliance Architecture Constraints:\n"
                "- All components must reside in FedRAMP/SPP compliant instance\n"
                "- Use domain separation or ACLs for data segregation\n"
                "- Audit logging required for all operations\n"
                "- Single instance preferred over multiple for compliance"
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
