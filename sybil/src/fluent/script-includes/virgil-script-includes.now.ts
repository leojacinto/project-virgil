import { ScriptInclude } from '@servicenow/sdk/core'

ScriptInclude({
    $id: Now.ID['virgil_utils_si'],
    name: 'VirgilUtils',
    description: 'Utility functions — record counts, table existence, plugin detection, CMDB stats',
    active: true,
    client_callable: false,
    script: Now.include('../server/VirgilUtils.server.js'),
})

ScriptInclude({
    $id: Now.ID['minos_ontology_si'],
    name: 'MinosOntology',
    description: 'Architecture ontology graph — loads nodes/edges from tables, maps instance to nodes, generates Mermaid diagrams',
    active: true,
    client_callable: false,
    script: Now.include('../server/MinosOntology.server.js'),
})

ScriptInclude({
    $id: Now.ID['minos_rule_engine_si'],
    name: 'MinosRuleEngine',
    description: 'Generic rule engine — loads rules from table, evaluates against instance model, produces findings',
    active: true,
    client_callable: false,
    script: Now.include('../server/MinosRuleEngine.server.js'),
})

ScriptInclude({
    $id: Now.ID['minos_scanner_si'],
    name: 'MinosScanner',
    description: 'Full architecture scan — plugins, tables, ontology mapping, rule evaluation, diagram generation, persistence',
    active: true,
    client_callable: false,
    script: Now.include('../server/MinosScanner.server.js'),
})

ScriptInclude({
    $id: Now.ID['plutus_scanner_si'],
    name: 'PlutusScanner',
    description: 'WDF credit sizing scan — rate card loading, capability detection, credit calculation, persistence',
    active: true,
    client_callable: false,
    script: Now.include('../server/PlutusScanner.server.js'),
})

ScriptInclude({
    $id: Now.ID['virgil_ajax_si'],
    name: 'VirgilAjax',
    description: 'Client-callable GlideAjax wrapper for triggering Minos and Plutus scans from workspace UI',
    active: true,
    client_callable: true,
    script: Now.include('../server/VirgilAjax.server.js'),
})
