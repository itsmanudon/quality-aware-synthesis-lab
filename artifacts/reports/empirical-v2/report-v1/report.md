# RC-QASyn empirical evidence v2

## Completed evidence

Frozen protocol: 3012014bae93ba81487eadaa9dfb4f7eb57b68d30d84fbaf1bf080e83d2eca43
Historical replay: 138 rows, all match: True.
Utility rows: 894; status counts: {'ok': 678, 'unavailable': 216}.
Fresh split populations: 15.
Bootstrap endpoint intervals: 216; paired difference intervals: 168.

## Five-split logistic results

| Dataset | Method | Completed | F1 mean | F1 SD | AP mean | AP SD |
|---|---|---:|---:|---:|---:|---:|
|Abalone19|CLASS_WEIGHTED_LR|5|0.051|0.009|0.045|0.014|
|Abalone19|REAL_TRAIN|5|0.000|0.000|0.042|0.015|
|Abalone19|RandomOverSampler+b|5|0.000|0.000|0.040|0.014|
|Abalone19|SMOTENC+b|5|0.000|0.000|0.041|0.013|
|Abalone19|combined/quality-coverage|5|0.000|0.000|0.044|0.011|
|Abalone19|combined/random|5|0.000|0.000|0.047|0.016|
|Abalone19|schema/random|5|0.000|0.000|0.041|0.012|
|Ecoli4|CLASS_WEIGHTED_LR|5|0.695|0.117|0.923|0.053|
|Ecoli4|REAL_TRAIN|5|0.848|0.119|0.944|0.058|
|Ecoli4|RandomOverSampler+b|5|0.745|0.177|0.908|0.055|
|Ecoli4|SMOTE+b|5|0.758|0.166|0.944|0.058|
|Ecoli4|combined/quality-coverage|5|0.758|0.166|0.934|0.050|
|Ecoli4|combined/random|5|0.758|0.166|0.934|0.050|
|Ecoli4|schema/random|5|0.758|0.166|0.944|0.058|
|page-blocks0|CLASS_WEIGHTED_LR|5|0.708|0.029|0.788|0.024|
|page-blocks0|REAL_TRAIN|5|0.728|0.026|0.800|0.019|
|page-blocks0|RandomOverSampler+b|5|0.738|0.028|0.800|0.019|
|page-blocks0|SMOTE+b|5|0.736|0.033|0.800|0.019|
|page-blocks0|combined/quality-coverage|5|0.738|0.028|0.800|0.020|
|page-blocks0|combined/random|5|0.741|0.027|0.799|0.019|
|page-blocks0|schema/random|5|0.736|0.030|0.800|0.019|

## Exploratory findings and unavailable comparisons

Historical TEST reuse and value overlap preclude untouched-confirmatory interpretation.
Offline minority-only pools make pure TSTR unavailable by construction.
page-blocks0 replication uses ROS and creates no novel support; SMOTE numeric baseline is not integer-coerced.
Classical training baselines and candidate curation answer different questions.
Bootstrap is conditional on observed class counts, not independent split uncertainty.
Admission ablations change eligibility; repair comparisons change pool and selection together.

## Pending scientific decisions

Author/affiliation/CRediT/funding/ethics and venue declarations; final scientific acceptance.
Human annotation and validity calibration are outside this paper's active scope.
