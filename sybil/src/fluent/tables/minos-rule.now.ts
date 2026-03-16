import {
    Table,
    StringColumn,
    IntegerColumn,
    BooleanColumn,
} from '@servicenow/sdk/core'

export const x_snc_virgil_minos_rule = Table({
    name: 'x_snc_virgil_minos_rule',
    label: 'Minos Rule',
    schema: {
        x_snc_virgil_rule_id: StringColumn({ label: 'Rule ID', maxLength: 40, mandatory: true }),
        x_snc_virgil_name: StringColumn({ label: 'Name', maxLength: 200, mandatory: true }),
        x_snc_virgil_description: StringColumn({ label: 'Description', maxLength: 4000 }),
        x_snc_virgil_source: StringColumn({ label: 'Source', maxLength: 40 }),
        x_snc_virgil_severity: StringColumn({ label: 'Severity', maxLength: 20 }),
        x_snc_virgil_category: StringColumn({ label: 'Category', maxLength: 40 }),
        x_snc_virgil_condition_desc: StringColumn({ label: 'Condition Description', maxLength: 4000 }),
        x_snc_virgil_eval_json: StringColumn({ label: 'Evaluation Logic (JSON)', maxLength: 8000 }),
        x_snc_virgil_message_template: StringColumn({ label: 'Message Template', maxLength: 4000 }),
        x_snc_virgil_recommendation: StringColumn({ label: 'Recommendation', maxLength: 4000 }),
        x_snc_virgil_tags: StringColumn({ label: 'Tags (JSON)', maxLength: 1000 }),
        x_snc_virgil_recommended_nodes: StringColumn({ label: 'Recommended Nodes (JSON)', maxLength: 2000 }),
        x_snc_virgil_active: BooleanColumn({ label: 'Active' }),
        x_snc_virgil_order: IntegerColumn({ label: 'Order' }),
    },
})
