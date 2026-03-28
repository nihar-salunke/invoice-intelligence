# Business Impact Model

## Problem

Indian banks process millions of tractor loan applications annually. Each application includes invoice documents that must be manually verified: extracting dealer information, checking tractor specifications, confirming signatures/stamps, and validating dealer legitimacy. This is slow, error-prone, and expensive.

## Current State (Manual Process)

| Metric | Value | Source/Assumption |
|--------|-------|-------------------|
| Tractor loans processed per year (large bank) | 200,000 | IDFC First Bank annual report estimates |
| Documents per loan requiring verification | 2-3 | Invoice + quotation + RC typically |
| Time per document (manual review) | 15-20 minutes | Industry benchmark for invoice verification |
| Cost per verification officer | INR 5,00,000/year | Average salary for document verification staff |
| Documents per officer per day | 25-30 | At ~20 min each in an 8-hour shift |
| Officers needed for 200K loans | 30-35 | ~500K documents / (27 docs/day x 250 working days) |
| Annual staffing cost | INR 1.5-1.75 Cr | 35 officers x INR 5L |
| Average turnaround time | 2-3 business days | Queue delays + manual processing |
| Error rate (missed discrepancies) | 5-8% | Industry average for manual document review |

## With Invoice Intelligence (AI Process)

| Metric | Value | Improvement |
|--------|-------|-------------|
| Time per document | 15-30 seconds | **97% faster** (from 20 min to 0.5 min) |
| Cost per document | INR 0.15 | Gemini API cost (~2 calls x $0.002) |
| Annual API cost for 500K documents | INR 7.5L | vs INR 1.5 Cr manual staffing |
| Turnaround time | Real-time | **From 2-3 days to instant** |
| Error rate | <2% | AI extraction + web verification cross-check |
| Documents needing human review | 15-25% | Only REVIEW/FAIL scores go to humans |

## Quantified Impact

### 1. Cost Reduction: INR 1.3+ Crore per year

```
Manual cost:        INR 1,50,00,000  (35 officers)
AI cost:            INR    7,50,000  (API + infrastructure)
                    ─────────────────
Annual savings:     INR 1,42,50,000  (~95% reduction)
```

### 2. Time Savings: 97% reduction in processing time

```
Manual:   20 minutes per document x 500,000 documents = 166,667 hours/year
AI:       0.5 minutes per document x 500,000 documents = 4,167 hours/year
                                                          ─────────────────
Hours saved:                                              162,500 hours/year
```

### 3. Faster Loan Disbursement

| Metric | Before | After |
|--------|--------|-------|
| Document verification turnaround | 2-3 days | Real-time |
| End-to-end loan processing | 7-10 days | 4-5 days |
| Customer drop-off due to delays | ~12% | ~4% |
| Additional loans closed per year | -- | ~16,000 |

At an average loan size of INR 6,00,000 and net interest margin of 3%:

```
Additional revenue from reduced drop-off:
16,000 loans x INR 6,00,000 x 3% NIM = INR 28.8 Cr additional interest income
```

### 4. Fraud Prevention

The Research Agent cross-references dealer names and HP specifications against the web. This catches:

- **Fake dealers** -- dealer name not found in any online listing
- **Inflated specifications** -- invoice claims 60 HP but the model is actually 42 HP
- **Price manipulation** -- cost significantly above market rate for the model

Assuming even 0.5% of applications involve document fraud at an average loan of INR 6L:

```
Fraud prevented: 200,000 loans x 0.5% x INR 6,00,000 = INR 6 Cr in prevented losses
```

### 5. Compliance and Audit

Every decision is logged in the audit trail. This provides:

- Full traceability for RBI audit requirements
- Automated compliance reporting
- Reduced regulatory risk

## Summary

| Impact Area | Annual Value |
|-------------|-------------|
| Staffing cost reduction | INR 1.4 Cr |
| Additional revenue (faster processing) | INR 28.8 Cr |
| Fraud prevention | INR 6 Cr |
| **Total quantifiable impact** | **INR 36+ Cr per year** |

## Assumptions

1. Bank processes ~200,000 tractor loans per year
2. Each loan has 2-3 documents requiring verification
3. Manual verification takes 15-20 minutes per document
4. Gemini 2.5 Flash costs ~$0.002 per document (2 API calls)
5. Average tractor loan size is INR 6,00,000
6. Customer drop-off rate reduces by ~8 percentage points with faster processing
7. Document fraud rate is conservatively estimated at 0.5%

All figures are back-of-envelope estimates based on publicly available industry data and can be refined with actual bank operations data.
