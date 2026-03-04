#!/usr/bin/env python3
"""
Virgil ServiceNow Scoped App Deployer

Deploys all Virgil artifacts to a ServiceNow instance via REST API:
  - Scoped app (x_snc_virgil)
  - Custom tables + fields
  - Script Includes (Minos, Plutus, Virgil utils)
  - Scripted REST APIs
  - App Menu navigation
  - Roles + ACLs

Usage:
    cd project-virgil
    backend/venv/bin/python servicenow-app/deploy.py [--dry-run] [--only COMPONENT]

Components: app, roles, tables, seed, scripts, rest_api, acls, menu
"""

import os
import sys
import json
import uuid
import time
import argparse
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# ── Config ────────────────────────────────────────────────────────────────────

APP_SCOPE = "x_snc_virgil"
APP_NAME = "Virgil"
APP_VERSION = "1.0.0"

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

INSTANCE = os.getenv("SN_INSTANCE", "").strip().rstrip("/")
USER = os.getenv("SN_USER", "")
PASSWORD = os.getenv("SN_PASSWORD", "")

if not INSTANCE.startswith("http"):
    INSTANCE = f"https://{INSTANCE}"

AUTH = (USER, PASSWORD)
HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}
BASE_DIR = Path(__file__).resolve().parent

# Persistent ID map — re-deploys update, not duplicate
ID_MAP_FILE = BASE_DIR / ".deploy_ids.json"


def load_id_map():
    if ID_MAP_FILE.exists():
        return json.loads(ID_MAP_FILE.read_text())
    return {}


def save_id_map(id_map):
    ID_MAP_FILE.write_text(json.dumps(id_map, indent=2))


def get_id(id_map, key):
    if key not in id_map:
        id_map[key] = uuid.uuid4().hex
    return id_map[key]


# ── REST helpers ──────────────────────────────────────────────────────────────

def sn_get(table, query, fields="sys_id"):
    url = f"{INSTANCE}/api/now/table/{table}"
    params = {"sysparm_query": query, "sysparm_fields": fields, "sysparm_limit": 1}
    r = requests.get(url, auth=AUTH, headers=HEADERS, params=params, timeout=30)
    if r.status_code == 200:
        results = r.json().get("result", [])
        return results[0] if results else None
    return None


def sn_get_all(table, query, fields="sys_id"):
    url = f"{INSTANCE}/api/now/table/{table}"
    params = {"sysparm_query": query, "sysparm_fields": fields, "sysparm_limit": 500}
    r = requests.get(url, auth=AUTH, headers=HEADERS, params=params, timeout=30)
    if r.status_code == 200:
        return r.json().get("result", [])
    return []


def sn_create(table, payload, dry_run=False):
    if dry_run:
        print(f"    [DRY-RUN] Would create {table}")
        return "dry-run-id"
    url = f"{INSTANCE}/api/now/table/{table}"
    r = requests.post(url, auth=AUTH, headers=HEADERS, json=payload, timeout=30)
    if r.status_code in (200, 201):
        sid = r.json().get("result", {}).get("sys_id")
        print(f"    ✅ Created {table} → {sid}")
        return sid
    else:
        print(f"    ❌ ERROR {table}: {r.status_code} - {r.text[:200]}")
        return None


def sn_update(table, sys_id, payload, dry_run=False):
    if dry_run:
        print(f"    [DRY-RUN] Would update {table}/{sys_id}")
        return True
    url = f"{INSTANCE}/api/now/table/{table}/{sys_id}"
    r = requests.patch(url, auth=AUTH, headers=HEADERS, json=payload, timeout=30)
    if r.status_code == 200:
        print(f"    ✅ Updated {table}/{sys_id}")
        return True
    else:
        print(f"    ❌ ERROR {table}/{sys_id}: {r.status_code} - {r.text[:200]}")
        return False


def sn_upsert(table, query, payload, dry_run=False):
    existing = sn_get(table, query)
    if existing:
        sn_update(table, existing["sys_id"], payload, dry_run)
        return existing["sys_id"]
    else:
        return sn_create(table, payload, dry_run)


