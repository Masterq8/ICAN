# Official QASPER evaluator

Source: https://github.com/allenai/qasper-led-baseline/blob/afd0fb96bf78ce8cd8157639c6f6a6995e4f9089/scripts/evaluator.py

Commit: afd0fb96bf78ce8cd8157639c6f6a6995e4f9089 (retrieved 2026-09-17).

Apache-2.0; LICENSE is retained from the same commit. evaluator.py is vendored verbatim apart from LF / final-newline normalization. Do not reformat it. We reuse its evaluate function after adapting our isolated annotations to its expected answer/evidence shape. Evaluation data never enters generation prompts.

Normalized evaluator SHA-256: 781aba7cd8e524bef4f0a1b4bf3504e5b02cb1d8d5bf32a8f0a89dfa83e86bfe.
