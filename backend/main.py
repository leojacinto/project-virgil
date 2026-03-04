from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
import os
import uuid
from datetime import datetime
import threading
import asyncio
import logging
from dotenv import load_dotenv
from pathlib import Path

# Load root .env first (SN_*, ONELLM_*), then backend/.env for overrides
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()  # backend/.env (overrides if same key exists)

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


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    favicon_path = Path(__file__).resolve().parent.parent / "frontend" / "public" / "favicon.svg"
    if favicon_path.exists():
        return FileResponse(favicon_path, media_type="image/svg+xml")
    return JSONResponse(status_code=204, content=None)


def normalize_instance_url(raw: str) -> str:
    """Normalize a ServiceNow instance URL to https://<host>.service-now.com"""
    url = raw.strip().rstrip('/')
    # Strip protocol for uniform handling
    for prefix in ('https://', 'http://'):
        if url.lower().startswith(prefix):
            url = url[len(prefix):]
            break
    url = url.rstrip('/')
    if not url.endswith('.service-now.com'):
        url = f"{url}.service-now.com"
    return f"https://{url}"

class LLMConfig(BaseModel):
    provider: str
    api_key: str
    model: Optional[str] = None
    api_url: Optional[str] = None

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

@app.get("/api/env-defaults")
async def get_env_defaults():
    """Return .env defaults so the SetupWizard can pre-fill fields."""
    return {
        "llm": {
            "provider": "onellm" if os.getenv("ONELLM_API_KEY") else "",
            "api_key": os.getenv("ONELLM_API_KEY", ""),
            "api_url": os.getenv("ONELLM_BASE_URL", ""),
        },
        "servicenow": {
            "instance": os.getenv("SN_INSTANCE") or settings.servicenow_instance or "",
            "username": os.getenv("SN_USER") or settings.servicenow_username or "",
            "password": os.getenv("SN_PASSWORD") or settings.servicenow_password or "",
        }
    }

