# Bounded-context modules (see docs/adr/0001-modular-monolith.md and
# docs/diagrams/bounded-contexts.md):
#
# Core:       identity, listings, search, booking, pricing, payments
# Supporting: reviews, crm, operations (ERP), marketing
# Generic:    notifications (deployed as a separate process)
