# Vendored schema provenance

`resume.schema.json` is a verbatim copy of the JSON Resume schema, vendored so that validation is
hermetic and works offline.

| | |
|---|---|
| Upstream | https://github.com/jsonresume/jsonresume.org/tree/master/packages/schema |
| Exact file | `packages/schema/schema.json` |
| Pinned commit | `d8ebc8c816ae15db10f40e0fefaf4c935e025ea1` (2026-07-16) |
| Draft | JSON Schema draft-07 |

Pinned at that commit deliberately: it is the commit that made the schema draft-07 compliant
(`fix(schema): make schema.json draft-07 compliant`). Before it, upstream declared draft-04, which
`Draft7Validator` would not have been the right validator for.

## Refreshing

```sh
curl -sSL -o schema/resume.schema.json \
  https://raw.githubusercontent.com/jsonresume/jsonresume.org/<COMMIT>/packages/schema/schema.json
```

Then update the commit above, and run `uv run pytest` — `tests/test_validate.py` will tell you
whether `resume.json` still satisfies the new schema.
