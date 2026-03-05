# Plan-Gate Specification (Admission Control)

POST /gates/plan evaluates intent before any actuation.

Plan JSON MUST include:
{
  "objective": "...",
  "steps": ["..."],
  "tools": ["..."],
  "sources": ["..."],
  "constraints": {"...": "..."}
}

Gate checks:
- GATE_SCOPE   - allowed scope
- GATE_POLICY  - policy_id recognized; tools allowed
- GATE_SCHEMA  - plan schema valid
- GATE_DATA    - sources are allow-listed
- GATE_TOOL    - tool contract satisfied
- GATE_BUDGET  - within time/IO/token budget
- GATE_PRIVACY - privacy flags satisfied (vision flows)
- GATE_INPUT_TYPE / GATE_CONFIDENCE / GATE_LOCATION (optional additions)

Violations format:
{ "pass": false, "violations": [["GATE_DATA","source_not_allowed:..."], ...] }
