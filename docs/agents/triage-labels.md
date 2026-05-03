# Triage label vocabulary

The `triage` skill and related engineering workflows use a five-role state machine to manage the lifecycle of issues. This file maps those abstract roles to the literal strings (labels) used in this repository's issue tracker.

| Role | Label | Description |
| :--- | :--- | :--- |
| `needs-triage` | `needs-triage` | Maintainer needs to evaluate the issue |
| `needs-info` | `needs-info` | Waiting on the reporter for more information |
| `ready-for-agent` | `ready-for-agent` | Fully specified; an AFK agent can implement this |
| `ready-for-human` | `ready-for-human` | Needs human implementation or complex judgment |
| `wontfix` | `wontfix` | The issue will not be actioned |
