# Virgil Workspace — Build Agent Prompt

Create a workspace experience for the Virgil app (scope: x_snc_virgil) with 3 pages: Home (launchpad), Minos (architecture scan), and Plutus (WDF credit sizing). This UI runs INSIDE ServiceNow — do NOT use REST APIs. Use GlideAjax to call server-side Script Includes and GlideRecord to read tables directly.

---

## How to Call Backend (GlideAjax — NOT REST)

Since the UI runs inside the same ServiceNow instance, use GlideAjax to invoke the `VirgilAjax` Script Include (which is `client_callable=true`):

```javascript
// Trigger a Minos scan
var ga = new GlideAjax('x_snc_virgil.VirgilAjax');
ga.addParam('sysparm_name', 'runMinosScan');
ga.getXMLAnswer(function(answer) {
    var result = JSON.parse(answer);
    // result contains the full scan output — see return shapes below
});

// Trigger a Plutus scan
var ga = new GlideAjax('x_snc_virgil.VirgilAjax');
ga.addParam('sysparm_name', 'runPlutusScan');
ga.getXMLAnswer(function(answer) {
    var result = JSON.parse(answer);
});
```

## How to Read Tables (GlideRecord — NOT REST)

Use client-side GlideRecord to read scan history and other data directly from tables:

```javascript
// Read Minos scan history
var gr = new GlideRecord('x_snc_virgil_minos_scan');
gr.orderByDesc('scan_date');
gr.setLimit(10);
gr.query(function(gr) {
    while (gr.next()) {
        // gr.getValue('scan_date'), gr.getValue('status'), etc.
    }
});

// Read findings for a specific scan
var fg = new GlideRecord('x_snc_virgil_minos_finding');
fg.addQuery('scan', scanSysId);
fg.query(function(fg) {
    while (fg.next()) {
        // fg.getValue('severity'), fg.getValue('rule_name'), etc.
    }
});

// Read Plutus scan history + lines
var gr = new GlideRecord('x_snc_virgil_wdf_scan');
gr.orderByDesc('scan_date');
gr.setLimit(10);
gr.query(function(gr) {
    while (gr.next()) {
        var scanId = gr.getUniqueValue();
        // then query x_snc_virgil_wdf_scan_line where scan=scanId
    }
});
```

---

## Script Includes (already deployed, server-side)

### VirgilAjax (client_callable=true)
```javascript
var VirgilAjax = Class.create();
VirgilAjax.prototype = Object.extendsObject(global.AbstractAjaxProcessor, {
    runMinosScan: function() {
        var scanner = new MinosScanner();
        var result = scanner.scan();
        return JSON.stringify(result);
    },
    runPlutusScan: function() {
        var scanner = new PlutusScanner();
        var result = scanner.scan();
        return JSON.stringify(result);
    },
    type: 'VirgilAjax'
});
```

### MinosScanner (full source)
```javascript
var MinosScanner = Class.create();
MinosScanner.prototype = {
    initialize: function() {
        this.utils = new VirgilUtils();
        this.ontology = new MinosOntology();
        this.ruleEngine = new MinosRuleEngine();
    },

    scan: function() {
        var startTime = new GlideDateTime();
        var model = this._buildInstanceModel();
        var mapping = this.ontology.mapInstanceToNodes(model);
        model.active_node_ids = mapping.active_node_ids;
        var ruleResults = this.ruleEngine.evaluate(model);
        var asIsDiagram = this.ontology.generateMermaid(mapping.active_node_ids, 'as_is');
        var recommendedDiagram = this.ontology.generateMermaid(
            mapping.active_node_ids, 'recommended', ruleResults.recommended_nodes
        );
        var it4itCoverage = this._buildIT4ITCoverage(mapping, ruleResults);
        var endTime = new GlideDateTime();
        var duration = GlideDateTime.subtract(startTime, endTime).getNumericValue() / 1000;

        var result = {
            status: 'completed',
            scan_duration_seconds: duration,
            instance_model: this._modelToDict(model),
            active_nodes: mapping.active_nodes,
            active_node_ids: mapping.active_node_ids,
            it4it_coverage: it4itCoverage,
            findings: ruleResults.findings,
            recommended_nodes: ruleResults.recommended_nodes,
            as_is_diagram: asIsDiagram,
            recommended_diagram: recommendedDiagram,
            summary: {
                plugins_scanned: Object.keys(model.installed_plugins).length,
                tables_scanned: Object.keys(model.active_tables).length,
                active_nodes: mapping.active_node_ids.length,
                total_findings: ruleResults.findings.length,
                recommended_additions: Object.keys(ruleResults.recommended_nodes).length
            }
        };

        var scanId = this._saveScan(result);
        result.scan_sys_id = scanId;
        return result;
    },

    // _saveScan persists to x_snc_virgil_minos_scan + x_snc_virgil_minos_finding tables
    // See table schemas below for field details
    type: 'MinosScanner'
};
```

