# ADR 0009: Local Ollama-compatible chat provider

- **Status:** Accepted
- **Date:** 2026-11-20

## Context

KALDRAX already sends chat-completion requests through a standard-library OpenAI-compatible adapter. HTTPS-only URL validation and mandatory API-key validation prevented operators from using local Ollama inference without adding another provider SDK.

The desktop UI also required a provider key before launching a task or team run, even when a loopback endpoint was configured.

## Decision

1. Reuse `OpenAICompatibleClient`; do not add a Python dependency or package the Ollama runtime.
2. Allow HTTP only when the URL host is exactly `localhost`, an IPv4 loopback address, or the IPv6 loopback address. Reject HTTP for every other host. Require HTTPS for hosted/non-loopback endpoints.
3. Allow an empty API key only for those loopback HTTP endpoints. Omit the Authorization header when the key is empty.
4. Preserve HTTPS and key requirements for hosted providers.
5. Default the completion token-limit parameter to `max_tokens` for loopback endpoints and `max_completion_tokens` otherwise. An explicit `KALDRAX_TOKEN_PARAMETER` overrides this choice.
6. Keep request budgets, timeout ceilings, output-size limits, and response validation unchanged.
7. Treat embeddings as a separate provider. The current embedding adapter remains HTTPS-only; operators seeking on-device-only memory must leave hosted embedding configuration unset and use lexical retrieval.

## Consequences

- Ollama can be used through its OpenAI-compatible endpoint, commonly `http://127.0.0.1:11434/v1`, without a key.
- The desktop can configure local inference through its existing base-URL field.
- KALDRAX does not install/manage Ollama, pull models, select GPU layers, or expose model lifecycle APIs.
- Non-loopback HTTP is rejected to avoid sending prompts or credentials over an unauthenticated network connection.
- Hosted embeddings can still transmit memory text to the configured embedding provider; this is not changed by local chat configuration.

## Verification

Unit tests cover local URL allowlisting, keyless requests, hosted key requirements, and provider-configuration validation. Hosted CI and a live Ollama run are required before claiming platform-level verification or model quality.
