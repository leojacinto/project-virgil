import re
import logging
from typing import List, Dict, Tuple, Optional
from services.servicenow_ontology import ServiceNowOntology

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


MAX_ARROWS = 15
MAX_OUTGOING_PER_NODE = 3

# Valid relationship labels from the ontology vocabulary
VALID_LABELS = {
    'runs on', 'creates', 'creates cases', 'creates tickets', 'creates requests',
    'references', 'resolves using', 'consumes', 'accesses',
    'authenticates via', 'extends', 'depends on', 'populates',
    'integrates with', 'connects to',
}

# Vague labels → standard replacements
LABEL_REPLACEMENTS = {
    'leverages': 'references',
    'manages': 'depends on',
    'utilizes': 'references',
    'feeds': 'creates',
    'provides': 'references',
    'supports': 'runs on',
    'uses': 'references',
    'interacts with': 'accesses',
    'connects': 'connects to',
    'handles': 'creates',
    'triggers': 'creates',
    'sends to': 'creates',
    'links to': 'references',
    'powered by': 'runs on',
    'built on': 'runs on',
    'hosted on': 'runs on',
    'relies on': 'depends on',
    'queries': 'references',
    'reads from': 'references',
    'writes to': 'creates',
    'calls': 'accesses',
    'invokes': 'accesses',
    'talks to': 'accesses',
    'fetches from': 'references',
    'stores in': 'creates',
    'logs to': 'creates',
    'monitors': 'references',
    'tracks': 'references',
    'enables': 'runs on',
    'drives': 'creates',
    'orchestrates': 'depends on',
    'automates': 'depends on',
}


class MermaidRelationship:
    """Represents a relationship in a Mermaid diagram"""
    def __init__(self, source: str, target: str, rel_type: str, label: str = "", raw_line: str = ""):
        self.source = source
        self.target = target
        self.rel_type = rel_type
        self.label = label
        self.raw_line = raw_line
    
    def __repr__(self):
        return f"{self.source} --{self.label or self.rel_type}--> {self.target}"


