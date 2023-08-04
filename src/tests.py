"""Unit tests."""
import unittest


# The test based on unittest module
class SessionTest(unittest.TestCase):
    def setUp(self):
        from web import app
        self.ctx = app.app_context()
        self.ctx.push()
        self.client = app.test_client()

    def test_session(self):
        import lib as lib
        s = lib.Session()

        # Broad search
        s.clear_search()
        s.search_api("e")
        assert s.page == 1
        assert s.total_project_count() > 1
        assert s.next_page_exists()
        assert not s.previous_page_exists()

        # Broad search, page 10
        s.clear_search()
        s.search_api("e", 10)
        assert s.page == 10
        assert s.total_project_count() > 1
        assert s.next_page_exists()
        assert s.previous_page_exists()

        # Exact search
        s.clear_search()
        s.search_api("msmc")
        assert s.total_project_count() == 1
        assert not s.next_page_exists()
        assert not s.previous_page_exists()

        # Double exact search
        s.clear_search()
        s.search_api("msmc,metexplore")
        assert s.total_project_count() == 2
        assert not s.next_page_exists()
        assert not s.previous_page_exists()

        # Topic search
        s.clear_search()
        s.search_api("topic_2830")
        assert s.total_project_count() > 1
        assert s.next_page_exists()
        assert not s.previous_page_exists()

        # Operation search
        s.clear_search()
        s.search_api("operation_0252")
        assert s.total_project_count() > 1
        assert s.next_page_exists()
        assert not s.previous_page_exists()

        # Collection search
        s.clear_search()
        s.search_api("nf-core")
        assert s.total_project_count() > 1
        assert not s.next_page_exists()
        assert not s.previous_page_exists()

        # Invalid search
        s.clear_search()
        s.search_api("aaaaaaaaaaaaaaaaaaaaa")
        assert s.total_project_count() == 0
        assert not s.next_page_exists()
        assert not s.previous_page_exists()

    def test_cli(self):
        import cli as cli
        # "end to end" CLI test, runs the CLI as if it was ran from the command line
        cli.main(["msmc,metexplore"])

    def test_web(self):
        response = self.client.get("/")
        assert response.status_code == 200
        
        response = self.client.get("/search/metexplore")
        assert response.status_code == 200

        response = self.client.get("/lint/metexplore")
        assert response.status_code == 200

unittest.main()
