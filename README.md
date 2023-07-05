# biotools-linter
This is a rule-based checker for the [bio.tools](https://bio.tools/) database. The script searches the bio.tools API for a given tool name and checks various properties of the tool's JSON data, such as invalid URL links.

## Instalation
1) Clone this git repository

2) Install dependencies
    ```
    $ pip install -r required.txt
    ```

## Usage
Run the CLI python script.
Web version coming later.

```sh
$ python main.py "MetExplore" -p 1
Search returned 1 results
Starting to lint MetExplore
https://metexplore.toulouse.inra.fr/metexplore-webservice-documentation/ in /documentation/2/url doesn't returns 200 (HTTP_OK)
```

## Architecture
![Architecture drawing](architecture.drawio.png)

## Disclaimer
This tool is meant to be a rule-based checker for bio.tools data and does not cover all possible aspects or validations that can be performed on the data. It should be used as an additional tool for evaluating the information retrieved from the bio.tools API.

Please use the tool responsibly and do not misuse or overwhelm the bio.tools API with excessive requests.

## License
This project is licensed under the MIT license.
