"""Unit tests. Use with pytest."""


import os
import subprocess
import time
import pytest


@pytest.mark.asyncio
async def test_session():
    import lib as lib
    from lib import flatten_json_to_single_dict
    import json

    s: lib.Session = lib.Session()
    import time

    assert not s.next_page_exists()
    assert not s.previous_page_exists()

    start_time = time.time()

    # Broad search
    s.clear_cache()
    s.search_api("e")
    assert s.get_total_tool_count() > 1
    assert s.next_page_exists()
    assert not s.previous_page_exists()
    last_json = s.json

    print(f"LIB - Broad: {time.time() - start_time}")
    start_time = time.time()

    # Broad search, page 10
    s.clear_cache()
    s.search_api("e", 10)
    assert s.get_total_tool_count() > 1
    assert s.next_page_exists()
    assert s.previous_page_exists()
    assert s.json != last_json

    print(f"LIB - Broad p10: {time.time() - start_time}")
    start_time = time.time()

    # Exact search
    s.clear_cache()
    s.search_api("msmc")
    assert s.get_total_tool_count() == 1
    assert not s.next_page_exists()
    assert not s.previous_page_exists()

    print(f"LIB - exact: {time.time() - start_time}")
    start_time = time.time()

    # Invalid search
    s.clear_cache()
    s.search_api("aaaaaaaaaaaaaaaaaaaaa")
    assert s.get_total_tool_count() == 0
    assert not s.next_page_exists()
    assert not s.previous_page_exists()

    print(f"LIB - Invalid: {time.time() - start_time}")
    start_time = time.time()

    # Multiple pages search
    s.clear_cache()
    s.search_api_multiple_pages("*", 1, 5 + 1)
    assert len(s.return_tool_list_json()) == 50

    print(f"LIB - Multiple pages 1: {time.time() - start_time}")
    start_time = time.time()

    s.clear_cache()
    s.search_api_multiple_pages("bioto", 1, 5 + 1)
    assert len(s.return_tool_list_json()) == 2

    print(f"LIB - Multiple pages 2: {time.time() - start_time}")
    start_time = time.time()

    s.clear_cache()
    s.search_api_exact_match("s")
    assert len(s.return_tool_list_json()) == 0
    s.search_api_exact_match("msmc")
    assert len(s.return_tool_list_json()) == 1

    print(f"LIB - Multiple pages 3: {time.time() - start_time}")
    start_time = time.time()

    s.clear_cache()
    for x in range(0, 2):
        s.search_api_multiple_pages("cli", x * 10 + 1, x * 10 + 10 + 1)
    assert len(s.return_tool_list_json()) > 10

    example_json = {
        "a": {
            "0": "1",
            "1": "8",
            "2": "42",
        },
        "the answer": "5",
        "list": ["1", "2", "3", "4", "5"],
    }
    example_output = {
        "//a/0": "1",
        "//a/1": "8",
        "//a/2": "42",
        "//the answer": "5",
        "//list/0": "1",
        "//list/1": "2",
        "//list/2": "3",
        "//list/3": "4",
        "//list/4": "5",
    }
    assert flatten_json_to_single_dict(example_json, "/", "/") == example_output

    tool_json = """
{
  "name": "test",
  "description": "test",
  "biotoolsID": "test",
  "biotoolsCURIE": "biotools:test",
  "documentation": [
    {
      "url": "https://httpbin.org/status/404"
    }
  ]
}
"""
    from queue import Queue

    q = Queue()
    await s.lint_specific_tool_json(json.loads(tool_json), q)
    assert q.get().code == "URL_BAD_STATUS"


@pytest.mark.asyncio
async def test_cli():
    import cli as cli

    # "end to end" CLI test, runs the CLI as if it was ran from the command line
    # Any use of certain tool names are only for testing purposes and not in bad faith
    assert await cli.main(["msmc"]) == 0
    assert await cli.main(["metexplore", "--no-color"]) == 0
    assert await cli.main(["metexplore", "--exit-on-error"]) == 254


