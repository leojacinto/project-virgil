import re
import logging
from typing import List, Dict, Tuple, Optional
from services.servicenow_ontology import ServiceNowOntology

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MermaidRelationship:
    """Represents a relationship in a Mermaid diagram"""
    def __init__(self, source: str, target: str, rel_type: str, label: str = ""):
        self.source = source
        self.target = target
        self.rel_type = rel_type
        self.label = label
    
    def __repr__(self):
        return f"{self.source} --{self.label or self.rel_type}--> {self.target}"


class ArchitectureValidator:
    """
    Post-generation validation layer that checks LLM output against ontology rules.
    This is the 5% validation layer that shifts quality from "usually good" to "reliably good".
    """
    
    def __init__(self, ontology: ServiceNowOntology):
        self.ontology = ontology
    
    def validate_mermaid_diagram(self, mermaid: str) -> Tuple[bool, List[str], Optional[str]]:
        """
        Validate Mermaid diagram against ontology rules.
        
        Returns:
            Tuple of (is_valid, errors, corrected_diagram)
        """
        errors = []
        
        # Parse relationships from Mermaid
        relationships = self._parse_mermaid_relationships(mermaid)
        
        if not relationships:
            errors.append("No relationships found in diagram")
            return False, errors, None
        
        # Validate each relationship
        for rel in relationships:
            validation_errors = self._validate_relationship(rel)
            errors.extend(validation_errors)
        
        # Check for architectural anti-patterns
        anti_pattern_errors = self._check_anti_patterns(relationships)
        errors.extend(anti_pattern_errors)
        
        # Check for circular dependencies in foundational components
        circular_errors = self._check_circular_dependencies(relationships)
        errors.extend(circular_errors)
        
        is_valid = len(errors) == 0
        
        if not is_valid:
            logger.warning(f"Mermaid validation found {len(errors)} issues: {errors}")
        else:
            logger.info("Mermaid diagram passed validation")
        
        return is_valid, errors, None
    
    def _parse_mermaid_relationships(self, mermaid: str) -> List[MermaidRelationship]:
        """Parse relationships from Mermaid diagram"""
        relationships = []
        
        # Pattern to match: A -->|label| B or A --> B
        pattern = r'(\w+)\s*-->\s*(?:\|([^\|]+)\|)?\s*(\w+)'
        
        for match in re.finditer(pattern, mermaid):
            source = match.group(1)
            label = match.group(2) or ""
            target = match.group(3)
            
            relationships.append(MermaidRelationship(source, target, "-->", label))
        
        return relationships
    
    def _validate_relationship(self, rel: MermaidRelationship) -> List[str]:
        """Validate a single relationship against ontology rules"""
        errors = []
        
        # Extract component names from node IDs (e.g., "CSM" from node ID)
        # This is a simplified check - in production, would map node IDs to component types
        source_lower = rel.source.lower()
        target_lower = rel.target.lower()
        
        # Check for known anti-patterns
        
        # 1. Portal should not directly access CMDB
        if 'portal' in source_lower and 'cmdb' in target_lower:
            errors.append(f"Invalid: {rel.source} → {rel.target} (Portals should access applications, not CMDB directly)")
        
        # 2. Knowledge Base should not depend on applications
        if 'kb' in source_lower or 'knowledge' in source_lower:
            if 'incident' in target_lower or 'case' in target_lower or 'service' in target_lower:
                errors.append(f"Invalid: {rel.source} → {rel.target} (Knowledge Base is consumed BY apps, not vice versa)")
        
        # 3. CMDB should not depend on applications
        if 'cmdb' in source_lower:
            if 'incident' in target_lower or 'case' in target_lower or 'itsm' in target_lower or 'csm' in target_lower:
                errors.append(f"Invalid: {rel.source} → {rel.target} (CMDB is foundational, cannot depend on applications)")
        
        # 4. User Management should not depend on applications
        if 'user' in source_lower and 'management' in source_lower:
            if 'incident' in target_lower or 'case' in target_lower:
                errors.append(f"Invalid: {rel.source} → {rel.target} (User Management is foundational)")
        
        return errors
    
    def _check_anti_patterns(self, relationships: List[MermaidRelationship]) -> List[str]:
        """Check for architectural anti-patterns"""
        errors = []
        
        # Build a graph to check patterns
        graph = {}
        for rel in relationships:
            if rel.source not in graph:
                graph[rel.source] = []
            graph[rel.source].append(rel.target)
        
        # Check for UI components depending on data layer directly
        ui_components = [node for node in graph.keys() if 'portal' in node.lower() or 'ui' in node.lower()]
        data_components = [node for node in graph.keys() if 'cmdb' in node.lower() or 'database' in node.lower()]
        
        for ui in ui_components:
            if ui in graph:
                for target in graph[ui]:
                    if target in data_components:
                        errors.append(f"Anti-pattern: UI component {ui} directly accessing data layer {target}")
        
        return errors
    
    def _check_circular_dependencies(self, relationships: List[MermaidRelationship]) -> List[str]:
        """Check for circular dependencies in foundational components"""
        errors = []
        
        # Build adjacency list
        graph = {}
        for rel in relationships:
            if rel.source not in graph:
                graph[rel.source] = []
            graph[rel.source].append(rel.target)
        
        # Check for cycles using DFS
        visited = set()
        rec_stack = set()
        
        def has_cycle(node, path):
            visited.add(node)
            rec_stack.add(node)
            
            if node in graph:
                for neighbor in graph[node]:
                    if neighbor not in visited:
                        if has_cycle(neighbor, path + [neighbor]):
                            return True
                    elif neighbor in rec_stack:
                        # Found a cycle
                        cycle_path = path[path.index(neighbor):] + [neighbor]
                        errors.append(f"Circular dependency detected: {' → '.join(cycle_path)}")
                        return True
            
            rec_stack.remove(node)
            return False
        
        for node in graph.keys():
            if node not in visited:
                has_cycle(node, [node])
        
        return errors
    
    def validate_recommendations(self, recommendations: List[Dict], instance_data: Dict) -> List[str]:
        """
        Validate recommendations against actual instance state.
        
        Args:
            recommendations: List of recommendation dicts with 'servicenow_components'
            instance_data: Instance metadata including installed apps and plugins
        
        Returns:
            List of validation warnings
        """
        warnings = []
        
        # Get installed components
        installed_apps = set()
        if 'applications' in instance_data:
            for app in instance_data['applications']:
                installed_apps.add(app.get('name', '').lower())
        
        # Check if recommendations suggest already-installed components
        for rec in recommendations:
            components = rec.get('servicenow_components', [])
            for component in components:
                component_lower = component.lower()
                
                # Check if component is already installed
                for installed in installed_apps:
                    if component_lower in installed or installed in component_lower:
                        warnings.append(
                            f"Recommendation suggests '{component}' but similar app '{installed}' is already installed"
                        )
        
        return warnings
    
    def generate_validation_report(self, mermaid: str, recommendations: List[Dict], 
                                   instance_data: Dict) -> Dict:
        """
        Generate comprehensive validation report.
        
        Returns:
            Dict with validation results and suggestions
        """
        report = {
            'diagram_valid': True,
            'diagram_errors': [],
            'recommendation_warnings': [],
            'suggestions': []
        }
        
        # Validate diagram
        is_valid, errors, _ = self.validate_mermaid_diagram(mermaid)
        report['diagram_valid'] = is_valid
        report['diagram_errors'] = errors
        
        # Validate recommendations
        warnings = self.validate_recommendations(recommendations, instance_data)
        report['recommendation_warnings'] = warnings
        
        # Generate suggestions
        if not is_valid:
            report['suggestions'].append("Consider simplifying the architecture to avoid invalid relationships")
        
        if warnings:
            report['suggestions'].append("Review recommendations against installed applications to avoid duplication")
        
        return report