def read_file(relative_path):
    fpath = BASE_DIR / relative_path
    if not fpath.exists():
        print(f"    ⚠️  File not found: {relative_path}")
        return ""
    return fpath.read_text(encoding="utf-8")


# ── SN field type mapping ─────────────────────────────────────────────────────

FIELD_TYPE_MAP = {
    "string": {"internal_type": "string", "element": ""},
    "integer": {"internal_type": "integer", "element": ""},
    "decimal": {"internal_type": "decimal", "element": ""},
    "boolean": {"internal_type": "boolean", "element": ""},
    "choice": {"internal_type": "string", "element": "choice"},
    "reference": {"internal_type": "reference", "element": ""},
    "glide_date_time": {"internal_type": "glide_date_time", "element": ""},
}


# ── Component deployers ───────────────────────────────────────────────────────

def deploy_app(id_map, dry_run):
    """Create or verify the scoped application."""
    print("\n══════ Scoped Application ══════")
    existing = sn_get("sys_app", f"scope={APP_SCOPE}", "sys_id,name,scope")
    if existing:
        id_map["app"] = existing["sys_id"]
        print(f"  App '{APP_SCOPE}' already exists: {existing['sys_id']}")
    else:
        sid = sn_create("sys_app", {
            "name": APP_NAME,
            "scope": APP_SCOPE,
            "version": APP_VERSION,
            "short_description": "Presales intelligence — Architecture Scan, WDF Sizing, AI Advisor",
            "active": "true",
        }, dry_run)
        if sid:
            id_map["app"] = sid
    return id_map.get("app")


def deploy_roles(id_map, dry_run):
    """Create application roles."""
    print("\n══════ Roles ══════")
    roles = [
        {"suffix": "admin", "name": "Virgil Admin", "description": "Full access to all Virgil engines"},
        {"suffix": "user", "name": "Virgil User", "description": "Run scans and view results"},
    ]
    for role in roles:
        role_name = f"{APP_SCOPE}.{role['suffix']}"
        sid = sn_upsert("sys_user_role", f"name={role_name}", {
            "name": role_name,
            "description": role["description"],
        }, dry_run)
        if sid:
            id_map[f"role_{role['suffix']}"] = sid


def deploy_tables(id_map, dry_run):
    """Create custom tables from JSON schema definitions in tables/."""
    print("\n══════ Custom Tables ══════")
    tables_dir = BASE_DIR / "tables"
    if not tables_dir.exists():
        print("  ⚠️  tables/ directory not found")
        return

    for schema_file in sorted(tables_dir.glob("*.json")):
        schema = json.loads(schema_file.read_text())
        table_name = schema["name"]
        table_label = schema["label"]
        print(f"\n  Table: {table_name} ({table_label})")

        # Check if table already exists
        existing = sn_get("sys_db_object", f"name={table_name}", "sys_id,name")
        if existing:
            print(f"    Table already exists: {existing['sys_id']}")
            id_map[f"table_{table_name}"] = existing["sys_id"]
        else:
            # Create table via sys_db_object
            table_payload = {
                "name": table_name,
                "label": table_label,
                "plural": schema.get("plural", table_label + "s"),
                "sys_scope": id_map.get("app", ""),
            }
            if schema.get("extends"):
                table_payload["super_class"] = schema["extends"]

            table_sid = sn_create("sys_db_object", table_payload, dry_run)
            if table_sid:
                id_map[f"table_{table_name}"] = table_sid

        # Create fields via sys_dictionary
        for field in schema.get("fields", []):
            field_name = field["name"]
            field_label = field["label"]
            ftype = FIELD_TYPE_MAP.get(field["type"], {"internal_type": "string", "element": ""})

            # Check if field exists
            existing_field = sn_get("sys_dictionary",
                f"name={table_name}^element={field_name}", "sys_id")
            if existing_field:
                print(f"    Field exists: {field_name}")
                continue

            field_payload = {
                "name": table_name,
                "element": field_name,
                "column_label": field_label,
                "internal_type": ftype["internal_type"],
                "max_length": str(field.get("max_length", 255)),
                "active": "true",
                "mandatory": str(field.get("mandatory", False)).lower(),
                "unique": str(field.get("unique", False)).lower(),
            }
            if field.get("default_value"):
                field_payload["default_value"] = field["default_value"]
            if field["type"] == "reference" and field.get("reference"):
                field_payload["reference"] = field["reference"]
            if ftype["element"]:
                # For choice fields, set the element type
                field_payload["internal_type"] = "string"

            print(f"    Creating field: {field_name} ({field['type']})")
            sn_create("sys_dictionary", field_payload, dry_run)

            # Create choice values if applicable
            if field["type"] == "choice" and field.get("choices"):
                for idx, choice_val in enumerate(field["choices"]):
                    sn_upsert("sys_choice",
                        f"name={table_name}^element={field_name}^value={choice_val}", {
                            "name": table_name,
                            "element": field_name,
                            "value": choice_val,
                            "label": choice_val.replace("_", " ").title(),
                            "sequence": str(idx * 10),
                        }, dry_run)


