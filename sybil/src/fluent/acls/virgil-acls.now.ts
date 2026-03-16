import { Acl } from '@servicenow/sdk/core'

// ── Minos Scan ───────────────────────────────────────────────────────────────

Acl({
    $id: Now.ID['minos_scan_read_acl'],
    type: 'record',
    table: 'x_snc_virgil_minos_scan',
    operation: 'read',
    roles: ['x_snc_virgil.user', 'x_snc_virgil.admin'],
    active: true,
})

Acl({
    $id: Now.ID['minos_scan_write_acl'],
    type: 'record',
    table: 'x_snc_virgil_minos_scan',
    operation: 'write',
    roles: ['x_snc_virgil.admin'],
    active: true,
})

// ── Minos Finding ────────────────────────────────────────────────────────────

Acl({
    $id: Now.ID['minos_finding_read_acl'],
    type: 'record',
    table: 'x_snc_virgil_minos_finding',
    operation: 'read',
    roles: ['x_snc_virgil.user', 'x_snc_virgil.admin'],
    active: true,
})

Acl({
    $id: Now.ID['minos_finding_write_acl'],
    type: 'record',
    table: 'x_snc_virgil_minos_finding',
    operation: 'write',
    roles: ['x_snc_virgil.admin'],
    active: true,
})

// ── Minos Rule ───────────────────────────────────────────────────────────────

Acl({
    $id: Now.ID['minos_rule_read_acl'],
    type: 'record',
    table: 'x_snc_virgil_minos_rule',
    operation: 'read',
    roles: ['x_snc_virgil.user', 'x_snc_virgil.admin'],
    active: true,
})

Acl({
    $id: Now.ID['minos_rule_write_acl'],
    type: 'record',
    table: 'x_snc_virgil_minos_rule',
    operation: 'write',
    roles: ['x_snc_virgil.admin'],
    active: true,
})

// ── Ontology Node ────────────────────────────────────────────────────────────

Acl({
    $id: Now.ID['ontology_node_read_acl'],
    type: 'record',
    table: 'x_snc_virgil_ontology_node',
    operation: 'read',
    roles: ['x_snc_virgil.user', 'x_snc_virgil.admin'],
    active: true,
})

Acl({
    $id: Now.ID['ontology_node_write_acl'],
    type: 'record',
    table: 'x_snc_virgil_ontology_node',
    operation: 'write',
    roles: ['x_snc_virgil.admin'],
    active: true,
})

// ── Ontology Edge ────────────────────────────────────────────────────────────

Acl({
    $id: Now.ID['ontology_edge_read_acl'],
    type: 'record',
    table: 'x_snc_virgil_ontology_edge',
    operation: 'read',
    roles: ['x_snc_virgil.user', 'x_snc_virgil.admin'],
    active: true,
})

Acl({
    $id: Now.ID['ontology_edge_write_acl'],
    type: 'record',
    table: 'x_snc_virgil_ontology_edge',
    operation: 'write',
    roles: ['x_snc_virgil.admin'],
    active: true,
})

// ── WDF Rate Card ────────────────────────────────────────────────────────────

Acl({
    $id: Now.ID['wdf_rate_card_read_acl'],
    type: 'record',
    table: 'x_snc_virgil_wdf_rate_card',
    operation: 'read',
    roles: ['x_snc_virgil.user', 'x_snc_virgil.admin'],
    active: true,
})

Acl({
    $id: Now.ID['wdf_rate_card_write_acl'],
    type: 'record',
    table: 'x_snc_virgil_wdf_rate_card',
    operation: 'write',
    roles: ['x_snc_virgil.admin'],
    active: true,
})

// ── WDF Scan ─────────────────────────────────────────────────────────────────

Acl({
    $id: Now.ID['wdf_scan_read_acl'],
    type: 'record',
    table: 'x_snc_virgil_wdf_scan',
    operation: 'read',
    roles: ['x_snc_virgil.user', 'x_snc_virgil.admin'],
    active: true,
})

Acl({
    $id: Now.ID['wdf_scan_write_acl'],
    type: 'record',
    table: 'x_snc_virgil_wdf_scan',
    operation: 'write',
    roles: ['x_snc_virgil.admin'],
    active: true,
})

// ── WDF Scan Line ────────────────────────────────────────────────────────────

Acl({
    $id: Now.ID['wdf_scan_line_read_acl'],
    type: 'record',
    table: 'x_snc_virgil_wdf_scan_line',
    operation: 'read',
    roles: ['x_snc_virgil.user', 'x_snc_virgil.admin'],
    active: true,
})

Acl({
    $id: Now.ID['wdf_scan_line_write_acl'],
    type: 'record',
    table: 'x_snc_virgil_wdf_scan_line',
    operation: 'write',
    roles: ['x_snc_virgil.admin'],
    active: true,
})
