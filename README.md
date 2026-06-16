# ha-inventory-addon

Home Assistant integration for **[whereiput.it](https://whereiput.it)** — ask your voice
assistant *"Minigolem, gdzie jest młotek?"* and hear where the item lives (location + area),
backed by the whereiput.it inventory search.

Despite the repo name, **no Home Assistant add-on / Docker container is required.** This is a
drop-in **config package**: a GPT-4o function plus an optional local intent. Everything reuses
the existing scoped search API on the whereiput.it side — nothing new is deployed there.

## How it works (and why it won't overflow the Assist pipeline)

The whole inventory is **never** put into the LLM prompt and items are **not** registered as HA
entities. Two paths, both keep inventory data out of context:

| Path | When it runs | What's in context |
| --- | --- | --- |
| **GPT-4o function** (primary) | Your `extended_openai_conversation` agent calls `search_inventory(q)` when asked | Only the function *spec* (~a few hundred tokens). Item rows are fetched on demand and discarded after the answer. |
| **Local intent** (optional) | HA's built-in intent recognizer matches `gdzie jest {item}` | No LLM at all — a direct REST call, instant and offline. |

Both call the same endpoint (note the **`api.`** host — the token API is served on
`api.whereiput.it`, while the SPA / token-minting UI lives on the apex `whereiput.it`):

```
GET https://api.whereiput.it/api/v1/inventory/items/search?q=<term>
Authorization: Bearer inv_<token>
```

which returns `{ "data": [ { "name": …, "location": { "name": … }, "area": { "name": … }, … } ] }`
— permission-scoped server-side, so HA only ever sees areas the token's owner can access.

## Prerequisites

- Home Assistant (tested target: Supervised, Core 2026.6) with an Assist pipeline.
- For the primary path: the **Extended OpenAI Conversation** custom component (the "GPT-4o
  Minigolem" agent) — already in use on this setup.
- The HA host must reach `https://api.whereiput.it` (port 443 outbound) — that's the host that
  serves the token API. (The apex `whereiput.it` only needs to be reachable from your browser
  to mint the token.)

## Step 1 — Mint a read-only API token

1. Open <https://whereiput.it/settings?tab=integrations>.
2. Create a token: name `Home Assistant`, **scope `read`** (voice search never needs write/ai).
3. Copy the `inv_…` secret — it's shown only once.

## Step 2 — Primary path: add the GPT-4o function

1. Open the function definition in [`functions/search_inventory.yaml`](functions/search_inventory.yaml).
2. Use **Variant A** (`rest`): paste your token into the `Authorization` header line.
3. In HA: **Settings → Devices & Services → Extended OpenAI Conversation → the "GPT-4o
   Minigolem" entry → Configure**, and paste the function into the **Functions** textarea
   (append it to any existing functions). Save.

> The Polish `description` in the spec is what tells GPT-4o *when* to call the function
> ("gdzie jest / gdzie mam / znajdź …"). The model phrases the spoken answer itself.

If you'd rather keep the token out of the integration options, use **Variant B** (`script`)
instead and also install the package from Step 3 (it defines the `rest_command` that holds the
token via `secrets.yaml`).

## Step 3 — Optional: local no-LLM fast-path

For an instant, offline answer to the exact phrasing (and to feed Variant B above):

1. Add the token to HA `secrets.yaml` (see [`secrets.example.yaml`](secrets.example.yaml)).
2. Copy `packages/whereiput_inventory.yaml` → `<config>/packages/` and enable packages in
   `configuration.yaml`:
   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```
3. Copy `custom_sentences/pl/inventory.yaml` → `<config>/custom_sentences/pl/`.
4. Restart Home Assistant.

> **Routing caveat:** the Minigolem pipeline's agent is GPT-4o, so the local intent only fires
> if that agent is set to try HA intents first, or if you test on the local
> "W pełni asystent lokalny" pipeline. If you only want the primary path, skip this step.

## Verify

1. **API smoke test** (no HA needed) — confirms the token + endpoint:
   ```bash
   curl -H "Authorization: Bearer inv_…" \
     "https://api.whereiput.it/api/v1/inventory/items/search?q=młotek"
   ```
   Expect a `data[].location.name` / `data[].area.name` in the JSON.
2. **Function** — in the GPT-4o agent (Assist debug or a chat), ask *"gdzie jest młotek?"*.
   Confirm it calls `search_inventory` and answers with the location + area in Polish.
3. **Voice** — full pipeline: wake word **"Minigolem"** → faster_whisper STT → GPT-4o →
   Piper Polish TTS.

## Notes

- **Polish inflection** ("młotek" vs "młotka") may not match a stored name exactly; the backend
  uses Typesense typo-tolerant fuzzy search, which absorbs most of it. Spot-check with your real
  item names and tune the synonyms / `per_page` if needed.
- **Read-only by design.** A `read`-scoped token cannot create, update, or delete anything, so
  the voice path is safe even if a query is mis-recognized.
- The MCP path (HA's native `mcp:` client) is intentionally **not** used here: HA's MCP client
  speaks SSE only, while the whereiput.it MCP server speaks Streamable HTTP — the GPT-4o
  function is the simpler fit for this setup.

## Files

```
functions/search_inventory.yaml      GPT-4o function spec (primary path) — paste into the agent
packages/whereiput_inventory.yaml    rest_command + local intent_script (optional / Variant B)
custom_sentences/pl/inventory.yaml   Polish "gdzie jest {item}" sentences (optional)
secrets.example.yaml                 token entry template for secrets.yaml
```
