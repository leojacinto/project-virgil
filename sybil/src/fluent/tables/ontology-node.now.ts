import {
    Table,
    StringColumn,
    IntegerColumn,
    BooleanColumn,
} from '@servicenow/sdk/core'

export const x_snc_virgil_ontology_node = Table({
    name: 'x_snc_virgil_ontology_node',
    label: 'Ontology Node',
    schema: {
        x_snc_virgil_node_id: StringColumn({ label: 'Node ID', maxLength: 40, mandatory: true }),
        x_snc_virgil_name: StringColumn({ label: 'Name', maxLength: 200, mandatory: true }),
        x_snc_virgil_node_type: StringColumn({ label: 'Node Type', maxLength: 40 }),
        x_snc_virgil_aliases: StringColumn({ label: 'Aliases (JSON)', maxLength: 2000 }),
        x_snc_virgil_tables: StringColumn({ label: 'Tables (JSON)', maxLength: 2000 }),
        x_snc_virgil_plugins: StringColumn({ label: 'Plugins (JSON)', maxLength: 2000 }),
        x_snc_virgil_layer: StringColumn({ label: 'Layer', maxLength: 40 }),
        x_snc_virgil_it4it_streams: StringColumn({ label: 'IT4IT Streams (JSON)', maxLength: 200 }),
        x_snc_virgil_active: BooleanColumn({ label: 'Active' }),
        x_snc_virgil_order: IntegerColumn({ label: 'Order' }),
    },
})