# Test url.py
@pytest.mark.asyncio
async def test_urls():
    # Needs internet access
    # Also big props to https://httpbin.org, http://httpforever.com and https://httpstat.us

    import rules
    import time

    start_time = time.time()

    # Ok
    assert await rules.filter_url("test", "https://httpbin.org/status/200") is None

    print(f"URL - OK: {time.time() - start_time}")
    start_time = time.time()

    # Invalid URLs
    assert await rules.filter_url("test", "ftp://ftp.gnu.org/gnu/") is None
    assert await rules.filter_url("test", "test") is None

    print(f"URL - Invalid URLs: {time.time() - start_time}")
    start_time = time.time()

    # URL_INVALID
    assert (await rules.filter_url("url", "also test"))[0].code == "URL_INVALID"

    print(f"URL - URL_INVALID: {time.time() - start_time}")
    start_time = time.time()

    # URL_CONN_ERROR
    assert (
        await rules.filter_url(
            "url", "https://gsjdhfskjhfklajshdfkashdfkashdfklashdfjakhsdflkahsfd.sdfsdf"
        )
    )[0].code == "URL_CONN_ERROR"

    print(f"URL - URL_CONN_ERROR: {time.time() - start_time}")
    start_time = time.time()

    # URL_PERMANENT_REDIRECT
    assert (
        await rules.filter_url(
            "test",
            "https://httpbin.org/redirect-to?url=https%3A%2F%2Fwww.example.com&status_code=308",
        )
    )[0].code == "URL_PERMANENT_REDIRECT"

    print(f"URL - URL_PERMANENT_REDIRECT: {time.time() - start_time}")
    start_time = time.time()

    # URL_BAD_STATUS
    assert (await rules.filter_url("test", "https://httpbin.org/status/404"))[
        0
    ].code == "URL_BAD_STATUS"

    print(f"URL - URL_BAD_STATUS: {time.time() - start_time}")
    start_time = time.time()

    # URL_UNUSED_SSL
    assert (await rules.filter_url("test", "http://httpbin.org/status/202"))[
        0
    ].code == "URL_UNUSED_SSL"

    print(f"URL - URL_UNUSED_SSL: {time.time() - start_time}")
    start_time = time.time()

    # URL_NO_SSL
    # Takes extreme amount of time (33s), need to make it faster
    assert (await rules.filter_url("test", "http://httpforever.com/"))[
        0
    ].code == "URL_NO_SSL"

    print(f"URL - URL_NO_SSL: {time.time() - start_time}")
    start_time = time.time()

    # URL_TIMEOUT - down again?
    # assert ((
    #     await rules.filter_url("test", "https://httpstat.us/200?sleep=60000"))[0].code
    #     == "URL_TIMEOUT"
    # )

    print(f"URL - URL_TIMEOUT: {time.time() - start_time}")
    start_time = time.time()

    # URL_SSL_ERROR
    assert (await rules.filter_url("test", "https://expired.badssl.com/"))[
        0
    ].code == "URL_SSL_ERROR"

    print(f"URL - URL_SSL_ERROR: {time.time() - start_time}")


# Test messages.py
@pytest.mark.asyncio
async def test_messages():
    import rules
    from message import Message, Level
    from queue import Queue

    q = Queue()

    msg = Message(
        code="001", body="Test message", location="//name", level=Level.LinterError
    )
    assert msg.code == "001"
    assert msg.body == "Test message"
    assert msg.location == "//name"
    assert msg.level == Level.LinterError
    assert msg.tool is None  # Should be set in lib.py
    msg.print_message(q)
    assert q.get() == "None [001]: Test message"

    (await rules.filter_url("url", "also test"))[0].print_message(q)
    assert (
        q.get()
        == "None [URL_INVALID]: The URL also test at url could not be parsed, possibly due to invisible Unicode characters"
    )


@pytest.mark.asyncio
async def test_publications():
    from rules.publications import PublicationData, filter_pub
    import json

    # Test converter
    x1: PublicationData = await PublicationData.convert("10.1093/BIOINFORMATICS/BTAA581")
    assert x1
    assert x1.pmid == ["32573681"]
    assert x1.pmcid == ["PMC8034561"]

    x2: PublicationData = await PublicationData.convert("test")
    assert x2 == None

    x3: PublicationData = await PublicationData.convert("PMC8034561")
    assert x3
    assert x3.doi == ["10.1093/bioinformatics/btaa581"]
    assert x3.pmid == ["32573681"]

    x4 = await PublicationData.convert("")
    assert x4 is None

    x5 = await PublicationData.convert(None)
    assert x5 is None

    # Test x_BUT_NOT_y
    json_bad = """
    {
        "name": "test",
        "description": "test",
        "biotoolsID": "test",
        "biotoolsCURIE": "biotools:test",
        "publication": [
            {
                "doi": "10.1093/bioinformatics/btaa581",
                "pmid": null,
                "pmcid": null,
                "type": [
                    "Primary"
                ],
                "version": null,
                "note": null
            }
        ]
    }
    """
    output = await filter_pub(json.loads(json_bad))
    assert len(output) == 2
    assert output[1].code == "DOI_BUT_NOT_PMCID"
    assert output[0].code == "DOI_BUT_NOT_PMID"

    json_good = """
    {
        "name": "test",
        "description": "test",
        "biotoolsID": "test",
        "biotoolsCURIE": "biotools:test",
        "publication": [
            {
                "doi": "10.1093/bioinformatics/btaa581",
                "pmid": "32573681",
                "pmcid": "PMC8034561",
                "type": [
                    "Primary"
                ],
                "version": null,
                "note": null
            }
        ]
    }
    """
    output = await filter_pub(json.loads(json_good))
    assert output is None
    
    # Test DOI_DISCREPANCY, PMID_DISCREPANCY, PMCID_DISCREPANCY
    js = """
    {
        "name": "test",
        "description": "test",
        "biotoolsID": "test",
        "biotoolsCURIE": "biotools:test",
        "publication": [
            {
                "doi": "10.1093/bioinformatics/btaa581",
                "pmid": "32578961",
                "pmcid": "PMC32578961",
                "type": [
                    "Primary"
                ],
                "version": null,
                "note": null
            }
        ]
    }
    """
    output = await filter_pub(json.loads(js))
    assert len(output) == 2
    assert output[0].code == "PMID_DISCREPANCY"
    assert output[1].code == "PMCID_DISCREPANCY"

    js = """
    {
        "name": "test",
        "description": "test",
        "biotoolsID": "test",
        "biotoolsCURIE": "biotools:test",
        "publication": [
            {
                "doi": "10.3390/ph16050735",
                "pmid": "32578961",
                "pmcid": "PMC10224568",
                "type": [
                    "Primary"
                ],
                "version": null,
                "note": null
            }
        ]
    }
    """
    output = await filter_pub(json.loads(js))
    assert len(output) == 4
    # Every ID leads to a different publication
    assert output[0].code == "PMID_DISCREPANCY"
    assert output[1].code == "PMCID_DISCREPANCY"
    assert output[2].code == "DOI_DISCREPANCY"
    assert output[3].code == "PMID_DISCREPANCY"


