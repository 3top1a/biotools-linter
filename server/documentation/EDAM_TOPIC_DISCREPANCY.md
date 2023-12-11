# EDAM TOPIC DISCREPANCY error

*see [source code](https://github.com/3top1a/biotools-linter/blob/main/linter/rules/edam.py#L168)*

This error is returned when a tool is annotated with an EDAM term which has a `has_topic` restriction, however the value (topic) of that restriction in not present in the tool's annotation.

For example, the [Structure analysis](https://edamontology.github.io/edam-browser/#operation_2480) operation has a `has_topic` restriction of the [Structure analysis](https://edamontology.github.io/edam-browser/#http://edamontology.org/topic_0081) topic. This error is returned when the `Structure analysis` topic is not present in the tools annotations.
