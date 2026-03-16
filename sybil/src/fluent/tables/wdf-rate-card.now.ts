import {
    Table,
    StringColumn,
    DecimalColumn,
    BooleanColumn,
} from '@servicenow/sdk/core'

export const x_snc_virgil_wdf_rate_card = Table({
    name: 'x_snc_virgil_wdf_rate_card',
    label: 'WDF Rate Card',
    schema: {
        x_snc_virgil_cap_id: StringColumn({ label: 'Capability ID', maxLength: 40, mandatory: true }),
        x_snc_virgil_label: StringColumn({ label: 'Label', maxLength: 200, mandatory: true }),
        x_snc_virgil_meter_unit: StringColumn({ label: 'Meter Unit', maxLength: 100 }),
        x_snc_virgil_credits: DecimalColumn({ label: 'Credits Per Unit' }),
        x_snc_virgil_measurable: BooleanColumn({ label: 'Auto-Measurable' }),
        x_snc_virgil_tier: StringColumn({ label: 'Tier', maxLength: 20 }),
        x_snc_virgil_order: DecimalColumn({ label: 'Order' }),
    },
})
