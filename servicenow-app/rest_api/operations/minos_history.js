(function process(/*RESTAPIRequest*/ request, /*RESTAPIResponse*/ response) {
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
