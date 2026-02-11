from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
import os
import uuid
from datetime import datetime
import threading
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from config import settings
from services.servicenow_connector import ServiceNowConnector
from services.document_processor import DocumentProcessor
from services.llm_service import LLMService
from services.diagram_generator import DiagramGenerator
from services.web_search import WebSearchService

app = FastAPI(title="ServiceNow Architecture Diagram Generator")

# Task cancellation tracking
active_tasks = {}
tasks_lock = threading.Lock()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

servicenow_connector = None
sn_utils_service_instance = None
connection_mode = None  # 'rest_only' or 'rest_and_jdbc'
document_processor = DocumentProcessor()
llm_service = LLMService()
diagram_generator = DiagramGenerator()
web_search_service = WebSearchService()

class LLMConfig(BaseModel):
    provider: str
    api_key: str
    model: Optional[str] = None

class ConnectionConfig(BaseModel):
    instance: str
    username: str
    password: str
    jdbc_path: Optional[str] = None
    connection_mode: str = 'rest_and_jdbc'  # 'rest_only' or 'rest_and_jdbc'

class ArchitectureRequest(BaseModel):
    query: str
    include_web_search: bool = True
    include_pricing: bool = True

class AnalysisResponse(BaseModel):
    analysis: str
    recommendations: List[dict]
    mermaid_diagram: Optional[str] = None
    metadata: dict
    diagram_pipeline: Optional[List[dict]] = None

@app.get("/")
async def root():
    return {"message": "ServiceNow Architecture Diagram Generator API", "status": "running"}

@app.post("/api/llm/configure")
async def configure_llm(config: LLMConfig):
    global llm_service
    try:
        llm_service = LLMService()
        llm_service.configure(
            provider=config.provider,
            api_key=config.api_key,
            model=config.model
        )
        
        if llm_service.is_configured():
            return {
                "status": "configured",
                "message": f"Successfully configured {config.provider}",
                "provider": config.provider
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to configure LLM")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Configuration error: {str(e)}")

@app.get("/api/llm/status")
async def get_llm_status():
    return {
        "configured": llm_service.is_configured(),
        "provider": llm_service.get_provider() if llm_service.is_configured() else None
    }

@app.post("/api/connect")
async def connect_servicenow(config: ConnectionConfig):
    global servicenow_connector, sn_utils_service_instance, connection_mode
    try:
        from services.sn_utils_service import SNUtilsService
        
        connection_mode = config.connection_mode
        
        # Build instance URL for REST API
        instance_url = config.instance
        if not instance_url.endswith('.service-now.com'):
            instance_url = f"{instance_url}.service-now.com"
        
        if connection_mode == 'rest_only':
            # REST API only — no JDBC, no Java required
            logger.info(f"Connecting to ServiceNow via REST API only: {config.instance}")
            sn_utils_service_instance = SNUtilsService(
                instance=instance_url,
                username=config.username,
                password=config.password
            )
            
            # Test REST connection by querying instance info
            test_result = sn_utils_service_instance.get_installed_applications()
            if test_result is not None:
                # Create a lightweight connector stub for backward compatibility
                servicenow_connector = type('RESTOnlyConnector', (), {
                    'instance': config.instance,
                    'username': config.username,
                    'password': config.password,
                    'is_connected': lambda self: True,
                    '_connected': True,
                    'get_available_tables': lambda self: [],
                    'get_installed_applications': lambda self: [],
                    'get_components': lambda self: {},
                    'get_instance_metadata': lambda self: {},
                })()
                return {
                    "status": "connected",
                    "message": "Successfully connected to ServiceNow via REST API",
                    "instance": config.instance,
                    "connection_mode": "rest_only"
                }
            else:
                raise HTTPException(status_code=500, detail="REST API connection failed — check credentials and instance URL")
        else:
            # Full JDBC + REST mode
            logger.info(f"Connecting to ServiceNow via JDBC + REST API: {config.instance}")
            jdbc_path = config.jdbc_path if config.jdbc_path else settings.servicenow_jdbc_path
            servicenow_connector = ServiceNowConnector(
                instance=config.instance,
                username=config.username,
                password=config.password,
                jdbc_path=jdbc_path
            )
            
            is_connected = servicenow_connector.test_connection()
            
            if is_connected:
                # Also init REST API service
                sn_utils_service_instance = SNUtilsService(
                    instance=instance_url,
                    username=config.username,
                    password=config.password
                )
                return {
                    "status": "connected",
                    "message": "Successfully connected to ServiceNow via JDBC + REST API",
                    "instance": config.instance,
                    "connection_mode": "rest_and_jdbc"
                }
            else:
                raise HTTPException(status_code=500, detail="JDBC connection failed")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection error: {str(e)}")