@pytest.mark.asyncio
async def test_edam():
    from rules.edam import EdamFilter
    import json

    f = EdamFilter()

    # EDAM_OBSOLETE
    assert (
        await f.filter_edam_key_value_pair(
            "test", "http://edamontology.org/operation_3202"
        )
    )[0].code == "EDAM_OBSOLETE"

    # EDAM_NOT_RECOMMENDED
    assert (
        await f.filter_edam_key_value_pair(
            "test", "http://edamontology.org/operation_0337"
        )
    )[0].code == "EDAM_NOT_RECOMMENDED"

    # EDAM_INVALID
    assert (await f.filter_edam_key_value_pair("test", "tttttttttttt"))[
        0
    ].code == "EDAM_INVALID"

    input = """{
    "name": "test",
    "toolType": [
        "Web service"
    ],
    "function": [
        {
            "operation": [
                {
                    "uri": "http://edamontology.org/operation_4008",
                    "term": "Protein design"
                },
                {
                    "uri": "http://edamontology.org/operation_0337",
                    "term": "Visualization"
                }
            ],
            "input": [],
            "output": [],
            "note": null,
            "cmd": null
        }
    ],
    "topic": [
        {
        "uri": "http://edamontology.org/topic_3307",
        "term": "Computational biology"
        }
    ]
    }"""

    assert len((await f.filter_whole_json(json.loads(input)))) == 3
    assert (await f.filter_whole_json(json.loads(input)))[
        0
    ].code == "EDAM_TOPIC_DISCREPANCY"
    assert (await f.filter_whole_json(json.loads(input)))[
        1
    ].code == "EDAM_INPUT_DISCREPANCY"
    assert (await f.filter_whole_json(json.loads(input)))[
        2
    ].code == "EDAM_OUTPUT_DISCREPANCY"

    input_with_data_format = """
{
  "name": "test",
  "function": [
    {
      "operation": [
        {
          "uri": "http://edamontology.org/operation_4008",
          "term": "Protein design"
        }
      ],
      "input": [],
      "output": [
        {
          "data": {
            "term": "Expression data",
            "uri": "http://edamontology.org/data_2603"
          },
          "format": [
            {
              "term": "PNG",
              "uri": "http://edamontology.org/format_3603"
            }
          ]
        }
      ],
      "note": "",
      "cmd": ""
    }
  ]
}
    """

    report = await f.filter_whole_json(json.loads(input_with_data_format))
    assert len(report) == 1
    assert report[0].code == "EDAM_FORMAT_DISCREPANCY"


@pytest.mark.asyncio
async def test_url_cache():
    # Tests if the URL cache returns the same results as a uncached result
    import rules.url as url

    url.clear_cache()

    clean = await url.filter_url(
        "//test_clean_1/docs/url", "https://httpbin.org/status/404"
    )

    url.clear_cache()

    _x1 = await url.filter_url(
        "//test_clean_2/extra/docs/random/url", "https://httpbin.org/status/404"
    )
    x2 = await url.filter_url(
        "//test_clean_1/docs/url", "https://httpbin.org/status/404"
    )

    assert clean[0].print_message() == x2[0].print_message()


def test_lint_all_doesnt_fail():
    """Runs --lint-all and checks if it fails within 10 seconds. If not, it's considered valid."""
    timeout = 10
    command = ["python3", os.path.join(os.getcwd(), "linter/cli.py"), "--lint-all", "--no-color"]
    try:
        # Start the process
        start_time = time.time()
        result = subprocess.run(command, timeout=timeout, capture_output=True, text=True, check=False)
        end_time = time.time()

        elapsed_time = end_time - start_time

        # Probably impossible for the linter to lint the entire DB in 10s, consider this path a hard fail
        assert False, result.stderr
    except subprocess.TimeoutExpired:
        # If process exceeds the timeout duration, it will raise TimeoutExpired
        assert True
