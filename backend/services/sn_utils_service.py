"""
ServiceNow Utils Service - REST API wrapper for instance metadata queries
Provides presales-ready capabilities for gap analysis and instance validation
"""

import requests
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class SNUtilsService:
    """ServiceNow REST API client for instance metadata and configuration queries"""
    
    def __init__(self, instance: str, username: str, password: str):
        """
        Initialize SN Utils service
        
        Args:
            instance: ServiceNow instance URL (e.g., 'instance.service-now.com')
            username: ServiceNow username
            password: ServiceNow password
        """
        self.instance = instance
        self.username = username
        self.password = password
        
        # Build base URL
        if not instance.startswith('http'):
            self.base_url = f"https://{instance}"
        else:
            self.base_url = instance
            
        # Cache for API responses (avoid rate limits)
        self._cache = {}
        self._cache_ttl = timedelta(minutes=30)
        
        logger.info(f"SNUtilsService initialized for instance: {instance}")
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None, cache_key: Optional[str] = None) -> Optional[Dict]:
        """
        Make REST API request with caching and error handling
        
        Args:
            endpoint: API endpoint path (e.g., '/api/now/table/sys_db_object')
            params: Query parameters
            cache_key: Optional cache key for this request
            
        Returns:
            Response JSON or None on error
        """
        # Check cache first
        if cache_key and cache_key in self._cache:
            cached_data, cached_time = self._cache[cache_key]
            if datetime.now() - cached_time < self._cache_ttl:
                logger.debug(f"Cache hit for {cache_key}")
                return cached_data
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.get(
                url,
                auth=(self.username, self.password),
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Cache successful response
                if cache_key:
                    self._cache[cache_key] = (data, datetime.now())
                
                return data
            elif response.status_code == 401:
                logger.error("Authentication failed - check credentials")
                return None
            elif response.status_code == 403:
                logger.warning(f"No permission to access {endpoint}")
                return None
            elif response.status_code == 400 and "Invalid table" in response.text:
                # Expected: table doesn't exist on this instance (plugin not installed)
                logger.debug(f"Table not available on instance: {response.text[:100]}")
                return None
            else:
                logger.error(f"API request failed: {response.status_code} - {response.text[:200]}")
                return None
                
        except Exception as e:
            logger.error(f"API request exception: {str(e)}")
            return None
    
    def get_record_count(self, table: str, query: str = None) -> int:
        """
        Get the true record count for a table using X-Total-Count header.
        Fetches 0 records — only the count.
        """
        url = f"{self.base_url}/api/now/table/{table}"
        params = {
            'sysparm_limit': 1,
            'sysparm_fields': 'sys_id',
            'sysparm_suppress_pagination_header': 'false',
        }
        if query:
            params['sysparm_query'] = query
        try:
            response = requests.get(
                url,
                auth=(self.username, self.password),
                params=params,
                timeout=15,
            )
            if response.status_code == 200:
                count = int(response.headers.get('X-Total-Count', 0))
                return count
        except Exception as e:
            logger.warning(f"Count query failed for {table}: {e}")
        return 0

    def get_table_data(self, table: str, query: str = None,
                       fields: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch records from a ServiceNow table with optional filtering.

        Args:
            table: Table name (e.g., 'sys_data_source')
            query: Encoded query string (e.g., 'type=JDBC')
            fields: Comma-separated field list
            limit: Max records to return

        Returns:
            List of record dicts, or empty list on error
        """
        params: Dict[str, Any] = {"sysparm_limit": limit}
        if query:
            params["sysparm_query"] = query
        if fields:
            params["sysparm_fields"] = fields
        cache_key = f"table_data_{table}_{query}_{fields}_{limit}"
        data = self._make_request(f"/api/now/table/{table}",
                                  params=params, cache_key=cache_key)
        if data:
            return data.get("result", [])
        return []

    def get_installed_applications(self) -> List[Dict[str, Any]]:
        """
        Get list of installed applications in the instance
        
        Returns:
            List of application dictionaries with name, version, scope
        """
        logger.info("Querying installed applications...")
        
        params = {
            'sysparm_fields': 'name,version,scope,short_description',
            'sysparm_limit': 1000
        }
        
        data = self._make_request(
            '/api/now/table/sys_app',
            params=params,
            cache_key='installed_apps'
        )
        
        if data:
            apps = data.get('result', [])
            logger.info(f"Found {len(apps)} installed applications")
            return apps
        
        return []
    
    def get_tables(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Get list of tables in the instance
        
        Args:
            limit: Maximum number of tables to retrieve
            
        Returns:
            List of table dictionaries with name, label, scope
        """
        logger.info("Querying tables...")
        
        params = {
            'sysparm_fields': 'name,label,super_class,sys_scope',
            'sysparm_limit': limit
        }
        
        data = self._make_request(
            '/api/now/table/sys_db_object',
            params=params,
            cache_key=f'tables_{limit}'
        )
        
        if data:
            tables = data.get('result', [])
            logger.info(f"Found {len(tables)} tables")
            return tables
        
        return []
    
    def get_table_fields(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Get fields for a specific table
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of field dictionaries with element, type, label
        """
        logger.info(f"Querying fields for table: {table_name}")
        
        params = {
            'sysparm_query': f'name={table_name}',
            'sysparm_fields': 'element,column_label,internal_type,max_length,mandatory',
            'sysparm_limit': 500
        }
        
        data = self._make_request(
            '/api/now/table/sys_dictionary',
            params=params,
            cache_key=f'fields_{table_name}'
        )
        
        if data:
            fields = data.get('result', [])
            logger.info(f"Found {len(fields)} fields for {table_name}")
            return fields
        
        return []
    
    def check_table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists in the instance
        
        Args:
            table_name: Name of the table to check
            
        Returns:
            True if table exists, False otherwise
        """
        params = {
            'sysparm_query': f'name={table_name}',
            'sysparm_limit': 1
        }
        
        data = self._make_request(
            '/api/now/table/sys_db_object',
            params=params
        )
        
        if data:
            return len(data.get('result', [])) > 0
        
        return False
    
    def check_application_installed(self, app_scope: str) -> Optional[Dict[str, Any]]:
        """
        Check if an application is installed
        
        Args:
            app_scope: Application scope (e.g., 'sn_customerservice')
            
        Returns:
            Application info if installed, None otherwise
        """
        params = {
            'sysparm_query': f'scope={app_scope}',
            'sysparm_fields': 'name,version,scope',
            'sysparm_limit': 1
        }
        
        data = self._make_request(
            '/api/now/table/sys_app',
            params=params
        )
        
        if data:
            apps = data.get('result', [])
            return apps[0] if apps else None
        
        return None
    
    def get_instance_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive instance summary for presales analysis
        
        Returns:
            Dictionary with installed apps, table count, key capabilities
        """
        logger.info("Building instance summary...")
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'instance': self.instance,
            'applications': [],
            'table_count': 0,
            'key_capabilities': {
                'itsm': False,
                'csm': False,
                'hrsd': False,
                'itom': False,
                'secops': False,
                'cmdb': False
            }
        }
        
        # Get applications
        apps = self.get_installed_applications()
        summary['applications'] = [
            {'name': app.get('name'), 'version': app.get('version'), 'scope': app.get('scope')}
            for app in apps
        ]
        
        # Get table count
        tables = self.get_tables(limit=10)
        summary['table_count'] = len(tables)
        
        # Detect key capabilities based on installed apps
        app_scopes = [app.get('scope', '').lower() for app in apps]
        
        if any('itsm' in scope or 'incident' in scope for scope in app_scopes):
            summary['key_capabilities']['itsm'] = True
        if any('csm' in scope or 'customer' in scope for scope in app_scopes):
            summary['key_capabilities']['csm'] = True
        if any('hrsd' in scope or 'hr_' in scope for scope in app_scopes):
            summary['key_capabilities']['hrsd'] = True
        if any('itom' in scope or 'discovery' in scope for scope in app_scopes):
            summary['key_capabilities']['itom'] = True
        if any('secops' in scope or 'security' in scope for scope in app_scopes):
            summary['key_capabilities']['secops'] = True
        
        # Check for CMDB
        if self.check_table_exists('cmdb_ci'):
            summary['key_capabilities']['cmdb'] = True
        
        logger.info(f"Instance summary complete: {len(apps)} apps, {summary['table_count']} tables")
        return summary
    
    def analyze_gaps(self, required_components: List[str]) -> Dict[str, Any]:
        """
        Analyze gaps between required components and current instance
        
        Args:
            required_components: List of required component names/scopes
            
        Returns:
            Dictionary with missing components and recommendations
        """
        logger.info(f"Analyzing gaps for {len(required_components)} required components...")
        
        installed_apps = self.get_installed_applications()
        installed_scopes = [app.get('scope', '').lower() for app in installed_apps]
        installed_names = [app.get('name', '').lower() for app in installed_apps]
        
        gaps = {
            'missing': [],
            'installed': [],
            'recommendations': []
        }
        
        for component in required_components:
            component_lower = component.lower()
            
            # Check if component is installed (by scope or name)
            if any(component_lower in scope for scope in installed_scopes) or \
               any(component_lower in name for name in installed_names):
                gaps['installed'].append(component)
            else:
                gaps['missing'].append(component)
                gaps['recommendations'].append(f"Install {component} to support proposed architecture")
        
        logger.info(f"Gap analysis complete: {len(gaps['missing'])} missing, {len(gaps['installed'])} installed")
        return gaps
    
    def clear_cache(self):
        """Clear the API response cache"""
        self._cache = {}
        logger.info("Cache cleared")
