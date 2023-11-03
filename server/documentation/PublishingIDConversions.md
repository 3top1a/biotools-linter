# PMID, PMCID and DOI conversion errors
_see [source code](https://github.com/3top1a/biotools-linter/blob/main/linter/rules/publications.py)_

These errors occur when an article has more digital identifiers than it is assigned. For example, if a paper has both a DOI and a PMID, but only a DOI is assigned, the linter will show a `DOI_BUT_NOT_PMID` error.
This is checked using the [NCBI AnyID Converter API](https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/).
