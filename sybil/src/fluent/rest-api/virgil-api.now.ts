import { RestApi, RestApiResource } from '@servicenow/sdk/core'

export const virgilApi = RestApi({
    $id: Now.ID['virgil_api'],
    name: 'Virgil API',
    api_id: 'virgil_api',
    api_namespace: 'x_snc_virgil',
})

// ── Minos endpoints ──────────────────────────────────────────────────────────

RestApiResource({
    $id: Now.ID['minos_scan_endpoint'],
    rest_api: virgilApi,
    name: 'Minos Scan',
    relative_path: '/minos/scan',
    http_method: 'POST',
    script: `
    (function process(request, response) {
        var scanner = new MinosScanner();
        var result = scanner.scan();
        response.setStatus(200);
        response.setBody(result);
    })(request, response);
    `,
})

RestApiResource({
    $id: Now.ID['minos_history_endpoint'],
    rest_api: virgilApi,
    name: 'Minos History',
    relative_path: '/minos/history',
    http_method: 'GET',
    script: `
    (function process(request, response) {
        var limit = parseInt(request.queryParams.limit) || 10;
        var scans = [];
        var gr = new GlideRecord('x_snc_virgil_minos_scan');
        gr.orderByDesc('scan_date');
        gr.setLimit(limit);
        gr.query();
        while (gr.next()) {
            scans.push({
                sys_id: gr.getUniqueValue(),
                scan_date: gr.getValue('scan_date'),
                status: gr.getValue('status'),
                plugins_scanned: parseInt(gr.getValue('plugins_scanned')) || 0,
                tables_scanned: parseInt(gr.getValue('tables_scanned')) || 0,
                active_nodes: parseInt(gr.getValue('active_nodes')) || 0,
                total_findings: parseInt(gr.getValue('total_findings')) || 0,
                recommended_additions: parseInt(gr.getValue('recommended_additions')) || 0
            });
        }
        response.setStatus(200);
        response.setBody({ scans: scans });
    })(request, response);
    `,
})

// ── Plutus endpoints ─────────────────────────────────────────────────────────

RestApiResource({
    $id: Now.ID['plutus_scan_endpoint'],
    rest_api: virgilApi,
    name: 'Plutus Scan',
    relative_path: '/plutus/scan',
    http_method: 'POST',
    script: `
    (function process(request, response) {
        var body = request.body ? request.body.data : {};
        var overrides = body.user_overrides || {};
        var scanner = new PlutusScanner();
        var result = scanner.scan(overrides);
        response.setStatus(200);
        response.setBody(result);
    })(request, response);
    `,
})

RestApiResource({
    $id: Now.ID['plutus_history_endpoint'],
    rest_api: virgilApi,
    name: 'Plutus History',
    relative_path: '/plutus/history',
    http_method: 'GET',
    script: `
    (function process(request, response) {
        var limit = parseInt(request.queryParams.limit) || 10;
        var scans = [];
        var gr = new GlideRecord('x_snc_virgil_wdf_scan');
        gr.orderByDesc('scan_date');
        gr.setLimit(limit);
        gr.query();
        while (gr.next()) {
            var scanId = gr.getUniqueValue();
            var lines = [];
            var lg = new GlideRecord('x_snc_virgil_wdf_scan_line');
            lg.addQuery('scan', scanId);
            lg.query();
            while (lg.next()) {
                lines.push({
                    capability_id: lg.getValue('capability_id'),
                    capability_label: lg.getValue('capability_label'),
                    detected: lg.getValue('detected') == 'true',
                    usage_value: parseFloat(lg.getValue('usage_value')) || 0,
                    meter_unit: lg.getValue('meter_unit'),
                    credits_per_unit: parseFloat(lg.getValue('credits_per_unit')) || 0,
                    credits_consumed: parseFloat(lg.getValue('credits_consumed')) || 0
                });
            }
            scans.push({
                sys_id: scanId,
                scan_date: gr.getValue('scan_date'),
                status: gr.getValue('status'),
                total_credits: parseFloat(gr.getValue('total_credits')) || 0,
                capabilities_detected: parseInt(gr.getValue('capabilities_detected')) || 0,
                lines: lines
            });
        }
        response.setStatus(200);
        response.setBody({ scans: scans });
    })(request, response);
    `,
})
