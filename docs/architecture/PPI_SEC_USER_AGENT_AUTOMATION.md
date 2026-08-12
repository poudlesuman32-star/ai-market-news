# PPI SEC Declared User-Agent Automation

The SEC universe pilot no longer requires a complete `PPI_SEC_USER_AGENT` repository variable.

The workflow constructs the declared user agent automatically in this order:

1. Optional non-secret repository variable `PPI_SEC_CONTACT_EMAIL`.
2. The repository owner's publicly visible GitHub profile email.
3. Fail closed before SEC network access when neither source contains a valid monitored contact address.

The application name is fixed as `PPI Universe Research`. The resulting request header has this form:

```text
PPI Universe Research contact@example.org
```

The resolver rejects placeholder, malformed, and GitHub noreply addresses. The contact is not a provider credential, but its configured value is still operational data that must not be reproduced in issue comments, reports, retained artifacts, or Actions logs.

Live SEC pilot run `30915422311` showed that assigning the configured contact through workflow environment rendering could expose its value in Actions logging even though the collector did not intentionally print or retain it. The masking remediation in this branch therefore registers both the resolved contact and the constructed SEC user-agent with the GitHub Actions masking command before validation, resolver, or collection commands execute. Regression coverage enforces that ordering.

Safe workflow summaries and retained pilot artifacts may expose only non-contact metadata such as the resolution source and SHA-256 identity. They must not contain the contact value or constructed user-agent string.

This automation does not add secrets, write permissions, private-repository access, screening, deep evidence, registry mutation, publication, or trading authority. The masking remediation does not itself dispatch acquisition and does not authorize a new SEC run.
