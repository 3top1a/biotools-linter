"""Unit tests. Use with pytest."""


def test_session():
    import lib as lib
    from lib import flatten_json_to_single_dict
    import json
    s = lib.Session()

    assert not s.next_page_exists()
    assert not s.previous_page_exists()

    # Broad search
    s.clear_cache()
    s.search_api("e")
    assert s.get_total_tool_count() > 1
    assert s.next_page_exists()
    assert not s.previous_page_exists()
    last_json = s.json

    # Broad search, page 10
    s.clear_cache()
    s.search_api("e", 10)
    assert s.get_total_tool_count() > 1
    assert s.next_page_exists()
    assert s.previous_page_exists()
    assert s.json != last_json

    # Exact search
    s.clear_cache()
    s.search_api("msmc")
    assert s.get_total_tool_count() == 1
    assert not s.next_page_exists()
    assert not s.previous_page_exists()

    # Invalid search
    s.clear_cache()
    s.search_api("aaaaaaaaaaaaaaaaaaaaa")
    assert s.get_total_tool_count() == 0
    assert not s.next_page_exists()
    assert not s.previous_page_exists()

    # Multiple pages search
    s.clear_cache()
    s.search_api_multiple_pages("*", 1, 5 + 1)
    assert len(s.return_tool_list_json()) == 50

    s.clear_cache()
    s.search_api_multiple_pages("bioto", 1, 5 + 1)
    assert len(s.return_tool_list_json()) == 2

    s.clear_cache()
    s.search_api_exact_match("s")
    assert len(s.return_tool_list_json()) == 0
    s.search_api_exact_match("msmc")
    assert len(s.return_tool_list_json()) == 1

    s.clear_cache()
    for x in range(0, 2):
        print(x * 10)
        print(x * 10 + 10)
        s.search_api_multiple_pages("cli", x * 10 + 1, x * 10 + 10 + 1)
    assert len(s.return_tool_list_json()) == 131

    example_json = {
        "a" : {
            "0": "1",
            "1": "8",
            "2": "42",
        },
        "the answer": "5",
        "list": [
            "1",
            "2",
            "3",
            "4",
            "5"
        ]
    }
    example_output = {
        '//a/0': '1',
        '//a/1': '8',
        '//a/2': '42',
        '//the answer': '5',
        '//list/0': '1',
        '//list/1': '2',
        '//list/2': '3',
        '//list/3': '4',
        '//list/4': '5',
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
    s.lint_specific_tool_json(json.loads(tool_json), q)
    assert q.get().code == "URL_BAD_STATUS"

def test_cli():
    import cli as cli
    # "end to end" CLI test, runs the CLI as if it was ran from the command line
    # Any use of certain tool names are only for testing purposes and not in bad faith
    assert cli.main(["msmc"]) == 0
    assert cli.main(["metexplore", "--threads", "16", "--no-color"]) == 0
    assert cli.main(["msmc", "--threads", "16", "--exit-on-error"]) == 1

    # Fails, as page can't be 0
    assert cli.main(["*", "--threads", "16", "-p", "0"]) == 1

# Test url.py
def test_urls():
    # Needs internet access
    # Also big props to https://httpbin.org, http://httpforever.com and https://httpstat.us

    import rules
    import time

    start_time = time.time()

    # Ok
    assert rules.filter_url("test", "https://httpbin.org/status/200") is None

    print(f"URL - OK: {time.time() - start_time}")
    start_time = time.time()

    # Invalid URLs
    assert rules.filter_url("test", "ftp://ftp.gnu.org/gnu/") is None
    assert rules.filter_url("test", "test") is None

    print(f"URL - Invalid URLs: {time.time() - start_time}")
    start_time = time.time()

    # URL_INVALID
    assert rules.filter_url("url", "also test")[0].code == "URL_INVALID"

    print(f"URL - URL_INVALID: {time.time() - start_time}")
    start_time = time.time()

    # URL_CONN_ERROR
    assert rules.filter_url("url", "https://gsjdhfskjhfklajshdfkashdfkashdfklashdfjakhsdflkahsfd.sdfsdf")[0].code == "URL_CONN_ERROR"

    print(f"URL - URL_CONN_ERROR: {time.time() - start_time}")
    start_time = time.time()

    # URL_PERMANENT_REDIRECT
    assert rules.filter_url(
        "test",
        "https://httpbin.org/redirect-to?url=https%3A%2F%2Fwww.example.com&status_code=308"
    )[0].code == "URL_PERMANENT_REDIRECT"

    print(f"URL - URL_PERMANENT_REDIRECT: {time.time() - start_time}")
    start_time = time.time()

    # URL_BAD_STATUS
    assert rules.filter_url(
        "test", "https://httpbin.org/status/404")[0].code == "URL_BAD_STATUS"

    print(f"URL - URL_BAD_STATUS: {time.time() - start_time}")
    start_time = time.time()

    # URL_UNUSED_SSL
    assert rules.filter_url(
        "test", "http://httpbin.org/status/202")[0].code == "URL_UNUSED_SSL"

    print(f"URL - URL_UNUSED_SSL: {time.time() - start_time}")
    start_time = time.time()

    # URL_NO_SSL
    # Takes extreme amount of time (33s), need to make it faster 
    assert rules.filter_url("test",
                            "http://httpforever.com/")[0].code == "URL_NO_SSL"

    print(f"URL - URL_NO_SSL: {time.time() - start_time}")
    start_time = time.time()

    # URL_TIMEOUT
    assert rules.filter_url(
        "test", "https://httpstat.us/200?sleep=60000")[0].code == "URL_TIMEOUT"

    print(f"URL - URL_TIMEOUT: {time.time() - start_time}")
    start_time = time.time()

    # URL_SSL_ERROR
    assert rules.filter_url(
        "test", "https://expired.badssl.com/")[0].code == "URL_SSL_ERROR"

    print(f"URL - URL_SSL_ERROR: {time.time() - start_time}")

# Test messages.py
def test_messages():
    import rules
    from message import Message, Level
    from queue import Queue

    q = Queue()

    msg = Message(code="001", body="Test message", location="//name", level=Level.LinterError)
    assert msg.code == "001"
    assert msg.body == "Test message"
    assert msg.location == "//name"
    assert msg.level == Level.LinterError
    assert msg.tool is None # Should be set in lib.py
    msg.print_message(q)
    assert q.get() == "None: [001] Test message"

    rules.filter_url("url", "also test")[0].print_message(q)
    assert q.get() == "None: [URL_INVALID] URL also test at url does not match a valid URL (there may be hidden unicode)."

def test_publications():
    from rules.publications import doi_to_pmid, doi_to_pmcid, pmid_or_pmcid_to_doi, filter_pub
    import json
    
    assert doi_to_pmid("10.1093/BIOINFORMATICS/BTAA581") == "32573681"
    assert doi_to_pmid("test") is None
    assert doi_to_pmcid("10.1093/BIOINFORMATICS/BTAA581") == "PMC8034561"
    assert doi_to_pmcid("test") is None
    assert pmid_or_pmcid_to_doi("PMC8034561") == "10.1093/bioinformatics/btaa581"
    assert pmid_or_pmcid_to_doi("test") is None

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
    output = filter_pub(json.loads(json_bad))
    assert len(output) == 2
    assert output[0].code == "DOI_BUT_NOT_PMID"
    assert output[1].code == "DOI_BUT_NOT_PMCID"

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
    output = filter_pub(json.loads(json_good))
    assert output is None

def test_edam():
    from rules.edam import EdamFilter
    import json
    
    f = EdamFilter()
    
    # EDAM_OBSOLETE
    assert f.filter_edam_key_value_pair('test', 'http://edamontology.org/operation_3202')[0].code == "EDAM_OBSOLETE"
    
    # EDAM_NOT_RECOMMENDED
    assert f.filter_edam_key_value_pair('test', 'http://edamontology.org/operation_0337')[0].code == "EDAM_NOT_RECOMMENDED"
    
    # EDAM_INVALID
    assert f.filter_edam_key_value_pair('test', 'tttttttttttt')[0].code == "EDAM_INVALID"
    
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
    
    assert len(f.filter_whole_json(json.loads(input))) == 3
    assert f.filter_whole_json(json.loads(input))[0].code == "EDAM_TOPIC_DISCREPANCY"
    assert f.filter_whole_json(json.loads(input))[1].code == "EDAM_INPUT_DISCREPANCY"
    assert f.filter_whole_json(json.loads(input))[2].code == "EDAM_OUTPUT_DISCREPANCY"

def test_benchmark():
    # Benchmark some stuff to make it faster
    
    import time
    import rules

    start_time = time.time()

    assert rules.filter_url("test", "https://httpbin.org/status/200") is None

    print(f"URL - OK: {time.time() - start_time}")
    start_time = time.time()

    assert rules.filter_url("test", "ftp://ftp.gnu.org/gnu/") is None
    assert rules.filter_url("test", "test") is None

    print(f"URL - Invalid URLs: {time.time() - start_time}")
    start_time = time.time()

    # URL_CONN_ERROR
    assert rules.filter_url("url", "https://gsjdhfskjhfklajshdfkashdfkashdfklashdfjakhsdflkahsfd.sdfsdf")[0].code == "URL_CONN_ERROR"

    print(f"URL - URL_CONN_ERROR: {time.time() - start_time}")
    start_time = time.time()
    
    assert rules.filter_url(
        "test",
        "https://httpbin.org/redirect-to?url=https%3A%2F%2Fwww.example.com&status_code=308"
    )[0].code == "URL_PERMANENT_REDIRECT"
    
    print(f"URL - URL_PERMANENT_REDIRECT: {time.time() - start_time}")
    start_time = time.time()
    
    