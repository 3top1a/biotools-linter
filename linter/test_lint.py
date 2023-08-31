"""Unit tests. Use with pytest."""

def test_session():
    import lib as lib
    s = lib.Session()

    # Broad search
    s.clear_search()
    s.search_api("e")
    assert s.get_total_project_count() > 1
    assert s.next_page_exists()
    assert not s.previous_page_exists()
    last_json = s.json

    # Broad search, page 10
    s.clear_search()
    s.search_api("e", 10)
    assert s.get_total_project_count() > 1
    assert s.next_page_exists()
    assert s.previous_page_exists()
    assert s.json != last_json

    # Exact search
    s.clear_search()
    s.search_api("msmc")
    assert s.get_total_project_count() == 1
    assert not s.next_page_exists()
    assert not s.previous_page_exists()

    # Double exact search
    s.clear_search()
    s.search_api("msmc,metexplore")
    assert s.get_total_project_count() == 2
    assert not s.next_page_exists()
    assert not s.previous_page_exists()

    # Topic search
    s.clear_search()
    s.search_api("topic_2830")
    assert s.get_total_project_count() > 1
    assert s.next_page_exists()
    assert not s.previous_page_exists()

    # Operation search
    s.clear_search()
    s.search_api("operation_0252")
    assert s.get_total_project_count() > 1
    assert s.next_page_exists()
    assert not s.previous_page_exists()

    # Collection search
    s.clear_search()
    s.search_api("nf-core")
    assert s.get_total_project_count() > 1
    assert not s.next_page_exists()
    assert not s.previous_page_exists()

    # Invalid search
    s.clear_search()
    s.search_api("aaaaaaaaaaaaaaaaaaaaa")
    assert s.get_total_project_count() == 0
    assert not s.next_page_exists()
    assert not s.previous_page_exists()

def test_cli():
    import cli as cli
    # "end to end" CLI test, runs the CLI as if it was ran from the command line
    assert cli.main(["msmc,metexplore"]) == 0
    assert cli.main(["msmc,metexplore", "--threads", "16"]) == 0

    # Fails
    assert cli.main(["*", "--threads", "16", "-p", "0"]) == 1
