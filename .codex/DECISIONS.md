# Decisions
- Keep approved section-aware parent–child chunking. Search children, return matching child plus unique parent context.
- Use pinned local multilingual-e5-small on CPU; no paid APIs or model fallback.
- Use actual MongoDB vector capability if verified. Report cosine separately from rank-fusion scores.
- Evaluation labels must reference real source IDs; source currency and label review remain explicit.
