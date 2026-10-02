# Authorised mapping replacement and recovery

Only marketer or full/data_scientist expose `set_campaign_mapping`; reviewer stops
and uses a separately configured full connection if the user requests authoring.
Prerequisites: explicit user intent, exact model channel keys, and the COMPLETE map
to retain. Inspect `list_campaigns` and selected model evidence first when identity is unknown.

The call replaces all rows. Each row has platform, exactly one of campaign_id or
name_pattern, channel and optional valid_from/valid_to. Keep every approved existing
row. Conflicting/date-overlapping rows or unknown channels refuse without saving.
The response's drift warnings may accompany a saved map; warnings do not prove refusal.
Read facts afterwards to inspect declared assignments, preserving unmapped rows.

An uncertain transport response does not establish whether replacement saved. The
server sends one write attempt, never an automatic retry. Inspect campaign facts and
hand off for authoritative app/map reconciliation before any further replacement.
Do not reconstruct a complete map from partial listing rows or replay the write blindly.
See section=mapping-examples for exact synthetic calls and a timeout recovery path.
