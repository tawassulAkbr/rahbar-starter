# ADR 0004: Provider boundary and data governance

## Status

Accepted · 2026-11-07

## Decision

The API calls an explicit provider interface and supports the offline stub,
Ollama, and hosted providers. Credentials are read from environment-backed
Kubernetes Secrets; they are never placed in prompts, source, or logs. Retrieved
text is delimited as untrusted evidence, and the validated response is checked
against retrieved citations before it is returned.

## Consequences

The provider can be changed without changing retrieval or routing, and local
tests do not require a network model. Hosted providers require an operational
privacy review, retention policy, and an appropriately scoped secret before
production use.