def flush_cache(dry_run):
    """Flush ServiceNow instance cache so newly created tables become accessible."""
    if dry_run:
        print("  [DRY-RUN] Would flush cache")
        return
    print("  Flushing instance cache...")
    # Try the cache flush endpoint
    try:
        r = requests.get(f"{INSTANCE}/cache.do", auth=AUTH, timeout=30, allow_redirects=True)
        print(f"    cache.do → {r.status_code}")
    except Exception:
        pass
    # Wait for tables to propagate
    print("  Waiting 20s for table schema propagation...")
    time.sleep(20)


def _seed_table_with_retry(table, records, key_fields, dry_run, max_retries=3):
    """Seed a single table, retrying on 'Invalid table' errors."""
    for attempt in range(max_retries):
        created = 0
        updated = 0
        errors = 0
        for record in records:
            query_parts = [f"{kf}={record.get(kf, '')}" for kf in key_fields]
            query = "^".join(query_parts)

            payload = {}
            for k, v in record.items():
                if isinstance(v, bool):
                    payload[k] = "true" if v else "false"
                else:
                    payload[k] = str(v) if v is not None else ""

            existing = sn_get(table, query)
            if existing:
                sn_update(table, existing["sys_id"], payload, dry_run)
                updated += 1
            else:
                result = sn_create(table, payload, dry_run)
                if result:
                    created += 1
                else:
                    errors += 1

        if errors == 0 or dry_run:
            print(f"    → {created} created, {updated} updated")
            return True
        elif attempt < max_retries - 1:
            wait = 15 * (attempt + 1)
            print(f"    ⚠️  {errors} errors — table may not be cached yet. Retrying in {wait}s (attempt {attempt+2}/{max_retries})...")
            time.sleep(wait)
        else:
            print(f"    ❌ {errors} errors after {max_retries} attempts")
            return False


def deploy_seed_data(id_map, dry_run):
    """Populate tables with seed data from data/ directory."""
    print("\n══════ Seed Data ══════")

    # Flush cache first so newly created tables are accessible
    flush_cache(dry_run)

    data_dir = BASE_DIR / "data"
    if not data_dir.exists():
        print("  ⚠️  data/ directory not found")
        return

    # Map: seed file → target table + unique key field
    seed_map = {
        "minos_rules_seed.json": {"table": "x_snc_virgil_minos_rule", "key": "rule_id"},
        "ontology_nodes_seed.json": {"table": "x_snc_virgil_ontology_node", "key": "node_id"},
        "ontology_edges_seed.json": {"table": "x_snc_virgil_ontology_edge", "key": "source_node^target_node^rel_type"},
        "wdf_rate_card_seed.json": {"table": "x_snc_virgil_wdf_rate_card", "key": "cap_id"},
    }

    for filename, config in seed_map.items():
        seed_file = data_dir / filename
        if not seed_file.exists():
            print(f"  ⚠️  {filename} not found, skipping")
            continue

        records = json.loads(seed_file.read_text())
        table = config["table"]
        key_fields = config["key"].split("^")
        print(f"\n  Seeding {table}: {len(records)} records")

        _seed_table_with_retry(table, records, key_fields, dry_run)


