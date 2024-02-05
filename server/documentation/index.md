# Documentation

Welcome to the bio.tools linter documentation.

## API

This website uses an [API](https://en.wikipedia.org/wiki/API) exposed by the server, that is publicly available.
To see the automatically generated documentation of the API, see [this link](/api/documentation).

## Monitoring

This server runs an instance of [Monitoror](https://monitoror.com/) for status monitoring. Is it available publicly at [this link](/dash/).

## Error types

### EDAM INPUT DISCREPANCY

*see [source code](https://github.com/3top1a/biotools-linter/blob/main/linter/rules/edam.py###L194)*

This error is returned when a tool is annotated with an EDAM operation which has a `has_input` restriction, however the value (operation input) of that restriction in not present in the tool's annotation.

For example, the [Visualisation](https://edamontology.github.io/edam-browser/###operation_0337) operation has a `has_input` restriction of an [Image](https://edamontology.github.io/edam-browser/###http://edamontology.org/data_2968) data type. This error is returned when the `Image` input data type is not present in the tools annotations.
### EDAM INVALID

*see [source code](https://github.com/3top1a/biotools-linter/blob/main/linter/rules/edam.py###L80)*

This error is returned when a tool is clasified with an EDAM term which could not be found in the EDAM ontology.
Such a case is rare as the bio.tools website checks for invalid classification, but may happen in aggregated data.
### EDAM NOT RECOMMENDED

*see [source code](https://github.com/3top1a/biotools-linter/blob/main/linter/rules/edam.py###L73)*

This error is returned when a tool is clasified with an EDAM term which is marked as not recommended for annotation.
### EDAM OBSOLETE

*see [source code](https://github.com/3top1a/biotools-linter/blob/main/linter/rules/edam.py###L66)*

This error is returned when a tool is clasified with an EDAM term which is marked as [obsolete](https://edamontologydocs.readthedocs.io/en/latest/developers_guide.html?highlight=obsolete###deprecating-concepts).
### EDAM OUTPUT DISCREPANCY

*see [source code](https://github.com/3top1a/biotools-linter/blob/main/linter/rules/edam.py###L204)*

This error is returned when a tool is annotated with an EDAM operation which has a `has_output` restriction, however the value (operation output) of that restriction in not present in the tool's annotation.

For example, the [Visualisation](https://edamontology.github.io/edam-browser/###operation_0337) operation has a `has_output` restriction of an [Image](https://edamontology.github.io/edam-browser/###http://edamontology.org/data_2968) data type. This error is returned when the `Image` output data type is not present in the tools annotations.
### EDAM TOPIC DISCREPANCY

*see [source code](https://github.com/3top1a/biotools-linter/blob/main/linter/rules/edam.py###L168)*

This error is returned when a tool is annotated with an EDAM term which has a `has_topic` restriction, however the value (topic) of that restriction in not present in the tool's annotation.

For example, the [Structure analysis](https://edamontology.github.io/edam-browser/###operation_2480) operation has a `has_topic` restriction of the [Structure analysis](https://edamontology.github.io/edam-browser/###http://edamontology.org/topic_0081) topic. This error is returned when the `Structure analysis` topic is not present in the tools annotations.
### PMID, PMCID and DOI conversion

*see [source code](https://github.com/3top1a/biotools-linter/blob/main/linter/rules/publications.py)*

These errors occur when an article has more digital identifiers than it is assigned. For example, if a paper has both a DOI and a PMID, but only a DOI is assigned, the linter will show a `DOI_BUT_NOT_PMID` error.
This is checked using the [NCBI AnyID Converter API](https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/).
### URL BAD STATUS

*see [source code](https://github.com/3top1a/biotools-linter/blob/main/linter/rules/url.py###L85)*

This error occurs when a website doesn't return a [status code](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status) that signifies success, such as a 404 or 403.
### URL TIMEOUT

*see [source code](https://github.com/3top1a/biotools-linter/blob/main/linter/rules/url.py###L145)*

This error occurs when the linter tries to connect to a website but is unsuccessful. This signifies a server failure.
### URL INVALID

*see [source code](https://github.com/3top1a/biotools-linter/blob/main/linter/rules/url.py###L60)*

This error occurs when a URL could not be parsed, for example because it contains invisible Unicode characters.
For more information, look up a Unicode invisible character checker, such as [this](https://www.soscisurvey.de/tools/view-chars.php).
### URL LINTER

*see [source code](https://github.com/3top1a/biotools-linter/blob/main/linter/rules/url.py###L152)*

This error is returned when the linter encounters an error it was not programmed to handle. Such cases are rare and should be fixed.
### URL NO SSL

*see [source code](https://github.com/3top1a/biotools-linter/blob/main/linter/rules/url.py###L101)*

This error occurs when a website does not use the [Transport Layer Security](https://developer.mozilla.org/en-US/docs/Glossary/TLS) for secure communications. Such an error can only be fixed by the website administrator.
### URL PERMANENT REDIRECT

*see [source code](https://github.com/3top1a/biotools-linter/blob/main/linter/rules/url.py###L77)*

This error is returned when a website returned [a redirection](https://developer.mozilla.org/en-US/docs/Web/HTTP/Redirections),
that tells the browser to go somewhere else.
### URL TIMEOUT

*see [source code](https://github.com/3top1a/biotools-linter/blob/main/linter/rules/url.py###L136)*

This error occurs when a website does use the [Transport Layer Security](https://developer.mozilla.org/en-US/docs/Glossary/TLS) however the certificate is invalid or expired.
### URL TIMEOUT

*see [source code](https://github.com/3top1a/biotools-linter/blob/main/linter/rules/url.py###L119)*

This error occurs when a website takes over 30 seconds to respond. This signifies a server failure.
### URL TOO MANY REDIRECTS

*see [source code](https://github.com/3top1a/biotools-linter/blob/main/linter/rules/url.py###L128)*

This error is returned when a website returns an infinite redirection loop. Such an error may be an improperly configured server or DDoS mitigation flagging the linter as malicious.
### URL UNUSED SSL

*see [source code](https://github.com/3top1a/biotools-linter/blob/main/linter/rules/url.py###L109)*

This error occurs when a website does use the [Transport Layer Security](https://developer.mozilla.org/en-US/docs/Glossary/TLS) for secure communications, but the URL link does not signify it does by starting with `https://`.
