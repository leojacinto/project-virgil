var MinosRuleEngine = Class.create();
MinosRuleEngine.prototype = {
    initialize: function() {
        this.rules = this._loadRulesFromTable();
    },

    /**
     * Load active rules from x_snc_virgil_minos_rule table.
     * @returns {Array} Array of rule objects with parsed eval_json
     */
    _loadRulesFromTable: function() {
        var rules = [];
        var gr = new GlideRecord('x_snc_virgil_minos_rule');
        gr.addQuery('active', true);
        gr.orderBy('order');
        gr.query();
        while (gr.next()) {
            var evalBlock = null;
            try {
                evalBlock = JSON.parse(gr.getValue('eval_json') || '{}');
            } catch (e) {
                gs.warn('MinosRuleEngine: Invalid eval_json for rule ' + gr.getValue('rule_id'));
                continue;
            }
            rules.push({
                id: gr.getValue('rule_id') || '',
                name: gr.getValue('name') || '',
                description: gr.getValue('description') || '',
                source: gr.getValue('source') || '',
                severity: gr.getValue('severity') || 'medium',
                category: gr.getValue('category') || '',
                condition_desc: gr.getValue('condition_desc') || '',
                eval: evalBlock,
                message: gr.getValue('message_template') || '',
                recommendation: gr.getValue('recommendation') || '',
                tags: this._parseJSON(gr.getValue('tags'), []),
                recommended_nodes: this._parseJSON(gr.getValue('recommended_nodes'), {}),
                sys_id: gr.getUniqueValue()
            });
        }
        gs.debug('MinosRuleEngine: Loaded ' + rules.length + ' active rules from table');
        return rules;
    },

    _parseJSON: function(str, fallback) {
        if (!str) return fallback;
        try { return JSON.parse(str); } catch (e) { return fallback; }
    },

    /**
     * Evaluate all rules against an instance model.
     * @param {Object} model - Instance model from MinosScanner
     * @returns {Object} {findings: [], recommended_nodes: {}}
     */
    evaluate: function(model) {
        gs.info('Virgil MinosRuleEngine: Evaluating ' + this.rules.length + ' rules...');
        var findings = [];
        var recommendedNodes = {};

        for (var i = 0; i < this.rules.length; i++) {
            var rule = this.rules[i];
            if (!rule.eval || Object.keys(rule.eval).length === 0) continue;

            var result = this._evalBlock(rule.eval, model);
            if (result.fired) {
                var message = this._formatMessage(rule.message, result.evidence);
                findings.push({
                    rule_id: rule.id,
                    rule_name: rule.name,
                    severity: rule.severity,
                    source: rule.source,
                    category: rule.category,
                    message: message,
                    recommendation: this._formatMessage(rule.recommendation, result.evidence),
                    evidence: result.evidence,
                    tags: rule.tags
                });
                if (rule.recommended_nodes) {
                    for (var nid in rule.recommended_nodes) {
                        recommendedNodes[nid] = rule.recommended_nodes[nid];
                    }
                }
            }
        }

        // Sort by severity: critical → high → medium → low
        var sevOrder = { critical: 0, high: 1, medium: 2, low: 3 };
        findings.sort(function(a, b) {
            return (sevOrder[a.severity] || 9) - (sevOrder[b.severity] || 9);
        });

        gs.info('Virgil MinosRuleEngine: ' + findings.length + ' findings, ' +
            Object.keys(recommendedNodes).length + ' recommended nodes');

        return {
            findings: findings,
            recommended_nodes: recommendedNodes
        };
    },

    // ──────────────────────────────────────────────────────────────────────
    // Evaluation Primitives — generic engine, no rule-specific logic
    // ──────────────────────────────────────────────────────────────────────

    _evalCheck: function(check, model) {
        var tables = model.active_tables || {};
        var cmdb = model.cmdb_stats || {};
        var props = model.instance_properties || {};
        var activeNodeIds = model.active_node_ids || [];
        var ev = {};

        // Node presence
        if (check.node_absent !== undefined) {
            return { fired: activeNodeIds.indexOf(check.node_absent) === -1, evidence: ev };
        }
        if (check.node_active !== undefined) {
            return { fired: activeNodeIds.indexOf(check.node_active) >= 0, evidence: ev };
        }

        // Plugin presence
        if (check.plugin_absent !== undefined) {
            return { fired: !model.installed_plugins[check.plugin_absent], evidence: ev };
        }
        if (check.plugin_present !== undefined) {
            return { fired: !!model.installed_plugins[check.plugin_present], evidence: ev };
        }

        // Table comparisons
        if (check.table_lte !== undefined) {
            var c = tables[check.table_lte.table] !== undefined ? tables[check.table_lte.table] : -1;
            ev[check.table_lte.table + '_count'] = c;
            return { fired: c <= check.table_lte.value, evidence: ev };
        }
        if (check.table_eq !== undefined) {
            var c2 = tables[check.table_eq.table] !== undefined ? tables[check.table_eq.table] : -1;
            ev[check.table_eq.table + '_count'] = c2;
            return { fired: c2 === check.table_eq.value, evidence: ev };
        }
        if (check.table_gt !== undefined) {
            var c3 = tables[check.table_gt.table] !== undefined ? tables[check.table_gt.table] : -1;
            ev[check.table_gt.table + '_count'] = c3;
            return { fired: c3 > check.table_gt.value, evidence: ev };
        }
        if (check.table_between !== undefined) {
            var c4 = tables[check.table_between.table] !== undefined ? tables[check.table_between.table] : -1;
            ev[check.table_between.table + '_count'] = c4;
            return { fired: c4 >= check.table_between.min && c4 < check.table_between.below, evidence: ev };
        }
        if (check.table_exceeds !== undefined) {
            var ca = tables[check.table_exceeds.table] !== undefined ? tables[check.table_exceeds.table] : -1;
            var cb = tables[check.table_exceeds.other] !== undefined ? tables[check.table_exceeds.other] : -1;
            ev[check.table_exceeds.table + '_count'] = ca;
            ev[check.table_exceeds.other + '_count'] = cb;
            return { fired: ca > cb, evidence: ev };
        }
        if (check.table_ratio_below !== undefined) {
            var ra = tables[check.table_ratio_below.table] !== undefined ? tables[check.table_ratio_below.table] : -1;
            var rb = tables[check.table_ratio_below.other] !== undefined ? tables[check.table_ratio_below.other] : -1;
            ev[check.table_ratio_below.table + '_count'] = ra;
            ev[check.table_ratio_below.other + '_count'] = rb;
            if (rb <= 0) return { fired: false, evidence: ev };
            return { fired: ra < rb * check.table_ratio_below.ratio, evidence: ev };
        }

        // CMDB checks
        if (check.cmdb_below !== undefined) {
            var cv = cmdb[check.cmdb_below.field] || 0;
            ev[check.cmdb_below.field] = cv;
            return { fired: cv < check.cmdb_below.value, evidence: ev };
        }
        if (check.cmdb_gt !== undefined) {
            var cv2 = cmdb[check.cmdb_gt.field] || 0;
            ev[check.cmdb_gt.field] = cv2;
            return { fired: cv2 > check.cmdb_gt.value, evidence: ev };
        }
        if (check.cmdb_flag_false !== undefined) {
            var fv = cmdb[check.cmdb_flag_false] || false;
            ev[check.cmdb_flag_false] = fv;
            return { fired: !fv, evidence: ev };
        }

        // Property checks
        if (check.property_neq !== undefined) {
            var actual = (props[check.property_neq.property] || '').toLowerCase();
            ev[check.property_neq.property] = actual || '(not set)';
            return { fired: actual !== check.property_neq.value.toLowerCase(), evidence: ev };
        }

        // Infrastructure checks
        if (check.mid_server_eq !== undefined) {
            var mc = (model.mid_servers || []).length;
            ev.mid_servers = mc;
            return { fired: mc === check.mid_server_eq, evidence: ev };
        }
        if (check.flow_count_eq !== undefined) {
            var fc = model.integration_flows_count || 0;
            ev.integration_flows = fc;
            return { fired: fc === check.flow_count_eq, evidence: ev };
        }

        // Nested combinators
        if (check.all) return this._evalBlock({ all: check.all }, model);
        if (check.any) return this._evalBlock({ any: check.any }, model);

        gs.warn('MinosRuleEngine: Unknown check type: ' + JSON.stringify(Object.keys(check)));
        return { fired: false, evidence: ev };
    },

    _evalBlock: function(block, model) {
        var evidence = {};

        if (block.all) {
            for (var i = 0; i < block.all.length; i++) {
                var r = this._evalCheck(block.all[i], model);
                for (var k in r.evidence) evidence[k] = r.evidence[k];
                if (!r.fired) return { fired: false, evidence: evidence };
            }
            return { fired: true, evidence: evidence };
        }

        if (block.any) {
            for (var j = 0; j < block.any.length; j++) {
                var r2 = this._evalCheck(block.any[j], model);
                for (var k2 in r2.evidence) evidence[k2] = r2.evidence[k2];
                if (r2.fired) return { fired: true, evidence: evidence };
            }
            return { fired: false, evidence: evidence };
        }

        if (block.streams_covered_below) {
            var info = block.streams_covered_below;
            var covered = [];
            for (var sName in info.streams) {
                var sr = this._evalBlock(info.streams[sName], model);
                if (sr.fired) covered.push(sName);
            }
            evidence.covered_count = covered.length;
            evidence.covered_streams = covered.length > 0 ? covered.join(', ') : 'none';
            return { fired: covered.length < info.threshold, evidence: evidence };
        }

        return this._evalCheck(block, model);
    },

    _formatMessage: function(template, evidence) {
        if (!template) return '';
        var msg = template;
        for (var key in evidence) {
            var val = evidence[key];
            if (typeof val === 'number') val = val.toLocaleString();
            msg = msg.replace(new RegExp('\\{' + key + '\\}', 'g'), String(val));
        }
        return msg;
    },

    type: 'MinosRuleEngine'
};
