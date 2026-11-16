# Model selection for text extraction

Decision date: 2026-11-15. Status: provisional pilot choice. The original [development run](development_run.md) and a [frozen prompt comparison](prompt_comparison.md) are complete. The latter uses 30 development reports and two paired rounds on 20 synthetic held-out reports. It reveals temporal gains, per-case regressions, and a shared normalization defect. No comparison against another model or claim of clinical validity has been established.

## Task fit

The model extracts short English reports about nausea and vomiting. It must distinguish present, absent, hypothetical, and uncertain statements; retain unknown values; extract exact supporting quotes; and separate episode counts from severity scores and their time contexts. It does not diagnose patients or recommend treatment. Specialized medical knowledge, a very large context window, and autonomous tool use are not selection criteria for this prototype.

Schema-constrained JSON helps enforce output structure. It does not establish semantic correctness. Date arithmetic, questionnaire handling, source conflicts, correction links, and identifiers belong to code. Reference answers are never sent to the model.

## Candidate decision

| Candidate | Role and rationale | Limitation |
| --- | --- | --- |
| `gpt-5.4-mini-2026-03-17` | First cloud pilot. Supports Structured Outputs, a pinned snapshot, and reasoning effort `none`. A hosted model avoids local memory and deployment constraints. | Requires an API key and metered calls. Small synthetic evaluation shows unresolved errors; real-world accuracy and superiority over alternatives remain unknown. |
| Installed `llama3:8b` through local Ollama | Optional local baseline, with no API charge and local processing. | Installation proves availability, not suitability. The original model was released in April 2024; general benchmarks do not establish performance on our cases. |
| Qwen3-8B | A possible alternative if local deployment becomes a requirement. Its documented non-thinking mode makes a bounded extraction pilot possible. | Not installed or tested here. Neither a newer release nor its general benchmarks proves better task accuracy. |

The user has confirmed that cloud APIs are acceptable. GPT-5.4 mini is therefore the first **candidate to evaluate**, not a declared benchmark winner. We are not downloading additional local models or fine-tuning models in this milestone. The local adapter requires an explicit model argument and never selects an installed model automatically.

The choice is deliberately bounded: a supported, structured-output-capable model with a fixed version, manageable pilot cost, and no local hardware dependency. A larger model would be considered only after examining systematic errors; a smaller model would be considered if measured quality remains acceptable while reducing cost or latency. Changing a provider or a model must not silently change normalization or scoring rules.

## Cost and reproducibility

The official GPT-5.4 mini page lists $0.75 per million input tokens and $4.50 per million output tokens when checked on the decision date. For illustration, 10 reports using 3,000 input tokens and 500 output tokens each cost about **$0.045**, excluding retries, additional reasoning, and other charges. This is an estimate, not a measured bill; the real prompt includes the schema. Prices may change.

The pilot uses reasoning effort `none`, a 2,048 output-token cap per request, and no automatic retries. Retain the requested and returned model, prompt/schema hash, source hash, code hash, token usage when returned, elapsed time, exact assistant output, and failure status. OpenAI requests use `store=false`; this setting alone is not a claim of zero provider retention or compliance for real patient data. All current examples are synthetic.

## Evidence required before final adoption

1. Validate the input fixtures and run offline code tests.
2. Run the candidate on the 10 development reports and save actual outputs before evaluating them.
3. Report completion, symptom-claim precision/recall/F1, known-value accuracy by field, null overfill, assertion correctness, and issue detection. Inspect source-specific checks before reconciliation. See [evaluation.md](evaluation.md).
4. Review errors by cause: extraction, schema/provenance rejection, normalization, or reference ambiguity. Do not edit references merely to agree with a model.
5. Freeze the prompt and rules, then use separately authored and reviewed cases that were not used to tune them. Include negation, hypothetical statements, unknown counts, incompatible scores, multiple symptoms, and temporal ambiguity. Do not describe the current 10 examples as held-out accuracy.
6. Compare another candidate on the same frozen cases if the first has material errors or if deployment/cost requirements justify it. Publish actual quality, latency, and usage side by side before claiming superiority.

Offline unit-test success is evidence about program behavior. It is not an LLM accuracy result. Actual per-run numbers and limitations are preserved in the reports. The temporal prompt candidate remains experimental because improved aggregate date scores coexist with count-scope and provenance regressions; the baseline remains the default without being certified as error-free.

## Primary sources

- [OpenAI GPT-5.4 mini: features, snapshot, reasoning controls, and pricing](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Meta Llama 3 8B Instruct model card](https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct)
- [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
- [Qwen3 model release and thinking modes](https://qwenlm.github.io/blog/qwen3/)
