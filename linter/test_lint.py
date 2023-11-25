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

    # Fails
    assert cli.main(["*", "--threads", "16", "-p", "0"]) == 1

# Test url.py
def test_urls():
    # Needs internet access
    # Also big props to https://httpbin.org, http://httpforever.com and https://httpstat.us

    import rules

    # Ok
    assert rules.filter_url("test", "https://httpbin.org/status/200") == None

    # Invalid URLs
    assert rules.filter_url("test", "ftp://ftp.gnu.org/gnu/") == None
    assert rules.filter_url("test", "test") == None

    # URL_INVALID
    assert rules.filter_url("url", "also test")[0].code == "URL_INVALID"

    # URL_CONN_ERROR
    assert rules.filter_url("url", "https://gsjdhfskjhfklajshdfkashdfkashdfklashdfjakhsdflkahsfd.sdfsdf")[0].code == "URL_CONN_ERROR"

    # URL_PERMANENT_REDIRECT
    assert rules.filter_url(
        "test",
        "https://httpbin.org/redirect-to?url=https%3A%2F%2Fwww.example.com&status_code=308"
    )[0].code == "URL_PERMANENT_REDIRECT"

    # URL_BAD_STATUS
    assert rules.filter_url(
        "test", "https://httpbin.org/status/404")[0].code == "URL_BAD_STATUS"

    # URL_UNUSED_SSL
    assert rules.filter_url(
        "test", "http://httpbin.org/status/202")[0].code == "URL_UNUSED_SSL"

    # URL_NO_SSL
    # Takes extreme amount of time (33s), need to make it faster 
    assert rules.filter_url("test",
                            "http://httpforever.com/")[0].code == "URL_NO_SSL"

    # URL_TIMEOUT
    # It seems httpstat.us has gone offline?
    #assert rules.filter_url(
    #    "test", "https://httpstat.us/200?sleep=60000")[0].code == "URL_TIMEOUT"
    
    # URL_SSL_ERROR
    assert rules.filter_url(
        "test", "https://expired.badssl.com/")[0].code == "URL_SSL_ERROR"

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
    assert msg.tool == None # Should be set in lib.py
    msg.print_message(q)
    assert q.get() == "None: [001] Test message"

    rules.filter_url("url", "also test")[0].print_message(q)
    assert q.get() == "None: [URL_INVALID] URL also test at url does not match a valid URL (there may be hidden unicode)."

def test_publications():
    from rules.publications import doi_to_pmid, doi_to_pmcid, pmid_or_pmcid_to_doi, filter_pub
    import json
    
    assert doi_to_pmid("10.1093/BIOINFORMATICS/BTAA581") == "32573681"
    assert doi_to_pmid("test") == None
    assert doi_to_pmcid("10.1093/BIOINFORMATICS/BTAA581") == "PMC8034561"
    assert doi_to_pmcid("test") == None
    assert pmid_or_pmcid_to_doi("PMC8034561") == "10.1093/bioinformatics/btaa581"
    assert pmid_or_pmcid_to_doi("test") == None

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
    assert output == None
