# EDAM OUTPUT DISCREPANCY error

*see [source code](https://github.com/3top1a/biotools-linter/blob/main/linter/rules/edam.py#L204)*

This error is returned when a tool is annotated with an EDAM operation which has a `has_output` restriction, however the value (operation output) of that restriction in not present in the tool's annotation.

For example, the [Visualisation](https://edamontology.github.io/edam-browser/#operation_0337) operation has a `has_output` restriction of an [Image](https://edamontology.github.io/edam-browser/#http://edamontology.org/data_2968) data type. This error is returned when the `Image` output data type is not present in the tools annotations.
