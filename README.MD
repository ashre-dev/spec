# ASHRE — Agent Shopping Registry

ASHRE is an open specification for agent-native commerce discovery.

It defines how vendors expose their products and services as MCP servers,
how agents discover verified vendors at runtime, and how payments are 
routed via the x402 protocol — without any single platform owning the flow.

ASHRE is agent-agnostic. It works with OpenClaw, Claude, GPT, or any 
agent that can make HTTP calls.

## Structure

- `spec/vendor-manifest.json` — schema for vendor registration
- `examples/` — sample vendor manifests
- `docs/` — protocol documentation

## Status

v0.1 — draft spec. Feedback welcome via issues.

## How it works

User → Agent → ASHRE Registry → Vendor MCP Servers → HTTP 402 → x402 Payment → Purchase Confirmed
