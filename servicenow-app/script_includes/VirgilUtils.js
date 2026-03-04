var VirgilUtils = Class.create();
VirgilUtils.prototype = {
    initialize: function() {},

    /**
     * Get record count for a table using GlideAggregate.
     * @param {string} tableName - Table to count
     * @param {string} [encodedQuery] - Optional encoded query filter
     * @returns {number} Record count
     */
    getRecordCount: function(tableName, encodedQuery) {
        try {
            var ga = new GlideAggregate(tableName);
            ga.addAggregate('COUNT');
            if (encodedQuery) {
                ga.addEncodedQuery(encodedQuery);
            }
            ga.query();
            if (ga.next()) {
                return parseInt(ga.getAggregate('COUNT'), 10) || 0;
            }
        } catch (e) {
            gs.debug('VirgilUtils.getRecordCount error on ' + tableName + ': ' + e);
        }
        return 0;
    },

    /**
     * Check if a table exists on this instance.
     * @param {string} tableName
     * @returns {boolean}
     */
    tableExists: function(tableName) {
        var gr = new GlideRecord('sys_db_object');
        gr.addQuery('name', tableName);
        gr.setLimit(1);
        gr.query();
        return gr.hasNext();
    },

    /**
     * Check if a plugin is active.
     * @param {string} pluginId - Plugin ID (e.g., 'com.snc.incident')
     * @returns {boolean}
     */
    isPluginActive: function(pluginId) {
        try {
            return GlidePluginManager.isActive(pluginId);
        } catch (e) {
            gs.debug('VirgilUtils.isPluginActive error: ' + e);
            return false;
        }
    },

    /**
     * Get installed applications (sys_app + v_plugin active).
     * @returns {Array} Array of {id, name, scope, version}
     */
    getInstalledApps: function() {
        var apps = [];
        var seen = {};

        // sys_app (scoped apps)
        var gr = new GlideRecord('sys_app');
        gr.addQuery('active', true);
        gr.query();
        while (gr.next()) {
            var scope = gr.getValue('scope') || '';
            if (!seen[scope]) {
                apps.push({
                    id: scope,
                    name: gr.getValue('name') || '',
                    scope: scope,
                    version: gr.getValue('version') || ''
                });
                seen[scope] = true;
            }
        }

        // v_plugin (platform plugins)
        var vp = new GlideRecord('v_plugin');
        vp.addQuery('active', 'active');
        vp.query();
        while (vp.next()) {
            var pid = vp.getValue('id') || '';
            if (!seen[pid]) {
                apps.push({
                    id: pid,
                    name: vp.getValue('name') || '',
                    scope: pid,
                    version: vp.getValue('version') || ''
                });
                seen[pid] = true;
            }
        }

        return apps;
    },

    /**
     * Get a system property value.
     * @param {string} propName
     * @param {string} [defaultValue]
     * @returns {string}
     */
    getProperty: function(propName, defaultValue) {
        return gs.getProperty(propName, defaultValue || '');
    },

    /**
     * Get multiple record counts in a single call.
     * @param {Array} tableSpecs - Array of {table, query} objects
     * @returns {Object} Map of table -> count
     */
    getMultipleRecordCounts: function(tableSpecs) {
        var result = {};
        for (var i = 0; i < tableSpecs.length; i++) {
            var spec = tableSpecs[i];
            var key = spec.table + (spec.query ? '_filtered' : '');
            result[spec.table] = this.getRecordCount(spec.table, spec.query || '');
        }
        return result;
    },

    /**
     * Get CMDB statistics.
     * @returns {Object} {total_cis, ci_classes, has_discovery, has_service_mapping, relationships}
     */
    getCMDBStats: function() {
        var stats = {
            total_cis: 0,
            ci_classes: 0,
            has_discovery: false,
            has_service_mapping: false,
            relationships: 0
        };

        // Total CIs
        stats.total_cis = this.getRecordCount('cmdb_ci');

        // Distinct CI classes
        var ga = new GlideAggregate('cmdb_ci');
        ga.addAggregate('COUNT', 'sys_class_name');
        ga.query();
        var classCount = 0;
        while (ga.next()) {
            classCount++;
        }
        stats.ci_classes = classCount;

        // Discovery & Service Mapping
        stats.has_discovery = this.isPluginActive('com.snc.discovery');
        stats.has_service_mapping = this.isPluginActive('com.snc.service_mapping');

        // Relationships
        stats.relationships = this.getRecordCount('cmdb_rel_ci');

        return stats;
    },

    /**
     * Build a JSON response object for Scripted REST.
     * @param {Object} data
     * @param {number} [status]
     * @returns {Object}
     */
    buildResponse: function(data, status) {
        return {
            status: status || 200,
            data: data,
            timestamp: new GlideDateTime().getDisplayValue()
        };
    },

    type: 'VirgilUtils'
};
