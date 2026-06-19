# whereiput.it Inventory — Home Assistant integration

A Home Assistant **custom integration** for **[whereiput.it](https://whereiput.it)**: ask your
voice assistant *"where is the hammer?"* / *"gdzie jest młotek?"* and hear where the item lives
(its location and area). Search is **permission-scoped server-side** — Home Assistant only ever
sees items in areas your token can access. Your inventory is **never dumped into LLM context** and
items are **never registered as Home Assistant entities**: each surface fetches matching rows
on demand and discards them after answering.

Install it through **HACS** as a custom repository, then set it up entirely in the UI — no YAML,
no `secrets.yaml`, no third-party conversation component.

## Install via HACS (custom repository)

1. In Home Assistant, open **HACS**.
2. Top-right **⋮ → Custom repositories**.
3. Add the repository URL `https://github.com/golem15com/ha-inventory-addon` with
   **Category: `Integration`**, then click **Add**.
4. Find **whereiput.it Inventory** in the list, open it, and click **Download**.
5. **Restart Home Assistant** when prompted.

> Requires Home Assistant Core **2026.6** or newer (the LLM Tools API floor is 2024.6, but this
> integration is developed and tested against 2026.6).

## Mint a read token

The integration authenticates with a personal **read** API token.

1. Open <https://whereiput.it/settings?tab=integrations> (the SPA / token-minting UI lives on the
   **apex** `whereiput.it`).
2. Create a token: name it `Home Assistant`, **scope `read`** — voice search never needs
   write or AI scope.
3. Copy the `inv_…` secret. It is shown **only once**.

> **Two hosts, by design.** You *mint* the token on the apex `whereiput.it`, but the integration
> *talks to* the token API on **`api.whereiput.it`** — that host is prefilled for you in the next
> step. Make sure your Home Assistant host can reach `https://api.whereiput.it` (outbound 443).

## Set it up

1. **Settings → Devices & Services → Add Integration**, search for **"whereiput.it Inventory"**.
2. The **Base URL** is prefilled to `https://api.whereiput.it` (edit it only if you self-host
   the server).
3. Paste your **read** token.
4. Submit. The connection is **validated on connect** — the entry is created only after one live
   test search succeeds. A bad token is rejected with *"Invalid token."*; an unreachable server
   with *"Could not reach the server."*

No `secrets.yaml`, no YAML editing. You can add **multiple entries** (e.g. the hosted
`whereiput.it` plus your own self-hosted server, or two accounts).

## How you search

The integration exposes **three native surfaces**, all backed by the same scoped search API:

- **LLM tool — `search_inventory`** (agent-agnostic): any conversation agent you use (built-in
  Assist, OpenAI, Google, Ollama, …) can call `search_inventory` on demand. Only the tool *spec*
  sits in the agent's context — item rows are fetched per call and discarded.
- **Offline conversation agent** (no LLM, instant): a built-in **ConversationEntity** that
  recognizes EN + PL *"where is X"* / *"gdzie jest X"* sentences locally and answers with a terse
  *name — location, area*. Select **"whereiput.it Inventory"** as your Assist pipeline's
  conversation agent (Settings → Voice assistants → your pipeline → Conversation agent) to use it.
- **Service / action — `whereiput_inventory.search`**: callable from automations and scripts.
  It returns **structured response data** (`matches[]` with `name`, `location`, `area`,
  `quantity`) so dashboards, templates, and automations can consume the results — not just a
  spoken phrase.

## Optional: limit to areas

By default the integration searches every area your token can access (server-side scope is the
boundary). To narrow further, open the integration's **Configure** (options flow) and pick one or
more areas — the picker is populated from your accessible areas. This only **narrows** results; it
can never widen scope beyond what the token allows.

## Migrating from the old config package

Earlier versions of this repo shipped a manual HA *config package* (hand-copied YAML +
`secrets.yaml`, tied to `extended_openai_conversation`). Those files are archived under
[`legacy/`](legacy/README.md) for anyone mid-migration — see that note for how to remove the old
pieces. **The integration is the single supported path going forward.**

## Verify

1. **API smoke test** (no Home Assistant needed) — confirms the token + endpoint are live:
   ```bash
   curl -H "Authorization: Bearer inv_<your_read_token>" \
     "https://api.whereiput.it/api/v1/inventory/items/search?q=mlotek"
   ```
   Expect JSON with `data[].location.name` and `data[].area.name`.
2. **Service** — in Home Assistant, **Developer Tools → Actions**, choose
   `whereiput_inventory.search`, set `q: młotek`, and **Perform action**. Confirm the response
   shows `matches` with `name` / `location` / `area` / `quantity`.
3. **Voice / offline** — select the **"whereiput.it Inventory"** conversation agent in an Assist
   pipeline and ask *"gdzie jest młotek?"* / *"where is the hammer?"*. Confirm a terse
   location + area answer.

## Notes

- **Read-only by design.** A `read`-scoped token cannot create, update, or delete anything, so the
  voice path is safe even when a query is mis-recognized.
- **Polish inflection** ("młotek" vs "młotka") may not match a stored name exactly; the backend
  uses Typesense typo-tolerant fuzzy search, which absorbs most of it.
- **Privacy.** Inventory is never placed in any LLM prompt context and items are never exposed as
  Home Assistant entities. Each surface fetches the minimal matching rows per call and returns
  only `name`, `location`, `area`, and `quantity`.
