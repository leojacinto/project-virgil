import {
    Table,
    StringColumn,
    DecimalColumn,
    BooleanColumn,
    ReferenceColumn,
} from '@servicenow/sdk/core'

export const x_snc_virgil_wdf_scan_line = Table({
    name: 'x_snc_virgil_wdf_scan_line',
    label: 'WDF Scan Line',
    schema: {
        x_snc_virgil_scan: ReferenceColumn({
            label: 'Scan',
            referenceTable: 'x_snc_virgil_wdf_scan',
            mandatory: true,
        }),
        x_snc_virgil_capability_id: StringColumn({ label: 'Capability ID', maxLength: 40 }),
        x_snc_virgil_capability_label: StringColumn({ label: 'Capability Label', maxLength: 200 }),
        x_snc_virgil_detected: BooleanColumn({ label: 'Detected' }),
        x_snc_virgil_usage_value: DecimalColumn({ label: 'Usage Value' }),
        x_snc_virgil_meter_unit: StringColumn({ label: 'Meter Unit', maxLength: 100 }),
        x_snc_virgil_credits_per_unit: DecimalColumn({ label: 'Credits Per Unit' }),
        x_snc_virgil_credits_consumed: DecimalColumn({ label: 'Credits Consumed' }),
        x_snc_virgil_evidence: StringColumn({ label: 'Evidence (JSON)', maxLength: 4000 }),
    },
})
