import { ApplicationMenu, Record } from '@servicenow/sdk/core'

export const virgilAppMenu = ApplicationMenu({
    $id: Now.ID['virgil_app_menu'],
    title: 'Virgil',
    active: true,
    order: 100,
    description: 'Presales intelligence — Architecture Scan, WDF Sizing, AI Advisor',
})

// ── Minos modules ────────────────────────────────────────────────────────────

Record({
    $id: Now.ID['minos_scans_module'],
    table: 'sys_app_module',
    data: {
        title: 'Minos Scans',
        name: 'x_snc_virgil_minos_scan',
        application: virgilAppMenu,
        link_type: 'LIST',
        active: true,
        order: 100,
    },
})

Record({
    $id: Now.ID['minos_findings_module'],
    table: 'sys_app_module',
    data: {
        title: 'Minos Findings',
        name: 'x_snc_virgil_minos_finding',
        application: virgilAppMenu,
        link_type: 'LIST',
        active: true,
        order: 200,
    },
})

Record({
    $id: Now.ID['minos_rules_module'],
    table: 'sys_app_module',
    data: {
        title: 'Minos Rules',
        name: 'x_snc_virgil_minos_rule',
        application: virgilAppMenu,
        link_type: 'LIST',
        active: true,
        order: 300,
    },
})

// ── Ontology modules ─────────────────────────────────────────────────────────

Record({
    $id: Now.ID['ontology_nodes_module'],
    table: 'sys_app_module',
    data: {
        title: 'Ontology Nodes',
        name: 'x_snc_virgil_ontology_node',
        application: virgilAppMenu,
        link_type: 'LIST',
        active: true,
        order: 400,
    },
})

Record({
    $id: Now.ID['ontology_edges_module'],
    table: 'sys_app_module',
    data: {
        title: 'Ontology Edges',
        name: 'x_snc_virgil_ontology_edge',
        application: virgilAppMenu,
        link_type: 'LIST',
        active: true,
        order: 500,
    },
})

// ── Plutus/WDF modules ──────────────────────────────────────────────────────

Record({
    $id: Now.ID['wdf_scans_module'],
    table: 'sys_app_module',
    data: {
        title: 'WDF Scans',
        name: 'x_snc_virgil_wdf_scan',
        application: virgilAppMenu,
        link_type: 'LIST',
        active: true,
        order: 600,
    },
})

Record({
    $id: Now.ID['wdf_rate_card_module'],
    table: 'sys_app_module',
    data: {
        title: 'WDF Rate Card',
        name: 'x_snc_virgil_wdf_rate_card',
        application: virgilAppMenu,
        link_type: 'LIST',
        active: true,
        order: 700,
    },
})