**Minos scan() return shape** (this is what `VirgilAjax.runMinosScan()` returns via GlideAjax):
```json
{
    "status": "completed",
    "scan_duration_seconds": 28.5,
    "scan_sys_id": "abc123...",
    "summary": {
        "plugins_scanned": 1281,
        "tables_scanned": 84,
        "active_nodes": 36,
        "total_findings": 11,
        "recommended_additions": 2
    },
    "findings": [
        {
            "rule_id": "R001",
            "rule_name": "Heavy JDBC Usage",
            "severity": "high",
            "source": "integration_pattern",
            "category": "integration_pattern",
            "message": "790 JDBC data sources detected...",
            "recommendation": "Evaluate Zero Copy Connectors...",
            "evidence": {},
            "tags": ["R2D", "D2C"]
        }
    ],
    "it4it_coverage": {
        "S2P": { "name": "Strategy to Portfolio", "active": [...], "status": "healthy|partial|at_risk|none" },
        "R2D": { "name": "Requirement to Deploy", "active": [...], "status": "..." },
        "R2F": { "name": "Request to Fulfill", "active": [...], "status": "..." },
        "D2C": { "name": "Detect to Correct", "active": [...], "status": "..." }
    },
    "as_is_diagram": "graph LR\n  ...(Mermaid syntax)...",
    "recommended_diagram": "graph LR\n  ...(Mermaid syntax)..."
}
```

### PlutusScanner (full source)
```javascript
var PlutusScanner = Class.create();
PlutusScanner.prototype = {
    initialize: function() {
        this.utils = new VirgilUtils();
        this.rateCard = this._loadRateCard();
    },

    _loadRateCard: function() {
        var caps = [];
        var gr = new GlideRecord('x_snc_virgil_wdf_rate_card');
        gr.addQuery('active', true);
        gr.orderBy('order');
        gr.query();
        while (gr.next()) {
            caps.push({
                cap_id: gr.getValue('cap_id') || '',
                label: gr.getValue('label') || '',
                meter_unit: gr.getValue('meter_unit') || '',
                credits: parseFloat(gr.getValue('credits')) || 0,
                pro_only: gr.getValue('pro_only') === 'true',
                measurable: gr.getValue('measurable') === 'true',
                detect_logic: gr.getValue('detect_logic') || ''
            });
        }
        return caps;
    },

    scan: function(opts) {
        opts = opts || {};
        var startTime = new GlideDateTime();
        var data = this._gatherInstanceData(opts.active_tables || {});
        var lines = [];
        var totalCredits = 0;
        var detected = 0;
        for (var i = 0; i < this.rateCard.length; i++) {
            var cap = this.rateCard[i];
            var usage = this._assessCapability(cap, data, opts.user_overrides || {});
            lines.push(usage);
            totalCredits += usage.credits_consumed;
            if (usage.detected) detected++;
        }
        var endTime = new GlideDateTime();
        var duration = GlideDateTime.subtract(startTime, endTime).getNumericValue() / 1000;
        var result = {
            status: 'completed',
            total_credits: totalCredits,
            capabilities_detected: detected,
            capabilities_total: this.rateCard.length,
            duration_seconds: duration,
            lines: lines
        };
        var scanSysId = this._saveScan(result);
        result.scan_sys_id = scanSysId;
        this._saveScanLines(scanSysId, lines);
        return result;
    },

    // _saveScan persists to x_snc_virgil_wdf_scan + x_snc_virgil_wdf_scan_line tables
    type: 'PlutusScanner'
};
```

**Plutus scan() return shape:**
```json
{
    "status": "completed",
    "scan_sys_id": "def456...",
    "total_credits": 12500,
    "capabilities_detected": 4,
    "capabilities_total": 9,
    "duration_seconds": 0.08,
    "lines": [
        {
            "cap_id": "integration_hub",
            "cap_label": "Integration Hub",
            "detected": true,
            "usage_value": 5000,
            "usage_unit": "Data fabric transaction",
            "annualized_usage": 5000,
            "credits_consumed": 5000,
            "scan_evidence": "5,000 IHub outbound executions...",
            "is_estimated": false,
            "excluded": false
        }
    ]
}
```

