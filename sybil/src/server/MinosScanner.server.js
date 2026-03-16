var MinosScanner = Class.create();
MinosScanner.prototype = {
    initialize: function() {
        this.utils = new VirgilUtils();
        this.ontology = new MinosOntology();
        this.ruleEngine = new MinosRuleEngine();
    },

    /**
     * Run full instance scan: plugins → tables → ontology → rules → findings.
     * @returns {Object} Full scan result
     */
    scan: function() {
        var startTime = new GlideDateTime();
        gs.info('Virgil MinosScanner: Starting instance scan...');

        // 1. Build instance model
        var model = this._buildInstanceModel();

        // 2. Map to ontology nodes
        var mapping = this.ontology.mapInstanceToNodes(model);
        model.active_node_ids = mapping.active_node_ids;

        // 3. Evaluate rules
        var ruleResults = this.ruleEngine.evaluate(model);

        // 4. Build architecture diagrams
        var asIsDiagram = this.ontology.generateMermaid(mapping.active_node_ids, 'as_is');
        var recommendedDiagram = this.ontology.generateMermaid(
            mapping.active_node_ids,
            'recommended',
            ruleResults.recommended_nodes
        );

        // 5. Build IT4IT coverage
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

        gs.info('Virgil MinosScanner: Scan complete. Plugins: ' +
            result.summary.plugins_scanned + ', Active nodes: ' +
            result.summary.active_nodes + ', Findings: ' +
            result.summary.total_findings);

        // Persist scan + findings
        var scanId = this._saveScan(result);
        result.scan_sys_id = scanId;

        return result;
    },

    _saveScan: function(result) {
        var gr = new GlideRecord('x_snc_virgil_minos_scan');
        gr.initialize();
        gr.setValue('scan_date', new GlideDateTime().getValue());
        gr.setValue('instance_url', result.instance_model.instance_url || '');
        gr.setValue('status', result.status);
        gr.setValue('duration_seconds', result.scan_duration_seconds || 0);
        gr.setValue('plugins_scanned', result.summary.plugins_scanned || 0);
        gr.setValue('tables_scanned', result.summary.tables_scanned || 0);
        gr.setValue('active_nodes', result.summary.active_nodes || 0);
        gr.setValue('total_findings', result.summary.total_findings || 0);
        gr.setValue('recommended_additions', result.summary.recommended_additions || 0);
        gr.setValue('it4it_coverage', JSON.stringify(result.it4it_coverage || {}));
        gr.setValue('active_node_ids', JSON.stringify(result.active_node_ids || []));
        gr.setValue('as_is_diagram', result.as_is_diagram || '');
        gr.setValue('recommended_diagram', result.recommended_diagram || '');
        gr.setValue('instance_model', JSON.stringify(result.instance_model || {}));
        var scanId = gr.insert();
        gs.info('Virgil MinosScanner: Saved scan ' + scanId);

        // Save findings
        var findings = result.findings || [];
        for (var i = 0; i < findings.length; i++) {
            var f = findings[i];
            var fg = new GlideRecord('x_snc_virgil_minos_finding');
            fg.initialize();
            fg.setValue('scan', scanId);
            fg.setValue('rule_id', f.rule_id || '');
            fg.setValue('rule_name', f.rule_name || '');
            fg.setValue('severity', f.severity || '');
            fg.setValue('source', f.source || '');
            fg.setValue('category', f.category || '');
            fg.setValue('message', f.message || '');
            fg.setValue('recommendation', f.recommendation || '');
            fg.setValue('evidence_json', JSON.stringify(f.evidence || {}));
            fg.setValue('tags', JSON.stringify(f.tags || []));
            fg.insert();
        }
        gs.info('Virgil MinosScanner: Saved ' + findings.length + ' findings');

        return scanId;
    },

    // ──────────────────────────────────────────────────────────────────────
    // Instance Model Builder
    // ──────────────────────────────────────────────────────────────────────

    _buildInstanceModel: function() {
        var model = {
            instance_url: gs.getProperty('glide.servlet.uri', ''),
            installed_plugins: {},
            active_tables: {},
            integration_flows: [],
            integration_flows_count: 0,
            mid_servers: [],
            cmdb_stats: {},
            instance_properties: {},
            domain_separation: false,
            active_node_ids: []
        };

        // Plugins/apps
        model.installed_plugins = this._scanPlugins();
        gs.info('Virgil MinosScanner: Scanned ' + Object.keys(model.installed_plugins).length + ' plugins/apps');

        // Table record counts
        model.active_tables = this._scanKeyTables();
        gs.info('Virgil MinosScanner: Scanned record counts for ' + Object.keys(model.active_tables).length + ' tables');

        // Custom tables
        model.active_tables['_custom_tables'] = this.utils.getRecordCount(
            'sys_db_object', 'nameSTARTSWITHu_^ORnameSTARTSWITHx_'
        );

        // Integration Hub flows
        var flowData = this._scanIntegrationFlows();
        model.integration_flows = flowData.flows;
        model.integration_flows_count = flowData.count;
        gs.info('Virgil MinosScanner: Scanned ' + flowData.count + ' active IHub flows');

        // MID Servers
        model.mid_servers = this._scanMIDServers();
        gs.info('Virgil MinosScanner: Scanned ' + model.mid_servers.length + ' active MID Servers');

        // CMDB stats
        model.cmdb_stats = this.utils.getCMDBStats();

        // Instance properties
        model.instance_properties = this._scanProperties();
        model.domain_separation = (
            (model.instance_properties['glide.sys.domain.enabled'] || 'false').toLowerCase() === 'true'
        );

        return model;
    },

    _scanPlugins: function() {
        var plugins = {};
        var seen = {};

        // sys_app (scoped apps)
        var gr = new GlideRecord('sys_app');
        gr.addQuery('active', true);
        gr.query();
        while (gr.next()) {
            var scope = gr.getValue('scope') || '';
            if (scope && !seen[scope]) {
                plugins[scope] = {
                    name: gr.getValue('name') || '',
                    version: gr.getValue('version') || '',
                    active: true
                };
                seen[scope] = true;
            }
        }

        // v_plugin (platform plugins)
        var vp = new GlideRecord('v_plugin');
        vp.addQuery('active', 'active');
        vp.query();
        while (vp.next()) {
            var pid = vp.getValue('id') || '';
            if (pid && !seen[pid]) {
                plugins[pid] = {
                    name: vp.getValue('name') || '',
                    version: vp.getValue('version') || '',
                    active: true
                };
                seen[pid] = true;
            }
        }

        return plugins;
    },

    _scanKeyTables: function() {
        // All tables referenced by ontology + integration/health detection tables
        var tables = this.ontology.getAllReferencedTables();

        // Integration pattern detection tables
        var extraTables = [
            'sys_data_source', 'sys_soap_message', 'sys_rest_message',
            'sys_import_set', 'sys_transform_map', 'sysauto_script',
            'sysevent_email_action',
            'sys_script', 'sys_ws_operation',
            'sys_audit', 'sc_cat_item'
        ];
        for (var i = 0; i < extraTables.length; i++) {
            if (tables.indexOf(extraTables[i]) === -1) {
                tables.push(extraTables[i]);
            }
        }

        var counts = {};
        for (var t = 0; t < tables.length; t++) {
            var tableName = tables[t];
            if (this.utils.tableExists(tableName)) {
                counts[tableName] = this.utils.getRecordCount(tableName);
            } else {
                counts[tableName] = -1;
            }
        }
        return counts;
    },

    _scanIntegrationFlows: function() {
        var flows = [];
        var ga = new GlideAggregate('sys_hub_flow');
        ga.addQuery('active', true);
        ga.addAggregate('COUNT');
        ga.query();
        var totalCount = 0;
        if (ga.next()) {
            totalCount = parseInt(ga.getAggregate('COUNT'), 10) || 0;
        }

        // Get sample of flows for metadata
        var gr = new GlideRecord('sys_hub_flow');
        gr.addQuery('active', true);
        gr.orderByDesc('sys_updated_on');
        gr.setLimit(200);
        gr.query();
        while (gr.next()) {
            flows.push({
                name: gr.getValue('name') || '',
                active: true,
                trigger_type: gr.getValue('trigger_type') || '',
                last_updated: gr.getValue('sys_updated_on') || ''
            });
        }

        return { flows: flows, count: totalCount };
    },

    _scanMIDServers: function() {
        var servers = [];
        var gr = new GlideRecord('ecc_agent');
        gr.addQuery('status', 'IN', 'up,upgrading');
        gr.setLimit(50);
        gr.query();
        while (gr.next()) {
            servers.push({
                name: gr.getValue('name') || '',
                status: gr.getValue('status') || '',
                host: gr.getValue('host_name') || ''
            });
        }
        return servers;
    },

    _scanProperties: function() {
        var props = {};
        var propNames = [
            'glide.sys.domain.enabled',
            'glide.security.use_csrf_token'
        ];

        for (var i = 0; i < propNames.length; i++) {
            props[propNames[i]] = gs.getProperty(propNames[i], '');
        }
        return props;
    },

    // ──────────────────────────────────────────────────────────────────────
    // IT4IT Coverage
    // ──────────────────────────────────────────────────────────────────────

    _buildIT4ITCoverage: function(mapping, ruleResults) {
        var streams = {
            S2P: { name: 'Strategy to Portfolio', active: [], missing: [], findings: [], status: 'none' },
            R2D: { name: 'Requirement to Deploy', active: [], missing: [], findings: [], status: 'none' },
            R2F: { name: 'Request to Fulfill', active: [], missing: [], findings: [], status: 'none' },
            D2C: { name: 'Detect to Correct', active: [], missing: [], findings: [], status: 'none' }
        };

        // Map active nodes to streams
        var allNodes = this.ontology.getAllNodes();
        for (var nid in allNodes) {
            var node = allNodes[nid];
            if (!node.it4it_streams) continue;
            for (var s = 0; s < node.it4it_streams.length; s++) {
                var stream = node.it4it_streams[s];
                if (streams[stream]) {
                    if (mapping.active_node_ids.indexOf(nid) >= 0) {
                        streams[stream].active.push({ id: nid, name: node.name });
                    }
                }
            }
        }

        // Map findings to streams
        for (var f = 0; f < ruleResults.findings.length; f++) {
            var finding = ruleResults.findings[f];
            var tags = finding.tags || [];
            for (var st in streams) {
                if (tags.indexOf(st) >= 0) {
                    streams[st].findings.push(finding);
                }
            }
        }

        // Calculate stream status
        for (var key in streams) {
            var str = streams[key];
            if (str.active.length === 0) {
                str.status = 'none';
            } else if (str.findings.length === 0) {
                str.status = 'healthy';
            } else {
                var hasCritical = false;
                for (var fi = 0; fi < str.findings.length; fi++) {
                    if (str.findings[fi].severity === 'critical' || str.findings[fi].severity === 'high') {
                        hasCritical = true;
                        break;
                    }
                }
                str.status = hasCritical ? 'at_risk' : 'partial';
            }
        }

        return streams;
    },

    _modelToDict: function(model) {
        return {
            instance_url: model.instance_url,
            installed_plugins_count: Object.keys(model.installed_plugins).length,
            active_tables: model.active_tables,
            integration_flows_count: model.integration_flows_count,
            mid_servers: model.mid_servers,
            cmdb_stats: model.cmdb_stats,
            domain_separation: model.domain_separation,
            properties_scanned: Object.keys(model.instance_properties).length
        };
    },

    type: 'MinosScanner'
};
