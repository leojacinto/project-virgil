import os
from typing import List, Dict, Optional
import logging
import json

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from config import settings

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
        if not self.is_configured():
            raise Exception("No LLM model configured. Please set OPENAI_API_KEY or ANTHROPIC_API_KEY")
        
        system_prompt = """You are an expert ServiceNow technical architect and solution consultant with deep knowledge of:
- ServiceNow platform architecture and best practices
- Integration patterns and data flows
- Master data management and enterprise architecture
- Customer service workflows and ITSM processes
- ServiceNow product capabilities and modules

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
    "mermaid_diagram": "mermaid diagram code showing the architecture flow",
    "implementation_notes": "key implementation considerations"
}}

Priority levels mean:
- HIGH: Critical for core functionality, must implement first
- MEDIUM: Important for complete solution, implement after high priority
- LOW: Nice-to-have enhancements, implement if time/budget allows

For mermaid_diagram, you MUST create a simple flowchart. Use this EXACT format:
graph TD
    A[Component 1] --> B[Component 2]
    B --> C[Component 3]

Rules for Mermaid:
- Start with: graph TD
- Use simple IDs: A, B, C, D, etc.
- Format: ID[Label] --> ID2[Label2]
- Max 8 nodes
- No special chars in labels
- Keep labels short (2-4 words)

Example for this query:
graph TD
    A[Public Portal] --> B[CSM Cases]
    C[Employee Portal] --> D[ITSM Tickets]
    B --> E[Knowledge Base]
    D --> E
    E --> F[CMDB]"""

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
                
            except Exception as e:
                # Fallback to regular response if structured output not supported
                logger.warning(f"Structured output failed, falling back to JSON parsing: {str(e)}")
                response = self.active_model.invoke(messages)
                response_text = response.content
                
                # Try to parse JSON from response
                try:
                    if "```json" in response_text:
                        json_start = response_text.find("```json") + 7
                        json_end = response_text.find("```", json_start)
                        response_text = response_text[json_start:json_end].strip()
                    
                    result = json.loads(response_text)
                    
                    if "mermaid_diagram" not in result:
                        result["mermaid_diagram"] = "graph TD\n    A[Analysis] --> B[See Details]"
                        
                except json.JSONDecodeError:
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
