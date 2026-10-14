# UXR-02A Review and Status/Consent Spec

## G5 Review compact toolbar and states

**Toolbar:** labeled `NgÃ y há»c` input/Date Picker, `XoÃ¡ bá»™ lá»c` secondary action, and a queue summary badge. The real `noteDate` query contract is preserved; clearing the filter removes only that filter and retains route/history semantics.

| State | Visible treatment | Dominant action | Safety rule |
|---|---|---|---|
| EMPTY | exactly one queue-empty explanation in the main surface | `Tra tá»« má»›i` | no duplicate header/footer empty prose |
| LOADING | toolbar remains; per-surface skeleton geometry | none until data is authoritative | do not show zero queue |
| ERROR | affected surface alert with cause/retry | `Thá»­ láº¡i` when safe | do not turn storage/session errors into empty |
| SUBMITTING | pending label/live announcement, disabled duplicate rating | none | preserve in-flight operation state |
| UNKNOWN | orange/striped unknown panel, reconciliation copy | `Kiá»ƒm tra tráº¡ng thÃ¡i` | no success implication and no unsafe duplicate rating |

The live region can announce queue or reconciliation changes without adding a second visible explanatory surface. Full Flashcards/reveal/rating interaction remains UXR-05 ownership.

## G8 Status + Consent compact summary

The first surface is a two-column `StatusSummary` on desktop and a stacked summary on mobile:

1. **Local learning readiness:** `READY`, `DEGRADED`, `NOT_READY` or `UNKNOWN` with the local capabilities that remain usable.
2. **External AI readiness:** separate state; `UNKNOWN` or degraded AI never implies local learning is blocked.
3. **Active alerts:** critical privacy, consent and operation alerts remain outside disclosure.
4. **Consent entry:** visible `Quáº£n lÃ½ AI consent` link to `/status#ai-consent` with policy/grant/revoke wording owned by UXR-08.
5. **Recovery:** only a truthful retry/reconciliation/open-consent action for the current state.

### Secondary diagnostics

`Chi tiáº¿t nguá»“n & lÆ°u trá»¯`, `Kháº£ nÄƒng offline`, `Bridge diagnostics`, `Performance & runbook` are named disclosure groups. Their content remains keyboard/AT discoverable. Technical IDs, metrics and runbook detail are not in the first viewport unless an active alert requires them.

### Deep-link and scrolling behavior

`/status#ai-consent` focuses the consent heading after route render and scrolls the main region so the heading is visible below the 54px desktop or 58px mobile header. Collapsed disclosures stay collapsed unless the target is inside one; expanding preserves focus. On mobile, the drawer closes before consent focus and background interaction is not restored until the drawer is closed. This is a future implementation requirement, not proven by the static frame.

### Consent safety

Mockups never fabricate grant, revoke or provider request execution. Consent is fail-closed: absent, stale or unknown consent keeps AI actions unavailable and leaves local study paths open. Detailed consent interaction and copy remain UXR-08 ownership.

## Evidence

- [R1 empty desktop](assets/frames/R1-review-empty-1366x768-light.png)
- [R2 empty mobile](assets/frames/R2-review-empty-390x844-light.png)
- [R3 unknown/pending mobile](assets/frames/R3-review-unknown-pending-390x844-light.png)
- [S1 summary desktop](assets/frames/S1-status-consent-summary-1366x768-light.png)
- [S2 summary mobile](assets/frames/S2-status-consent-summary-390x844-light.png)
- [S3 degraded desktop](assets/frames/S3-status-degraded-1366x768-light.png)
