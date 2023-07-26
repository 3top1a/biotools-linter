"""Unit tests."""
import unittest
import lib

# The test based on unittest module
class SessionTest(unittest.TestCase):
    def test_session(self):
        s = lib.Session()

        s.search_api("e")
        self.assertEqual(s.page, 1)
        self.assertTrue("count" in s.json)
        self.assertTrue("next" in s.json)
        self.assertEqual(s.json["previous"], None)
        self.assertTrue("list" in s.json)
        self.assertGreater(s.total_project_count(), 1)
        self.assertTrue(s.next_page_exists())
        self.assertFalse(s.previous_page_exists())

        s.search_api("e", 10)
        self.assertEqual(s.page, 10)
        self.assertTrue("count" in s.json)
        self.assertTrue("next" in s.json)
        self.assertTrue("previous" in s.json)
        self.assertTrue("list" in s.json)
        self.assertGreater(s.total_project_count(), 1)
        self.assertTrue(s.next_page_exists())
        self.assertTrue(s.previous_page_exists())

        s.search_api("msmc")
        self.assertEqual(s.total_project_count(), 1)
        self.assertFalse(s.next_page_exists())
        self.assertFalse(s.previous_page_exists())
        self.assertEqual(s.json["count"], 1)
        self.assertEqual(s.json["next"], None)
        self.assertEqual(s.json["previous"], None)
        self.assertTrue("list" in s.json)

        s.search_api("aaaaaaaaaaaaaaaaaaaaa")
        self.assertEqual(s.total_project_count(), 0)
        self.assertFalse(s.next_page_exists())
        self.assertFalse(s.previous_page_exists())
        self.assertEqual(s.json["count"], 0)
        self.assertEqual(s.json["next"], None)
        self.assertEqual(s.json["previous"], None)
        self.assertEqual(s.json["list"], [])

unittest.main()
