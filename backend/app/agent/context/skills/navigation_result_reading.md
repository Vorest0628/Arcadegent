Use this skill when runtime state includes `memory_snapshot.route`.

Interpretation rules:
- `distance_m` is route distance in meters.
- `duration_s` is route duration in seconds; convert it to approximate whole minutes for the reply.
- Mention the destination shop name when available from `memory_snapshot.shop` or `memory_snapshot.shops_preview`.
- Include `hint` only when it adds concrete value.
- If the route is missing but a shop is known, ask only for the missing navigation input instead of inventing a path.
