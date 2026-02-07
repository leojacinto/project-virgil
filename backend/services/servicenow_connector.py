import jaydebeapi
import os
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ServiceNowConnector:
    def __init__(self, instance: str, username: str, password: str, jdbc_path: str):
        self.instance = instance
        self.username = username
        self.password = password
        self.jdbc_path = os.path.abspath(jdbc_path)
        self.connection = None
        self._connected = False
        
        logger.info(f"ServiceNow connector initialized for instance: {instance}")
    
    def test_connection(self) -> bool:
        try:
            self.connect()
            return self._connected
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False
    
    def connect(self):
        try:
            logger.info(f"Attempting to connect to ServiceNow instance: {self.instance}")
            
            if not os.path.exists(self.jdbc_path):
                raise FileNotFoundError(f"JDBC JAR file not found at: {self.jdbc_path}")
            
            logger.info(f"JDBC JAR found at: {self.jdbc_path}")
            
            # Handle both "instance" and "instance.service-now.com" formats
            if ".service-now.com" in self.instance:
                jdbc_url = f"jdbc:servicenow://{self.instance}"
            else:
                jdbc_url = f"jdbc:servicenow://{self.instance}.service-now.com"
            
            logger.info(f"JDBC URL: {jdbc_url}")
            
            jdbc_driver = "com.snc.db.jdbc.JDBCDriver"
            
            logger.info("Connecting via jaydebeapi...")
            self.connection = jaydebeapi.connect(
                jdbc_driver,
                jdbc_url,
                [self.username, self.password],
                self.jdbc_path
            )
            self._connected = True
            logger.info(f"Successfully connected to ServiceNow instance: {self.instance}")
            
        except Exception as e:
            logger.error(f"Connection failed: {str(e)}", exc_info=True)
            self._connected = False
            raise
    
    def is_connected(self) -> bool:
        return self._connected and self.connection is not None
    
    def execute_query(self, query: str, max_retries: int = 2) -> List[Dict]:
        if not self.is_connected():
            raise Exception("Not connected to ServiceNow")
        
        import time
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                cursor = self.connection.cursor()
                cursor.execute(query)
                
                # Get column names
                column_names = [desc[0] for desc in cursor.description]
                
                # Fetch all rows
                rows = cursor.fetchall()
                
                # Convert to list of dictionaries
                results = []
                for row in rows:
                    row_dict = {}
                    for i, col_name in enumerate(column_names):
                        row_dict[col_name] = str(row[i]) if row[i] is not None else None
                    results.append(row_dict)
                
                cursor.close()
                return results
            except Exception as e:
                last_error = e
                logger.warning(f"Query attempt {attempt + 1}/{max_retries + 1} failed: {str(e)}")
                if attempt < max_retries:
                    time.sleep(0.5)  # Brief pause before retry
                    continue
                logger.error(f"Query execution failed after {max_retries + 1} attempts: {str(e)}")
                raise last_error
    
    def get_available_tables(self) -> List[str]:
        try:
            # Use simpler query that's less likely to fail
            query = "SELECT name FROM sys_db_object WHERE name NOT LIKE 'sys_%' ORDER BY name LIMIT 100"
            results = self.execute_query(query, max_retries=1)
            return [row['name'] for row in results if row.get('name')]
        except Exception as e:
            logger.warning(f"Could not fetch tables via query: {str(e)}")
            # Return common ServiceNow tables as fallback
            return [
                'incident', 'task', 'change_request', 'problem', 'cmdb_ci',
                'sys_user', 'sys_user_group', 'cmdb_ci_server', 'cmdb_ci_service'
            ]
    
    def get_installed_applications(self) -> List[Dict]:
        try:
            query = "SELECT sys_id, name, version FROM sys_app WHERE active = 'true' ORDER BY name LIMIT 50"
            return self.execute_query(query, max_retries=1)
        except Exception as e:
            logger.warning(f"Could not fetch installed applications: {str(e)}")
            return []
    
    def get_components(self) -> Dict:
        components = {}
        
        # Fetch components one at a time with delays to avoid overwhelming the connection
        import time
        
        try:
            workflows_query = "SELECT sys_id, name FROM wf_workflow WHERE active = 'true' LIMIT 20"
            components["workflows"] = self.execute_query(workflows_query, max_retries=1)
            time.sleep(0.3)  # Small delay between queries
        except Exception as e:
            logger.warning(f"Could not fetch workflows: {str(e)}")
            components["workflows"] = []
        
        try:
            business_rules_query = "SELECT sys_id, name FROM sys_script WHERE active = 'true' LIMIT 20"
            components["business_rules"] = self.execute_query(business_rules_query, max_retries=1)
            time.sleep(0.3)
        except Exception as e:
            logger.warning(f"Could not fetch business rules: {str(e)}")
            components["business_rules"] = []
        
        try:
            integrations_query = "SELECT sys_id, name FROM sys_integration WHERE active = 'true' LIMIT 20"
            components["integrations"] = self.execute_query(integrations_query, max_retries=1)
        except Exception as e:
            logger.warning(f"Could not fetch integrations: {str(e)}")
            components["integrations"] = []
        
        return components
    
    def get_table_schema(self, table_name: str) -> List[Dict]:
        try:
            query = f"""
                SELECT column_name, element, internal_type, max_length
                FROM sys_dictionary
                WHERE name = '{table_name}'
                ORDER BY column_name
            """
            return self.execute_query(query)
        except Exception as e:
            logger.error(f"Could not fetch schema for table {table_name}: {str(e)}")
            return []
    
    def close(self):
        if self.connection:
            try:
                self.connection.close()
                self._connected = False
                logger.info("Connection closed")
            except Exception as e:
                logger.error(f"Error closing connection: {str(e)}")
    
    def __del__(self):
        self.close()
