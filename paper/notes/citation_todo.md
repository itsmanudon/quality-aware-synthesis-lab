# Citation verification ledger

| Topic or intended statement | Candidate source | Verification state | Required action |
| --- | --- | --- | --- |
| CTGAN and conditional tabular GANs | Xu et al. (2019), NeurIPS | VERIFIED: official NeurIPS page | None for v0.1 |
| GReaT | Borisov et al., arXiv:2210.06280 | VERIFIED as arXiv preprint; ICLR publication metadata not encoded | Verify the primary ICLR record before changing publication status |
| REaLTabFormer | Solatorio and Dupriez, arXiv:2302.02041 | VERIFIED as arXiv preprint | Verify whether a later archival version should replace the preprint |
| TabDDPM | Kotelnikov et al. (2023), PMLR 202 | VERIFIED: official PMLR page | None for v0.1 |
| TabSyn | Zhang et al. (2024), ICLR | VERIFIED: official ICLR paper/PDF and OpenReview identifier | None for v0.1 |
| EPIC | Kim et al. (2024), NeurIPS | VERIFIED: official NeurIPS page and DOI | None for v0.1 |
| Constrained tabular generation | Stoian et al. (2024), ICLR | VERIFIED: official ICLR page | None for v0.1 |
| Alpha-precision, beta-recall, and authenticity | Alaa et al. (2022), PMLR 162 | VERIFIED: official PMLR page | None for v0.1 |
| LLM synthetic-data workflow survey | Long et al. (2024), ACL Findings | VERIFIED: ACL Anthology and DOI | None for v0.1 |
| Controlled LM-generator evaluation | Kim et al. (2025), ACL | VERIFIED: ACL Anthology and DOI | None for v0.1 |
| LLM-as-a-judge limitations | Zheng et al. (2023), NeurIPS | VERIFIED: official NeurIPS page and DOI | Keep claims limited to the evaluated chat-assistant setting |
| Sampling-based self-checking | Manakul et al. (2023), EMNLP | VERIFIED: ACL Anthology and DOI | Do not generalize factuality results to tabular validity |
| Iterative self-refinement | Madaan et al. (2023), NeurIPS | VERIFIED: official NeurIPS page | Do not imply localized tabular repair |
| Chain-of-Verification | Dhuliawala et al. (2024), ACL Findings | VERIFIED: ACL Anthology and DOI | Do not imply applicability to tabular repair without evaluation |
| Confidence calibration | Guo et al. (2017), PMLR 70 | VERIFIED: official PMLR page | Use only for general calibration motivation |
| Conformal risk control | Angelopoulos et al., arXiv:2208.02814 | VERIFIED as arXiv preprint | Verify archival publication status before changing the entry |
| Tool-interactive self-correction | Gou et al., CRITIC | UNRESOLVED: primary OpenReview page blocked by browser challenge | Do not cite in v0.1; verify the primary record manually |
| Placeholder repository notes | `literature/notes/` files without a populated `Verified bibliography` field | EXCLUDED | Verify the original paper before adding any citation or claim |

## Repository-note follow-up

The following local notes still have blank placeholder bibliography fields and
must not be treated as independently verified: `qa02`--`qa04`, `qa06`--`qa11`,
`qa15`--`qa26`, and `qa28`--`qa34`. Primary web records were used to verify
GReaT, REaLTabFormer, CTGAN, TabDDPM, and TabSyn for this manuscript, but their
corresponding repository notes should still be backfilled in a separate
literature-maintenance task. `qa23` (CRITIC) remains excluded from the paper.
