# Virgil ServiceNow App: Approach Comparison

## Three Approaches

| | **`servicenow-app/` (deploy.py)** | **Market Research App** | **`sybil/` (this folder)** |
|---|---|---|---|
| **Pattern** | Hand-rolled REST API deployer | SDK Fluent (declarative TypeScript) | SDK Fluent (declarative TypeScript) |
| **Same pattern?** | ❌ Different | ✅ Reference implementation | ✅ **Same as Market Research** |

**`sybil/` uses the exact same ServiceNow SDK Fluent pattern as the Market Research app.** The COMPARISON below shows why we migrated from `deploy.py` to this approach.

---

## What "SDK Fluent" Means

Both the Market Research app and `sybil/` follow this pattern:

```
src/
  fluent/           ← Declarative TypeScript (.now.ts files)
    tables/         ← Table() + typed columns (StringColumn, ReferenceColumn, etc.)
    roles/          ← Role() declarations
    acls/           ← Acl() declarations
    script-includes/ ← ScriptInclude() wrappers pointing to server scripts
    rest-api/       ← RestApi() + RestApiResource() declarations
    navigation/     ← ApplicationMenu() + Record() for modules
    index.now.ts    ← Barrel file exporting everything
  server/           ← Server-side JS/TS (.server.js files) — actual business logic
now.config.json     ← Scope + scopeId
package.json        ← @servicenow/sdk devDependency, build/deploy scripts
```

Deployment: `now-sdk build` → `now-sdk install` (replaces `deploy.py` entirely)

---

## Why We Migrated from deploy.py

### deploy.py Approach (servicenow-app/)
- **Python script** that makes REST API calls to create tables, script includes, REST API, seed data, navigation
- Custom upsert logic, cache flush, retry with exponential backoff
- **Cannot create ACLs** — requires security_admin role, manual configuration
- Admin must set scope picker manually before running
- No type safety — errors discovered at deploy time (HTTP 400s)
- State tracked in `.deploy_ids.json` (instance-specific, gitignored)

### SDK Fluent Approach (sybil/ = Market Research pattern)
- **TypeScript declarations** compiled by `now-sdk build`
- Built-in idempotency via `$id` references
- **ACLs as code** — `Acl()` declaration, version-controlled
- Scope handled automatically via `now.config.json`
- Full TypeScript type safety with `@servicenow/glide`
- SDK manages state internally

---

## Component-by-Component

| Component | deploy.py | SDK Fluent (sybil/) | Key Improvement |
|---|---|---|---|
| **Tables** | JSON schema + REST to `sys_db_object`/`sys_dictionary` + cache flush | `Table()` + typed columns (`StringColumn`, `DateTimeColumn`, etc.) | Type safety, no cache flush |
| **Script Includes** | Raw `.js` + REST POST to `sys_script_include` | `.server.js` files + `ScriptInclude()` wrapper with `Now.include()` | Glide types, declarative config |
| **REST API** | REST to `sys_ws_definition` + `sys_ws_operation` with manual sys_id linking | `RestApi()` + `RestApiResource()` with object references | Declarative linking |
| **ACLs** | ❌ Cannot create via REST | ✅ `Acl()` — read/write per table per role | **Biggest win** — was manual-only |
| **Roles** | REST to `sys_user_role` | `Role()` declaration | Cleaner |
| **Seed Data** | REST POST + `cache.do` flush + exponential backoff retry | `Record()` — declarative, atomic | No timing issues |
| **Navigation** | REST to `sys_app_module` (with `uri` vs `query` field trap) | `ApplicationMenu()` + `Module()` | No field name gotchas |
| **Business Rules** | Not implemented | `BusinessRule()` available | New capability |
| **Flows** | Not implemented | `Flow()` with triggers, actions, data pills | New capability |
| **Workspace UI** | ❌ Failed (all methods) | ❌ Not supported (`UiPage()` = classic `.do` only) | **Tie** — both need Build Agent |
| **Scope** | Manual scope picker required | `now.config.json` automatic | Eliminates human error |
| **Errors** | Runtime (HTTP errors on instance) | Compile-time (TypeScript) | Catch before deploy |

---

## What's Identical Between Market Research App and sybil/

| Aspect | Market Research | sybil/ |
|---|---|---|
| SDK version | `@servicenow/sdk` 4.4.0 | `@servicenow/sdk` 4.4.0 |
| Project root | `now.config.json` + `package.json` | `now.config.json` + `package.json` |
| Table definitions | `src/fluent/tables/*.now.ts` with `Table()` | `src/fluent/tables/*.now.ts` with `Table()` |
| Server scripts | `src/server/*.server.js` | `src/server/*.server.js` |
| Business logic ref | `Now.include('./script.server.js')` | `Now.include('../server/Script.server.js')` |
| Navigation | `ApplicationMenu()` + `Record()` for modules | `ApplicationMenu()` + `Record()` for modules |
| Barrel file | `src/fluent/index.now.ts` | `src/fluent/index.now.ts` |
| Build | `now-sdk build` | `now-sdk build` |
| Deploy | `now-sdk install` | `now-sdk install` |

### What sybil/ Adds Beyond Market Research

| Extra | Description |
|---|---|
| **ACLs** | Market Research has no ACLs. sybil/ declares read/write ACLs for all 8 tables. |
| **Roles** | Market Research has no roles. sybil/ declares `x_snc_virgil.admin` and `x_snc_virgil.user`. |
| **Script Includes** | Market Research uses Business Rules only. sybil/ uses `ScriptInclude()` for reusable scanner classes. |
| **Scripted REST API** | Market Research has no REST API. sybil/ declares 4 endpoints (minos/plutus scan + history). |
| **Client-callable wrapper** | `VirgilAjax` with `client_callable: true` for GlideAjax from workspace UI. |

---

## Summary

**sybil/ is the Market Research SDK Fluent pattern applied to Virgil with additional enterprise artifacts (ACLs, roles, REST API, Script Includes).** The underlying pattern, project structure, and toolchain are identical. `deploy.py` is the old approach we're migrating away from.
