# ServiceNow JDBC Integration Guide

This document explains how to integrate your existing ServiceNow JDBC connection code with this application.

## Overview

The application uses JPype to create a Python-Java bridge, allowing Python code to use the ServiceNow JDBC driver. The main connection logic is in `backend/services/servicenow_connector.py`.

## Your Existing Code Integration

If you have existing Java or Python code that connects to ServiceNow's RaptorDB, you can integrate it as follows:

### Option 1: Replace the ServiceNowConnector Class

If you have a working Python JDBC connection, you can replace the entire `ServiceNowConnector` class in `backend/services/servicenow_connector.py` with your implementation.

Your class should implement these methods:

```python
class ServiceNowConnector:
    def __init__(self, instance: str, username: str, password: str, jdbc_path: str):
        # Initialize connection parameters
        pass
    
    def connect(self):
        # Establish connection to ServiceNow
        pass
    
    def is_connected(self) -> bool:
        # Return connection status
        pass
    
    def execute_query(self, query: str) -> List[Dict]:
        # Execute SQL query and return results as list of dictionaries
        pass
    
    def get_available_tables(self) -> List[str]:
        # Return list of available table names
        pass
    
    def get_installed_applications(self) -> List[Dict]:
        # Return list of installed applications
        pass
    
    def get_components(self) -> Dict:
        # Return dictionary of components (workflows, business rules, etc.)
        pass
    
    def close(self):
        # Close connection
        pass
```

### Option 2: Modify Existing Methods

If you have specific query patterns or connection logic, modify the relevant methods:

#### Custom Connection Logic

Replace the `connect()` method in `servicenow_connector.py`:

```python
def connect(self):
    try:
        # YOUR EXISTING CONNECTION CODE HERE
        # Example:
        if jpype.isJVMStarted():
            from java.sql import DriverManager
            
            # Your custom JDBC URL format
            jdbc_url = f"jdbc:servicenow://{self.instance}.service-now.com"
            
            # Your custom properties
            properties = jpype.JClass("java.util.Properties")()
            properties.setProperty("user", self.username)
            properties.setProperty("password", self.password)
            # Add any additional properties your connection needs
            
            self.connection = DriverManager.getConnection(jdbc_url, properties)
            self._connected = True
            logger.info(f"Connected to ServiceNow instance: {self.instance}")
    except Exception as e:
        logger.error(f"Connection failed: {str(e)}")
        self._connected = False
        raise
```

#### Custom Query Execution

If you have specific query patterns, modify `execute_query()`:

```python
def execute_query(self, query: str) -> List[Dict]:
    if not self.is_connected():
        raise Exception("Not connected to ServiceNow")
    
    try:
        # YOUR EXISTING QUERY EXECUTION CODE HERE
        statement = self.connection.createStatement()
        result_set = statement.executeQuery(query)
        
        # Your custom result processing
        results = []
        # ... process results ...
        
        return results
    except Exception as e:
        logger.error(f"Query execution failed: {str(e)}")
        raise
```

### Option 3: Add Your Existing Code as a Module

If you have a complete working module, you can add it alongside the existing connector:

1. Create a new file: `backend/services/your_connector.py`
2. Copy your existing code there
3. Modify `backend/main.py` to use your connector:

```python
# Replace this line:
from services.servicenow_connector import ServiceNowConnector

# With:
from services.your_connector import YourConnector as ServiceNowConnector
```

## Common JDBC Patterns

### Pattern 1: Basic Query

```python
def get_data(self, table_name: str) -> List[Dict]:
    query = f"SELECT * FROM {table_name} LIMIT 100"
    return self.execute_query(query)
```

### Pattern 2: Parameterized Query

```python
def get_filtered_data(self, table_name: str, field: str, value: str) -> List[Dict]:
    query = f"""
        SELECT * FROM {table_name} 
        WHERE {field} = '{value}'
        LIMIT 100
    """
    return self.execute_query(query)
```

### Pattern 3: Join Query

```python
def get_related_data(self) -> List[Dict]:
    query = """
        SELECT a.name, b.description
        FROM sys_app a
        JOIN sys_app_module b ON a.sys_id = b.application
        WHERE a.active = 'true'
    """
    return self.execute_query(query)
```

### Pattern 4: Metadata Query

```python
def get_table_info(self, table_name: str) -> List[Dict]:
    query = f"""
        SELECT column_name, internal_type, max_length
        FROM sys_dictionary
        WHERE name = '{table_name}'
        ORDER BY column_name
    """
    return self.execute_query(query)
```

## Providing Your Existing Code

When you provide your existing JDBC connection code, please include:

1. **Connection initialization code**:
   - How you start the JVM
   - JDBC URL format
   - Connection properties

2. **Query execution code**:
   - How you execute queries
   - How you process result sets
   - Any error handling

3. **Specific queries you use**:
   - Table discovery queries
   - Application queries
   - Component queries

4. **Any special configuration**:
   - Custom JDBC properties
   - Timeout settings
   - Connection pooling

## Example Integration

Here's an example of how to integrate your code:

```python
# Your existing code
class MyServiceNowConnection:
    def __init__(self, instance, user, password, jar_path):
        self.instance = instance
        self.user = user
        self.password = password
        self.jar_path = jar_path
        self.conn = None
    
    def connect(self):
        # Your connection logic
        pass
    
    def query(self, sql):
        # Your query logic
        pass

# Adapter to make it work with the application
class ServiceNowConnector:
    def __init__(self, instance: str, username: str, password: str, jdbc_path: str):
        self.my_conn = MyServiceNowConnection(instance, username, password, jdbc_path)
        self.my_conn.connect()
    
    def is_connected(self) -> bool:
        return self.my_conn.conn is not None
    
    def execute_query(self, query: str) -> List[Dict]:
        results = self.my_conn.query(query)
        # Convert your result format to List[Dict]
        return results
    
    # Implement other required methods...
```

## Testing Your Integration

After integrating your code, test it:

```python
# Test script: test_connection.py
from services.servicenow_connector import ServiceNowConnector

connector = ServiceNowConnector(
    instance="your_instance",
    username="your_username",
    password="your_password",
    jdbc_path="./jdbc/servicenow-jdbc.jar"
)

# Test connection
print("Testing connection...")
connector.connect()
print(f"Connected: {connector.is_connected()}")

# Test query
print("\nTesting query...")
tables = connector.get_available_tables()
print(f"Found {len(tables)} tables")
print(f"First 5 tables: {tables[:5]}")

# Test applications
print("\nTesting applications...")
apps = connector.get_installed_applications()
print(f"Found {len(apps)} applications")

connector.close()
print("\nConnection closed")
```

Run the test:
```bash
cd backend
source venv/bin/activate
python test_connection.py
```

## Need Help?

If you need assistance integrating your existing code:

1. Share your existing connection code
2. Describe any specific requirements or constraints
3. Provide example queries you typically use
4. Mention any issues you've encountered

The application is designed to be flexible and can accommodate various JDBC connection patterns.
