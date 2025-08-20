import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from src.utils.news.forex_news import ForexNewsFilter

@pytest.fixture
def news_filter():
    return ForexNewsFilter()

@pytest.fixture
def sample_news_events():
    current_time = datetime.now()
    return [
        {
            'title': 'ECB Interest Rate Decision',
            'currency': 'EUR',
            'importance': 'high',
            'time': (current_time + timedelta(hours=1)).isoformat(),
            'forecast': '4.50%',
            'previous': '4.50%'
        },
        {
            'title': 'US Non-Farm Payrolls',
            'currency': 'USD',
            'importance': 'high',
            'time': (current_time + timedelta(hours=2)).isoformat(),
            'forecast': '180K',
            'previous': '175K'
        }
    ]

def test_news_filter_initialization(news_filter):
    assert news_filter is not None
    assert hasattr(news_filter, 'cached_news')

@patch('src.utils.news.forex_news.ForexNewsFilter._get_sample_events')
def test_fetch_economic_calendar(mock_events, news_filter, sample_news_events):
    mock_events.return_value = sample_news_events
    events = news_filter.fetch_economic_calendar()
    
    assert len(events) == 2
    assert events[0]['title'] == 'ECB Interest Rate Decision'
    assert events[1]['title'] == 'US Non-Farm Payrolls'

def test_is_news_time(news_filter):
    current_time = datetime.now()
    
    # Test exact news time
    with patch('src.utils.news.forex_news.ForexNewsFilter.fetch_economic_calendar') as mock_fetch:
        mock_fetch.return_value = [{
            'time': current_time.isoformat(),
            'title': 'Test Event'
        }]
        assert news_filter.is_news_time(current_time)

    # Test buffer period
    with patch('src.utils.news.forex_news.ForexNewsFilter.fetch_economic_calendar') as mock_fetch:
        mock_fetch.return_value = [{
            'time': (current_time + timedelta(minutes=10)).isoformat(),
            'title': 'Test Event'
        }]
        assert news_filter.is_news_time(current_time, buffer_minutes=15)

def test_get_upcoming_events(news_filter, sample_news_events):
    with patch('src.utils.news.forex_news.ForexNewsFilter.fetch_economic_calendar') as mock_fetch:
        mock_fetch.return_value = sample_news_events
        upcoming = news_filter.get_upcoming_events(hours=3)
        
        assert len(upcoming) == 2
        assert all(isinstance(event['time'], str) for event in upcoming)

def test_get_next_event(news_filter, sample_news_events):
    with patch('src.utils.news.forex_news.ForexNewsFilter.fetch_economic_calendar') as mock_fetch:
        mock_fetch.return_value = sample_news_events
        next_event = news_filter.get_next_event()
        
        assert next_event is not None
        assert next_event['title'] == 'ECB Interest Rate Decision'

def test_cache_functionality(news_filter, sample_news_events):
    # Test cache saving
    with patch('src.utils.news.forex_news.ForexNewsFilter.fetch_economic_calendar') as mock_fetch:
        mock_fetch.return_value = sample_news_events
        news_filter.fetch_economic_calendar()
        
        # Check if events are cached
        date_key = datetime.now().date().isoformat()
        assert date_key in news_filter.cached_news
        assert len(news_filter.cached_news[date_key]) == 2

def test_handle_api_errors(news_filter):
    with patch('src.utils.news.forex_news.ForexNewsFilter.fetch_economic_calendar') as mock_fetch:
        mock_fetch.side_effect = Exception("API Error")
        events = news_filter.fetch_economic_calendar()
        assert events == []

def test_news_event_filtering(news_filter):
    current_time = datetime.now()
    
    # Test no events
    with patch('src.utils.news.forex_news.ForexNewsFilter.fetch_economic_calendar') as mock_fetch:
        mock_fetch.return_value = []
        assert not news_filter.is_news_time(current_time)
    
    # Test event outside buffer
    with patch('src.utils.news.forex_news.ForexNewsFilter.fetch_economic_calendar') as mock_fetch:
        mock_fetch.return_value = [{
            'time': (current_time + timedelta(minutes=30)).isoformat(),
            'title': 'Test Event'
        }]
        assert not news_filter.is_news_time(current_time, buffer_minutes=15)

def test_timezone_handling(news_filter):
    # Test handling of different timezone formats
    current_time = datetime.now()
    
    with patch('src.utils.news.forex_news.ForexNewsFilter.fetch_economic_calendar') as mock_fetch:
        mock_fetch.return_value = [{
            'time': current_time.astimezone().isoformat(),  # With timezone
            'title': 'Test Event'
        }]
        assert news_filter.is_news_time(current_time)
