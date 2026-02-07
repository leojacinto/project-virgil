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

class ArchitectureRequest(BaseModel):
    query: str
    include_web_search: bool = True
    include_pricing: bool = True
    diagram_format: str = "png"

class AnalysisResponse(BaseModel):
    analysis: str
    recommendations: List[dict]
    diagram_path: Optional[str] = None
    metadata: dict

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
    global servicenow_connector
    try:
        jdbc_path = config.jdbc_path if config.jdbc_path else settings.servicenow_jdbc_path
        servicenow_connector = ServiceNowConnector(
            instance=config.instance,
            username=config.username,
            password=config.password,
            jdbc_path=jdbc_path
        )
        
        is_connected = servicenow_connector.test_connection()
        
        if is_connected:
            return {
                "status": "connected",
                "message": "Successfully connected to ServiceNow RaptorDB",
                "instance": config.instance
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to connect to ServiceNow")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection error: {str(e)}")

@app.get("/api/connection/status")
async def get_connection_status():
    if servicenow_connector and servicenow_connector.is_connected():
        return {
            "connected": True,
            "instance": servicenow_connector.instance
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
        servicenow_data = {
            "tables": servicenow_connector.get_available_tables(),
            "applications": servicenow_connector.get_installed_applications(),
            "components": servicenow_connector.get_components()
        }
        
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
        
        check_cancelled()
        diagram_path = None
        if analysis.get("architecture_components"):
            diagram_path = diagram_generator.generate_diagram(
                components=analysis["architecture_components"],
                format=request.diagram_format
            )
        
        return AnalysisResponse(
            analysis=analysis["analysis"],
            recommendations=analysis["recommendations"],
            diagram_path=diagram_path,
            metadata={
                "timestamp": datetime.now().isoformat(),
                "query": request.query,
                "servicenow_instance": servicenow_connector.instance,
                "tables_analyzed": len(servicenow_data["tables"]),
                "apps_analyzed": len(servicenow_data["applications"]),
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