---

## Table Schemas

### x_snc_virgil_minos_scan
| Field | Type |
|-------|------|
| scan_date | glide_date_time |
| instance_url | string |
| status | choice: running, completed, failed |
| duration_seconds | decimal |
| plugins_scanned | integer |
| tables_scanned | integer |
| active_nodes | integer |
| total_findings | integer |
| recommended_additions | integer |
| it4it_coverage | string (JSON) |
| active_node_ids | string (JSON) |
| as_is_diagram | string (Mermaid) |
| recommended_diagram | string (Mermaid) |
| instance_model | string (JSON) |

### x_snc_virgil_minos_finding
| Field | Type |
|-------|------|
| scan | reference → minos_scan |
| rule_id | string |
| rule_name | string |
| severity | choice: critical, high, medium, low |
| source | string |
| category | string |
| message | string |
| recommendation | string |
| evidence_json | string (JSON) |
| tags | string (JSON) |

### x_snc_virgil_wdf_scan
| Field | Type |
|-------|------|
| scan_date | glide_date_time |
| status | choice: running, completed, failed |
| total_credits | decimal |
| capabilities_detected | integer |

### x_snc_virgil_wdf_scan_line
| Field | Type |
|-------|------|
| scan | reference → wdf_scan |
| cap_id | string |
| cap_label | string |
| detected | boolean |
| usage_value | decimal |
| usage_unit | string |
| annualized_usage | decimal |
| credits_consumed | decimal |
| scan_evidence | string |
| is_estimated | boolean |
| excluded | boolean |

### x_snc_virgil_wdf_rate_card (9 records, reference data)
| Field | Type |
|-------|------|
| cap_id | string |
| label | string |
| meter_unit | string |
| credits | decimal |
| pro_only | boolean |
| measurable | boolean |

---

## UI Pages to Build

### Page 1: Home (Launchpad)
- Heading: "Virgil — Presales Intelligence Platform"
- 3 cards in a row:
  - **Minos** — subtitle "Architecture & Design Scan" — icon: Shield (Lucide) — navigates to Minos page
  - **Plutus** — subtitle "WDF Credit Sizing" — icon: Coins (Lucide) — navigates to Plutus page
  - **Virgil Chat** — subtitle "AI Architecture Advisor" — icon: MessageSquare (Lucide) — placeholder (future)
- Optional: show latest 3 scans from minos_scan and wdf_scan tables as recent activity

### Page 2: Minos (Architecture Scan)
- **"Run Minos Scan" button** — calls `VirgilAjax.runMinosScan()` via GlideAjax
- While scanning (~30 seconds): show loading spinner with "Scanning instance architecture..."
- **Summary bar** after scan: plugins scanned, tables scanned, active nodes, total findings, recommended additions (from `result.summary`)
- **IT4IT coverage bar**: 4 boxes for S2P, R2D, R2F, D2C — color by status: healthy=green, partial=yellow, at_risk=red, none=gray
- **Findings table**: columns = severity (color-coded badge: critical=red, high=orange, medium=yellow, low=blue), rule_name, category, message, recommendation — sorted by severity (critical first)
- **Mermaid diagrams**: render `as_is_diagram` and `recommended_diagram` as Mermaid charts (or show as code blocks if Mermaid rendering not available)

### Page 3: Plutus (WDF Credit Sizing)
- **"Scan Instance" button** — calls `VirgilAjax.runPlutusScan()` via GlideAjax
- **Summary cards**: capabilities detected (X of 9), total credits/year
- **Capability table**: columns = cap_label, detected (green checkmark or red X), usage_value, usage_unit, credits_consumed, scan_evidence
- **IMPORTANT**: No pack calculations, no tier recommendations, no annual cost estimates — only show credit consumption per capability
- **3 hidden capabilities that must NEVER appear**: Orchestration, Automation Center, Now Assist for Spokes/AI Agents

### Style
- Modern, clean look matching ServiceNow workspace aesthetic
- Dark/light mode support
- Color-coded severity badges (critical=red, high=orange, medium=yellow, low=blue)
- Responsive layout
