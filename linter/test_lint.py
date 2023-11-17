"""Unit tests. Use with pytest."""


def test_session():
    import lib as lib
    s = lib.Session()

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
    for x in range(0, 2):
        print(x * 10)
        print(x * 10 + 10)
        s.search_api_multiple_pages("cli", x * 10 + 1, x * 10 + 10 + 1)
    assert len(s.return_tool_list_json()) == 131

def test_cli():
    import cli as cli
    # "end to end" CLI test, runs the CLI as if it was ran from the command line
    assert cli.main(["msmc,metexplore"]) == 0
    assert cli.main(["msmc,metexplore", "--threads", "16"]) == 0

    # Fails
    assert cli.main(["*", "--threads", "16", "-p", "0"]) == 1


# Test url.py
def test_urls():
    # Needs internet access
    # Also big props to https://httpbin.org, http://httpforever.com and https://httpstat.us

    import rules

    # Ok
    assert rules.filter_url("test", "https://httpbin.org/status/200") == None

    # URL_INVALID
    assert rules.filter_url("url", "also test")[0].code == "URL_INVALID"

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
    assert rules.filter_url("test",
                            "http://httpforever.com/")[0].code == "URL_NO_SSL"

    # URL_TIMEOUT
    # It seems httpstat.us has gone offline?
    #assert rules.filter_url(
    #    "test", "https://httpstat.us/200?sleep=60000")[0].code == "URL_TIMEOUT"
    
    # URL_SSL_ERROR
    assert rules.filter_url(
        "test", "https://expired.badssl.com/")[0].code == "URL_SSL_ERROR"
