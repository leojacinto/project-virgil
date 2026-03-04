var PlutusScanner = Class.create();
PlutusScanner.prototype = {

    initialize: function() {
        this.utils = new VirgilUtils();
        this.rateCard = this._loadRateCard();
    },

    /**
     * Load active capabilities from x_snc_virgil_wdf_rate_card table.
     */
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
                detect_logic: gr.getValue('detect_logic') || '',
                sys_id: gr.getUniqueValue()
            });
        }
        gs.debug('PlutusScanner: Loaded ' + caps.length + ' capabilities from rate card');
        return caps;
    },

    /**
     * Run full WDF credit scan. Saves results to x_snc_virgil_wdf_scan + lines.
     * No pack/tier calculations — just credit consumption per capability.
     * @param {Object} [opts] - {active_tables: {}, user_overrides: {}}
     * @returns {Object} Scan result
     */
    scan: function(opts) {
        opts = opts || {};
        var startTime = new GlideDateTime();
        gs.info('Virgil PlutusScanner: Starting WDF scan...');

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

        // Persist to tables
        var scanSysId = this._saveScan(result);
        result.scan_sys_id = scanSysId;
        this._saveScanLines(scanSysId, lines);

        gs.info('Virgil PlutusScanner: Scan complete. ' +
            detected + '/' + this.rateCard.length + ' capabilities detected, ' +
            Math.round(totalCredits).toLocaleString() + ' total credits');

        return result;
    },

    // ──────────────────────────────────────────────────────────────────────
    // Instance Data Gathering (GlideAggregate — direct, no REST overhead)
    // ──────────────────────────────────────────────────────────────────────

    _gatherInstanceData: function(activeTables) {
        var data = {
            active_tables: activeTables,
            ihub_execution_count: 0,
            outbound_http_count: 0,
            outbound_http_avg_bytes: 0,
            jdbc_data_sources: [],
            rest_message_count: 0,
            import_run_count: 0,
            import_row_count: 0,
            reports_count: 0,
            dashboards_count: 0,
            rpa_execution_count: 0,
            custom_table_count: activeTables['_custom_tables'] || 0,
            data_days: 0
        };

        // 1. Outbound HTTP — execution counts + byte estimation
        if (this.utils.tableExists('sys_outbound_http_log')) {
            data.outbound_http_count = this.utils.getRecordCount('sys_outbound_http_log');
            data.ihub_execution_count = this.utils.getRecordCount(
                'sys_outbound_http_log', 'source_table=sys_hub_step_instance'
            );

            // Sample for average byte size
            var ga = new GlideAggregate('sys_outbound_http_log');
            ga.addAggregate('AVG', 'response_length');
            ga.query();
            if (ga.next()) {
                data.outbound_http_avg_bytes = parseFloat(ga.getAggregate('AVG', 'response_length')) || 0;
            }

            // Estimate data span from oldest→newest log
            data.data_days = this._estimateDataDays('sys_outbound_http_log');
        }

        // 2. JDBC data sources (for ZCC detection)
        if (this.utils.tableExists('sys_data_source')) {
            var ds = new GlideRecord('sys_data_source');
            ds.addQuery('type', 'JDBC');
            ds.setLimit(500);
            ds.query();
            while (ds.next()) {
                data.jdbc_data_sources.push({
                    name: ds.getValue('name') || '',
                    connection_url: ds.getValue('connection_url') || ''
                });
            }
        }

        // 3. REST message count
        data.rest_message_count = this.utils.getRecordCount('sys_rest_message');

        // 4. Import sets
        if (this.utils.tableExists('sys_import_set_run')) {
            data.import_run_count = this.utils.getRecordCount('sys_import_set_run');
        }
        if (this.utils.tableExists('sys_import_set_row')) {
            data.import_row_count = this.utils.getRecordCount('sys_import_set_row');
        }

        // 5. Reports + dashboards
        data.reports_count = this.utils.getRecordCount('sys_report');
        data.dashboards_count = this.utils.getRecordCount('pa_dashboards');

        // 6. RPA
        if (this.utils.tableExists('sn_rpa_execution')) {
            data.rpa_execution_count = this.utils.getRecordCount('sn_rpa_execution');
        }

        gs.info('PlutusScanner: Gathered instance data — ' +
            data.outbound_http_count + ' outbound HTTP, ' +
            data.ihub_execution_count + ' IHub executions, ' +
            data.jdbc_data_sources.length + ' JDBC sources');

        return data;
    },

    _estimateDataDays: function(tableName) {
        var gr = new GlideRecord(tableName);
        gr.orderBy('sys_created_on');
        gr.setLimit(1);
        gr.query();
        if (!gr.next()) return 0;

        var oldest = new GlideDateTime(gr.getValue('sys_created_on'));
        var now = new GlideDateTime();
        var diff = GlideDateTime.subtract(oldest, now);
        return Math.max(1, Math.round(diff.getNumericValue() / 86400000));
    },

    // ──────────────────────────────────────────────────────────────────────
    // Capability Assessment
    // ──────────────────────────────────────────────────────────────────────

    _assessCapability: function(cap, data, userOverrides) {
        var usage = {
            cap_id: cap.cap_id,
            cap_label: cap.label,
            detected: false,
            usage_value: 0,
            usage_unit: cap.meter_unit,
            annualized_usage: 0,
            credits_consumed: 0,
            scan_evidence: '',
            is_estimated: false,
            excluded: false
        };

        // Manual override takes precedence
        if (userOverrides[cap.cap_id] !== undefined) {
            usage.usage_value = parseFloat(userOverrides[cap.cap_id]) || 0;
            usage.annualized_usage = usage.usage_value;
            usage.detected = usage.usage_value > 0;
            usage.credits_consumed = usage.annualized_usage * cap.credits;
            usage.scan_evidence = 'Manual override: ' + usage.usage_value + ' ' + cap.meter_unit;
            return usage;
        }

        // Not measurable = skip auto-detect
        if (!cap.measurable) {
            usage.scan_evidence = 'Not auto-measurable. Enter value manually.';
            return usage;
        }

        // Auto-detect by capability type
        var capId = cap.cap_id;

        if (capId === 'integration_hub') {
            this._detectIntegrationHub(usage, cap, data);
        } else if (capId === 'api_access_volume') {
            this._detectApiAccessVolume(usage, cap, data);
        } else if (capId === 'rpa_hub') {
            this._detectRPA(usage, cap, data);
        } else if (capId === 'zero_copy_connectors') {
            this._detectZCC(usage, cap, data);
        } else if (capId === 'stream_connect') {
            this._detectStreamConnect(usage, cap, data);
        } else if (capId === 'ai_data_explorer') {
            this._detectAIDataExplorer(usage, cap, data);
        }

        // Annualize if we have data_days
        if (usage.detected && data.data_days > 0 && data.data_days < 365) {
            usage.annualized_usage = Math.round(usage.usage_value * (365 / data.data_days));
            usage.is_estimated = true;
        } else if (usage.detected) {
            usage.annualized_usage = usage.usage_value;
        }

        usage.credits_consumed = usage.annualized_usage * cap.credits;
        return usage;
    },

    _detectIntegrationHub: function(usage, cap, data) {
        var count = data.ihub_execution_count;
        if (count > 0) {
            usage.detected = true;
            usage.usage_value = count;
            usage.scan_evidence = count.toLocaleString() + ' IHub outbound executions ' +
                '(sys_outbound_http_log where source_table=sys_hub_step_instance)';
            if (data.data_days > 0 && data.data_days < 365) {
                usage.scan_evidence += '. Data span: ' + data.data_days + ' days.';
            }
        }
    },

    _detectApiAccessVolume: function(usage, cap, data) {
        var totalBytes = data.outbound_http_count * data.outbound_http_avg_bytes;
        var totalMB = totalBytes / (1024 * 1024);
        if (totalMB > 0) {
            usage.detected = true;
            usage.usage_value = Math.round(totalMB * 10) / 10;
            usage.scan_evidence = 'Estimated ' + usage.usage_value.toLocaleString() + ' MB egressed. ' +
                data.outbound_http_count.toLocaleString() + ' outbound calls × ' +
                Math.round(data.outbound_http_avg_bytes).toLocaleString() + ' avg bytes.';
        }
    },

    _detectRPA: function(usage, cap, data) {
        if (data.rpa_execution_count > 0) {
            usage.detected = true;
            usage.usage_value = data.rpa_execution_count;
            usage.scan_evidence = data.rpa_execution_count.toLocaleString() +
                ' RPA execution records (sn_rpa_execution). Actual minutes may differ.';
        }
    },

    _detectZCC: function(usage, cap, data) {
        // Match JDBC data sources against supported DB patterns
        var supportedPatterns = [
            'sqlserver', 'mssql', 'oracle', 'ojdbc', 'mysql',
            'postgresql', 'postgres', 'snowflake', 'sap', 'hana',
            'redshift', 'bigquery', 'databricks', 'db2', 'ibm'
        ];
        var matched = [];
        for (var i = 0; i < data.jdbc_data_sources.length; i++) {
            var url = (data.jdbc_data_sources[i].connection_url || '').toLowerCase();
            var name = (data.jdbc_data_sources[i].name || '').toLowerCase();
            for (var p = 0; p < supportedPatterns.length; p++) {
                if (url.indexOf(supportedPatterns[p]) >= 0 || name.indexOf(supportedPatterns[p]) >= 0) {
                    matched.push(data.jdbc_data_sources[i].name);
                    break;
                }
            }
        }
        if (matched.length > 0) {
            usage.detected = true;
            usage.usage_value = matched.length;
            usage.scan_evidence = 'Proposed due to usage patterns that might benefit from this WDF capability. ' +
                matched.length + ' JDBC data source(s) to supported DBs: ' + matched.join(', ') + '.';
        }
    },

    _detectStreamConnect: function(usage, cap, data) {
        var indicators = [];

        // High-frequency outbound to single host pattern
        if (data.outbound_http_count > 1000) {
            indicators.push('~' + data.outbound_http_count.toLocaleString() + ' outbound HTTP calls');
        }

        // High-volume import sets
        if (data.import_run_count > 0 && data.import_row_count > 10000) {
            var avgRows = Math.round(data.import_row_count / data.import_run_count);
            if (avgRows > 100) {
                indicators.push(data.import_run_count.toLocaleString() + ' import runs averaging ' +
                    avgRows.toLocaleString() + ' rows/run (' + data.import_row_count.toLocaleString() + ' total rows)');
            }
        }

        if (indicators.length > 0) {
            usage.detected = true;
            usage.scan_evidence = 'Proposed due to usage patterns that might benefit from this WDF capability. ' +
                'Stream Connect indicators: ' + indicators.join('; ') + '.';
        }
    },

    _detectAIDataExplorer: function(usage, cap, data) {
        var totalReports = data.reports_count + data.dashboards_count;
        if (totalReports > 50) {
            usage.detected = true;
            var estExplorations = Math.round(totalReports * 0.1);
            usage.usage_value = estExplorations;
            usage.scan_evidence = totalReports.toLocaleString() + ' reports/dashboards. ' +
                'Estimated ~' + estExplorations.toLocaleString() + ' explorations (~10% of report estate).';
        }
    },

    // ──────────────────────────────────────────────────────────────────────
    // Persistence — save results to x_snc_virgil_wdf_scan + x_snc_virgil_wdf_scan_line
    // ──────────────────────────────────────────────────────────────────────

    _saveScan: function(result) {
        var gr = new GlideRecord('x_snc_virgil_wdf_scan');
        gr.initialize();
        gr.setValue('scan_date', new GlideDateTime().getDisplayValue());
        gr.setValue('instance_url', gs.getProperty('glide.servlet.uri', ''));
        gr.setValue('status', 'completed');
        gr.setValue('total_credits', result.total_credits);
        gr.setValue('capabilities_detected', result.capabilities_detected);
        gr.setValue('summary_json', JSON.stringify({
            total_credits: result.total_credits,
            capabilities_detected: result.capabilities_detected,
            capabilities_total: result.capabilities_total,
            duration_seconds: result.duration_seconds
        }));
        return gr.insert();
    },

    _saveScanLines: function(scanSysId, lines) {
        for (var i = 0; i < lines.length; i++) {
            var line = lines[i];
            var gr = new GlideRecord('x_snc_virgil_wdf_scan_line');
            gr.initialize();
            gr.setValue('scan', scanSysId);
            gr.setValue('cap_id', line.cap_id);
            gr.setValue('cap_label', line.cap_label);
            gr.setValue('detected', line.detected ? 'true' : 'false');
            gr.setValue('usage_value', line.usage_value);
            gr.setValue('usage_unit', line.usage_unit);
            gr.setValue('annualized_usage', line.annualized_usage);
            gr.setValue('credits_consumed', line.credits_consumed);
            gr.setValue('scan_evidence', line.scan_evidence);
            gr.setValue('is_estimated', line.is_estimated ? 'true' : 'false');
            gr.setValue('excluded', line.excluded ? 'true' : 'false');
            gr.insert();
        }
    },

    type: 'PlutusScanner'
};
