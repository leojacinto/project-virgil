import os
from typing import List, Dict, Optional
import logging
import json

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage

from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    "implementation_notes": "key implementation considerations"
}}"""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.active_model.invoke(messages)
            response_text = response.content
            
            try:
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    response_text = response_text[json_start:json_end].strip()
                elif "```" in response_text:
                    json_start = response_text.find("```") + 3
                    json_end = response_text.find("```", json_start)
                    response_text = response_text[json_start:json_end].strip()
                
                result = json.loads(response_text)
            except json.JSONDecodeError:
                logger.warning("Could not parse JSON response, creating structured response")
                result = {
                    "analysis": response_text,
                    "recommendations": [
                        {
                            "title": "Review Full Analysis",
                            "description": "Please review the detailed analysis provided",
                            "servicenow_components": [],
                            "priority": "high"
                        }
                    ],
                    "architecture_components": [],
                    "implementation_notes": "See analysis for details"
                }
            
            return result
        except Exception as e:
            logger.error(f"Error in LLM analysis: {str(e)}")
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
            response = self.active_model.invoke(messages)
            
            response_text = response.content
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            questions = json.loads(response_text)
            return questions if isinstance(questions, list) else []
        except Exception as e:
            logger.error(f"Error generating follow-up questions: {str(e)}")
            return []
