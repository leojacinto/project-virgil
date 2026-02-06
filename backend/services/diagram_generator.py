import os
from typing import List, Dict, Optional
import logging
from datetime import datetime
import uuid

from diagrams import Diagram, Cluster, Edge
from diagrams.custom import Custom
from diagrams.onprem.database import PostgreSQL
from diagrams.onprem.workflow import Airflow
from diagrams.programming.framework import React
from diagrams.saas.analytics import Snowflake
from diagrams.onprem.client import Users
from diagrams.onprem.network import Internet
from diagrams.generic.blank import Blank

from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DiagramGenerator:
    def __init__(self):
        self.output_dir = settings.diagram_output_dir
        os.makedirs(self.output_dir, exist_ok=True)
    
    def generate_diagram(
        self,
        components: List[Dict],
        format: str = "png",
        title: str = "ServiceNow Architecture"
    ) -> str:
        if not components:
            logger.warning("No components provided for diagram generation")
            return None
        
        try:
            diagram_id = f"{uuid.uuid4()}.{format}"
            diagram_path = os.path.join(self.output_dir, diagram_id)
            base_path = diagram_path.replace(f".{format}", "")
            
            with Diagram(
                title,
                filename=base_path,
                show=False,
                direction="TB",
                outformat=format
            ):
                node_map = {}
                
                for component in components:
                    node = self._create_node(component)
                    node_map[component["name"]] = node
                
                for component in components:
                    if "connections" in component and component["connections"]:
                        source_node = node_map.get(component["name"])
                        if source_node:
                            for target_name in component["connections"]:
                                target_node = node_map.get(target_name)
                                if target_node:
                                    source_node >> Edge(label="") >> target_node
            
            logger.info(f"Diagram generated: {diagram_id}")
            return diagram_id
        except Exception as e:
            logger.error(f"Error generating diagram: {str(e)}")
            return None
    
    def _create_node(self, component: Dict):
        comp_type = component.get("type", "service").lower()
        name = component.get("name", "Unknown")
        
        if comp_type == "database":
            return PostgreSQL(name)
        elif comp_type == "workflow":
            return Airflow(name)
        elif comp_type == "ui":
            return React(name)
        elif comp_type == "user":
            return Users(name)
        elif comp_type == "integration":
            return Internet(name)
        else:
            return Blank(name)
    
    def generate_mermaid_diagram(self, components: List[Dict]) -> str:
        if not components:
            return ""
        
        mermaid_lines = ["graph TB"]
        
        node_ids = {}
        for i, component in enumerate(components):
            node_id = f"N{i}"
            name = component.get("name", "Unknown")
            comp_type = component.get("type", "service")
            
            node_ids[name] = node_id
            
            if comp_type == "database":
                mermaid_lines.append(f'    {node_id}[("{name}")]')
            elif comp_type == "workflow":
                mermaid_lines.append(f'    {node_id}{{{{{name}}}}}')
            elif comp_type == "ui":
                mermaid_lines.append(f'    {node_id}["{name}"]')
            else:
                mermaid_lines.append(f'    {node_id}["{name}"]')
        
        for component in components:
            source_name = component.get("name")
            source_id = node_ids.get(source_name)
            
            if source_id and "connections" in component:
                for target_name in component["connections"]:
                    target_id = node_ids.get(target_name)
                    if target_id:
                        mermaid_lines.append(f'    {source_id} --> {target_id}')
        
        return "\n".join(mermaid_lines)
    
    def generate_plantuml_diagram(self, components: List[Dict]) -> str:
        if not components:
            return ""
        
        plantuml_lines = ["@startuml", "!theme plain"]
        
        for component in components:
            name = component.get("name", "Unknown")
            comp_type = component.get("type", "service")
            description = component.get("description", "")
            
            if comp_type == "database":
                plantuml_lines.append(f'database "{name}" as {self._sanitize_id(name)}')
            elif comp_type == "workflow":
                plantuml_lines.append(f'component "{name}" as {self._sanitize_id(name)}')
            elif comp_type == "ui":
                plantuml_lines.append(f'rectangle "{name}" as {self._sanitize_id(name)}')
            elif comp_type == "user":
                plantuml_lines.append(f'actor "{name}" as {self._sanitize_id(name)}')
            else:
                plantuml_lines.append(f'component "{name}" as {self._sanitize_id(name)}')
        
        plantuml_lines.append("")
        
        for component in components:
            source_name = component.get("name")
            if "connections" in component:
                for target_name in component["connections"]:
                    source_id = self._sanitize_id(source_name)
                    target_id = self._sanitize_id(target_name)
                    plantuml_lines.append(f'{source_id} --> {target_id}')
        
        plantuml_lines.append("@enduml")
        
        return "\n".join(plantuml_lines)
    
    def _sanitize_id(self, name: str) -> str:
        return name.replace(" ", "_").replace("-", "_").replace(".", "_")
    
    def list_diagrams(self) -> List[Dict]:
        diagrams = []
        
        for filename in os.listdir(self.output_dir):
            if filename.endswith(('.png', '.jpg', '.svg', '.pdf')):
                file_path = os.path.join(self.output_dir, filename)
                stat = os.stat(file_path)
                
                diagrams.append({
                    "filename": filename,
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        
        return sorted(diagrams, key=lambda x: x["modified"], reverse=True)
    
    def delete_diagram(self, diagram_id: str):
        diagram_path = os.path.join(self.output_dir, diagram_id)
        if os.path.exists(diagram_path):
            os.remove(diagram_path)
            logger.info(f"Deleted diagram: {diagram_id}")
        else:
            raise FileNotFoundError(f"Diagram not found: {diagram_id}")
