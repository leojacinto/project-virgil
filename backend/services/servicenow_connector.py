import jpype
import jpype.imports
from jpype.types import *
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
        self.jdbc_path = jdbc_path
        self.connection = None
        self._connected = False
        
        self._initialize_jvm()
    
    def _initialize_jvm(self):
        if not jpype.isJVMStarted():
            try:
                jar_path = os.path.abspath(self.jdbc_path)
                if not os.path.exists(jar_path):
                    raise FileNotFoundError(f"JDBC JAR file not found at: {jar_path}")
                
                jpype.startJVM(
                    jpype.getDefaultJVMPath(),
                    f"-Djava.class.path={jar_path}",
                    "-ea"
                )
                logger.info("JVM started successfully")
            except Exception as e:
                logger.error(f"Failed to start JVM: {str(e)}")
                raise
    
    def test_connection(self) -> bool:
        try:
            self.connect()
            return self._connected
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False
    
    def connect(self):
        try:
            if jpype.isJVMStarted():
                from java.sql import DriverManager
                
                # Handle both "instance" and "instance.service-now.com" formats
                if ".service-now.com" in self.instance:
                    jdbc_url = f"jdbc:servicenow://{self.instance}"
                else:
                    jdbc_url = f"jdbc:servicenow://{self.instance}.service-now.com"
                
                properties = jpype.JClass("java.util.Properties")()
                properties.setProperty("user", self.username)
                properties.setProperty("password", self.password)
                
                self.connection = DriverManager.getConnection(jdbc_url, properties)
                self._connected = True
                logger.info(f"Connected to ServiceNow instance: {self.instance}")
            else:
                raise Exception("JVM not started")
        except Exception as e:
            logger.error(f"Connection failed: {str(e)}")
            self._connected = False
            raise
    
    def is_connected(self) -> bool:
        return self._connected and self.connection is not None
    
    def execute_query(self, query: str) -> List[Dict]:
        if not self.is_connected():
            raise Exception("Not connected to ServiceNow")
        
        try:
            statement = self.connection.createStatement()
            result_set = statement.executeQuery(query)
            
            metadata = result_set.getMetaData()
            column_count = metadata.getColumnCount()
            column_names = [metadata.getColumnName(i) for i in range(1, column_count + 1)]
            
            results = []
            while result_set.next():
                row = {}
                for i, col_name in enumerate(column_names, 1):
                    row[col_name] = str(result_set.getString(i)) if result_set.getString(i) else None
                results.append(row)
            
            result_set.close()
            statement.close()
            
            return results
        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            raise
    
    def get_available_tables(self) -> List[str]:
        try:
            query = """
                SELECT name 
                FROM sys_db_object 
                WHERE name NOT LIKE 'sys_%' 
                ORDER BY name
                LIMIT 1000
            """
            results = self.execute_query(query)
            return [row['name'] for row in results if row.get('name')]
        except Exception as e:
            logger.warning(f"Could not fetch tables via query, using metadata: {str(e)}")
            try:
                metadata = self.connection.getMetaData()
                tables_rs = metadata.getTables(None, None, "%", ["TABLE"])
                
                tables = []
                while tables_rs.next():
                    table_name = tables_rs.getString("TABLE_NAME")
                    if table_name and not table_name.startswith("sys_"):
                        tables.append(table_name)
                
                tables_rs.close()
                return sorted(tables)
            except Exception as meta_error:
                logger.error(f"Metadata fetch also failed: {str(meta_error)}")
                return []
    
    def get_installed_applications(self) -> List[Dict]:
        try:
            query = """
                SELECT name, version, scope, active
                FROM sys_app
                WHERE active = 'true'
                ORDER BY name
                LIMIT 500
            """
            return self.execute_query(query)
        except Exception as e:
            logger.error(f"Could not fetch installed applications: {str(e)}")
            return []
    
    def get_components(self) -> Dict:
        components = {
            "workflows": [],
            "business_rules": [],
            "ui_policies": [],
            "integrations": [],
            "modules": []
        }
        
        try:
            workflows_query = """
                SELECT name, table, active
                FROM wf_workflow
                WHERE active = 'true'
                LIMIT 100
            """
            components["workflows"] = self.execute_query(workflows_query)
        except Exception as e:
            logger.warning(f"Could not fetch workflows: {str(e)}")
        
        try:
            business_rules_query = """
                SELECT name, collection, active, when_to_run
                FROM sys_script
                WHERE active = 'true'
                LIMIT 100
            """
            components["business_rules"] = self.execute_query(business_rules_query)
        except Exception as e:
            logger.warning(f"Could not fetch business rules: {str(e)}")
        
        try:
            integrations_query = """
                SELECT name, type, active
                FROM sys_integration
                WHERE active = 'true'
                LIMIT 100
            """
            components["integrations"] = self.execute_query(integrations_query)
        except Exception as e:
            logger.warning(f"Could not fetch integrations: {str(e)}")
        
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