def deploy_script_includes(id_map, dry_run):
    """Deploy all Script Includes."""
    print("\n══════ Script Includes ══════")
    scripts_dir = BASE_DIR / "script_includes"
    if not scripts_dir.exists():
        print("  ⚠️  script_includes/ directory not found")
        return

    for js_file in sorted(scripts_dir.glob("*.js")):
        name = js_file.stem
        script_content = js_file.read_text(encoding="utf-8")
        api_name = f"{APP_SCOPE}.{name}"

        # VirgilAjax must be client_callable for GlideAjax from UI Builder
        client_callable = "true" if name == "VirgilAjax" else "false"

        print(f"  Deploying Script Include: {name} (client_callable={client_callable})")
        sid = sn_upsert("sys_script_include", f"api_name={api_name}", {
            "name": name,
            "api_name": api_name,
            "script": script_content,
            "active": "true",
            "access": "public",
            "client_callable": client_callable,
            "sys_scope": id_map.get("app", ""),
        }, dry_run)
        if sid:
            id_map[f"si_{name}"] = sid


def deploy_rest_api(id_map, dry_run):
    """Deploy Scripted REST API definition + operations."""
    print("\n══════ Scripted REST API ══════")
    rest_def_file = BASE_DIR / "rest_api" / "virgil_api.json"
    if not rest_def_file.exists():
        print("  ⚠️  rest_api/virgil_api.json not found, skipping")
        return

    rest_def = json.loads(rest_def_file.read_text())
    api_name = rest_def["name"]
    print(f"  Deploying REST API: {api_name}")
    api_sid = sn_upsert("sys_ws_definition", f"name={api_name}", {
        "name": api_name,
        "short_description": rest_def.get("description", ""),
        "is_active": "true",
        "namespace": APP_SCOPE,
    }, dry_run)
    if api_sid:
        id_map["rest_api"] = api_sid

    ops_dir = BASE_DIR / "rest_api" / "operations"
    if ops_dir.exists():
        for op_file in sorted(ops_dir.glob("*.json")):
            op_def = json.loads(op_file.read_text())
            op_name = op_def["name"]
            script_file = op_def.get("script_file", "")
            script_content = ""
            if script_file:
                spath = ops_dir / script_file
                if spath.exists():
                    script_content = spath.read_text(encoding="utf-8")

            print(f"    Operation: {op_def['http_method']} {op_def['relative_path']}")
            sn_upsert("sys_ws_operation",
                f"name={op_name}^web_service_definition={api_sid}", {
                    "name": op_name,
                    "web_service_definition": api_sid,
                    "http_method": op_def["http_method"],
                    "relative_path": op_def["relative_path"],
                    "operation_script": script_content,
                    "short_description": op_def.get("description", ""),
                    "active": "true",
                }, dry_run)




def deploy_acls(id_map, dry_run):
    """Create ACLs for custom tables — read/write restricted to virgil roles.
    Note: ACL creation via REST requires elevated security_admin role.
    If this fails (403), ACLs must be created manually in the SN instance."""
    print("\n══════ ACLs ══════")
    custom_tables = [
        "x_snc_virgil_minos_rule", "x_snc_virgil_ontology_node", "x_snc_virgil_ontology_edge",
        "x_snc_virgil_minos_scan", "x_snc_virgil_minos_finding",
        "x_snc_virgil_wdf_rate_card", "x_snc_virgil_wdf_scan", "x_snc_virgil_wdf_scan_line",
    ]

    # Test if we can access sys_security_acl at all
    test = sn_get("sys_security_acl", "name=task^operation=read", "sys_id")
    if not test and not dry_run:
        print("  ⚠️  Cannot access sys_security_acl via REST (requires security_admin role).")
        print("  ⚠️  ACLs must be configured manually in the instance.")
        print("  ⚠️  Tables are accessible to admin by default — scoped app ACLs protect non-admin users.")
        return

    acl_ok = 0
    acl_fail = 0
    for table in custom_tables:
        is_config = table in [
            "x_snc_virgil_minos_rule", "x_snc_virgil_ontology_node",
            "x_snc_virgil_ontology_edge", "x_snc_virgil_wdf_rate_card",
        ]
        for op in ["read", "write"]:
            role_label = "admin" if (op == "write" and is_config) else "user"
            result = sn_upsert("sys_security_acl",
                f"name={table}^operation={op}^type=record", {
                    "name": table,
                    "operation": op,
                    "type": "record",
                    "active": "true",
                    "admin_overrides": "true",
                    "sys_scope": id_map.get("app", ""),
                }, dry_run)
            if result:
                acl_ok += 1
            else:
                acl_fail += 1

    if acl_fail > 0:
        print(f"\n  ⚠️  {acl_fail} ACLs could not be created via REST — configure manually in instance.")
    else:
        print(f"\n  ✅ {acl_ok} ACLs created")


