# Design

Task 1 owns sitemap ingestion, article storage, keyword retrieval, source citations, and expert tasks. Task 2 and Task 3 call Task 1 over HTTP instead of importing its code.

```text
Official sitemap -> Task 1 crawler -> SQLite articles -> keyword retrieval
                                              -> model answer + source URLs
Task 2 Inbox Agent --------------------HTTP /ask
  classify -> draft -> human edits -> feedback/streak record
Task 3 Meeting-to-SOW ----------------HTTP /ask
  transcript -> scope/estimate -> proposal DB -> follow-up comparison -> human approval
```

Safety: restrict crawler URLs to the official host; treat page contents and emails as untrusted input; require evidence for product claims; request human review for refunds/complaints; never send emails; keep proposals pending until explicitly approved. Keyword retrieval is intentionally transparent but should be evaluated for recall before adding semantic/vector search.
