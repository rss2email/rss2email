import unittest
import unittest.mock

from rss2email.feed import Feed
from rss2email.config import Config, CONFIG
import rss2email.feed as _rss2email_feed


class TestCacheControl(unittest.TestCase):
    @unittest.mock.patch("time.time")
    @unittest.mock.patch("rss2email.feed._feedparser.parse")
    def test_cache_control_mocked(self, mock_parse, mock_time):
        # Create a real config object with default values
        config = Config()
        config.read_dict({"DEFAULT": CONFIG["DEFAULT"]})

        # Create a feed
        feed = Feed(
            name="test-feed",
            url="http://example.com/feed.rss",
            to="a@b.com",
            config=config,
        )

        # Mock the return value of feedparser.parse
        parsed = _rss2email_feed._feedparser.FeedParserDict()
        parsed.status = 200
        parsed.headers = {"cache-control": "max-age=5"}
        parsed.entries = []
        parsed.bozo = 0
        mock_parse.return_value = parsed

        # First run, should fetch
        mock_time.return_value = 1000
        feed.run(send=False)
        self.assertEqual(mock_parse.call_count, 1)

        # Second run, should be cached
        mock_time.return_value = 1002
        feed.run(send=False)
        self.assertEqual(mock_parse.call_count, 1)

        # Third run, should fetch again
        mock_time.return_value = 1006
        feed.run(send=False)
        self.assertEqual(mock_parse.call_count, 2)


if __name__ == "__main__":
    unittest.main()
