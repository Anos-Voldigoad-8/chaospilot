---
name: semgrep-audit
description: >-
  Static code security, pattern checking, secret leak defense, and safe coding standards (semgrep/semgrep).
---

# Semgrep Security Standards

Based on [semgrep/semgrep](https://github.com/semgrep/semgrep).

## Security Guardrails
1. **Zero Secret Leaks**: Never expose tokens or keys in code or frontend bundles.
2. **Safe Input Sanitization**: Validate all scenario IDs and query inputs.
3. **No Unsanitized HTML**: Escape markdown and raw telemetry strings.
