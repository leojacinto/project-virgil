var MinosOntology = Class.create();
MinosOntology.prototype = {
    initialize: function() {
        this.nodes = {};
        this.edges = [];
        this._loadFromTables();
        this._buildIndexes();
    },

    // ──────────────────────────────────────────────────────────────────────
    // Load graph from x_snc_virgil_ontology_node and x_snc_virgil_ontology_edge
    // ──────────────────────────────────────────────────────────────────────

    _loadFromTables: function() {
        // Load nodes
        var gr = new GlideRecord('x_snc_virgil_ontology_node');
        gr.addQuery('active', true);
        gr.orderBy('order');
        gr.query();
        while (gr.next()) {
            var nid = gr.getValue('node_id');
            this.nodes[nid] = {
                id: nid,
                name: gr.getValue('name') || '',
                node_type: gr.getValue('node_type') || '',
                aliases: this._parseJSON(gr.getValue('aliases'), []),
                tables: this._parseJSON(gr.getValue('tables'), []),
                plugins: this._parseJSON(gr.getValue('plugins'), []),
                layer: gr.getValue('layer') || '',
                it4it_streams: this._parseJSON(gr.getValue('it4it_streams'), [])
            };
        }

        // Load edges
        var eg = new GlideRecord('x_snc_virgil_ontology_edge');
        eg.addQuery('active', true);
        eg.query();
        while (eg.next()) {
            this.edges.push({
                source: eg.getValue('source_node') || '',
                target: eg.getValue('target_node') || '',
                rel_type: eg.getValue('rel_type') || '',
                constraint: eg.getValue('constraint') || ''
            });
        }

        gs.debug('MinosOntology: Loaded ' + Object.keys(this.nodes).length +
                 ' nodes, ' + this.edges.length + ' edges from tables');
    },

    _parseJSON: function(str, fallback) {
        if (!str) return fallback;
        try { return JSON.parse(str); } catch (e) { return fallback; }
    },

    _buildIndexes: function() {
        this._pluginToNodes = {};
        this._tableToNodes = {};
        this._productModules = {};

        for (var nid in this.nodes) {
            var node = this.nodes[nid];
            for (var p = 0; p < node.plugins.length; p++) {
                var pid = node.plugins[p];
                if (!this._pluginToNodes[pid]) this._pluginToNodes[pid] = [];
                this._pluginToNodes[pid].push(nid);
            }
            for (var t = 0; t < node.tables.length; t++) {
                var tbl = node.tables[t];
                if (!this._tableToNodes[tbl]) this._tableToNodes[tbl] = [];
                this._tableToNodes[tbl].push(nid);
            }
        }

        for (var ei = 0; ei < this.edges.length; ei++) {
            var edge = this.edges[ei];
            if (edge.rel_type === 'depends_on') {
                if (!this._productModules[edge.source]) this._productModules[edge.source] = [];
                this._productModules[edge.source].push(edge.target);
            }
        }
    },

    // ──────────────────────────────────────────────────────────────────────
    // Instance → Ontology Mapping
    // ──────────────────────────────────────────────────────────────────────

    /**
     * Map installed plugins and table activity to active ontology nodes.
     * @param {Object} model - Instance model from MinosScanner
     * @returns {Object} {active_node_ids: [], active_nodes: []}
     */
    mapInstanceToNodes: function(model) {
        var activeIds = {};

        // 1. Plugin presence
        for (var pid in model.installed_plugins) {
            if (this._pluginToNodes[pid]) {
                var pNodes = this._pluginToNodes[pid];
                for (var pn = 0; pn < pNodes.length; pn++) {
                    activeIds[pNodes[pn]] = true;
                }
            }
        }

        // 2. Table activity (record count > 0)
        for (var tbl in model.active_tables) {
            if (tbl.indexOf('_') === 0) continue; // skip meta keys like _custom_tables
            var count = model.active_tables[tbl];
            if (count > 0 && this._tableToNodes[tbl]) {
                var tNodes = this._tableToNodes[tbl];
                for (var tn = 0; tn < tNodes.length; tn++) {
                    activeIds[tNodes[tn]] = true;
                }
            }
        }

        // 3. Promote: if a module is active, its parent product is also active
        for (var prod in this._productModules) {
            var modules = this._productModules[prod];
            for (var m = 0; m < modules.length; m++) {
                if (activeIds[modules[m]]) {
                    activeIds[prod] = true;
                    break;
                }
            }
        }

        // 4. Foundational nodes active if any application is active
        var hasAnyApp = false;
        for (var nid in activeIds) {
            var node = this.nodes[nid];
            if (node && node.layer === 'application') {
                hasAnyApp = true;
                break;
            }
        }
        if (hasAnyApp) {
            var foundational = ['cmdb', 'user_mgmt', 'knowledge_base', 'audit', 'platform'];
            for (var fi = 0; fi < foundational.length; fi++) {
                activeIds[foundational[fi]] = true;
            }
        }

        // Build result arrays
        var activeIdList = [];
        var activeNodeList = [];
        for (var aid in activeIds) {
            activeIdList.push(aid);
            if (this.nodes[aid]) {
                activeNodeList.push({
                    id: aid,
                    name: this.nodes[aid].name,
                    layer: this.nodes[aid].layer,
                    it4it_streams: this.nodes[aid].it4it_streams
                });
            }
        }

        return {
            active_node_ids: activeIdList,
            active_nodes: activeNodeList
        };
    },

    // ──────────────────────────────────────────────────────────────────────
    // Helpers
    // ──────────────────────────────────────────────────────────────────────

    getAllNodes: function() {
        return this.nodes;
    },

    getAllReferencedTables: function() {
        var tables = [];
        var seen = {};
        for (var nid in this.nodes) {
            var nodeTables = this.nodes[nid].tables;
            for (var t = 0; t < nodeTables.length; t++) {
                if (!seen[nodeTables[t]]) {
                    tables.push(nodeTables[t]);
                    seen[nodeTables[t]] = true;
                }
            }
        }
        return tables;
    },

    /**
     * Generate a Mermaid diagram from active nodes.
     * @param {Array} activeNodeIds
     * @param {string} mode - 'as_is' or 'recommended'
     * @param {Object} [recommendedNodes] - {nodeId: reason} from rule engine
     * @returns {string} Mermaid diagram source
     */
    generateMermaid: function(activeNodeIds, mode, recommendedNodes) {
        recommendedNodes = recommendedNodes || {};
        var lines = ['graph TB'];

        // Layer subgraphs
        var layers = {
            'platform': 'Platform',
            'data': 'Data Layer',
            'application': 'Applications',
            'orchestration': 'Orchestration',
            'ui': 'User Interface',
            'external': 'External'
        };

        var activeSet = {};
        for (var a = 0; a < activeNodeIds.length; a++) {
            activeSet[activeNodeIds[a]] = true;
        }

        for (var layerId in layers) {
            var layerNodes = [];
            for (var nid in this.nodes) {
                var node = this.nodes[nid];
                if (node.layer !== layerId) continue;

                var isActive = !!activeSet[nid];
                var isRecommended = !!recommendedNodes[nid];

                if (mode === 'as_is' && !isActive) continue;
                if (mode === 'recommended' && !isActive && !isRecommended) continue;

                var style = '';
                if (isRecommended && !isActive) {
                    style = ':::recommended';
                    layerNodes.push('    ' + nid + '[' + node.name + ' ⭐]' + style);
                } else {
                    layerNodes.push('    ' + nid + '[' + node.name + ']');
                }
            }

            if (layerNodes.length > 0) {
                lines.push('  subgraph ' + layers[layerId]);
                for (var ln = 0; ln < layerNodes.length; ln++) {
                    lines.push(layerNodes[ln]);
                }
                lines.push('  end');
            }
        }

        // Edges between active (and recommended) nodes
        var allRelevant = {};
        for (var key in activeSet) allRelevant[key] = true;
        if (mode === 'recommended') {
            for (var rn in recommendedNodes) allRelevant[rn] = true;
        }

        for (var ei = 0; ei < this.edges.length; ei++) {
            var edge = this.edges[ei];
            if (allRelevant[edge.source] && allRelevant[edge.target]) {
                if (edge.rel_type !== 'extends' && edge.rel_type !== 'segregated_from') {
                    lines.push('  ' + edge.source + ' --> ' + edge.target);
                }
            }
        }

        // Style classes
        lines.push('  classDef recommended fill:#fef3c7,stroke:#f59e0b,stroke-width:2px');

        return lines.join('\n');
    },

    type: 'MinosOntology'
};
