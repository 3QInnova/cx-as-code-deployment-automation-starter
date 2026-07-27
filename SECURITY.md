# Security and Production Boundaries

This repository is a platform-neutral reference implementation. It does not
authenticate to or change a live environment.

Before connecting a production adapter:

- use workload identity or a managed secret store rather than committed keys;
- separate read-only export, planning, deployment, and verification identities;
- enforce least-privilege permissions per environment and resource type;
- require peer approval for production promotion and rollback;
- validate API responses against explicit schemas;
- redact or omit secrets, customer data, recordings, and prompt content from plans;
- sign and retain immutable promotion artifacts and audit events;
- apply rate limits, retry budgets, idempotency keys, and circuit breakers;
- test dependency ordering and rollback in a non-production environment;
- verify the resulting live state through the source API rather than trusting
  only a deployment command's exit code.

Deletion is intentionally excluded from the starter. A production deletion
workflow should require an explicit allowlist, dependency-impact analysis,
backup confirmation, and elevated approval.

Report security concerns privately to the repository owner. Do not open a
public issue containing credentials, vulnerabilities, or customer data.

