# biotools-linter
This is a rule-based checker for the [bio.tools](https://bio.tools/) database. The script searches the bio.tools API for a given tool name and checks various properties of the tool's JSON data, such as invalid URL links.

## Installation
1) Clone this git repository
    ```sh
    $ git clone https://github.com/3top1a/biotools-linter.git
    ```

2) Install dependencies
    ```sh
    $ pip install -r required.txt
    ```

## Usage
Run the CLI linter.

```sh
$ python linter/cli.py --threads 16 "MetExplore" -p 1
Search returned 1 results
Starting to lint MetExplore
https://metexplore.toulouse.inra.fr/metexplore-webservice-documentation/ in /documentation/2/url doesn't returns 200 (HTTP_OK)
```

You can also lint the entire bio.tools database

```sh
$ python linter/cli.py --threads 16 --lint-all
...
```

To send the results to a PostgreSQL database
```sh
$ export DATABASE_URL="postgres://username:passwd@IP/database"
$ python linter/cli.py --threads 16 "MetExplore" -p 1
Starting to lint MetExplore
https://metexplore.toulouse.inra.fr/metexplore-webservice-documentation/ in /documentation/2/url doesn't returns 200 (HTTP_OK)
Sending messages to database
```
The program will automatically create a new table called `messages_new` and fill data in.
After manual inspection, the table should be renamed to `messages` for the web server.

## Architecture
![Architecture drawing](architecture.drawio.svg)

## Disclaimer
This tool is meant to be a rule-based checker for bio.tools data and does not cover all possible aspects or validations that can be performed on the data. It should be used as an additional tool for evaluating the information retrieved from the bio.tools API.

Please use the tool responsibly and do not misuse or overwhelm the bio.tools API with excessive requests.

## Contribution



## License
This project is licensed under the MIT license.
