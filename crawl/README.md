# Agoda Hotel Pricing Scraper

A comprehensive web scraping tool for collecting competitor pricing data from Agoda.com hotel booking platform.

## Features

- **Multi-date Scraping**: Automatically scrapes pricing for current date (D), D+7, and D+15
- **Daily Scheduling**: Automated daily scraping with configurable time
- **Multiple Hotels**: Support for scraping multiple competitor hotels
- **Robust Error Handling**: Retry mechanisms and comprehensive logging
- **Data Export**: JSON and CSV output formats
- **Anti-detection**: User-agent rotation, delays, and other anti-bot measures
- **Flexible Configuration**: Easy hotel URL management and scheduling

## Installation

1. **Activate the virtual environment**:
   ```bash
   source ../scraper_env/bin/activate
   ```

2. **Install additional dependencies** (if needed):
   ```bash
   pip install schedule
   ```

3. **Verify Chrome/Chromium installation**:
   The scraper uses Chrome WebDriver. Make sure Chrome or Chromium is installed on your system.

## Quick Start

### 1. Add Hotel URLs

Add competitor hotel URLs to the configuration:

```bash
python main.py --add-url "https://www.agoda.com/hotel/example-hotel"
python main.py --add-url "https://www.agoda.com/another-hotel"
```

### 2. Test Single Hotel Scraping

Test scraping a single hotel:

```bash
python main.py --url "https://www.agoda.com/hotel/example-hotel"
```

### 3. Run Daily Scheduler

Start the daily scheduler (default time: 09:00):

```bash
python main.py --schedule
```

Or specify a custom time:

```bash
python main.py --schedule --schedule-time "14:30"
```

### 4. Run Once for All Hotels

Run scraping immediately for all configured hotels:

```bash
python main.py --run-once
```

## Usage Examples

### Basic Operations

```bash
# List configured hotels
python main.py --list-urls

# Show scheduler status
python main.py --status

# Remove a hotel URL
python main.py --remove-url "https://www.agoda.com/hotel/example"

# Clear all hotel URLs
python main.py --clear-urls
```

### Advanced Scraping

```bash
# Scrape for specific dates
python main.py --url "https://www.agoda.com/hotel/example" --dates "2024-01-15" "2024-01-22"

# Scrape multiple hotels from file
echo "https://www.agoda.com/hotel1" > hotels.txt
echo "https://www.agoda.com/hotel2" >> hotels.txt
python main.py --urls-file hotels.txt

# Run in headless mode (default)
python main.py --url "https://www.agoda.com/hotel/example" --headless
```

## Configuration

### Hotel URLs

Hotel URLs are stored in `data/scheduler_config.json`. You can manage them using:

- `--add-url`: Add a new hotel URL
- `--remove-url`: Remove a hotel URL
- `--list-urls`: List all configured URLs
- `--clear-urls`: Remove all URLs

### Schedule Time

The default scraping time is 09:00 (9 AM). You can change it using:

```bash
python main.py --schedule --schedule-time "14:30"
```

### Data Storage

Scraped data is stored in the `data/` directory:

- **JSON format**: Complete session data with all details
- **CSV format**: Flattened data suitable for analysis
- **Logs**: Detailed logs in `logs/` directory

## Data Structure

### Scraped Data Fields

For each hotel and date combination, the scraper collects:

**Hotel Information:**
- Hotel name and ID
- Location/address
- Rating and review count
- Hotel URL

**Room Information:**
- Room type/name
- Price and currency
- Availability status
- Maximum guests
- Bed type and room size
- Amenities list
- Cancellation policy

**Session Metadata:**
- Scraping timestamp
- Session ID
- Success/error counts
- Target dates

### Output Formats

**JSON Output** (`data/agoda_pricing_session_YYYYMMDD_HHMMSS.json`):
```json
{
  "session_id": "uuid",
  "start_time": "2024-01-15T09:00:00",
  "hotels_scraped": [
    {
      "hotel_name": "Example Hotel",
      "location": "Bangkok, Thailand",
      "check_in_date": "2024-01-15",
      "check_out_date": "2024-01-16",
      "rooms": [
        {
          "room_type": "Deluxe Room",
          "price": 1500.0,
          "currency": "THB",
          "availability": true
        }
      ]
    }
  ]
}
```

**CSV Output** (`data/agoda_pricing_session_YYYYMMDD_HHMMSS.csv`):
Flattened format with one row per room per hotel per date.

## Target Dates

By default, the scraper collects data for:
- **D (Today)**: Current date
- **D+7**: 7 days from current date  
- **D+15**: 15 days from current date

You can customize target dates in `config.py` by modifying `TARGET_DATES_OFFSET`.

## Error Handling

The scraper includes comprehensive error handling:

- **Retry Logic**: Failed requests are retried up to 3 times
- **Rate Limiting**: Delays between requests to avoid being blocked
- **Logging**: Detailed logs for debugging and monitoring
- **Graceful Degradation**: Continues scraping other hotels if one fails

## Anti-Detection Features

- **User-Agent Rotation**: Random user agents for each session
- **Request Delays**: Configurable delays with jitter
- **Headless Mode**: Runs without visible browser window
- **WebDriver Stealth**: Removes automation detection properties

## Monitoring and Logs

Logs are stored in `logs/` directory with daily rotation:

- `agoda_scraper_YYYYMMDD.log`: Main scraper logs
- `scheduler_YYYYMMDD.log`: Scheduler logs

Log levels: INFO, WARNING, ERROR

## Troubleshooting

### Common Issues

1. **Chrome Driver Issues**:
   ```bash
   # Update webdriver-manager
   pip install --upgrade webdriver-manager
   ```

2. **Page Loading Timeouts**:
   - Increase timeout values in `config.py`
   - Check internet connection
   - Verify hotel URLs are valid

3. **No Data Scraped**:
   - Check if Agoda has changed their page structure
   - Verify CSS selectors in scraper code
   - Enable non-headless mode for debugging

4. **Rate Limiting**:
   - Increase delays in `config.py`
   - Reduce concurrent requests
   - Use different IP addresses if needed

### Debug Mode

Run with visible browser for debugging:

```bash
python main.py --url "https://www.agoda.com/hotel/example" --headless false
```

## Configuration Files

### `config.py`
Main configuration settings:
- Timeouts and delays
- Chrome options
- Data storage settings
- Target date offsets

### `data/scheduler_config.json`
Runtime configuration:
- Hotel URLs list
- Schedule time
- Last update timestamp

## Contributing

To extend the scraper:

1. **Add new data fields**: Modify `data_models.py`
2. **Update selectors**: Edit extraction methods in `agoda_scraper.py`
3. **Add new features**: Extend main classes
4. **Improve anti-detection**: Update `utils.py` and `config.py`

## License

This tool is for educational and competitive analysis purposes. Please respect Agoda's terms of service and implement appropriate rate limiting.
