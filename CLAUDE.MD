# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is ASHRE

ASHRE (Agent Shopping Registry) is an open specification for agent-native commerce discovery. It defines:
- How vendors expose products/services as MCP servers
- How agents discover verified vendors at runtime
- How payments are routed via the x402 protocol

ASHRE is agent-agnostic (works with Claude, GPT, or any HTTP-capable agent) and is a commerce-specific sub-registry on top of the MCP registry ecosystem — a lean alternative to SAP/Shopify registries. Open source spec; hosted service is the business model. Domain: ashre.dev, GitHub org: ashre-dev.

## Flow

```
User → Agent → ASHRE Registry → Vendor MCP Servers → HTTP 402 → x402 Payment → Purchase Confirmed
```

1. Agent queries ASHRE registry for matching vendors
2. ASHRE returns verified vendor MCP endpoints
3. Agent calls all vendors in parallel
4. Vendor returns HTTP 402 (payment required, e.g. 0.05 USDC)
5. Agent pays via x402, vendor unlocks catalog
6. Agent reasons over results, picks best match, executes purchase

## Tech Stack

- **Python** + **FastAPI** — vendor server and registry API
- **MCP protocol** — vendor server transport
- **x402** — payment protocol (mock first, real Base L2 later)
- **Anthropic SDK** — buying agent (Claude)
- **Pytest** — testing
- **PyPI** — SDK publishing target (`pip install ashre`)

## Repo Structure

- `vendor-manifest.json` — core spec schema (v0.1.0); JSON Schema draft-07
- `examples/` — sample vendor manifests (e.g. `helsinki-maker-store.json`)
- `src/vendor_server/` — FastAPI vendor mock (to be built)
- `src/agent/` — buying agent script (to be built)
- `src/registry/` — registry API (to be built)
- `sdk/vendor/` and `sdk/agent/` — vendor and agent SDKs (to be built)
- `docs/` — protocol documentation (to be built)

## Vendor Manifest Schema

Required fields: `vendor_id` (lowercase-hyphenated), `name`, `category` (array), `mcp_endpoint` (URI), `payment` (x402, USDC, base or base-sepolia network), `schema_version`.

Optional: `description`, `ships_to` (ISO 3166-1 alpha-2 codes), `verified` (set by ASHRE, default false).

## Build Phases

| Phase | Target |
|-------|--------|
| 1 | Repo layout + `pyproject.toml` |
| 2 | Vendor server: `GET /catalog` (402-gated), `POST /pay` (mock token), `POST /buy` |
| 3 | Buying agent: handles 402 automatically, pays mock x402, queries catalog, executes purchase |
| 4 | Multi-vendor: Docker Compose + asyncio parallel queries |
| 5 | Real x402 on Base Sepolia testnet |
| 6 | Registry API: `POST /vendors/register`, `GET /vendors/discover`, `GET /vendors/{id}/health` |
| 7 | SDKs published to PyPI |

## Key Decisions

- ASHRE is not in the payment flow — it is a discovery and trust layer only
- Start with mock x402, graduate to real Base Sepolia testnet, then mainnet
- Agent-agnostic: no tight coupling to any specific agent runtime