# Model selection for text extraction

Initial decision: 2026-11-15. Current status, 2026-11-17: `gpt-5.4-mini-2026-03-17` is the evaluated extraction model used by the all-text prototype. Its frozen run explicitly selected `prompts/extraction_nausea_grouping.txt`; the CLI's original v1 default is retained for historical reproducibility. No comparison against another model or claim of clinical validity has been established.

The current [71-report integration run](../results/longitudinal-text-extraction/README.md) and the separate [twenty-report frozen validation](../results/text-holdout-extraction/README.md) are complete. Earlier [development](development_run.md) and [v1/v2 prompt comparisons](prompt_comparison.md) remain historical evidence, including their regressions. Model selection and prompt selection are separate decisions.

## Task fit

The model extracts short English reports about nausea and vomiting. It must distinguish present, absent, hypothetical, and uncertain statements; retain unknown values; extract exact supporting quotes; and separate episode counts from severity scores and their time contexts. It does not diagnose patients or recommend treatment. Specialized medical knowledge, a very large context window, and autonomous tool use are not selection criteria for this prototype.

Schema-constrained JSON helps enforce output structure. It does not establish semantic correctness. Date arithmetic, questionnaire handling, source conflicts, correction links, and identifiers belong to code. Reference answers are never sent to the model.

## Candidate decision

| Candidate | Role and rationale | Limitation |
| --- | --- | --- |
| `gpt-5.4-mini-2026-03-17` | Evaluated cloud model used by the current prototype. Supports Structured Outputs, a pinned snapshot, and reasoning effort `none`. A hosted model avoids local memory and deployment constraints. | Requires an API key and metered calls. Small synthetic evaluation shows unresolved errors; real-world accuracy and superiority over alternatives remain unknown. |
| Installed `llama3:8b` through local Ollama | Optional local baseline, with no API charge and local processing. | Installation proves availability, not suitability. The original model was released in April 2024; general benchmarks do not establish performance on our cases. |
| Qwen3-8B | A possible alternative if local deployment becomes a requirement. Its documented non-thinking mode makes a bounded extraction pilot possible. | Not installed or tested here. Neither a newer release nor its general benchmarks proves better task accuracy. |

Cloud API use was explicitly approved for this project. GPT-5.4 mini was selected as a bounded candidate and retained for the prototype after the recorded evaluations; it is not a demonstrated cross-model benchmark winner. No alternative model was benchmarked and no model was fine-tuned. The local adapter requires an explicit model argument and never selects an installed model automatically.

The assessment brief suggests open-source tools and avoiding paid services. Using a proprietary, metered API departs from that recommendation and is an explicit trade-off for structured output, a fixed model version, and no local deployment requirement. The SQLite/Python dashboard rebuild uses saved actual model outputs and makes zero additional API calls. It runs offline after dependency installation; a fresh extraction still requires an API key and incurs usage charges. The unbenchmarked local adapter is an option for future comparison, not evidence that this project used an open-source extraction model.

The choice is deliberately bounded: a supported, structured-output-capable model with a fixed version, manageable pilot cost, and no local hardware dependency. A larger model would be considered only after examining systematic errors; a smaller model would be considered if measured quality remains acceptable while reducing cost or latency. Changing a provider or a model must not silently change normalization or scoring rules.

## Cost and reproducibility

The official GPT-5.4 mini page lists $0.75 per million input tokens and $4.50 per million output tokens when checked on the decision date. For illustration, 10 reports using 3,000 input tokens and 500 output tokens each cost about **$0.045**, excluding retries, additional reasoning, and other charges. This is an estimate, not a measured bill; the real prompt includes the schema. Prices may change.

The recorded pilot and current all-text extraction use reasoning effort `none`, a 2,048 output-token cap per request, and no automatic retries. Saved provenance includes the requested and returned model, prompt/schema hash, source hash, code hash, token usage when returned, elapsed time, exact assistant output, and failure status. OpenAI requests use `store=false`; this setting alone is not a claim of zero provider retention or compliance for real patient data. All current examples are synthetic.

## Evaluation completed and remaining limits

| Evidence | What it establishes and what it does not |
| --- | --- |
| Original ten-report run and historical prompt comparisons | Actual extraction behavior and known regressions, with saved outputs and unchanged scoring. Cases used to guide revisions become development/regression material. |
| Five-report pilot and ten-report text development set | Bounded prompt iterations and separate Python replays. Replaying old candidates measures a code change, not an improved model response. |
| Twenty-report frozen text validation | 20/20 processed and 18/20 fully correct; 339/341 candidate fields and 260/261 normalized core fields match. The unknown-count scope omission and morning/current context error remain documented. |
| Seventy-one-report all-text integration | All 137 reference observations and 1,233 core fields match. One extra supported raw candidate is merged by code; two literal time phrases differ. Known scenarios, repeated generated text, and a shared generation/extraction model family limit generalization. |
| Offline tests and SQLite/dashboard checks | Validation, normalization, correction, query, and display behavior. These checks are not additional measurements of LLM accuracy. |

Reference answers were authored from the source and contract, with separate agent review, before the corresponding extraction runs. They are AI-assisted synthetic labels, not independently annotated clinical ground truth. Evaluation distinguishes completion, claim detection, known and null field agreement, issue flags, and raw candidate structure; see [evaluation.md](evaluation.md). No model weights were trained: prompt revisions change instructions, Python replays change processing, and synthetic text generation creates evaluation material.

Historical v2/v3 results did not justify replacing the original default. The later nausea-grouping prompt is explicitly selected for the current all-text path and has its own frozen validation. These results do not erase earlier errors. Before claiming superiority over another model, compare quality, latency, and usage under the same frozen cases and rules. Broader adoption would require independent, more diverse validation beyond these synthetic sets.

## Primary sources

- [OpenAI GPT-5.4 mini: features, snapshot, reasoning controls, and pricing](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Meta Llama 3 8B Instruct model card](https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct)
- [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
- [Qwen3 model release and thinking modes](https://qwenlm.github.io/blog/qwen3/)