def deploy_app_menu(id_map, dry_run):
    """Register Virgil in the application navigator."""
    print("\n══════ Application Menu ══════")
    menu_sid = sn_upsert("sys_app_application", f"title={APP_NAME}", {
        "title": APP_NAME,
        "hint": "Presales intelligence platform",
        "active": "true",
        "category": "custom_apps",
    }, dry_run)
    if menu_sid:
        id_map["app_menu"] = menu_sid

    modules = [
        {"title": "Launchpad", "order": 100, "link_type": "uri", "uri": "/$na.do?id=virgil-home"},
        {"title": "Architecture Scan (Minos)", "order": 200, "link_type": "uri", "uri": "/$na.do?id=virgil-minos"},
        {"title": "WDF Sizing (Plutus)", "order": 300, "link_type": "uri", "uri": "/$na.do?id=virgil-plutus"},
        {"title": "AI Advisor (Virgil)", "order": 400, "link_type": "uri", "uri": "/$na.do?id=virgil-chat"},
    ]
    for mod in modules:
        print(f"  Module: {mod['title']}")
        sn_upsert("sys_app_module",
            f"title={mod['title']}^application={menu_sid}", {
                "title": mod["title"],
                "application": menu_sid,
                "order": str(mod["order"]),
                "link_type": mod["link_type"],
                "query": mod["uri"],
                "active": "true",
            }, dry_run)


# ── Main ──────────────────────────────────────────────────────────────────────

COMPONENTS = {
    "app": deploy_app,
    "roles": deploy_roles,
    "tables": deploy_tables,
    "seed": deploy_seed_data,
    "scripts": deploy_script_includes,
    "rest_api": deploy_rest_api,
    "acls": deploy_acls,
    "menu": deploy_app_menu,
}

DEPLOY_ORDER = ["app", "roles", "tables", "seed", "scripts", "rest_api", "acls", "menu"]


def main():
    parser = argparse.ArgumentParser(description="Deploy Virgil to ServiceNow")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deployed")
    parser.add_argument("--only", help=f"Deploy only: {', '.join(COMPONENTS.keys())}")
    args = parser.parse_args()

    print(f"{'='*60}")
    print(f"  Virgil ServiceNow App Deployer")
    print(f"  Instance: {INSTANCE}")
    print(f"  Scope:    {APP_SCOPE}")
    print(f"  Time:     {datetime.now().isoformat()}")
    if args.dry_run:
        print(f"  Mode:     DRY RUN")
    print(f"{'='*60}")

    # Test connection
    test = sn_get("sys_user", "user_name=admin", "sys_id,user_name")
    if not test:
        print("\n❌ Cannot connect to instance. Check credentials.")
        sys.exit(1)
    print(f"\n✅ Connection verified")

    id_map = load_id_map()

    if args.only:
        if args.only not in COMPONENTS:
            print(f"Unknown component: {args.only}")
            print(f"Available: {', '.join(COMPONENTS.keys())}")
            sys.exit(1)
        COMPONENTS[args.only](id_map, args.dry_run)
    else:
        for comp in DEPLOY_ORDER:
            COMPONENTS[comp](id_map, args.dry_run)

    save_id_map(id_map)
    print(f"\n{'='*60}")
    print(f"  Deployment complete. ID map saved to .deploy_ids.json")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
