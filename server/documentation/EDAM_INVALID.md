# EDAM INVALID error
*see [source code](https://github.com/3top1a/biotools-linter/blob/main/linter/rules/edam.py#L80)*

This error is returned when a tool is clasified with an EDAM term which could not be found in the EDAM ontology.
Such a case is rare as the bio.tools website checks for invalid classification, but may happen in aggregated data.
