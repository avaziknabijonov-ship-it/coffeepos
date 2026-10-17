# Customer bonuses

The manager enables the program under Admin → Bonus tizimi. New and existing cafes start with the program disabled; the suggested editable rates are 5% earned and a maximum 30% redemption. One point is one Uzbek sum. Points do not expire.

At checkout, search by phone, or create a customer with their consent. Nine-digit local numbers normalize to +998. The cashier can choose how many existing points to use. New points equal floor((subtotal − ordinary discount − points used) × earn percentage / 100). Debt sales neither earn nor redeem points. Customers can still buy without joining.

The server recalculates all totals and enforces limits. The customer's balance changes atomically in the same transaction as the order, stock movements and ledger entry. A conditional database update prevents simultaneous spending beyond the existing balance. New points from the current purchase cannot fund that purchase. The receipt shows earned, spent and resulting balance; financial and shift totals contain the amount payable after points. These are recorded payments, not automatic bank confirmation.

Customer lookup, balances, history and settings are scoped to a cafe. Cashiers can register/search customers and see their last 100 entries; only owners/admins can change rates. Baristas cannot access customer bonus endpoints. Account deletion removes the cafe's customers, bonus entries and configuration together with its other data. The privacy page discloses phone and bonus history processing.

Installation: stop the Python server; extract the entire update ZIP and run UPDATE.cmd. The updater backs up local SQLite databases and previous source before replacing files. Restart the server using the same DATABASE_URL as before, restart Vite, and refresh the browser. Existing orders receive zero earned/spent bonuses; migration preserves data and is repeatable. An old APK must be rebuilt to show the checkout controls. Safari/browser clients use the updated web interface.

Validated: backend API flow, cash payment totals after discounts and points, permissions, tenant isolation, negative/fractional values, overspending, limits, failed payment rollback, simultaneous redemptions, repeated migrations; production frontend build and lint. No real tablet or printer validation has been performed for this change. Returns/refunds are not implemented in CoffeePOS and do not have bonus reversal controls.
