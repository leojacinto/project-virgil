import os
import re
from typing import List, Dict, Optional, Any, Iterator
import logging
import json
import datetime
import requests as http_requests

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from pydantic import BaseModel, Field

from config import settings
from services.servicenow_ontology import ServiceNowOntology
from services.architecture_validator import ArchitectureValidator
from services.instance_scanner_rules import RuleEngine, InstanceModel, ENABLED as RULES_ENABLED


class ChatOneLLM(BaseChatModel):
    """LangChain-compatible wrapper for ServiceNow OneLLM gateway.
    
    OneLLM proxies Claude via Vertex AI with a custom auth scheme:
      - Header: 'api-key' (not 'x-api-key')
      - Path:   <base_url>//v1/messages
      - Body:   standard Anthropic messages format
    """
    base_url: str
    api_key: str
    model_name: str = "claude-3-7-sonnet-20250219"
    temperature: float = 0.7
    max_tokens: int = 16384

    @property
    def _llm_type(self) -> str:
        return "onellm"

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, **kwargs) -> ChatResult:
        # Convert LangChain messages to Anthropic format
        system_text = ""
        api_messages = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                system_text += msg.content + "\n"
            elif isinstance(msg, HumanMessage):
                api_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                api_messages.append({"role": "assistant", "content": msg.content})
            else:
                api_messages.append({"role": "user", "content": msg.content})

        url = self.base_url.rstrip("/") + "//v1/messages"
        headers = {
            "accept": "application/json",
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "messages": api_messages,
        }
        if system_text.strip():
            payload["system"] = system_text.strip()
        if stop:
            payload["stop_sequences"] = stop

        resp = http_requests.post(url, json=payload, headers=headers, timeout=120)
        if resp.status_code != 200:
            raise Exception(f"OneLLM API error {resp.status_code}: {resp.text[:500]}")

        data = resp.json()
        # Extract text from Anthropic-format response
        content_blocks = data.get("content", [])
        text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")

        message = AIMessage(content=text)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models for structured output
class Recommendation(BaseModel):
    """A single recommendation"""
    title: str = Field(description="Clear, actionable title")
    description: str = Field(description="Detailed description explaining why, what, and how")
    servicenow_components: List[str] = Field(description="ServiceNow products, modules, plugins, or tables involved")
    priority: str = Field(description="Priority: high, medium, or low")

class ArchitectureAnalysis(BaseModel):
    """Complete architecture analysis response"""
    analysis: str = Field(description="Comprehensive markdown-formatted architecture analysis with headings")
    recommendations: List[Recommendation] = Field(description="List of actionable recommendations ordered by priority")
    mermaid_diagram: str = Field(description="Mermaid diagram code showing architecture flow")
    implementation_notes: str = Field(description="Implementation considerations including phasing, dependencies, and risks")

