import os
from typing import List, Dict, Optional
import logging
import requests
from bs4 import BeautifulSoup

from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebSearchService:
    def __init__(self):
        self.serpapi_key = settings.serpapi_key
    
    def search(self, query: str, num_results: int = 5) -> List[Dict]:
        # Web search disabled - no API key configured
        # TODO: Configure real search API (SerpAPI, Google Custom Search, or alternative)
        logger.info("Web search disabled - no API key configured")
        return []
    
    def _search_with_serpapi(self, query: str, num_results: int) -> List[Dict]:
        try:
            url = "https://serpapi.com/search"
            params = {
                "q": f"{query} ServiceNow",
                "api_key": self.serpapi_key,
                "num": num_results
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get("organic_results", [])[:num_results]:
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "source": "serpapi"
                })
            
            return results
        except Exception as e:
            logger.error(f"SerpAPI search failed: {str(e)}")
            return self._search_fallback(query, num_results)
    
    def _search_fallback(self, query: str, num_results: int) -> List[Dict]:
        results = []
        
        servicenow_docs = [
            {
                "title": "ServiceNow Documentation - Platform Overview",
                "link": "https://docs.servicenow.com",
                "snippet": "Official ServiceNow documentation covering platform capabilities, best practices, and implementation guides.",
                "source": "fallback"
            },
            {
                "title": "ServiceNow Integration Hub",
                "link": "https://docs.servicenow.com/integration",
                "snippet": "Integration patterns and connectors for enterprise systems including SAP, Salesforce, and custom APIs.",
                "source": "fallback"
            },
            {
                "title": "ServiceNow Customer Service Management",
                "link": "https://www.servicenow.com/products/customer-service-management.html",
                "snippet": "Customer service workflows, case management, and omnichannel support capabilities.",
                "source": "fallback"
            },
            {
                "title": "ServiceNow Master Data Management",
                "link": "https://docs.servicenow.com/mdm",
                "snippet": "Master data management solutions for maintaining consistent data across enterprise systems.",
                "source": "fallback"
            },
            {
                "title": "ServiceNow Architecture Best Practices",
                "link": "https://developer.servicenow.com/architecture",
                "snippet": "Best practices for designing scalable and maintainable ServiceNow solutions.",
                "source": "fallback"
            }
        ]
        
        return servicenow_docs[:num_results]
    
    def fetch_page_content(self, url: str) -> Optional[str]:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            for script in soup(["script", "style"]):
                script.decompose()
            
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text[:5000]
        except Exception as e:
            logger.error(f"Error fetching page content from {url}: {str(e)}")
            return None
