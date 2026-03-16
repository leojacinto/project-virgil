import {
    Table,
    StringColumn,
    IntegerColumn,
    DecimalColumn,
    DateTimeColumn,
} from '@servicenow/sdk/core'

export const x_snc_virgil_wdf_scan = Table({
    name: 'x_snc_virgil_wdf_scan',
    label: 'WDF Scan',
    schema: {
        x_snc_virgil_scan_date: DateTimeColumn({ label: 'Scan Date' }),
        x_snc_virgil_instance_url: StringColumn({ label: 'Instance URL', maxLength: 200 }),
        x_snc_virgil_status: StringColumn({ label: 'Status', maxLength: 20 }),
        x_snc_virgil_duration_seconds: DecimalColumn({ label: 'Duration (seconds)' }),
        x_snc_virgil_total_credits: DecimalColumn({ label: 'Total Credits' }),
        x_snc_virgil_capabilities_detected: IntegerColumn({ label: 'Capabilities Detected' }),
        x_snc_virgil_capabilities_total: IntegerColumn({ label: 'Capabilities Total' }),
    },
})