@app.post("/api/llm/configure")
async def configure_llm(config: LLMConfig):
    global llm_service
    try:
        llm_service = LLMService()
        llm_service.configure(
            provider=config.provider,
            api_key=config.api_key,
            model=config.model,
            api_url=config.api_url
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
        instance_url = normalize_instance_url(config.instance)
        
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
        if connection_mode == 'rest_only' and sn_utils_service_instance:
            total_count = sn_utils_service_instance.get_record_count('sys_db_object')
            tables = sn_utils_service_instance.get_tables(limit=200)
            return {"tables": [t.get('name', '') for t in tables], "count": total_count}
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
        if connection_mode == 'rest_only' and sn_utils_service_instance:
            sn = sn_utils_service_instance
            components = {}
            # Workflows
            wf_count = sn.get_record_count('wf_workflow', query='active=true')
            wf_data = sn._make_request(
                '/api/now/table/wf_workflow',
                params={'sysparm_query': 'active=true', 'sysparm_fields': 'sys_id,name', 'sysparm_limit': 50}
            )
            components['workflows'] = wf_data.get('result', []) if wf_data else []
            # Business rules
            br_count = sn.get_record_count('sys_script', query='active=true')
            br_data = sn._make_request(
                '/api/now/table/sys_script',
                params={'sysparm_query': 'active=true', 'sysparm_fields': 'sys_id,name', 'sysparm_limit': 50}
            )
            components['business_rules'] = br_data.get('result', []) if br_data else []
            # Integrations (Flow Designer flows)
            flow_count = sn.get_record_count('sys_hub_flow', query='active=true')
            flow_data = sn._make_request(
                '/api/now/table/sys_hub_flow',
                params={'sysparm_query': 'active=true', 'sysparm_fields': 'sys_id,name', 'sysparm_limit': 50}
            )
            components['integrations'] = flow_data.get('result', []) if flow_data else []
            components['counts'] = {
                'workflows': wf_count,
                'business_rules': br_count,
                'integrations': flow_count,
            }
            return {"components": components}
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
async def upload_document(
    file: UploadFile = File(...),
    store: str = Form(default='customer_documents')
):
    """Upload a document to either servicenow_assets or customer_documents store."""
    try:
        if not any(file.filename.endswith(ext) for ext in settings.allowed_extensions):
            raise HTTPException(status_code=400, detail="File type not allowed")
        
        if store not in ('servicenow_assets', 'customer_documents'):
            raise HTTPException(status_code=400, detail=f"Invalid store: {store}")
        
        file_id = str(uuid.uuid4())
        file_extension = os.path.splitext(file.filename)[1]
        file_path = os.path.join(settings.upload_dir, f"{file_id}{file_extension}")
        
        content = await file.read()
        if len(content) > settings.max_file_size:
            raise HTTPException(status_code=400, detail="File too large")
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        processed_content = document_processor.process_document(file_path)
        current_instance = servicenow_connector.instance if servicenow_connector else "unknown"
        document_processor.add_to_vector_store(file_id, processed_content, file.filename, store=store, instance_name=current_instance)
        
        return {
            "file_id": file_id,
            "filename": file.filename,
            "status": "processed",
            "store": store,
            "content_length": len(processed_content)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")

@app.get("/api/documents")
async def list_documents(store: str = Query(default=None)):
    """List documents. Pass ?store=servicenow_assets or ?store=customer_documents to filter."""
    try:
        documents = document_processor.list_documents(store=store)
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

@app.get("/api/analyze/progress")
async def analyze_progress():
    return llm_service.get_progress()

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
                "key_capabilities": rest_capabilities,
                "instance_summary": summary if sn_utils_service_instance else {}
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
                    servicenow_data["instance_summary"] = summary
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
        analysis = await asyncio.to_thread(
            llm_service.analyze_architecture,
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

@app.get("/api/debug/plugins")
async def debug_plugins():
    """Temporary diagnostic — dump all discovered plugin IDs from the live instance."""
    if sn_utils_service_instance is None:
        raise HTTPException(status_code=400, detail="Not connected")
    sn = sn_utils_service_instance
    result = {"sys_app": {}, "v_plugin": {}, "sys_store_app": {}}
    # 1) sys_app
    apps = sn.get_installed_applications() or []
    for a in apps:
        s = a.get("scope", "")
        if s: result["sys_app"][s] = a.get("name", "")
    # 2) v_plugin
    data = sn._make_request("/api/now/table/v_plugin",
        params={"sysparm_fields": "id,name,active", "sysparm_query": "active=true", "sysparm_limit": 2000},
        cache_key="debug_v_plugin")
    if data:
        for p in data.get("result", []):
            pid = p.get("id", "")
            if pid: result["v_plugin"][pid] = p.get("name", "")
    # 3) sys_store_app
    sdata = sn._make_request("/api/now/table/sys_store_app",
        params={"sysparm_fields": "scope,name", "sysparm_limit": 1000},
        cache_key="debug_sys_store_app")
    if sdata:
        for sa in sdata.get("result", []):
            s = sa.get("scope", "")
            if s: result["sys_store_app"][s] = sa.get("name", "")
    result["totals"] = {k: len(v) for k, v in result.items() if k != "totals"}
    return result

@app.post("/api/assess")
async def assess_instance():
    """Run Instance Assessment (Minos) — deterministic scan + rule evaluation."""
    from services.instance_scanner import InstanceScanner
    from services.instance_scanner_rules import ENABLED as RULES_ENABLED, RuleEngine

    if sn_utils_service_instance is None:
        raise HTTPException(status_code=400, detail="Not connected to a ServiceNow instance")

    try:
        scanner = InstanceScanner(sn_utils_service_instance)
        result = scanner.scan()
        return result
    except Exception as e:
        logger.error(f"Instance assessment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/assess/rules")
async def get_assessment_rules():
    """Return the full rule catalog and enabled status (no instance connection needed)."""
    from services.instance_scanner_rules import RuleEngine
    engine = RuleEngine()
    return {
        "summary": engine.get_rule_summary(),
        "rules": engine.get_all_rules(),
    }

@app.get("/api/assess/knowledge-base")
async def get_assessment_knowledge_base():
    """Return structured knowledge base summaries for each rule source."""
    from services.instance_scanner_rules import RuleEngine
    engine = RuleEngine()
    return {"sources": engine.get_knowledge_base()}

@app.get("/api/rules/yaml")
async def get_rules_yaml():
    """Return the full YAML data for the rule editor."""
    from services.instance_scanner_rules import get_full_yaml
    return get_full_yaml()

@app.post("/api/rules/save")
async def save_rules(payload: dict):
    """Save modified rules back to rules.yaml and hot-reload the engine."""
    from services.instance_scanner_rules import save_rules_yaml, RuleEngine
    try:
        total = save_rules_yaml(payload)
        engine = RuleEngine()
        return {
            "status": "saved",
            "total_rules": total,
            "summary": engine.get_rule_summary(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to save rules: {str(e)}")

# ---------------------------------------------------------------------------
# Plutus — WDF Pricing & Credit Sizing
# ---------------------------------------------------------------------------

_PLUTUS_KEY_PATH = Path(__file__).resolve().parent / ".plutus_key"

def _plutus_hash(password: str, salt: bytes) -> bytes:
    import hashlib
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)

@app.post("/api/plutus/verify-password")
async def plutus_verify_password(payload: dict):
    """Verify Plutus access password against the stored hash."""
    import hashlib, base64
    password = payload.get("password", "")
    if not _PLUTUS_KEY_PATH.exists():
        raise HTTPException(status_code=503, detail="Plutus password not configured. Run: python set_plutus_password.py")
    raw = _PLUTUS_KEY_PATH.read_bytes()
    salt, stored_hash = raw[:32], raw[32:]
    if _plutus_hash(password, salt) == stored_hash:
        return {"status": "ok"}
    raise HTTPException(status_code=401, detail="Incorrect password")

@app.post("/api/plutus/scan")
async def plutus_scan():
    """Run Plutus WDF credit sizing scan against the connected instance."""
    from services.plutus_scanner import PlutusScanner

    if sn_utils_service_instance is None:
        raise HTTPException(status_code=400, detail="Not connected to a ServiceNow instance")

    try:
        # Reuse Minos scan data if available (active_node_ids, active_tables)
        from services.instance_scanner import InstanceScanner
        minos = InstanceScanner(sn_utils_service_instance)
        minos_result = minos.scan()

        # Extract active node IDs from the active_nodes list
        active_node_ids = set(
            n["id"] for n in minos_result.get("active_nodes", [])
        )
        # Extract table counts from instance_model
        active_tables = minos_result.get("instance_model", {}).get("active_tables", {})

        scanner = PlutusScanner(sn_utils_service_instance)
        result = scanner.scan(
            active_node_ids=active_node_ids,
            active_tables=active_tables,
        )
        return scanner.result_to_dict(result)
    except Exception as e:
        logger.error(f"Plutus scan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/plutus/recalculate")
async def plutus_recalculate(payload: dict):
    """Recalculate Plutus credits with user-supplied usage overrides (no instance scan)."""
    from services.plutus_scanner import PlutusPricingConfig

    try:
        config = PlutusPricingConfig()
        overrides = payload.get("overrides", {})
        previous_usage = payload.get("previous_usage", [])

        # Index previous scan results by capability_id for fast lookup
        prev_by_id = {u["capability_id"]: u for u in previous_usage}

        from services.plutus_scanner import PlutusResult, CapabilityUsage
        result = PlutusResult()
        result.pricing_config = config.raw
        result.credits_per_pack = config.packs.get("credits_per_pack", 2_000_000)
        result.price_per_pack = config.packs.get("price_per_pack_yearly", 100_000)

        for cap in config.rate_card:
            if cap.get("hidden", False):
                continue
            cap_id = cap["id"]
            prev = prev_by_id.get(cap_id, {})

            usage = CapabilityUsage(
                capability_id=cap_id,
                label=cap.get("label", cap_id),
                meter_unit=cap.get("meter_unit", ""),
                credits_per_unit=cap.get("credits", 0),
                pro_only=cap.get("pro_only", False),
                measurable=cap.get("measurable", True),
                measurement_rule=(cap.get("measurement_rule", "") or "").strip(),
            )

            if cap_id in overrides:
                # User explicitly changed this value
                usage.user_override = overrides[cap_id]
                usage.usage_value = overrides[cap_id]
                usage.usage_per_year = overrides[cap_id]
                usage.detected = overrides[cap_id] > 0
                usage.scan_evidence = "User-provided value" if overrides[cap_id] > 0 else ""
                usage.is_estimated = False
                usage.data_days = 0
            elif prev:
                # Preserve original scan data including annualized fields
                usage.usage_value = prev.get("usage_value", 0)
                usage.detected = prev.get("detected", False)
                usage.scan_evidence = prev.get("scan_evidence", "")
                usage.data_days = prev.get("data_days", 0)
                usage.is_estimated = prev.get("is_estimated", False)
                usage.usage_per_year = prev.get("usage_per_year", 0)

            usage.total_credits = usage.usage_per_year * usage.credits_per_unit
            result.capability_usage.append(usage)
            result.total_credits += usage.total_credits

            if usage.pro_only and usage.usage_value > 0:
                result.requires_pro = True
                result.pro_reasons.append(f"{usage.label} requires Professional tier")

        from services.plutus_scanner import PlutusScanner
        scanner = PlutusScanner(None, pricing_config=config)
        scanner._calculate_tier(result)
        return scanner.result_to_dict(result)
    except Exception as e:
        logger.error(f"Plutus recalculation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/plutus/config")
async def get_plutus_config():
    """Return the full Plutus pricing YAML for the frontend editor."""
    from services.plutus_scanner import PlutusPricingConfig
    config = PlutusPricingConfig()
    return config.raw


@app.post("/api/plutus/config")
async def save_plutus_config(payload: dict):
    """Save modified Plutus pricing config back to YAML."""
    from services.plutus_scanner import PlutusPricingConfig
    try:
        config = PlutusPricingConfig()
        config.save(payload)
        config.reload()
        return {
            "status": "saved",
            "rate_card_count": len(config.rate_card),
            "tiers": list(config.tiers.keys()),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to save pricing config: {str(e)}")


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "servicenow_connected": servicenow_connector is not None and servicenow_connector.is_connected(),
        "llm_configured": llm_service.is_configured(),
        "timestamp": datetime.now().isoformat()
    }

@app.on_event("startup")
async def auto_connect_from_env():
    """Auto-connect to ServiceNow on startup if .env credentials are present."""
    global servicenow_connector, sn_utils_service_instance, connection_mode
    # Skip if already connected (e.g. from a previous call)
    if servicenow_connector is not None:
        return
    sn_inst = settings.servicenow_instance
    sn_user = settings.servicenow_username
    sn_pass = settings.servicenow_password
    if not sn_inst or not sn_user or not sn_pass:
        logger.info("No ServiceNow credentials in .env — skipping auto-connect")
        return
    try:
        from services.sn_utils_service import SNUtilsService
        instance_url = normalize_instance_url(sn_inst)
        logger.info(f"Auto-connecting to ServiceNow from .env: {instance_url}")
        sn_utils_service_instance = SNUtilsService(
            instance=instance_url,
            username=sn_user,
            password=sn_pass,
        )
        test = sn_utils_service_instance.get_installed_applications()
        if test is not None:
            connection_mode = "rest_only"
            servicenow_connector = type('RESTOnlyConnector', (), {
                'instance': instance_url,
                'username': sn_user,
                'password': sn_pass,
                'is_connected': lambda self: True,
                '_connected': True,
                'get_available_tables': lambda self: [],
                'get_installed_applications': lambda self: [],
                'get_components': lambda self: {},
                'get_instance_metadata': lambda self: {},
            })()
            logger.info(f"Auto-connected to {instance_url} via REST API (from .env)")
        else:
            logger.warning("Auto-connect failed — REST API returned None. Connect manually.")
            sn_utils_service_instance = None
    except Exception as e:
        logger.warning(f"Auto-connect from .env failed: {e}")
        sn_utils_service_instance = None

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