class ArchitectureValidator:
    """
    Post-generation validation layer that checks LLM output against ontology rules.
    This is the 5% validation layer that shifts quality from "usually good" to "reliably good".
    """
    
    def __init__(self, ontology: ServiceNowOntology):
        self.ontology = ontology
    
    def validate_mermaid_diagram(self, mermaid: str) -> Tuple[bool, List[str], Optional[str], Dict]:
        """
        Validate Mermaid diagram against ontology rules.
        Removes invalid relationships and enforces arrow limits.
        
        Returns:
            Tuple of (is_valid, errors, corrected_diagram, rules_applied)
        """
        errors = []
        rules_applied = {
            "label_replacements_applied": [],
            "arrows_removed": [],
            "anti_patterns_detected": [],
            "arrows_pruned": 0,
            "circular_dependencies": [],
            "missing_relationships": [],
            "outgoing_limit_warnings": [],
            "architectural_rules_triggered": [],
        }
        
        # Parse node ID -> label mappings
        self._node_labels = self._parse_node_labels(mermaid)
        
        # Parse relationships from Mermaid
        relationships = self._parse_mermaid_relationships(mermaid)
        
        if not relationships:
            errors.append("No relationships found in diagram")
            return False, errors, None, rules_applied
        
        # Track lines to remove
        lines_to_remove = set()
        
        # Validate each relationship
        for rel in relationships:
            validation_errors = self._validate_relationship(rel)
            if validation_errors:
                errors.extend(validation_errors)
                lines_to_remove.add(rel.raw_line.strip())
                source_label = self._get_label(rel.source)
                target_label = self._get_label(rel.target)
                for err in validation_errors:
                    rules_applied["arrows_removed"].append({
                        "source": source_label, "target": target_label, "reason": err
                    })
                    # Map error back to architectural rule
                    if 'portal' in source_label and 'cmdb' in target_label:
                        rules_applied["architectural_rules_triggered"].append(
                            "Portals sit at UI layer, they consume services not provide them")
                    if 'knowledge' in source_label:
                        rules_applied["architectural_rules_triggered"].append(
                            "Knowledge Base is consumed BY other components, never consumes them")
                    if 'cmdb' in source_label or 'configuration management' in source_label:
                        rules_applied["architectural_rules_triggered"].append(
                            "CMDB is always foundational, cannot depend on other components")
                    if 'user management' in source_label:
                        rules_applied["architectural_rules_triggered"].append(
                            "User Management is always foundational, required for authentication")
        
        # Check for architectural anti-patterns
        anti_pattern_errors = self._check_anti_patterns(relationships)
        errors.extend(anti_pattern_errors)
        for err in anti_pattern_errors:
            if 'bidirectional' in err.lower():
                rules_applied["anti_patterns_detected"].append(err)
                rules_applied["architectural_rules_triggered"].append(
                    "No bidirectional arrows unless peer-to-peer integration")
            elif 'anti-pattern' in err.lower():
                rules_applied["anti_patterns_detected"].append(err)
        
        # Check for circular dependencies in foundational components
        circular_errors = self._check_circular_dependencies(relationships)
        errors.extend(circular_errors)
        rules_applied["circular_dependencies"] = circular_errors[:]
        
        # Normalize vague labels to standard vocabulary
        mermaid, label_fixes = self._normalize_labels(mermaid)
        if label_fixes:
            errors.extend(label_fixes)
            for fix in label_fixes:
                # Parse "Label fix: 'vague' → 'standard'"
                parts = fix.replace("Label fix: '", "").replace("'", "").split(" → ")
                if len(parts) == 2:
                    rules_applied["label_replacements_applied"].append(
                        {"from": parts[0], "to": parts[1]})
        
        # Check for missing required relationships
        missing = self._check_missing_required(relationships, lines_to_remove)
        if missing:
            errors.extend(missing)
            rules_applied["missing_relationships"] = missing[:]
            for m in missing:
                if 'runs on' in m.lower():
                    rules_applied["architectural_rules_triggered"].append(
                        "Every application must 'runs on' Platform")
                if 'authenticates via' in m.lower():
                    rules_applied["architectural_rules_triggered"].append(
                        "Every portal must 'authenticates via' User Management")
        
        # Enforce arrow count limit
        valid_relationships = [r for r in relationships if r.raw_line.strip() not in lines_to_remove]
        if len(valid_relationships) > MAX_ARROWS:
            excess = len(valid_relationships) - MAX_ARROWS
            errors.append(f"Diagram has {len(valid_relationships)} arrows, exceeds limit of {MAX_ARROWS}. Pruning {excess} lowest-priority connections.")
            rules_applied["arrows_pruned"] = excess
            valid_relationships = self._prune_excess_arrows(valid_relationships, MAX_ARROWS)
            # Update lines_to_remove with pruned arrows
            valid_lines = {r.raw_line.strip() for r in valid_relationships}
            for rel in relationships:
                if rel.raw_line.strip() not in valid_lines:
                    lines_to_remove.add(rel.raw_line.strip())
        
        # Enforce max outgoing per node
        outgoing_count = {}
        for rel in valid_relationships:
            outgoing_count[rel.source] = outgoing_count.get(rel.source, 0) + 1
        for node, count in outgoing_count.items():
            if count > MAX_OUTGOING_PER_NODE:
                label = self._node_labels.get(node, node)
                errors.append(f"Node {label} has {count} outgoing connections (max {MAX_OUTGOING_PER_NODE})")
                rules_applied["outgoing_limit_warnings"].append(
                    f"{label}: {count} outgoing (max {MAX_OUTGOING_PER_NODE})")
        
        # Deduplicate architectural rules triggered
        rules_applied["architectural_rules_triggered"] = list(
            dict.fromkeys(rules_applied["architectural_rules_triggered"]))
        
        is_valid = len(errors) == 0
        
        # Build corrected diagram (label fixes already applied to mermaid variable)
        corrected = None
        labels_were_fixed = len(label_fixes) > 0
        if lines_to_remove:
            corrected_lines = []
            for line in mermaid.split("\n"):
                if line.strip() not in lines_to_remove:
                    corrected_lines.append(line)
            corrected = "\n".join(corrected_lines)
            logger.info(f"Validator removed {len(lines_to_remove)} lines from diagram")
        elif labels_were_fixed:
            corrected = mermaid
            logger.info(f"Validator fixed {len(label_fixes)} labels in diagram")
        
        if not is_valid:
            logger.warning(f"Mermaid validation found {len(errors)} issues: {errors}")
        else:
            logger.info("Mermaid diagram passed validation")
        
        return is_valid, errors, corrected, rules_applied
    
    def _parse_node_labels(self, mermaid: str) -> Dict[str, str]:
        """Parse node ID to label mappings from Mermaid (e.g., CP[Customer Portal] -> {'CP': 'customer portal'})"""
        labels = {}
        pattern = r'(\w+)\[([^\]]+)\]'
        for match in re.finditer(pattern, mermaid):
            node_id = match.group(1)
            label = match.group(2).strip().lower()
            labels[node_id] = label
        return labels
    
    def _get_label(self, node_id: str) -> str:
        """Get the label for a node ID, falling back to the ID itself"""
        return self._node_labels.get(node_id, node_id.lower())
    
    def _parse_mermaid_relationships(self, mermaid: str) -> List[MermaidRelationship]:
        """Parse relationships from Mermaid diagram"""
        relationships = []
        
        # Pattern to match: A -->|label| B or A --> B
        pattern = r'(\w+)\s*-->\s*(?:\|([^\|]+)\|)?\s*(\w+)'
        
        for line in mermaid.split("\n"):
            match = re.search(pattern, line)
            if match:
                source = match.group(1)
                label = match.group(2) or ""
                target = match.group(3)
                relationships.append(MermaidRelationship(source, target, "-->", label, line))
        
        return relationships
    
    def _prune_excess_arrows(self, relationships: List[MermaidRelationship], max_count: int) -> List[MermaidRelationship]:
        """Prune excess arrows, keeping high-priority relationships and removing low-priority ones."""
        # Priority: higher = keep
        high_priority_labels = {'runs on', 'creates', 'references', 'resolves using', 'creates cases', 'creates tickets', 'creates requests', 'authenticates via'}
        medium_priority_labels = {'accesses', 'depends on', 'consumes', 'populates'}
        # Everything else is low priority: 'manages', 'connects', 'uses', 'automates', 'provides', 'leverages', 'integrates'
        
        def priority(rel):
            label_lower = rel.label.lower() if rel.label else ""
            if any(hp in label_lower for hp in high_priority_labels):
                return 2
            if any(mp in label_lower for mp in medium_priority_labels):
                return 1
            return 0
        
        # Sort by priority descending, keep top max_count
        sorted_rels = sorted(relationships, key=priority, reverse=True)
        kept = sorted_rels[:max_count]
        pruned = sorted_rels[max_count:]
        
        if pruned:
            logger.info(f"Pruned {len(pruned)} low-priority arrows: {[str(r) for r in pruned]}")
        
        return kept
    
    def _validate_relationship(self, rel: MermaidRelationship) -> List[str]:
        """Validate a single relationship against ontology rules using node labels"""
        errors = []
        
        # Use labels for matching, not node IDs
        source_label = self._get_label(rel.source)
        target_label = self._get_label(rel.target)
        
        # 1. Portal should not directly access CMDB
        if 'portal' in source_label and 'cmdb' in target_label:
            errors.append(f"Removed: {source_label} → {target_label} (Portals should access applications, not CMDB directly)")
        
        # 2. Knowledge Base should not depend on applications
        if 'knowledge' in source_label:
            if any(term in target_label for term in ['incident', 'case', 'service catalog', 'itsm', 'csm']):
                errors.append(f"Removed: {source_label} → {target_label} (Knowledge Base is consumed BY apps, not vice versa)")
        
        # 3. CMDB should not depend on applications
        if 'cmdb' in source_label or 'configuration management' in source_label:
            if any(term in target_label for term in ['incident', 'case', 'itsm', 'csm', 'service catalog', 'problem', 'change']):
                errors.append(f"Removed: {source_label} → {target_label} (CMDB is foundational, cannot depend on applications)")
        
        # 4. User Management should not depend on applications
        if 'user management' in source_label:
            if any(term in target_label for term in ['incident', 'case', 'itsm', 'csm', 'portal']):
                errors.append(f"Removed: {source_label} → {target_label} (User Management is foundational)")
        
        return errors
    
    def _check_anti_patterns(self, relationships: List[MermaidRelationship]) -> List[str]:
        """Check for architectural anti-patterns using node labels"""
        errors = []
        
        # Build a graph using labels
        graph = {}
        for rel in relationships:
            source_label = self._get_label(rel.source)
            if source_label not in graph:
                graph[source_label] = []
            graph[source_label].append(self._get_label(rel.target))
        
        # Check for UI components depending on data layer directly
        ui_labels = [label for label in graph.keys() if 'portal' in label or 'ui' in label]
        data_labels = [label for label in graph.keys() if 'cmdb' in label or 'configuration management' in label]
        
        for ui in ui_labels:
            if ui in graph:
                for target in graph[ui]:
                    if target in data_labels:
                        errors.append(f"Anti-pattern: {ui} directly accessing {target}")
        
        # Check for bidirectional arrows (A→B and B→A)
        seen_pairs = set()
        for rel in relationships:
            pair = (rel.source, rel.target)
            reverse = (rel.target, rel.source)
            if reverse in seen_pairs:
                s_label = self._get_label(rel.source)
                t_label = self._get_label(rel.target)
                errors.append(f"Bidirectional: {s_label} ↔ {t_label} (use single direction unless peer-to-peer)")
            seen_pairs.add(pair)
        
        return errors
    
    def _normalize_labels(self, mermaid: str) -> Tuple[str, List[str]]:
        """Replace vague labels with standard ontology vocabulary."""
        fixes = []
        for vague, standard in LABEL_REPLACEMENTS.items():
            # Match |vague label| in arrows
            pattern = re.compile(r'\|' + re.escape(vague) + r'\|', re.IGNORECASE)
            if pattern.search(mermaid):
                mermaid = pattern.sub(f'|{standard}|', mermaid)
                fixes.append(f"Label fix: '{vague}' → '{standard}'")
        return mermaid, fixes
    
    def _check_missing_required(self, relationships: List[MermaidRelationship], lines_to_remove: set) -> List[str]:
        """Check that application-layer nodes have 'runs on' → Platform."""
        warnings = []
        
        # Find app-layer nodes and whether they connect to platform
        app_keywords = {'itsm', 'it service management', 'csm', 'customer service management',
                        'hrsd', 'hr service delivery', 'itom', 'secops', 'security operations', 'grc'}
        platform_keywords = {'platform', 'servicenow platform', 'now platform'}
        
        app_nodes = set()
        platform_nodes = set()
        for node_id, label in self._node_labels.items():
            if any(kw in label for kw in app_keywords):
                app_nodes.add(node_id)
            if any(kw in label for kw in platform_keywords):
                platform_nodes.add(node_id)
        
        # Check each app node has runs_on to platform
        for app_id in app_nodes:
            has_runs_on = False
            for rel in relationships:
                if rel.raw_line.strip() in lines_to_remove:
                    continue
                if rel.source == app_id and rel.target in platform_nodes:
                    if 'runs on' in (rel.label or '').lower():
                        has_runs_on = True
                        break
            if not has_runs_on:
                app_label = self._node_labels.get(app_id, app_id)
                warnings.append(f"Missing: {app_label} should have 'runs on' → Platform")
        
        return warnings
    
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
                        # Found a cycle - build cycle path safely
                        if neighbor in path:
                            cycle_path = path[path.index(neighbor):] + [neighbor]
                        else:
                            cycle_path = [node, neighbor]
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