@app.get("/api/connection/status")
async def get_connection_status():
    if servicenow_connector and servicenow_connector.is_connected():
        return {
            "connected": True,
            "instance": servicenow_connector.instance,
            "connection_mode": connection_mode or 'rest_and_jdbc'
        }
    return {"connected": False}

@app.get("/api/servicenow/tables")
async def get_available_tables():
    if not servicenow_connector or not servicenow_connector.is_connected():
        raise HTTPException(status_code=400, detail="Not connected to ServiceNow")
    
    try:
        tables = servicenow_connector.get_available_tables()
        return {"tables": tables, "count": len(tables)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching tables: {str(e)}")

@app.get("/api/servicenow/installed-apps")
async def get_installed_applications():
    if not servicenow_connector or not servicenow_connector.is_connected():
        raise HTTPException(status_code=400, detail="Not connected to ServiceNow")
    
    try:
        apps = servicenow_connector.get_installed_applications()
        return {"applications": apps, "count": len(apps)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching applications: {str(e)}")

@app.get("/api/servicenow/components")
async def get_components():
    if not servicenow_connector or not servicenow_connector.is_connected():
        raise HTTPException(status_code=400, detail="Not connected to ServiceNow")
    
    try:
        components = servicenow_connector.get_components()
        return {"components": components}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching components: {str(e)}")

@app.get("/api/servicenow/instance-summary")
async def get_instance_summary():
    """Get comprehensive instance data using SN Utils REST API"""
    if not servicenow_connector or not servicenow_connector.is_connected():
        raise HTTPException(status_code=400, detail="Not connected to ServiceNow")
    
    try:
        # Use stored SN Utils instance if available, otherwise create one
        sn_utils = sn_utils_service_instance
        if not sn_utils:
            from services.sn_utils_service import SNUtilsService
            instance_url = servicenow_connector.instance
            if not instance_url.endswith('.service-now.com'):
                instance_url = f"{instance_url}.service-now.com"
            sn_utils = SNUtilsService(
                instance_url,
                servicenow_connector.username,
                servicenow_connector.password
            )
        
        instance_summary = sn_utils.get_instance_summary()
        
        # Get JDBC metadata only if in JDBC mode
        jdbc_metadata = {}
        if connection_mode != 'rest_only':
            try:
                jdbc_metadata = servicenow_connector.get_instance_metadata()
            except Exception as jdbc_err:
                logger.warning(f"JDBC metadata fetch failed (non-critical): {str(jdbc_err)}")
        
        # Combine both data sources
        return {
            "instance": instance_summary.get('instance'),
            "applications": instance_summary.get('applications', []),
            "key_capabilities": instance_summary.get('key_capabilities', {}),
            "connection_mode": connection_mode or 'rest_and_jdbc',
            "jdbc_metadata": {
                "relationships": len(jdbc_metadata.get('relationships', [])),
                "plugins": len(jdbc_metadata.get('plugins', [])),
                "usage_stats": jdbc_metadata.get('usage_stats', []),
                "custom_tables": jdbc_metadata.get('custom_tables', [])
            }
        }
    except Exception as e:
        logger.error(f"Error fetching instance summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching instance summary: {str(e)}")

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    try:
        if not any(file.filename.endswith(ext) for ext in settings.allowed_extensions):
            raise HTTPException(status_code=400, detail="File type not allowed")
        
        file_id = str(uuid.uuid4())
        file_extension = os.path.splitext(file.filename)[1]
        file_path = os.path.join(settings.upload_dir, f"{file_id}{file_extension}")
        
        content = await file.read()
        if len(content) > settings.max_file_size:
            raise HTTPException(status_code=400, detail="File too large")
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        processed_content = document_processor.process_document(file_path)
        document_processor.add_to_vector_store(file_id, processed_content, file.filename)
        
        return {
            "file_id": file_id,
            "filename": file.filename,
            "status": "processed",
            "content_length": len(processed_content)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")

@app.get("/api/documents")
async def list_documents():
    try:
        documents = document_processor.list_documents()
        return {"documents": documents}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")

@app.delete("/api/documents/{file_id}")
async def delete_document(file_id: str):
    try:
        document_processor.delete_document(file_id)
        return {"status": "deleted", "file_id": file_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")

@app.post("/api/analyze")
async def analyze_architecture(request: ArchitectureRequest):
    if not servicenow_connector or not servicenow_connector.is_connected():
        raise HTTPException(status_code=400, detail="Not connected to ServiceNow")
    
    # Generate task ID for cancellation tracking
    task_id = str(uuid.uuid4())
    with tasks_lock:
        active_tasks[task_id] = {"cancelled": False}
    
    try:
        # Check cancellation before each major step
        def check_cancelled():
            with tasks_lock:
                if active_tasks.get(task_id, {}).get("cancelled", False):
                    raise HTTPException(status_code=499, detail="Analysis cancelled by user")
        
        check_cancelled()
        
        # Build servicenow_data based on connection mode
        if connection_mode == 'rest_only':
            # REST API only — use SN Utils for instance data
            rest_apps = []
            rest_capabilities = {}
            if sn_utils_service_instance:
                try:
                    rest_apps = sn_utils_service_instance.get_installed_applications() or []
                    summary = sn_utils_service_instance.get_instance_summary() or {}
                    rest_capabilities = summary.get('key_capabilities', {})
                except Exception as rest_err:
                    logger.warning(f"REST API data fetch failed (non-critical): {str(rest_err)}")
            
            servicenow_data = {
                "tables": [],
                "applications": rest_apps,
                "components": {},
                "connection_mode": "rest_only",
                "key_capabilities": rest_capabilities
            }
        else:
            # Full JDBC + REST mode
            servicenow_data = {
                "tables": servicenow_connector.get_available_tables(),
                "applications": servicenow_connector.get_installed_applications(),
                "components": servicenow_connector.get_components(),
                "connection_mode": "rest_and_jdbc"
            }
            # Enrich with REST API data if available
            if sn_utils_service_instance:
                try:
                    summary = sn_utils_service_instance.get_instance_summary() or {}
                    servicenow_data["key_capabilities"] = summary.get('key_capabilities', {})
                    # Merge REST apps if JDBC apps are empty
                    if not servicenow_data["applications"]:
                        servicenow_data["applications"] = sn_utils_service_instance.get_installed_applications() or []
                except Exception as rest_err:
                    logger.warning(f"REST API enrichment failed (non-critical): {str(rest_err)}")
        
        check_cancelled()
        relevant_docs = []
        if request.include_pricing:
            relevant_docs = document_processor.search_documents(request.query, top_k=5)
        
        check_cancelled()
        web_context = []
        if request.include_web_search:
            web_context = web_search_service.search(request.query)
        
        check_cancelled()
        analysis = llm_service.analyze_architecture(
            query=request.query,
            servicenow_data=servicenow_data,
            documents=relevant_docs,
            web_context=web_context
        )
        
        return AnalysisResponse(
            analysis=analysis.get("analysis", "Analysis not available"),
            recommendations=analysis.get("recommendations", []),
            mermaid_diagram=analysis.get("mermaid_diagram"),
            diagram_pipeline=analysis.get("diagram_pipeline"),
            metadata={
                "timestamp": datetime.now().isoformat(),
                "query": request.query,
                "servicenow_instance": servicenow_connector.instance,
                "connection_mode": connection_mode or 'rest_and_jdbc',
                "tables_analyzed": len(servicenow_data.get("tables", [])),
                "apps_analyzed": len(servicenow_data.get("applications", [])),
                "documents_used": len(relevant_docs),
                "web_sources": len(web_context),
                "task_id": task_id
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        logger.error(f"Analysis failed with error: {error_detail}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup task tracking
        with tasks_lock:
            active_tasks.pop(task_id, None)

@app.post("/api/cancel/{task_id}")
async def cancel_analysis(task_id: str):
    with tasks_lock:
        if task_id in active_tasks:
            active_tasks[task_id]["cancelled"] = True
            return {"status": "cancelled", "task_id": task_id}
        else:
            return {"status": "not_found", "task_id": task_id}

@app.get("/api/diagrams/{diagram_id}")
async def get_diagram(diagram_id: str):
    diagram_path = os.path.join(settings.diagram_output_dir, diagram_id)
    if not os.path.exists(diagram_path):
        raise HTTPException(status_code=404, detail="Diagram not found")
    return FileResponse(diagram_path)

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "servicenow_connected": servicenow_connector is not None and servicenow_connector.is_connected(),
        "llm_configured": llm_service.is_configured(),
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