class LLMService:
    ANALYSIS_STEPS = [
        "Preparing analysis context",
        "Generating baseline diagram",
        "Querying LLM",
        "Parsing response",
        "Validating architecture",
        "Finalizing results",
    ]

    def __init__(self):
        self.active_model = None
        self.provider = None
        self.model_name = None
        self.ontology = ServiceNowOntology()
        self.validator = ArchitectureValidator(self.ontology)
        self.rule_engine = RuleEngine()
        self._progress = {"step": 0, "total": len(self.ANALYSIS_STEPS), "label": "", "active": False}

    def get_progress(self) -> dict:
        return dict(self._progress)

    def _set_progress(self, step: int):
        self._progress = {"step": step, "total": len(self.ANALYSIS_STEPS), "label": self.ANALYSIS_STEPS[step - 1] if step else "", "active": step > 0}
    
    def _sanitize_mermaid(self, mermaid: str) -> str:
        """Sanitize Mermaid diagram syntax to prevent rendering errors.
        Handles subgraph names, edge labels, and node labels."""
        if not mermaid or len(mermaid.strip()) < 10:
            return mermaid
        
        fixed = mermaid.strip()
        
        # Remove any markdown code blocks
        if "```" in fixed:
            fixed = fixed.replace("```mermaid", "").replace("```", "").strip()
        
        # Ensure it starts with graph TD
        if not fixed.startswith("graph"):
            fixed = "graph TD\n" + fixed
        
        # First pass: fix labels [text] - remove newlines and collapse whitespace
        def fix_label(match):
            return f"[{' '.join(match.group(1).split())}]"
        fixed = re.sub(r'\[([^\]]+)\]', fix_label, fixed)
        
        # Process line by line
        cleaned_lines = []
        for line in fixed.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            
            # Fix subgraph names: remove &, /, (), numbered prefixes
            if stripped.startswith("subgraph "):
                sg_name = stripped[len("subgraph "):]
                sg_name = sg_name.replace("&", "and").replace("/", " ").replace('"', '')
                sg_name = re.sub(r'\([^)]*\)', '', sg_name)  # remove parenthesised text
                sg_name = re.sub(r'^\d+\.\s*', '', sg_name)  # remove leading "1. ", "2. "
                sg_name = " ".join(sg_name.split())
                line = line[:len(line) - len(line.lstrip())] + "subgraph " + sg_name
            
            # Fix edge labels |text|: remove /, &, ()
            if "|" in line:
                def fix_edge_label(match):
                    lbl = match.group(1)
                    lbl = lbl.replace("/", " ").replace("&", "and")
                    lbl = re.sub(r'\([^)]*\)', '', lbl)
                    lbl = " ".join(lbl.split())
                    return f"|{lbl}|"
                line = re.sub(r'\|([^|]+)\|', fix_edge_label, line)
            
            # Fix node labels [text]: remove problematic chars
            if "[" in line and "]" in line:
                parts = line.split("[")
                if len(parts) > 1:
                    label_part = parts[1].split("]")[0]
                    cleaned_label = label_part.replace("\n", " ").replace("\r", " ")
                    cleaned_label = cleaned_label.replace("/", " ").replace("&", "and")
                    cleaned_label = cleaned_label.replace("\\", "").replace('"', '').replace("'", "")
                    cleaned_label = cleaned_label.replace("(", "- ").replace(")", "")
                    cleaned_label = " ".join(cleaned_label.split())
                    line = parts[0] + "[" + cleaned_label + "]" + "]".join(parts[1].split("]")[1:])
            
            cleaned_lines.append(line)
        
        fixed = "\n".join(cleaned_lines)
        
        # Validate it has at least one arrow
        if "-->" not in fixed and "---" not in fixed:
            logger.error("Sanitized Mermaid has no arrows, returning original")
            return mermaid
        
        return fixed
    
    def configure(self, provider: str, api_key: str, model: Optional[str] = None, api_url: Optional[str] = None):
        provider_lower = provider.lower()
        
        try:
            if provider_lower == "openai":
                model_name = model or "gpt-4-turbo-preview"
                self.active_model = ChatOpenAI(
                    model=model_name,
                    temperature=0.7,
                    api_key=api_key
                )
                self.provider = "openai"
                self.model_name = model_name
                logger.info(f"OpenAI model configured: {model_name}")
                
            elif provider_lower == "claude":
                model_name = model or "claude-3-5-sonnet-20241022"
                anthropic_kwargs = {
                    "model": model_name,
                    "temperature": 0.7,
                    "api_key": api_key,
                }
                effective_url = api_url or settings.anthropic_api_url
                if effective_url:
                    anthropic_kwargs["anthropic_api_url"] = effective_url
                    logger.info(f"Anthropic using custom API URL: {effective_url}")
                self.active_model = ChatAnthropic(**anthropic_kwargs)
                self.provider = "claude"
                self.model_name = model_name
                logger.info(f"Claude model configured: {model_name}")
                
            elif provider_lower == "google":
                from langchain_google_genai import ChatGoogleGenerativeAI
                # Try different model name formats for compatibility
                model_name = model or "gemini-pro"
                
                # If user provided a model name, try it first, otherwise try common variants
                models_to_try = [model_name] if model else [
                    "gemini-2.5-flash",
                    "gemini-1.5-pro-latest",
                    "gemini-1.5-flash-latest", 
                    "gemini-pro-latest",
                    "gemini-1.5-pro",
                    "gemini-pro"
                ]
                
                configured = False
                for try_model in models_to_try:
                    try:
                        self.active_model = ChatGoogleGenerativeAI(
                            model=try_model,
                            temperature=0.7,
                            google_api_key=api_key
                        )
                        self.provider = "google"
                        self.model_name = try_model
                        configured = True
                        logger.info(f"Google model configured: {try_model}")
                        break
                    except Exception as e:
                        logger.debug(f"Failed to configure {try_model}: {str(e)[:50]}")
                        continue
                
                if not configured:
                    raise Exception("Could not configure Google Gemini. Please verify your API key has Gemini API access enabled in Google AI Studio.")
                
            elif provider_lower == "onellm":
                if not api_url:
                    raise ValueError("OneLLM requires an API URL (e.g. https://apicid-dev.servicenow.com/v4/onellm/models/anthropic)")
                model_name = model or "claude-3-7-sonnet-20250219"
                self.active_model = ChatOneLLM(
                    base_url=api_url,
                    api_key=api_key,
                    model_name=model_name,
                    temperature=0.7,
                )
                self.provider = "onellm"
                self.model_name = model_name
                logger.info(f"OneLLM configured: {model_name} via {api_url}")
                
            else:
                raise ValueError(f"Unsupported provider: {provider}")
            
            # Validate API key with a minimal test call
            try:
                test_response = self.active_model.invoke([HumanMessage(content="Reply with OK")])
                logger.info(f"API key validated for {provider}")
            except Exception as val_err:
                self.active_model = None
                self.provider = None
                self.model_name = None
                raise Exception(f"API key validation failed: {val_err}")
                
        except Exception as e:
            logger.error(f"Error configuring {provider}: {str(e)}")
            raise
    
    def is_configured(self) -> bool:
        return self.active_model is not None
    
    def get_provider(self) -> Optional[str]:
        return self.provider
    
    def analyze_architecture(
        self,
        query: str,
        servicenow_data: Dict,
        documents: List[Dict],
        web_context: List[Dict]
    ) -> Dict:
        # Log request immediately at function entry
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        request_log = f"/tmp/virgil_request_{timestamp}.txt"
        try:
            with open(request_log, 'w') as f:
                f.write(f"=== ANALYSIS REQUEST ===\n")
                f.write(f"Timestamp: {timestamp}\n")
                f.write(f"Query: {query}\n")
                f.write(f"ServiceNow Apps: {len(servicenow_data.get('applications', []))}\n")
                f.write(f"Documents: {len(documents)}\n")
            logger.info(f"Request logged to: {request_log}")
        except Exception as e:
            logger.error(f"Failed to log request: {e}")
        
        if not self.is_configured():
            raise Exception("No LLM model configured. Please set OPENAI_API_KEY or ANTHROPIC_API_KEY")
        
        self._set_progress(1)  # Step 1: Preparing analysis context
        
        # Detect query type for specialized handling
        query_types = self.ontology.detect_query_type(query)
        logger.info(f"Detected query types: {query_types}")
        
        # Get specialized constraints based on query type
        specialized_constraints = self.ontology.get_specialized_constraints(query_types)
        
        # Run assessment rules against instance data for prompt enrichment
        assessment_findings = self._get_assessment_findings(servicenow_data)
        findings_prompt = self._format_findings_for_prompt(assessment_findings, query_types)
        
        # Use instance summary from the active connection (passed via servicenow_data)
        instance_summary = servicenow_data.get("instance_summary")
        jdbc_metadata = servicenow_data.get("jdbc_metadata")
        if instance_summary:
            logger.info(f"Instance summary from active connection: {instance_summary.get('instance', 'N/A')}, "
                       f"{len(instance_summary.get('applications', []))} apps")
        
        # Get instance-aware recommendations
        installed_apps = servicenow_data.get("applications", [])
        instance_recommendations = self.ontology.get_instance_aware_recommendations(
            [app.get("name", "") for app in installed_apps],
            query_types
        )
        
        system_prompt = f"""You are an expert ServiceNow technical architect and solution consultant with deep knowledge of:
- ServiceNow platform architecture and best practices
- Integration patterns and data flows

CRITICAL SERVICENOW ARCHITECTURAL RULES:
1. CMDB (Configuration Management Database) is ALWAYS foundational - it cannot depend on other components
2. User Management is ALWAYS foundational - required for all authentication
3. Knowledge Base is consumed BY other components (Incident, Case, Portal) - it does NOT consume them
4. Service Portals and Customer Portals sit at the UI layer - they consume services, not provide them
5. Integration Hub and Flow Designer are orchestration layers - they connect components but are not foundational

{specialized_constraints}

INSTANCE CONTEXT:
The user's ServiceNow instance has these applications installed: {', '.join([app.get('name', '') for app in installed_apps[:10]])}

{chr(10).join('- ' + rec for rec in instance_recommendations) if instance_recommendations else ''}

{f'''
CURRENT INSTANCE STATE (from REST API):
- Instance: {instance_summary.get('instance', 'N/A')}
- Total Applications: {len(instance_summary.get('applications', []))}
- Key Capabilities Detected:
  * ITSM: {'Yes' if instance_summary.get('key_capabilities', {}).get('itsm') else 'No'}
  * CSM: {'Yes' if instance_summary.get('key_capabilities', {}).get('csm') else 'No'}
  * HRSD: {'Yes' if instance_summary.get('key_capabilities', {}).get('hrsd') else 'No'}
  * ITOM: {'Yes' if instance_summary.get('key_capabilities', {}).get('itom') else 'No'}
  * CMDB: {'Yes' if instance_summary.get('key_capabilities', {}).get('cmdb') else 'No'}

When providing recommendations, consider what's ALREADY INSTALLED vs. what's NEEDED for the proposed architecture.
Highlight gaps and provide specific migration steps.
''' if instance_summary else ''}

{f'''
INSTANCE STRUCTURAL METADATA (from JDBC):
- Active Plugins: {len(jdbc_metadata.get('plugins', []))}
- Table Relationships: {len(jdbc_metadata.get('relationships', []))}
- Custom Tables: {len(jdbc_metadata.get('custom_tables', []))}

Key Usage Insights:
{chr(10).join(f"  * {stat['table_name']}: {stat['row_count']} records" for stat in jdbc_metadata.get('usage_stats', [])[:5]) if jdbc_metadata and jdbc_metadata.get('usage_stats') else '  * No usage data available'}

Customizations Detected:
{chr(10).join(f"  * {table['name']} ({table.get('label', 'N/A')})" for table in jdbc_metadata.get('custom_tables', [])[:5]) if jdbc_metadata and jdbc_metadata.get('custom_tables') else '  * No custom tables detected'}

Use this structural data to provide specific, instance-aware recommendations.
''' if jdbc_metadata else ''}

{findings_prompt}

ANALYSIS DEPTH REQUIREMENTS:
Your analysis must be thorough but CONCISE. Aim for focused insight, not length.
Keep the total analysis under 1500 words — prioritize architectural decisions and trade-offs over background descriptions.
For each major capability area mentioned in the query, address:
- Current state: What exists today on this instance (installed apps, data volumes, gaps)
- Target state: What the architecture should look like
- Gap analysis: What's missing and needs to be implemented
- Trade-offs: Key architectural decisions with pros/cons (e.g., single vs dual instance, domain separation vs ACLs, shared vs dedicated portals)
- Dependencies: What must be in place before other components can be deployed

When multiple ServiceNow products are involved (e.g., CSM + ITSM, HRSD + ITSM), explicitly address:
- How they share foundational components (CMDB, User Management, Knowledge Base)
- Data segregation between public-facing and internal operations
- Workflow crossover points (e.g., a customer case escalating to an internal incident)
- User experience separation (external customers vs internal agents)

Your task is to provide:
1. **Analysis**: A structured architectural analysis with markdown headings covering current state, proposed architecture, key decisions, data flows, compliance, and risks
2. **Recommendations** (4-8 items): Specific, actionable recommendations with concrete ServiceNow products, tables, and configurations — not generic advice
3. **Architecture Diagram**: Components for Mermaid diagram generation
4. **Implementation Notes**: Phasing, dependencies, migration steps, testing strategy, and configuration decisions

Be specific, practical, and reference actual ServiceNow tables, applications, and components. Avoid generic statements like "implement best practices" — instead specify WHICH practices and HOW."""

        servicenow_summary = self._summarize_servicenow_data(servicenow_data)
        documents_summary = self._summarize_documents(documents)
        web_summary = self._summarize_web_context(web_context)
        
        user_prompt = f"""User Query: {query}

Available ServiceNow Instance Data:
{servicenow_summary}

Relevant Documentation:
{documents_summary}

Additional Context from Web Search:
{web_summary}

Please provide a THOROUGH response covering all aspects of this query.

{self._build_analysis_guidance(query_types)}

FORMAT YOUR ANALYSIS using markdown headings (## Current State Assessment, ## Proposed Architecture, ## Key Architectural Decisions, etc.)

For RECOMMENDATIONS, provide 4-8 specific items. Each recommendation must explain:
- WHY it is needed (the problem or gap it addresses)
- WHAT to implement (specific ServiceNow product, plugin, or table)
- HOW to implement it (configuration approach, not just "install it")

Format your response as JSON with the following structure:
{{
    "analysis": "markdown-formatted analysis with ## headings",
    "recommendations": [
        {{
            "title": "clear actionable title",
            "description": "description with WHY, WHAT, and HOW",
            "servicenow_components": ["specific_product_or_table_1", "specific_product_or_table_2"],
            "priority": "high|medium|low"
        }}
    ],
    "architecture_components": [
        {{
            "name": "component name",
            "type": "database|service|integration|ui|workflow",
            "description": "component description",
            "connections": ["connected_component1", "connected_component2"]
        }}
    ],
    "mermaid_diagram": "REQUIRED: Valid Mermaid flowchart syntax starting with 'graph TD' and using --> arrows between nodes. Example: graph TD\\n    A[Component1] --> B[Component2]\\n    B --> C[Component3]",
    "implementation_notes": "phasing, dependencies, migration steps, testing strategy"
}}

CRITICAL JSON FORMATTING: You MUST escape all double quotes inside JSON string values with a backslash (e.g. \"example\"). Do NOT use unescaped quotes inside strings. This is essential for valid JSON output.

CRITICAL MERMAID REQUIREMENTS:
- MUST start with "graph TD" on first line
- MUST use --> arrows to connect nodes (e.g., A --> B)
- Node format: ID[Label Text] where ID is a single letter or short identifier
- Subgraph names MUST NOT be quoted (use "subgraph Users" not "subgraph \"1. Users\"")
- Example valid diagram:
  graph TD
      A[User Portal] --> B[ServiceNow CSM]
      B --> C[CMDB]
      A --> D[ITSM]
      D --> C

MERMAID DIAGRAM HARD LIMITS:
- MAXIMUM 15 arrows/connections in the entire diagram. Fewer is better.
- MAXIMUM 10 nodes. Group related modules into single nodes (e.g., use one "ITSM" node, NOT separate Incident/Problem/Change nodes)
- MAXIMUM 4 subgraphs. Combine related layers.
- Each node should have MAXIMUM 3 outgoing connections.
- Orchestration components (Integration Hub, Flow Designer) go INSIDE the Application layer subgraph, not in a separate subgraph.

MERMAID DIAGRAM GUIDELINES FOR CLARITY:
- Focus on primary architectural flows: User → Portal → Application → Platform → Data
- Prioritize key relationships: "runs on", "creates", "resolves using"
- Drop secondary relationships like "accesses", "manages", "connects" if they would exceed the arrow limit
- Use subgraphs to organize components by layer (e.g., "subgraph Users" not "subgraph \"1. Users\"")

Priority levels mean:
- HIGH: Critical for core functionality, must implement first
- MEDIUM: Important for complete solution, implement after high priority
- LOW: Nice-to-have enhancements, implement if time/budget allows

For mermaid_diagram, you MUST create an architecture diagram with SEMANTIC RELATIONSHIPS.

ALLOWED RELATIONSHIP LABELS (use ONLY these exact labels on arrows):
- "runs on" — application runs on platform (e.g., ITSM -->|runs on| Platform)
- "creates" / "creates cases" / "creates tickets" / "creates requests" — portal creates work items
- "references" — application reads data from foundational component (e.g., ITSM -->|references| CMDB)
- "resolves using" — application uses knowledge to resolve issues
- "accesses" — user accesses a portal
- "authenticates via" — portal authenticates through identity management
- "consumes" — portal consumes content (e.g., Portal -->|consumes| Knowledge Base)
- "populates" — discovery/mapping populates CMDB
- "integrates with" — integration hub connects to external systems

DO NOT USE vague labels like "leverages", "manages", "uses", "utilizes", "supports", "feeds", "provides".
These will be automatically replaced or removed by the validator.

REQUIRED RELATIONSHIPS (must be present if these nodes exist):
- Every application node (ITSM, CSM, HRSD, etc.) MUST have "runs on" → Platform
- Every portal node MUST have "authenticates via" → User Management/Identity
- User Management/Identity MUST be INSIDE the Foundation subgraph, not outside it

{self.ontology.get_mermaid_guidance(query_types)}

Remember:
- Use subgraphs to show layers
- Label arrows with ONLY the allowed relationship types listed above
- CMDB, Platform, Knowledge Base, and User Management are FOUNDATIONAL - they ALL go inside the Foundation subgraph at the bottom
- NO bidirectional arrows unless peer-to-peer integration
- NO cross-connections between segregated paths (Public ≠ ITSM, Internal ≠ CSM)
- STRICT LIMIT: Maximum 15 arrows total. If you exceed this, remove the least important connections."""

        # Get query-relevant subgraph from ontology
        from services.architecture_validator import LABEL_REPLACEMENTS
        relevant_subgraph = self.ontology.get_relevant_subgraph(query, query_types)

        # Build label replacement mapping for display
        label_replacements = {k: v for k, v in LABEL_REPLACEMENTS.items()}

        # Capture ontology constraints for the pipeline
        ontology_constraints = {
            "stage": "Ontology Constraints",
            "description": "Rules injected into the LLM prompt before generation, derived from the ServiceNow ontology graph",
            "mermaid": relevant_subgraph.get("example_diagram"),
            "constraints": {
                "hard_limits": {
                    "max_arrows": 15,
                    "max_nodes": 10,
                    "max_subgraphs": 4,
                    "max_outgoing_per_node": 3
                },
                "allowed_labels": [
                    "runs on", "creates", "creates cases", "creates tickets",
                    "creates requests", "references", "resolves using",
                    "accesses", "authenticates via", "consumes", "populates",
                    "integrates with", "connects to", "depends on"
                ],
                "label_replacements": label_replacements,
                "architectural_rules": [
                    "CMDB is always foundational, cannot depend on other components",
                    "User Management is always foundational, required for authentication",
                    "Knowledge Base is consumed BY other components, never consumes them",
                    "Portals sit at UI layer, they consume services not provide them",
                    "No bidirectional arrows unless peer-to-peer integration",
                    "No cross-connections between segregated paths (Public ≠ ITSM, Internal ≠ CSM)",
                    "Every application must 'runs on' Platform",
                    "Every portal must 'authenticates via' User Management"
                ],
                "layer_order": ["Users", "Portals/UI", "Applications", "Orchestration", "Platform", "Foundation/Data"],
                "query_relevant_subgraph": {
                    "nodes": relevant_subgraph.get("nodes", []),
                    "edges": relevant_subgraph.get("edges", []),
                    "segregation_rules": relevant_subgraph.get("segregation_rules", []),
                    "total_nodes": relevant_subgraph.get("total_nodes", 0),
                    "total_edges": relevant_subgraph.get("total_edges", 0),
                },
                "ontology_stats": {
                    "nodes": len(self.ontology._nodes),
                    "edges": len(self.ontology._edges),
                    "relationship_types": list(set(e.rel_type for e in self.ontology._edges))
                }
            },
            "changes": [
                f"Ontology graph: {len(self.ontology._nodes)} nodes, {len(self.ontology._edges)} edges",
                f"Query-relevant subgraph: {relevant_subgraph.get('total_nodes', 0)} nodes, {relevant_subgraph.get('total_edges', 0)} edges",
                "Hard limits: max 15 arrows, 10 nodes, 4 subgraphs, 3 outgoing per node",
                f"Allowed labels: {', '.join(['runs on', 'creates', 'references', 'resolves using', 'accesses', 'authenticates via', 'consumes', 'populates', 'integrates with'])}",
                f"Blocked labels with replacements: {len(label_replacements)} vague labels auto-mapped to standard vocabulary",
                "Required: apps must 'runs on' Platform, portals must 'authenticates via' User Management",
                "Foundational components (CMDB, Platform, KB, User Mgmt) must be at bottom layer"
            ]
        }

        self._set_progress(2)  # Step 2: Generating baseline diagram
        
        # --- Baseline: Unconstrained LLM call (no guardrails) ---
        baseline_stage = None
        try:
            bare_prompt = f"""Generate a Mermaid architecture diagram for this ServiceNow requirement.
Use 'graph TD' format with --> arrows. Include relevant ServiceNow components.

Requirement: {query}

Return ONLY the Mermaid diagram code, nothing else. Start with 'graph TD'."""

            logger.info("Baseline: Generating unconstrained diagram (no guardrails)")
            bare_response = self.active_model.invoke([HumanMessage(content=bare_prompt)])
            bare_mermaid = bare_response.content.strip()
            # Strip markdown fences if present
            if "```" in bare_mermaid:
                bare_mermaid = bare_mermaid.replace("```mermaid", "").replace("```", "").strip()
            # Extract just the graph portion if there's extra text
            if "graph " in bare_mermaid:
                idx = bare_mermaid.index("graph ")
                bare_mermaid = bare_mermaid[idx:]

            baseline_stage = {
                "stage": "Baseline",
                "description": "Unconstrained LLM output with NO ontology rules, NO hard limits, NO label vocabulary — raw baseline for comparison",
                "mermaid": bare_mermaid,
                "changes": [
                    "No hard limits enforced",
                    "No label vocabulary restrictions",
                    "No architectural rules applied",
                    "No anti-pattern detection",
                    "No post-processing or validation"
                ]
            }
            logger.info(f"Baseline diagram generated: {len(bare_mermaid)} chars")
        except Exception as p0_err:
            logger.warning(f"Baseline generation failed (non-critical): {str(p0_err)}")

        self._set_progress(3)  # Step 3: Querying LLM
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            # Use structured output with Pydantic model
            try:
                structured_llm = self.active_model.with_structured_output(ArchitectureAnalysis)
                response = structured_llm.invoke(messages)
                
                # Convert Pydantic model to dict
                result = {
                    "analysis": response.analysis,
                    "recommendations": [
                        {
                            "title": rec.title,
                            "description": rec.description,
                            "servicenow_components": rec.servicenow_components,
                            "priority": rec.priority
                        }
                        for rec in response.recommendations
                    ],
                    "mermaid_diagram": response.mermaid_diagram,
                    "implementation_notes": response.implementation_notes
                }
                
                logger.info("Successfully generated structured response")
                
                self._set_progress(5)  # Step 5: Validating architecture
                
                # Write full response to debug file
                debug_file = f"/tmp/llm_response_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(debug_file, 'w') as f:
                    json.dump(result, f, indent=2)
                logger.info(f"Full LLM response saved to: {debug_file}")
                
                # Add visible validation to recommendations
                validation_warnings = []
                
                # Check analysis for foundational components
                analysis_text = result.get("analysis", "").lower()
                if "cmdb" not in analysis_text and "configuration" not in analysis_text:
                    validation_warnings.append("⚠️ CMDB not mentioned - most ServiceNow architectures require CMDB as foundation")
                
                # Check Mermaid diagram syntax
                mermaid = result.get("mermaid_diagram", "")
                if mermaid and not mermaid.strip().startswith("graph"):
                    validation_warnings.append("⚠️ Mermaid diagram may have syntax issues - should start with 'graph TD' or 'graph LR'")
                
                # Add validation warnings as a high-priority recommendation
                if validation_warnings:
                    logger.warning(f"Validation warnings: {validation_warnings}")
                    result["recommendations"].insert(0, {
                        "title": "🔍 Architecture Review Notes",
                        "description": "Please review these architectural considerations:\n\n" + 
                                     "\n".join(f"• {warning}" for warning in validation_warnings),
                        "servicenow_components": [],
                        "priority": "high"
                    })
                
                # Fix common Mermaid syntax errors
                diagram_pipeline = []
                if baseline_stage:
                    diagram_pipeline.append(baseline_stage)
                diagram_pipeline.append(ontology_constraints)
                try:
                    mermaid = result.get("mermaid_diagram", "")
                    
                    if not mermaid or len(mermaid.strip()) < 10:
                        # Generate a simple fallback diagram
                        logger.warning("No valid Mermaid diagram from LLM, generating fallback")
                        mermaid = """graph TD
    A[User Requirements] --> B[ServiceNow Platform]
    B --> C[CMDB]
    B --> D[Applications]
    D --> C"""
                        result["mermaid_diagram"] = mermaid
                        diagram_pipeline.append({"stage": "LLM Output", "description": "No valid diagram from LLM, using fallback", "mermaid": mermaid, "changes": ["Generated fallback diagram"]})
                    else:
                        # Stage 1: Raw LLM output
                        diagram_pipeline.append({"stage": "LLM Output", "description": "Raw diagram from the language model before any processing", "mermaid": mermaid, "changes": []})
                        
                        # Save original Mermaid to file for debugging
                        mermaid_file = f"/tmp/mermaid_original_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                        with open(mermaid_file, 'w') as f:
                            f.write(mermaid)
                        logger.info(f"Original Mermaid diagram saved to: {mermaid_file}")
                        logger.info(f"Original Mermaid diagram:\n{mermaid}")
                        
                        fixed_mermaid = self._sanitize_mermaid(mermaid)
                        
                        # Stage 2: After sanitization
                        sanitize_changes = []
                        if fixed_mermaid != mermaid:
                            mermaid_fixed_file = f"/tmp/mermaid_fixed_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                            with open(mermaid_fixed_file, 'w') as f:
                                f.write(fixed_mermaid)
                            logger.info(f"Fixed Mermaid diagram saved to: {mermaid_fixed_file}")
                            logger.info(f"Fixed Mermaid diagram:\n{fixed_mermaid}")
                            sanitize_changes.append("Syntax errors corrected")
                        else:
                            sanitize_changes.append("No syntax issues found")
                        diagram_pipeline.append({"stage": "Syntax Sanitizer", "description": "Fixed Mermaid syntax issues (special characters, arrow format, node IDs)", "mermaid": fixed_mermaid, "changes": sanitize_changes})
                        
                        result["mermaid_diagram"] = fixed_mermaid
                        
                        # Validate the Mermaid diagram against ontology rules
                        try:
                            is_valid, validation_errors, corrected_diagram, rules_applied = self.validator.validate_mermaid_diagram(fixed_mermaid)
                            
                            # Stage 3: After validation
                            validator_changes = []
                            if not is_valid:
                                logger.warning(f"Mermaid validation found {len(validation_errors)} issues")
                                if 'validation_warnings' not in result:
                                    result['validation_warnings'] = []
                                result['validation_warnings'].extend(validation_errors)
                                validator_changes = validation_errors[:]
                                
                                # Use the corrected diagram if the validator produced one
                                if corrected_diagram:
                                    result["mermaid_diagram"] = corrected_diagram
                                    corrected_file = f"/tmp/mermaid_validated_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                                    with open(corrected_file, 'w') as f:
                                        f.write(corrected_diagram)
                                    logger.info(f"Validator-corrected diagram saved to: {corrected_file}")
                                    logger.info(f"Validator-corrected diagram:\n{corrected_diagram}")
                            else:
                                logger.info("Mermaid diagram passed validation")
                                validator_changes.append("Ontology rules already satisfied — prompt constraints prevented issues pre-generation")
                            
                            # Attach rules_applied to the ontology constraints stage
                            ontology_constraints["rules_applied"] = rules_applied
                            
                            diagram_pipeline.append({"stage": "Ontology Validator", "description": "Enforced architectural rules: label vocabulary, arrow limits, anti-patterns, required relationships", "mermaid": result["mermaid_diagram"], "changes": validator_changes, "rules_applied": rules_applied})
                            
                            # Validate recommendations against instance data
                            if jdbc_metadata:
                                rec_warnings = self.validator.validate_recommendations(
                                    result.get('recommendations', []),
                                    jdbc_metadata
                                )
                                if rec_warnings:
                                    logger.info(f"Recommendation validation: {len(rec_warnings)} warnings")
                                    if 'validation_warnings' not in result:
                                        result['validation_warnings'] = []
                                    result['validation_warnings'].extend(rec_warnings)
                        except Exception as val_error:
                            logger.error(f"Validation error: {str(val_error)}")
                            diagram_pipeline.append({"stage": "Ontology Validator", "description": "Validation encountered an error", "mermaid": fixed_mermaid, "changes": [f"Validator error: {str(val_error)}"]})
                
                except Exception as mermaid_error:
                    logger.error(f"Mermaid processing failed: {str(mermaid_error)}")
                    # Use simple fallback if processing crashes
                    result["mermaid_diagram"] = """graph TD
    A[User Requirements] --> B[ServiceNow Platform]
    B --> C[CMDB]
    B --> D[Applications]
    D --> C"""
                
                # Attach diagram pipeline to result
                if diagram_pipeline:
                    result["diagram_pipeline"] = diagram_pipeline
                
                # Validate architecture against ServiceNow domain knowledge
                if "architecture_components" in result or hasattr(response, 'architecture_components'):
                    arch_components = result.get("architecture_components", [])
                    if hasattr(response, 'architecture_components'):
                        # Convert Pydantic models if needed
                        arch_components = [
                            {
                                "name": comp.name if hasattr(comp, 'name') else comp.get("name", ""),
                                "type": comp.type if hasattr(comp, 'type') else comp.get("type", ""),
                                "connections": comp.connections if hasattr(comp, 'connections') else comp.get("connections", [])
                            }
                            for comp in (response.architecture_components if hasattr(response, 'architecture_components') else [])
                        ]
                    
                    validation = self.ontology.validate_architecture(arch_components)
                    
                    if not validation["valid"]:
                        logger.warning(f"Architecture validation found errors: {validation['errors']}")
                        # Add validation warnings to recommendations
                        result["recommendations"].insert(0, {
                            "title": "Architecture Validation Issues",
                            "description": "The following architectural issues were detected:\n" + 
                                         "\n".join(f"- {error}" for error in validation["errors"]),
                            "servicenow_components": [],
                            "priority": "high"
                        })
                    
                    if validation["warnings"]:
                        logger.info(f"Architecture validation warnings: {validation['warnings']}")
                
                self._set_progress(6)  # Step 6: Finalizing results
                
                # Post-validate recommendations: confidence tagging + ontology validation
                try:
                    recs = result.get("recommendations", [])
                    recs = self._tag_recommendation_confidence(recs, assessment_findings)
                    recs = self._validate_recommendation_components(recs, servicenow_data)
                    result["recommendations"] = recs
                    logger.info(f"Recommendation validation: {sum(1 for r in recs if r.get('confidence') == 'rule-backed')} rule-backed, "
                               f"{sum(1 for r in recs if r.get('confidence') == 'ontology-validated')} ontology-validated, "
                               f"{sum(1 for r in recs if r.get('confidence') == 'llm-generated')} llm-generated")
                except Exception as tag_err:
                    logger.warning(f"Recommendation tagging failed (non-critical): {tag_err}")
                
                # Log successful completion
                success_log = f"/tmp/virgil_success_{timestamp}.txt"
                try:
                    with open(success_log, 'w') as f:
                        f.write(f"Analysis completed successfully\n")
                        f.write(f"Mermaid diagram length: {len(result.get('mermaid_diagram', ''))}\n")
                        f.write(f"Recommendations: {len(result.get('recommendations', []))}\n")
                    logger.info(f"Success logged to: {success_log}")
                except:
                    pass
                
            except Exception as e:
                # Fallback to regular response if structured output not supported
                logger.warning(f"Structured output failed, falling back to JSON parsing: {str(e)}")
                self._set_progress(3)  # Still on step 3 in fallback
                response = self.active_model.invoke(messages)
                # response.content is Union[str, List[Union[str, Dict]]]
                if isinstance(response.content, str):
                    response_text = response.content
                elif isinstance(response.content, list):
                    parts = []
                    for part in response.content:
                        if isinstance(part, str):
                            parts.append(part)
                        elif isinstance(part, dict):
                            parts.append(part.get("text", ""))
                        else:
                            parts.append(str(part))
                    response_text = "".join(parts)
                else:
                    response_text = str(response.content)
                
                # Save raw response for debugging
                raw_file = f"/tmp/llm_raw_response_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                with open(raw_file, 'w') as f:
                    f.write(response_text)
                logger.info(f"Raw LLM response saved to: {raw_file}")
                
                self._set_progress(4)  # Step 4: Parsing response
                
                # Try to parse JSON from response
                try:
                    json_text = response_text
                    # Strip code fences if present
                    if "```json" in json_text:
                        start = json_text.find("```json") + 7
                        end = json_text.rfind("```")
                        if end > start:
                            json_text = json_text[start:end].strip()
                    elif not json_text.strip().startswith("{"):
                        # Find the JSON object in the response
                        brace_start = json_text.find("{")
                        if brace_start >= 0:
                            json_text = json_text[brace_start:]
                    
                    result = json.loads(json_text, strict=False)
                    logger.info("Successfully parsed JSON response")
                except (json.JSONDecodeError, Exception) as je:
                    logger.warning(f"JSON parsing failed ({je}), using regex field extraction")
                    result = self._extract_fields_from_text(response_text)
                
                # Save parsed result for debugging
                debug_file = f"/tmp/llm_response_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                try:
                    with open(debug_file, 'w') as f:
                        json.dump(result, f, indent=2)
                except Exception:
                    pass
                
                if "mermaid_diagram" not in result:
                    result["mermaid_diagram"] = ""
                
                self._set_progress(5)  # Step 5: Validating architecture
                
                # Sanitize and log Mermaid diagram from fallback path
                fallback_pipeline = []
                if baseline_stage:
                    fallback_pipeline.append(baseline_stage)
                fallback_pipeline.append(ontology_constraints)
                mermaid = result.get("mermaid_diagram", "")
                if mermaid:
                    fallback_pipeline.append({"stage": "LLM Output", "description": "Raw diagram from the language model before any processing", "mermaid": mermaid, "changes": []})
                    
                    fixed_mermaid = self._sanitize_mermaid(mermaid)
                    sanitize_changes = ["Syntax errors corrected"] if fixed_mermaid != mermaid else ["No syntax issues found"]
                    fallback_pipeline.append({"stage": "Syntax Sanitizer", "description": "Fixed Mermaid syntax issues", "mermaid": fixed_mermaid, "changes": sanitize_changes})
                    result["mermaid_diagram"] = fixed_mermaid
                    
                    try:
                        is_valid, validation_errors, corrected_diagram, rules_applied = self.validator.validate_mermaid_diagram(fixed_mermaid)
                        validator_changes = []
                        if not is_valid:
                            validator_changes = validation_errors[:]
                            if corrected_diagram:
                                result["mermaid_diagram"] = corrected_diagram
                        else:
                            validator_changes.append("Ontology rules already satisfied")
                        ontology_constraints["rules_applied"] = rules_applied
                        fallback_pipeline.append({"stage": "Ontology Validator", "description": "Enforced architectural rules", "mermaid": result["mermaid_diagram"], "changes": validator_changes, "rules_applied": rules_applied})
                    except Exception as val_err:
                        logger.error(f"Fallback validation error: {str(val_err)}")
                
                if fallback_pipeline:
                    result["diagram_pipeline"] = fallback_pipeline
                
                self._set_progress(6)  # Step 6: Finalizing results
                
                # Post-validate recommendations (fallback path)
                try:
                    recs = result.get("recommendations", [])
                    recs = self._tag_recommendation_confidence(recs, assessment_findings)
                    recs = self._validate_recommendation_components(recs, servicenow_data)
                    result["recommendations"] = recs
                except Exception as tag_err:
                    logger.warning(f"Recommendation tagging failed (non-critical): {tag_err}")
            
            # Post-process analysis text
            if "analysis" in result and result["analysis"]:
                analysis = result["analysis"]
                # Strip embedded JSON the LLM sometimes dumps into analysis text
                for marker in ['{\n    "recommendations"', '{"recommendations"', '{\n  "title"']:
                    cut = analysis.find(marker)
                    if cut > 0:
                        analysis = analysis[:cut].rstrip()
                        break
                result["analysis"] = analysis
            
            self._set_progress(0)  # Done
            return result
        except Exception as e:
            self._set_progress(0)  # Reset on error
            import traceback
            error_log = f"/tmp/virgil_error_{timestamp}.txt"
            error_details = f"Error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            try:
                with open(error_log, 'w') as f:
                    f.write(error_details)
                logger.error(f"Error logged to: {error_log}")
            except:
                pass
            logger.error(f"Architecture analysis failed: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise
    
    def _summarize_servicenow_data(self, data: Dict) -> str:
        summary = []
        
        tables = data.get("tables", [])
        if tables:
            summary.append(f"Available Tables ({len(tables)}): {', '.join(tables[:20])}")
            if len(tables) > 20:
                summary.append(f"... and {len(tables) - 20} more tables")
        
        apps = data.get("applications", [])
        if apps:
            app_names = [app.get("name", "Unknown") for app in apps[:10]]
            summary.append(f"\nInstalled Applications ({len(apps)}): {', '.join(app_names)}")
            if len(apps) > 10:
                summary.append(f"... and {len(apps) - 10} more applications")
            
            # Detect demo/test instance
            demo_patterns = ["demo", "test", "sample", "example", "star wars", "90s rock",
                           "make a wish", "dummy", "postman"]
            demo_apps = [a.get("name", "") for a in apps
                        if any(p in a.get("name", "").lower() or p in a.get("scope", "").lower()
                              for p in demo_patterns)]
            if demo_apps and len(demo_apps) / len(apps) > 0.15:
                summary.append(f"\n⚠ INSTANCE TYPE WARNING: {len(demo_apps)} of {len(apps)} apps "
                             f"({len(demo_apps)*100//len(apps)}%) are demo/test artifacts "
                             f"(e.g., {', '.join(demo_apps[:3])}). "
                             f"This appears to be a DEMO or SANDBOX instance — "
                             f"the app inventory is NOT representative of production. "
                             f"Clearly state this in your analysis and do not treat demo apps as custom development.")
            
            # Flag notable signals that might be missed
            global_apps = [a.get("name", "") for a in apps if a.get("scope") == "global"]
            if global_apps:
                summary.append(f"\nGlobal-Scope Applications: {', '.join(global_apps)}")
        
        components = data.get("components", {})
        for comp_type, comp_list in components.items():
            if comp_list:
                summary.append(f"\n{comp_type.replace('_', ' ').title()} ({len(comp_list)})")
        
        # Flag REST-only data limitations
        if data.get("connection_mode") == "rest_only":
            summary.append("\n⚠ DATA LIMITATION: Connected via REST API only. "
                         "Table-level record counts, usage statistics, plugin inventory, "
                         "and custom table detection are NOT available. "
                         "Acknowledge this limitation in your analysis.")
        
        return "\n".join(summary) if summary else "No ServiceNow data available"
    
    def _extract_fields_from_text(self, text: str) -> Dict:
        """Extract fields from JSON-like LLM output using field-boundary detection.
        Uses str.find instead of regex to handle unescaped quotes in long text."""
        result = {
            "analysis": "",
            "recommendations": [],
            "mermaid_diagram": "",
            "implementation_notes": ""
        }
        
        # Strip code fences if present
        clean = text
        if "```" in clean:
            fence_start = clean.find("```")
            newline_after = clean.find("\n", fence_start)
            if newline_after >= 0:
                clean = clean[newline_after + 1:]
            end_fence = clean.rfind("```")
            if end_fence > 0:
                clean = clean[:end_fence]
        
        # Find field positions by looking for "fieldname": pattern
        field_names = ["analysis", "recommendations", "architecture_components",
                       "mermaid_diagram", "implementation_notes"]
        field_positions = []
        for name in field_names:
            pattern = f'"{name}"'
            search_from = 0
            while True:
                pos = clean.find(pattern, search_from)
                if pos < 0:
                    break
                # Verify it's a JSON key (followed by colon)
                after = clean[pos + len(pattern):pos + len(pattern) + 10].lstrip()
                if after.startswith(":"):
                    field_positions.append((pos, name))
                    break
                search_from = pos + 1
        
        field_positions.sort()
        
        for i, (pos, name) in enumerate(field_positions):
            # Find the colon and start of value
            colon_pos = clean.find(":", pos + len(name) + 2)
            if colon_pos < 0:
                continue
            value_start = colon_pos + 1
            # Skip whitespace
            while value_start < len(clean) and clean[value_start] in ' \t\n\r':
                value_start += 1
            
            # Value ends just before the next field (or end of object)
            if i + 1 < len(field_positions):
                # Find the comma separator before the next field
                next_pos = field_positions[i + 1][0]
                raw_segment = clean[value_start:next_pos].rstrip()
                # Strip trailing comma
                if raw_segment.endswith(","):
                    raw_segment = raw_segment[:-1].rstrip()
            else:
                # Last field — ends at closing brace
                end_brace = clean.rfind("}")
                raw_segment = clean[value_start:end_brace].rstrip() if end_brace > value_start else clean[value_start:].rstrip()
                if raw_segment.endswith(","):
                    raw_segment = raw_segment[:-1].rstrip()
            
            # Process based on field type
            if name in ("analysis", "mermaid_diagram", "implementation_notes"):
                # String value: strip surrounding quotes
                if raw_segment.startswith('"'):
                    raw_segment = raw_segment[1:]
                if raw_segment.endswith('"'):
                    raw_segment = raw_segment[:-1]
                # Unescape JSON string escapes
                raw_segment = (raw_segment
                    .replace('\\n', '\n')
                    .replace('\\t', '\t')
                    .replace('\\"', '"')
                    .replace('\\\\', '\\'))
                result[name] = raw_segment
            
            elif name == "recommendations":
                # Array value: try json.loads on the raw segment
                try:
                    result["recommendations"] = json.loads(raw_segment, strict=False)
                except Exception:
                    # If the array itself has unescaped quotes, extract individual objects
                    recs = []
                    # Find each {"title": ...} block
                    obj_start = raw_segment.find("{")
                    while obj_start >= 0:
                        # Find matching } by counting braces
                        depth = 0
                        for j in range(obj_start, len(raw_segment)):
                            if raw_segment[j] == "{":
                                depth += 1
                            elif raw_segment[j] == "}":
                                depth -= 1
                                if depth == 0:
                                    obj_text = raw_segment[obj_start:j + 1]
                                    try:
                                        recs.append(json.loads(obj_text, strict=False))
                                    except Exception:
                                        pass
                                    obj_start = raw_segment.find("{", j + 1)
                                    break
                        else:
                            break
                    if recs:
                        result["recommendations"] = recs
        
        logger.info(f"Field extraction: analysis={len(result.get('analysis', ''))} chars, "
                    f"recs={len(result.get('recommendations', []))}, "
                    f"diagram={len(result.get('mermaid_diagram', ''))} chars")
        return result
    
    def _build_analysis_guidance(self, query_types: List[str]) -> str:
        """Build dynamic analysis guidance based on detected query types.
        Tells the LLM exactly what dimensions to cover for the specific query."""
        sections = []
        
        if len(query_types) > 1 and "general" not in query_types:
            sections.append(
                "This is a MULTI-DOMAIN query spanning: " + ", ".join(query_types).upper() + ".\n"
                "Your analysis MUST address each domain individually AND their intersections."
            )
        
        guidance = {
            "itsm": (
                "FOR ITSM, address:\n"
                "- Which ITSM modules are needed (Incident, Problem, Change, Request, Knowledge)\n"
                "- Service Catalog structure and request fulfillment workflows\n"
                "- How CMDB CIs relate to incident/problem/change records\n"
                "- Agent experience: Service Portal vs Agent Workspace vs classic UI\n"
                "- SLA definitions and OLA/UC considerations"
            ),
            "csm": (
                "FOR CSM, address:\n"
                "- Customer Portal design and self-service capabilities\n"
                "- Account-Contact-Case data model vs ITSM's User-Incident model\n"
                "- Customer-facing Knowledge Base with ACL-controlled visibility\n"
                "- Case escalation paths (when does a case become an internal incident?)\n"
                "- Agent Workspace for CSM agents\n"
                "- Entitlements and SLA management for customer contracts"
            ),
            "compliance": (
                "FOR COMPLIANCE/FEDRAMP, address:\n"
                "- FedRAMP authorization boundary and data classification (IL2/IL4/IL5)\n"
                "- Single instance vs dual instance: present BOTH options with clear pros/cons\n"
                "- Domain separation configuration if single instance\n"
                "- ACL strategy for data segregation between public and internal data\n"
                "- Audit trail requirements (sys_audit, transaction logs)\n"
                "- Encryption requirements (at rest and in transit)\n"
                "- Authentication: MFA, SSO/SAML for both internal and external users"
            ),
            "integration": (
                "FOR INTEGRATION, address:\n"
                "- Integration patterns: REST vs SOAP vs MID Server vs Integration Hub spokes\n"
                "- Data synchronization direction and frequency\n"
                "- Error handling and retry mechanisms\n"
                "- Authentication for external system connections"
            ),
            "portal": (
                "FOR PORTAL, address:\n"
                "- Portal type: Service Portal vs Customer Portal vs Employee Center\n"
                "- User experience design and branding\n"
                "- Authentication flow for portal users\n"
                "- Content management and knowledge article visibility"
            ),
            "hrsd": (
                "FOR HRSD, address:\n"
                "- Employee lifecycle management\n"
                "- HR case types and assignment rules\n"
                "- Employee Center portal configuration\n"
                "- Integration with ITSM for IT-related onboarding tasks"
            ),
            "itom": (
                "FOR ITOM, address:\n"
                "- Discovery and Service Mapping configuration\n"
                "- CMDB population strategy and CI class structure\n"
                "- Event Management and alert correlation\n"
                "- Health Log Analytics integration"
            ),
            "secops": (
                "FOR SECOPS, address:\n"
                "- Security Incident Response workflows\n"
                "- Vulnerability Response integration with scanners\n"
                "- Threat Intelligence integration\n"
                "- SIEM integration patterns"
            ),
        }
        
        for qt in query_types:
            if qt in guidance:
                sections.append(guidance[qt])
        
        # Add cross-domain guidance when multiple types detected
        cross_domain = []
        if "csm" in query_types and "itsm" in query_types:
            cross_domain.append(
                "CSM ↔ ITSM INTERSECTION:\n"
                "- How customer cases escalate to internal incidents\n"
                "- Shared vs separate Knowledge Bases\n"
                "- Shared CMDB for service-aware case routing\n"
                "- Agent experience: do CSM and ITSM agents use same or different workspaces?\n"
                "- Reporting across both domains"
            )
        if "compliance" in query_types and ("csm" in query_types or "itsm" in query_types):
            cross_domain.append(
                "COMPLIANCE ↔ SERVICE MANAGEMENT INTERSECTION:\n"
                "- How FedRAMP requirements affect the CSM/ITSM architecture choice\n"
                "- Data residency and sovereignty constraints\n"
                "- Impact of compliance on portal design (public vs internal)\n"
                "- Audit requirements for both customer-facing and internal operations"
            )
        
        if cross_domain:
            sections.append("CROSS-DOMAIN CONSIDERATIONS:\n" + "\n\n".join(cross_domain))
        
        return "\n\n".join(sections) if sections else ""
    
    def _get_assessment_findings(self, servicenow_data: Dict) -> List[Dict]:
        """Run the rule engine against available instance data to get deterministic findings.
        Returns a list of finding dicts, or empty list if rules are disabled or data is insufficient."""
        if not RULES_ENABLED:
            return []
        
        try:
            # Build a lightweight InstanceModel from the servicenow_data already available
            model = InstanceModel()
            
            # Map applications to plugin IDs
            apps = servicenow_data.get("applications", [])
            for app in apps:
                scope = app.get("scope", "")
                if scope:
                    model.installed_plugins[scope] = {
                        "name": app.get("name", ""),
                        "active": True,
                    }
            
            # Map key capabilities to known plugin IDs for rule matching
            caps = servicenow_data.get("key_capabilities", {})
            cap_to_plugin = {
                "itsm": "com.snc.incident",
                "csm": "com.sn_customerservice",
                "hrsd": "com.sn_hr_core",
                "itom": "com.snc.discovery",
                "cmdb": "com.snc.cmdb",
            }
            for cap, plugin_id in cap_to_plugin.items():
                if caps.get(cap) and plugin_id not in model.installed_plugins:
                    model.installed_plugins[plugin_id] = {"name": cap.upper(), "active": True}
            
            # Run the rule engine
            evaluation = self.rule_engine.evaluate(model)
            findings = evaluation.get("findings", [])
            logger.info(f"Assessment produced {len(findings)} findings for architecture query enrichment")
            return findings
        except Exception as e:
            logger.warning(f"Assessment enrichment failed (non-critical): {e}")
            return []
    
    def _format_findings_for_prompt(self, findings: List[Dict], query_types: List[str]) -> str:
        """Format assessment findings as structured prompt context.
        Filters to findings relevant to the detected query types."""
        if not findings:
            return ""
        
        # Map query types to relevant rule categories and tags
        type_to_tags = {
            "itsm": {"D2C", "itsm", "incident", "problem", "change"},
            "csm": {"R2F", "csm", "customer", "portal"},
            "hrsd": {"R2F", "hrsd", "employee"},
            "itom": {"D2C", "itom", "discovery", "cmdb"},
            "secops": {"D2C", "secops", "security"},
            "compliance": {"security", "compliance", "audit", "fedramp"},
            "integration": {"integration", "web_service", "mid_server"},
            "portal": {"R2F", "portal", "self_service"},
            "automation": {"workflow", "flow_designer", "orchestration"},
            "data_flow": {"data_persistence", "integration"},
        }
        
        relevant_tags = set()
        for qt in query_types:
            relevant_tags.update(type_to_tags.get(qt, set()))
        
        # If no specific query types matched, include all findings
        if not relevant_tags:
            relevant = findings
        else:
            relevant = []
            for f in findings:
                # Include finding if its category or any evidence overlaps with relevant tags
                if f.get("category", "") in relevant_tags:
                    relevant.append(f)
                    continue
                # Check rule_id prefix as fallback
                rule_id = f.get("rule_id", "")
                if any(tag.upper() in rule_id.upper() for tag in relevant_tags):
                    relevant.append(f)
        
        # Also always include CRITICAL and HIGH severity findings regardless of relevance
        for f in findings:
            if f.get("severity") in ("critical", "high") and f not in relevant:
                relevant.append(f)
        
        if not relevant:
            return ""
        
        lines = ["VERIFIED INSTANCE FINDINGS (from deterministic rule engine):"]
        for f in relevant[:15]:  # Cap at 15 to avoid prompt bloat
            severity = f.get("severity", "info").upper()
            lines.append(f"- [{severity}] {f.get('rule_name', '')}: {f.get('message', '')}")
            lines.append(f"  Recommendation: {f.get('recommendation', '')}")
        
        lines.append("")
        lines.append("Your analysis and recommendations MUST address these verified findings where relevant to the user's query.")
        lines.append("Reference the specific finding when your recommendation aligns with one.")
        
        return "\n".join(lines)
    
    def _tag_recommendation_confidence(self, recommendations: List[Dict], 
                                        findings: List[Dict]) -> List[Dict]:
        """Tag each recommendation with a confidence source:
        - 'rule-backed': recommendation aligns with a deterministic rule finding
        - 'ontology-validated': recommended components exist in the ontology graph
        - 'llm-generated': pure LLM output with no deterministic backing
        """
        # Build lookup structures
        finding_keywords = set()
        for f in findings:
            # Extract key terms from finding messages and rule names
            for word in f.get("rule_name", "").lower().split():
                if len(word) > 3:
                    finding_keywords.add(word)
            for word in f.get("message", "").lower().split():
                if len(word) > 3:
                    finding_keywords.add(word)
        
        ontology_labels = set()
        for node_id, node in self.ontology._nodes.items():
            ontology_labels.add(node.label.lower())
            ontology_labels.add(node_id.lower())
            for alias in node.aliases:
                ontology_labels.add(alias.lower())
        
        for rec in recommendations:
            components = rec.get("servicenow_components", [])
            title_lower = rec.get("title", "").lower()
            desc_lower = rec.get("description", "").lower()
            combined = title_lower + " " + desc_lower
            
            # Check if recommendation aligns with a rule finding
            rule_match = False
            matching_rules = []
            for f in findings:
                rule_name_lower = f.get("rule_name", "").lower()
                message_lower = f.get("message", "").lower()
                # Check for significant keyword overlap
                rule_words = set(w for w in rule_name_lower.split() if len(w) > 3)
                overlap = sum(1 for w in rule_words if w in combined)
                if overlap >= 2:
                    rule_match = True
                    matching_rules.append(f.get("rule_id", ""))
            
            # Check if components exist in ontology
            ontology_match = False
            validated_components = []
            unvalidated_components = []
            for comp in components:
                comp_lower = comp.lower()
                if any(comp_lower in label or label in comp_lower for label in ontology_labels):
                    ontology_match = True
                    validated_components.append(comp)
                else:
                    unvalidated_components.append(comp)
            
            # Assign confidence tag
            if rule_match:
                rec["confidence"] = "rule-backed"
                rec["confidence_detail"] = f"Backed by assessment rule(s): {', '.join(matching_rules[:3])}"
            elif ontology_match:
                rec["confidence"] = "ontology-validated"
                rec["confidence_detail"] = "Components verified in ServiceNow ontology graph"
            else:
                rec["confidence"] = "llm-generated"
                rec["confidence_detail"] = "Generated by LLM without deterministic validation"
            
            # Tag unvalidated components
            if unvalidated_components:
                rec["unvalidated_components"] = unvalidated_components
        
        return recommendations
    
    def _validate_recommendation_components(self, recommendations: List[Dict],
                                             instance_data: Dict) -> List[Dict]:
        """Post-validate recommendation components against the ontology graph
        and instance data. Adds validation_notes to each recommendation."""
        installed_apps = set()
        if 'applications' in instance_data:
            for app in instance_data['applications']:
                installed_apps.add(app.get('name', '').lower())
                installed_apps.add(app.get('scope', '').lower())
        
        ontology_labels = {}
        for node_id, node in self.ontology._nodes.items():
            ontology_labels[node.label.lower()] = node
            for alias in node.aliases:
                ontology_labels[alias.lower()] = node
        
        for rec in recommendations:
            notes = []
            components = rec.get("servicenow_components", [])
            
            for comp in components:
                comp_lower = comp.lower()
                
                # Check if already installed
                for installed in installed_apps:
                    if comp_lower in installed or installed in comp_lower:
                        notes.append(f"'{comp}' appears already installed on this instance")
                        break
                
                # Check if component exists in ontology
                found_in_ontology = False
                for label, node in ontology_labels.items():
                    if comp_lower in label or label in comp_lower:
                        found_in_ontology = True
                        break
                
                if not found_in_ontology:
                    notes.append(f"'{comp}' is not in the ServiceNow ontology — verify this component exists")
            
            if notes:
                rec["validation_notes"] = notes
        
        return recommendations
    
    def _summarize_documents(self, documents: List[Dict]) -> str:
        if not documents:
            return "No relevant documents found"
        
        summary = []
        for i, doc in enumerate(documents[:5], 1):
            filename = doc.get("filename", "Unknown")
            content = doc.get("content", "")
            relevance = doc.get("relevance_score", 0)
            source_label = doc.get("source_label", "Document")
            source_instance = doc.get("source_instance", "unknown")
            instance_tag = f" [uploaded for: {source_instance}]" if source_instance != "unknown" else ""
            summary.append(f"{i}. [{source_label}]{instance_tag} {filename} (relevance: {relevance:.2f})\n   {content}")
        
        # Warn if documents are from a different instance
        instances = set(doc.get("source_instance", "unknown") for doc in documents[:5])
        instances.discard("unknown")
        if len(instances) > 0:
            summary.insert(0, f"NOTE: These documents were uploaded during connections to: {', '.join(instances)}. "
                           f"They may reference a DIFFERENT instance or customer than the one currently connected. "
                           f"Use document content for general requirements context, but verify instance-specific claims "
                           f"against the CURRENT INSTANCE STATE data above.")
        
        return "\n\n".join(summary)
    
    def _summarize_web_context(self, web_context: List[Dict]) -> str:
        if not web_context:
            return "No web search results available"
        
        summary = []
        for i, result in enumerate(web_context[:5], 1):
            title = result.get("title", "Unknown")
            snippet = result.get("snippet", "")
            summary.append(f"{i}. {title}\n   {snippet}")
        
        return "\n\n".join(summary)
    
    def generate_follow_up_questions(self, analysis: Dict) -> List[str]:
        if not self.is_configured():
            return []
        
        prompt = f"""Based on this architecture analysis, generate 3-5 relevant follow-up questions 
that would help refine the solution:

Analysis: {json.dumps(analysis, indent=2)}

Return only a JSON array of question strings."""

        try:
            messages = [HumanMessage(content=prompt)]
            logger.info(f"Sending prompt to {self.provider} ({len(prompt)} chars)")
            response = self.active_model.invoke(prompt)
            logger.info(f"Received response from {self.provider} ({len(response.content)} chars)")
            
            response_text = response.content
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            try:
                questions = json.loads(response_text)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON response from {self.provider}: {response_text}")
                questions = []
            
            return questions if isinstance(questions, list) else []
        except Exception as e:
            logger.error(f"Error generating follow-up questions: {str(e)}")
            return []
