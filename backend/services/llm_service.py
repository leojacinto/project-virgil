import os
from typing import List, Dict, Optional
import logging
import json
import datetime

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from config import settings
from services.servicenow_ontology import ServiceNowOntology

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models for structured output
class Recommendation(BaseModel):
    """A single recommendation"""
    title: str = Field(description="Title of the recommendation")
    description: str = Field(description="Detailed description")
    servicenow_components: List[str] = Field(description="List of ServiceNow components")
    priority: str = Field(description="Priority: high, medium, or low")

class ArchitectureAnalysis(BaseModel):
    """Complete architecture analysis response"""
    analysis: str = Field(description="Detailed architecture analysis text")
    recommendations: List[Recommendation] = Field(description="List of recommendations")
    mermaid_diagram: str = Field(description="Mermaid diagram code showing architecture flow")
    implementation_notes: str = Field(description="Key implementation considerations")

class LLMService:
    def __init__(self):
        self.active_model = None
        self.provider = None
        self.model_name = None
        self.ontology = ServiceNowOntology()
        
        if settings.openai_api_key:
            try:
                self.configure("openai", settings.openai_api_key)
            except Exception as e:
                logger.warning(f"Could not initialize OpenAI from config: {str(e)}")
        
        if settings.anthropic_api_key and not self.active_model:
            try:
                self.configure("anthropic", settings.anthropic_api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Anthropic from config: {str(e)}")
    
    def configure(self, provider: str, api_key: str, model: Optional[str] = None):
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
                
            elif provider_lower == "anthropic":
                model_name = model or "claude-3-5-sonnet-20241022"
                self.active_model = ChatAnthropic(
                    model=model_name,
                    temperature=0.7,
                    api_key=api_key
                )
                self.provider = "anthropic"
                self.model_name = model_name
                logger.info(f"Anthropic model configured: {model_name}")
                
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
                
            elif provider_lower == "azure":
                from langchain_openai import AzureChatOpenAI
                model_name = model or "gpt-4"
                self.active_model = AzureChatOpenAI(
                    azure_deployment=model_name,
                    temperature=0.7,
                    api_key=api_key
                )
                self.provider = "azure"
                self.model_name = model_name
                logger.info(f"Azure OpenAI model configured: {model_name}")
                
            else:
                raise ValueError(f"Unsupported provider: {provider}")
                
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
        
        # Detect query type for specialized handling
        query_types = self.ontology.detect_query_type(query)
        logger.info(f"Detected query types: {query_types}")
        
        # Get specialized constraints based on query type
        specialized_constraints = self.ontology.get_specialized_constraints(query_types)
        
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

Your task is to analyze the user's requirements and provide:
1. A comprehensive architectural analysis
2. Specific recommendations based on available ServiceNow components
3. Architecture components for diagram generation
4. Implementation considerations and best practices

Be specific, practical, and reference actual ServiceNow tables, applications, and components when available."""

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

Please provide:
1. **Analysis**: A detailed analysis of the requirements and how they map to ServiceNow capabilities
2. **Recommendations**: Specific recommendations with ServiceNow products, tables, and components to use
3. **Architecture Components**: A structured list of components for the architecture diagram
4. **Implementation Notes**: Key considerations, risks, and best practices

Format your response as JSON with the following structure:
{{
    "analysis": "detailed analysis text",
    "recommendations": [
        {{
            "title": "recommendation title",
            "description": "detailed description",
            "servicenow_components": ["component1", "component2"],
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
    "implementation_notes": "key implementation considerations"
}}

CRITICAL MERMAID REQUIREMENTS:
- MUST start with "graph TD" on first line
- MUST use --> arrows to connect nodes (e.g., A --> B)
- Node format: ID[Label Text] where ID is a single letter or short identifier
- Example valid diagram:
  graph TD
      A[User Portal] --> B[ServiceNow CSM]
      B --> C[CMDB]
      A --> D[ITSM]
      D --> C

Priority levels mean:
- HIGH: Critical for core functionality, must implement first
- MEDIUM: Important for complete solution, implement after high priority
- LOW: Nice-to-have enhancements, implement if time/budget allows

For mermaid_diagram, you MUST create an architecture diagram with SEMANTIC RELATIONSHIPS.

{self.ontology.get_mermaid_guidance(query_types)}

Remember:
- Use subgraphs to show layers
- Label arrows with relationship types (creates, runs on, references, resolves using)
- CMDB and Platform are FOUNDATIONAL - they go at the bottom
- NO bidirectional arrows unless peer-to-peer integration
- NO cross-connections between segregated paths (Public ≠ ITSM, Internal ≠ CSM)"""

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
                    else:
                        # Save original Mermaid to file for debugging
                        mermaid_file = f"/tmp/mermaid_original_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                        with open(mermaid_file, 'w') as f:
                            f.write(mermaid)
                        logger.info(f"Original Mermaid diagram saved to: {mermaid_file}")
                        logger.info(f"Original Mermaid diagram:\n{mermaid}")
                        
                        # Fix common issues
                        fixed_mermaid = mermaid.strip()
                        
                        # Remove any markdown code blocks first
                        if "```" in fixed_mermaid:
                            fixed_mermaid = fixed_mermaid.replace("```mermaid", "").replace("```", "").strip()
                        
                        # Ensure it starts with graph TD
                        if not fixed_mermaid.startswith("graph"):
                            fixed_mermaid = "graph TD\n" + fixed_mermaid
                        
                        # First pass: join lines that are part of split labels
                        # This fixes labels like "E[Customer Service Management (\nCSM)]"
                        fixed_lines = []
                        i = 0
                        lines = fixed_mermaid.split("\n")
                        while i < len(lines):
                            line = lines[i]
                            # If line has [ but no ], it's a split label - join with next line
                            while "[" in line and "]" not in line and i + 1 < len(lines):
                                i += 1
                                line = line.strip() + " " + lines[i].strip()
                            fixed_lines.append(line)
                            i += 1
                        
                        # Second pass: clean special characters
                        cleaned_lines = []
                        for line in fixed_lines:
                            # Skip empty lines
                            if not line.strip():
                                continue
                            # Remove special chars from labels
                            if "[" in line and "]" in line:
                                # Extract label and clean it
                                parts = line.split("[")
                                if len(parts) > 1:
                                    label_part = parts[1].split("]")[0]
                                    # Remove problematic characters and newlines
                                    cleaned_label = label_part.replace("\n", " ").replace("\r", " ").replace("/", " ").replace("&", "and").replace("\\", "").replace('"', '').replace("'", "")
                                    # Remove extra spaces
                                    cleaned_label = " ".join(cleaned_label.split())
                                    line = parts[0] + "[" + cleaned_label + "]" + "]".join(parts[1].split("]")[1:])
                            cleaned_lines.append(line)
                        
                        fixed_mermaid = "\n".join(cleaned_lines)
                        
                        # Validate it has at least one arrow
                        if "-->" not in fixed_mermaid and "---" not in fixed_mermaid:
                            logger.error("Fixed Mermaid has no arrows, using fallback")
                            fixed_mermaid = """graph TD
    A[User Requirements] --> B[ServiceNow Platform]
    B --> C[CMDB]
    B --> D[Applications]
    D --> C"""
                        
                        if fixed_mermaid != mermaid:
                            mermaid_fixed_file = f"/tmp/mermaid_fixed_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                            with open(mermaid_fixed_file, 'w') as f:
                                f.write(fixed_mermaid)
                            logger.info(f"Fixed Mermaid diagram saved to: {mermaid_fixed_file}")
                            logger.info(f"Fixed Mermaid diagram:\n{fixed_mermaid}")
                        
                        result["mermaid_diagram"] = fixed_mermaid
                
                except Exception as mermaid_error:
                    logger.error(f"Mermaid processing failed: {str(mermaid_error)}")
                    # Use simple fallback if processing crashes
                    result["mermaid_diagram"] = """graph TD
    A[User Requirements] --> B[ServiceNow Platform]
    B --> C[CMDB]
    B --> D[Applications]
    D --> C"""
                
                # Validate architecture against ServiceNow domain knowledge
                if "architecture_components" in result or response.architecture_components:
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
                response = self.active_model.invoke(messages)
                response_text = response.content
                
                # Save raw response for debugging
                raw_file = f"/tmp/llm_raw_response_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                with open(raw_file, 'w') as f:
                    f.write(response_text)
                logger.info(f"Raw LLM response saved to: {raw_file}")
                
                # Try to parse JSON from response
                try:
                    if "```json" in response_text:
                        json_start = response_text.find("```json") + 7
                        json_end = response_text.find("```", json_start)
                        response_text = response_text[json_start:json_end].strip()
                    
                    result = json.loads(response_text)
                    
                    # Save parsed result
                    debug_file = f"/tmp/llm_response_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    with open(debug_file, 'w') as f:
                        json.dump(result, f, indent=2)
                    logger.info(f"Parsed LLM response saved to: {debug_file}")
                    
                    if "mermaid_diagram" not in result:
                        result["mermaid_diagram"] = ""
                    
                    logger.info("Successfully parsed JSON response")
                    
                    # Log Mermaid diagram from fallback path
                    mermaid = result.get("mermaid_diagram", "")
                    if mermaid:
                        mermaid_file = f"/tmp/mermaid_original_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                        with open(mermaid_file, 'w') as f:
                            f.write(mermaid)
                        logger.info(f"Mermaid diagram (from fallback) saved to: {mermaid_file}")
                    
                except json.JSONDecodeError as je:
                    logger.error("Both structured output and JSON parsing failed")
                    result = {
                        "analysis": response_text,
                        "recommendations": [{
                            "title": "Review Analysis",
                            "description": "See detailed analysis above",
                            "servicenow_components": [],
                            "priority": "high"
                        }],
                        "mermaid_diagram": "graph TD\n    A[Analysis] --> B[See Details]",
                        "implementation_notes": "See analysis for details"
                    }
            
            return result
        except Exception as e:
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
        
        components = data.get("components", {})
        for comp_type, comp_list in components.items():
            if comp_list:
                summary.append(f"\n{comp_type.replace('_', ' ').title()} ({len(comp_list)})")
        
        return "\n".join(summary) if summary else "No ServiceNow data available"
    
    def _summarize_documents(self, documents: List[Dict]) -> str:
        if not documents:
            return "No relevant documents found"
        
        summary = []
        for i, doc in enumerate(documents[:5], 1):
            filename = doc.get("filename", "Unknown")
            content_preview = doc.get("content", "")[:200]
            relevance = doc.get("relevance_score", 0)
            summary.append(f"{i}. {filename} (relevance: {relevance:.2f})\n   {content_preview}...")
        
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
