import os
import sys
from dotenv import load_dotenv

load_dotenv()

from services.servicenow_connector import ServiceNowConnector

def test_connection():
    print("=" * 60)
    print("ServiceNow Connection Test")
    print("=" * 60)
    
    instance = os.getenv('SERVICENOW_INSTANCE')
    username = os.getenv('SERVICENOW_USERNAME')
    password = os.getenv('SERVICENOW_PASSWORD')
    jdbc_path = os.getenv('SERVICENOW_JDBC_PATH', './jdbc/ServiceNowJdbc-1.0.3-SNAPSHOT.jar')
    
    if not all([instance, username, password]):
        print("ERROR: Missing required environment variables")
        print("Please set SERVICENOW_INSTANCE, SERVICENOW_USERNAME, and SERVICENOW_PASSWORD in .env")
        sys.exit(1)
    
    print(f"\nInstance: {instance}")
    print(f"Username: {username}")
    print(f"JDBC Path: {jdbc_path}")
    print()
    
    try:
        print("Creating connector...")
        connector = ServiceNowConnector(
            instance=instance,
            username=username,
            password=password,
            jdbc_path=jdbc_path
        )
        
        print("Testing connection...")
        connector.connect()
        
        if connector.is_connected():
            print("✓ Connection successful!")
            
            print("\n" + "-" * 60)
            print("Testing: Get Available Tables")
            print("-" * 60)
            tables = connector.get_available_tables()
            print(f"Found {len(tables)} tables")
            if tables:
                print(f"First 10 tables: {tables[:10]}")
            
            print("\n" + "-" * 60)
            print("Testing: Get Installed Applications")
            print("-" * 60)
            apps = connector.get_installed_applications()
            print(f"Found {len(apps)} applications")
            if apps:
                print(f"First 5 applications:")
                for app in apps[:5]:
                    print(f"  - {app.get('name', 'Unknown')} (v{app.get('version', 'N/A')})")
            
            print("\n" + "-" * 60)
            print("Testing: Get Components")
            print("-" * 60)
            components = connector.get_components()
            for comp_type, comp_list in components.items():
                print(f"  {comp_type}: {len(comp_list)} items")
            
            print("\n" + "=" * 60)
            print("All tests passed successfully!")
            print("=" * 60)
            
            connector.close()
        else:
            print("✗ Connection failed")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_connection()
