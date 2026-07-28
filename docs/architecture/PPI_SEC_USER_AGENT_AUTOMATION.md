# PPI SEC Declared User-Agent Automation

The SEC universe pilot no longer requires a complete `PPI_SEC_USER_AGENT` repository variable.

The workflow now constructs the declared user agent automatically in this order:

1. Optional non-secret repository variable `PPI_SEC_CONTACT_EMAIL`.
2. The repository owner's publicly visible GitHub profile email.
3. Fail closed before SEC network access when neither source contains a valid monitored contact address.

The application name is fixed as `PPI Universe Research`. The resulting request header has this form:

```text
PPI Universe Research contact@example.org
```

The resolver rejects placeholder, malformed, and GitHub noreply addresses. It does not log or retain the contact email in the pilot artifact. Only the resolution source and SHA-256 identity are exposed to the workflow summary.

This automation does not add secrets, write permissions, private-repository access, screening, deep evidence, registry mutation, publication, or trading authority.
