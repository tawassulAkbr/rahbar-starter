# Phase 4 root-cause note

1. Trace `phase4-abstention-sample` records an abstained answer with no retrieved chunks.
2. Its `filters` show the relevance floor was 0.6 and the retrieved list is empty.
3. Therefore no document version, citation, or chunk could support the question.
4. The response correctly set `answered_from_context` to false and returned no citations.
5. The trace alone identifies retrieval coverage, rather than generation, as the cause.
