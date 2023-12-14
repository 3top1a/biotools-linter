# Development info

## Link icons

Links should have appropriate icons under a appropriate license, for example from https://www.svgrepo.com.

## Adding new rules

All rules should be in `linter/rules/` and categorized into separate files.
They should also have unique English names (e.g. `URL_NO_SSL`), a severity (see message.py) and text that should include the most helpful information.

Here are all other places the error needs to be places in:
- `statistics.py` - Add the error code at line 15
- `api.rs` - Add the error code at line 29 and increment the number
- `test_lint.py` - Add a test, if possible
- `server/docs/` - Write documentation
- `server/templates/index.html` line 150
