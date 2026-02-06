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
        self.openai_model = None
        self.anthropic_model = None
        
        if settings.openai_api_key:
            try:
                self.openai_model = ChatOpenAI(
                    model="gpt-4-turbo-preview",
                    temperature=0.7,
                    api_key=settings.openai_api_key
                )
                logger.info("OpenAI model initialized")
            except Exception as e:
                logger.warning(f"Could not initialize OpenAI: {str(e)}")
        
        if settings.anthropic_api_key:
            try:
                self.anthropic_model = ChatAnthropic(
                    model="claude-3-opus-20240229",
                    temperature=0.7,
                    api_key=settings.anthropic_api_key
                )
                logger.info("Anthropic model initialized")
            except Exception as e:
                logger.warning(f"Could not initialize Anthropic: {str(e)}")
        
        self.active_model = self.openai_model or self.anthropic_model
    
    def is_configured(self) -> bool:
        return self.active_model is not None
    
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
