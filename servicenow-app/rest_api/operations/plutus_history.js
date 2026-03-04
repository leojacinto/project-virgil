(function process(/*RESTAPIRequest*/ request, /*RESTAPIResponse*/ response) {
    var limit = parseInt(request.queryParams.limit) || 10;
    var scans = [];

    var gr = new GlideRecord('x_snc_virgil_wdf_scan');
    gr.orderByDesc('scan_date');
    gr.setLimit(limit);
    gr.query();
    while (gr.next()) {
        var scanId = gr.getUniqueValue();
        var scanObj = {
            sys_id: scanId,
            scan_date: gr.getValue('scan_date'),
            status: gr.getValue('status'),
            total_credits: parseFloat(gr.getValue('total_credits')) || 0,
            capabilities_detected: parseInt(gr.getValue('capabilities_detected')) || 0
        };

        // Load scan lines
        var lines = [];
        var lg = new GlideRecord('x_snc_virgil_wdf_scan_line');
        lg.addQuery('scan', scanId);
        lg.query();
        while (lg.next()) {
            lines.push({
                cap_id: lg.getValue('cap_id'),
                cap_label: lg.getValue('cap_label'),
                detected: lg.getValue('detected') === 'true',
                usage_value: parseFloat(lg.getValue('usage_value')) || 0,
                usage_unit: lg.getValue('usage_unit'),
                annualized_usage: parseFloat(lg.getValue('annualized_usage')) || 0,
                credits_consumed: parseFloat(lg.getValue('credits_consumed')) || 0,
                scan_evidence: lg.getValue('scan_evidence'),
                is_estimated: lg.getValue('is_estimated') === 'true'
            });
        }
        scanObj.lines = lines;
        scans.push(scanObj);
    }

    response.setStatus(200);
    response.setBody({ scans: scans });
})(request, response);
