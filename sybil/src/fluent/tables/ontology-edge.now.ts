import {
    Table,
    StringColumn,
    BooleanColumn,
} from '@servicenow/sdk/core'

export const x_snc_virgil_ontology_edge = Table({
    name: 'x_snc_virgil_ontology_edge',
    label: 'Ontology Edge',
    schema: {
        x_snc_virgil_source_node: StringColumn({ label: 'Source Node ID', maxLength: 40, mandatory: true }),
        x_snc_virgil_target_node: StringColumn({ label: 'Target Node ID', maxLength: 40, mandatory: true }),
        x_snc_virgil_rel_type: StringColumn({ label: 'Relationship Type', maxLength: 40 }),
        x_snc_virgil_constraint: StringColumn({ label: 'Constraint', maxLength: 500 }),
        x_snc_virgil_active: BooleanColumn({ label: 'Active' }),
    },
})
