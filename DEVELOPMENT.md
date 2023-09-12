# Development info

## Link icons

Links should have appropriate icons under a appropriate license, for example from https://www.svgrepo.com.

## Adding new rules

All rules should be in `linter/rules/` and categorized into separate files.
They should also have unique English names (e.g. `URL_NO_SSL`), a severity (re: message.py) and text that should include the most helpful information.

Here are all other places the error needs to be places in:
- `statistics.py` - Around line 62, 77, 100
- `test_lint.py` - Add a test, if possible