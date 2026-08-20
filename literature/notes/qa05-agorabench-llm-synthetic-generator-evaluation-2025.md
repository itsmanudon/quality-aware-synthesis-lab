# Literature note

- Source PDF: `literature/papers/qa05-agorabench-llm-synthetic-generator-evaluation-2025.pdf`
- Verified bibliography: Seungone Kim, Juyoung Suk, Xiang Yue, Vijay Viswanathan, Seongyun Lee, Yizhong Wang, Kiril Gashteovski, Carolin Lawrence, Sean Welleck, and Graham Neubig. “Evaluating Language Models as Synthetic Data Generators.” Proceedings of ACL 2025 (Volume 1), pp. 6385–6403, July 2025. Primary: https://aclanthology.org/2025.acl-long.320/ (PDF: https://aclanthology.org/2025.acl-long.320.pdf).
- Central idea: AGORA BENCH standardizes comparisons of LMs as data generators across three domains and three generation methods. Within each setting it fixes the seed data, meta-prompt, number of instances, student model, and evaluation while varying the generator (pp. 6385–6387).
- Datasets / metrics: math, instruction-following, and code settings; 1.26M generated instances and 99 student models. The headline downstream metric is Performance Gap Recovered; intrinsic measures include response quality, perplexity, instruction difficulty, and diversity (pp. 6385–6387, 6391–6392).
- Limitations: experiments primarily use Llama-3.1-8B as the student and do not establish behavior beyond 10K generated instances; some intrinsic metrics depend on base architecture and API cost constrained coverage (p. 6392).
- Pipeline stage: controlled generator benchmarking and intrinsic/downstream evaluation.
- M1 relevance: enforce strict pairing: one raw call pool, identical candidate IDs, split, prompt, requested count, and metrics for B1/B2/B3; keep generator and judge configurations independently selectable and record calls/tokens/latency.
- Useful pages / figures: Fig. 1 (p. 6386) controlled-vs-conventional comparison; Sec. 2 (pp. 6386–6387) generator formalization; Fig. 4–6 and Sec. 5 (pp. 6391–6392) intrinsic metrics and limitations; conclusion (p. 6392).
- Baseline implication: static configuration and resolved artifacts matter more than a nominal model name; report cost and utility without claiming generator ranking from a tiny replay fixture.
- What this changes in our repo: the experiment config resolves all generator/judge settings, batch size, seed, prompt hash, metrics, and artifacts; replay runs the same architecture and shared raw pool offline.
