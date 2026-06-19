# Legacy config-package (archived)

These files are the OLD manual Home Assistant config-package path (hand-copied YAML +
a `secrets.yaml` token, tied to the third-party `extended_openai_conversation` component).
They are kept ONLY for anyone mid-migration. The supported, documented path is now the
HACS custom integration under `custom_components/whereiput_inventory/` — install it via HACS
and set it up in the UI.

## Migrating off the old path

1. Remove the `whereiput_inventory_token: "Bearer inv_..."` line from your HA `secrets.yaml`.
2. Delete `<config>/packages/whereiput_inventory.yaml` and the
   `<config>/custom_sentences/pl/inventory.yaml` copy.
3. Remove the pasted `search_inventory` function from your `extended_openai_conversation` agent.
4. Install the integration and add it via Settings → Devices & Services.

## Archived files

- `functions/search_inventory.yaml` — the old GPT-4o function spec pasted into the
  `extended_openai_conversation` agent (primary path).
- `packages/whereiput_inventory.yaml` — the `rest_command` + local `intent_script` config package
  (optional / Variant B fast-path).
- `custom_sentences/pl/inventory.yaml` — the Polish "gdzie jest {item}" wildcard sentences for the
  built-in intent recognizer.
- `secrets.example.yaml` — the `secrets.yaml` token-entry template (Bearer-prefixed read token).
