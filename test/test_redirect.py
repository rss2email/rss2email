import unittest
from unittest.mock import patch, MagicMock

from rss2email.feed import Feed
from rss2email.config import Config, CONFIG


class TestFeedURLRedirect(unittest.TestCase):

    def setUp(self):
        """Set up a feed object for testing."""
        # Use a mock config to avoid touching the user's real configuration
        mock_config = Config()
        mock_config.read_dict({'DEFAULT': CONFIG['DEFAULT']})
        # Prevent the config from trying to load or save real files
        mock_config.load_from_file = MagicMock()
        mock_config.save_to_file = MagicMock()

        self.feed = Feed(name='TestFeed', url='http://old-url.com/feed',
                         config=mock_config)
        self.feed.to = 'test@example.com'
        # Mock the save method on the feed object to isolate the test
        self.feed.save_to_config = MagicMock()

    @patch('rss2email.feed._feedparser.parse')
    def test_redirect_updates_url_and_saves_config(self, mock_parse):
        # Simulate a 301 redirect response from feedparser
        data = {
            'status': 301,
            'url': 'http://new-url.com/feed',
            'entries': [],
            'bozo': 0,
            'headers': {},
            'etag': None,
            'modified': None,
            'bozo_exception': None,
        }
        mock_parsed = MagicMock()
        mock_parsed.status = data['status']
        mock_parsed.entries = data['entries']
        mock_parsed.bozo = data['bozo']

        def getitem_side_effect(key):
            return data[key]
        mock_parsed.__getitem__.side_effect = getitem_side_effect

        def get_side_effect(key, default=None):
            return data.get(key, default)
        mock_parsed.get.side_effect = get_side_effect
        mock_parse.return_value = mock_parsed

        # Run the feed with save_config=True, disable sending emails
        self.feed.run(send=False, save_config=True)

        # Check that the URL was updated in the feed object
        self.assertEqual(self.feed.url, 'http://new-url.com/feed')
        # Check that the change was persisted to config
        self.feed.save_to_config.assert_called_once()

    @patch('rss2email.feed._feedparser.parse')
    def test_redirect_updates_url_without_saving_config(self, mock_parse):
        """Test a 301 redirect updates the URL in memory but does not save."""
        # Simulate a 301 redirect response from feedparser
        data = {
            'status': 301,
            'url': 'http://new-url.com/feed',
            'entries': [],
            'bozo': 0,
            'headers': {},
            'etag': None,
            'modified': None,
            'bozo_exception': None,
        }
        mock_parsed = MagicMock()
        mock_parsed.status = data['status']
        mock_parsed.entries = data['entries']
        mock_parsed.bozo = data['bozo']

        def getitem_side_effect(key):
            return data[key]
        mock_parsed.__getitem__.side_effect = getitem_side_effect

        def get_side_effect(key, default=None):
            return data.get(key, default)
        mock_parsed.get.side_effect = get_side_effect
        mock_parse.return_value = mock_parsed

        # Run the feed with save_config=False
        self.feed.run(send=False, save_config=False)

        # Check that the URL was updated in the feed object for this session
        self.assertEqual(self.feed.url, 'http://new-url.com/feed')
        # Check that the change was NOT persisted to config
        self.feed.save_to_config.assert_not_called()

    @patch('rss2email.feed._feedparser.parse')
    def test_no_redirect_does_not_update_url(self, mock_parse):
        """Test that a normal (200 OK) response does not change the URL."""
        # Simulate a normal 200 OK response
        mock_parsed = MagicMock()
        mock_parsed.status = 200
        mock_parsed.url = 'http://old-url.com/feed'
        mock_parsed.entries = []
        mock_parsed.bozo = 0
        mock_parsed.headers = {}
        mock_parsed.etag = None
        mock_parsed.modified = None
        mock_parse.return_value = mock_parsed

        # Run the feed, save_config can be true or false
        self.feed.run(send=False, save_config=True)

        # Check that the URL was NOT updated
        self.assertEqual(self.feed.url, 'http://old-url.com/feed')
        # Check that save_to_config was NOT called for a non-redirect
        self.feed.save_to_config.assert_not_called()


if __name__ == '__main__':
    unittest.main()