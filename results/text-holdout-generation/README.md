# Twenty-report text generation record

This directory records **one text-generation request**, not an extraction run.
`gpt-5.4-mini-2026-03-17` produced twenty fictional report texts from the frozen
facts in `data/text_holdout/seeds.jsonl`. Usage: 5,751 input tokens, 709 output
tokens, 6,460 total. Reasoning effort was `none`; maximum output was 8,192 tokens.
There were no retries or discarded reports.

- `request.json`: exact generation payload, without authentication headers.
- `response.json`: complete API response.
- `generated_texts.jsonl`: twenty unedited report/text pairs.
- `manifest.json`: timestamps, hashes, usage, and status at generation time.

The generation-time manifest says semantic review is pending because it is an
unaltered snapshot. The completed [preparation review](../../data/text_holdout/review.md)
documents the later review and eight pre-extraction edits; twelve texts remain
verbatim. No numeric seed facts changed. Final sources and references are in
[`data/text_holdout/`](../../data/text_holdout/README.md).

No extraction, training, or fine-tuning requests were made for these cases.
