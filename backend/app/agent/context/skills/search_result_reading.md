Use this skill when runtime state includes `memory_snapshot.last_db_query`, `memory_snapshot.total`, or `memory_snapshot.shops_preview`.

Interpretation rules:
- `total` means matched shop count, not machine count.
- `shops_preview` is only a preview of current results; do not claim it is the full result set unless counts match.
- Prefer mentioning 1 to 3 shops by `name` plus `city_name` or `county_name`.
- If `last_db_query.sort_by=title_quantity`, rank shops by the summed `arcades[].quantity` for `sort_title_name`.
- If `total=0`, clearly say no matching shop was found and suggest another keyword or region.
- If the user asked for "most" or "least", mention the sort direction and the leading shop(s) when available.
