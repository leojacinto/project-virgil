import {
    Table,
    StringColumn,
    ReferenceColumn,
} from '@servicenow/sdk/core'

export const x_snc_virgil_minos_finding = Table({
    name: 'x_snc_virgil_minos_finding',
    label: 'Minos Finding',
    schema: {
        x_snc_virgil_scan: ReferenceColumn({
            label: 'Scan',
            referenceTable: 'x_snc_virgil_minos_scan',
            mandatory: true,
        }),
        x_snc_virgil_rule: ReferenceColumn({
            label: 'Rule',
            referenceTable: 'x_snc_virgil_minos_rule',
        }),
        x_snc_virgil_rule_id: StringColumn({ label: 'Rule ID', maxLength: 40 }),
        x_snc_virgil_rule_name: StringColumn({ label: 'Rule Name', maxLength: 200 }),
        x_snc_virgil_severity: StringColumn({ label: 'Severity', maxLength: 20 }),
        x_snc_virgil_source: StringColumn({ label: 'Source', maxLength: 40 }),
        x_snc_virgil_category: StringColumn({ label: 'Category', maxLength: 40 }),
        x_snc_virgil_message: StringColumn({ label: 'Message', maxLength: 4000 }),
        x_snc_virgil_recommendation: StringColumn({ label: 'Recommendation', maxLength: 4000 }),
        x_snc_virgil_evidence_json: StringColumn({ label: 'Evidence (JSON)', maxLength: 4000 }),
        x_snc_virgil_tags: StringColumn({ label: 'Tags (JSON)', maxLength: 1000 }),
    },
})
