import { Role } from '@servicenow/sdk/core'

Role({
    $id: Now.ID['virgil_admin_role'],
    name: 'x_snc_virgil.admin',
    description: 'Full access to all Virgil engines — Minos, Plutus, Advisor',
})

Role({
    $id: Now.ID['virgil_user_role'],
    name: 'x_snc_virgil.user',
    description: 'Run scans and view results',
})
