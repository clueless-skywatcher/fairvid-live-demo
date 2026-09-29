"""Generators that build a synthetic, fully labelled applicant cohort.

Three layers, from simplest to hardest:
  1. records   - the tabular applicant data (grades, scores, demographics)
  2. documents - diploma/transcript images built from those records
  3. answers   - interview answer transcripts, each tagged with a quality label

A cohort is assembled by `generate.py`.
"""
