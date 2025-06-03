# Plex FlixPatrol Collections

This script automatically creates and updates Plex collections based on the current top movies and TV shows from various streaming services as listed on FlixPatrol.

## Features

- Scrapes top content from FlixPatrol for multiple streaming services:
  - Netflix
  - HBO
  - Disney+
  - Prime
  - Apple
  - Paramount+
- Creates/updates collections in Plex for both movies and TV shows
- Supports multiple library sections for both movies and TV shows
- Automatically matches content titles with your Plex library
- Detailed logging for troubleshooting

## Requirements

- Python 3.7+
- Plex Media Server

## Installation

1. Clone this repository
2. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
4. Edit `.env` and add your Plex configuration:
   - `PLEX_URL`: Your Plex server URL (e.g., http://localhost:32400)
   - `PLEX_TOKEN`: Your Plex authentication token
   - `LIBRARY_SECTION_MOVIES`: Comma-separated list of movie library sections (e.g., "Movies, Movies - 4K, Movies - Anime")
   - `LIBRARY_SECTION_SHOWS`: Comma-separated list of TV show library sections (e.g., "TV Shows, TV Shows - 4K, TV Shows - Anime")

## Usage

Run the script:
```bash
python update_plex_collections.py
```

The script will:
1. Scrape current top content from FlixPatrol
2. Create/update collections in each of your specified Plex library sections
3. Match content with your library
4. Log all actions and any issues

## Getting Your Plex Token

1. Sign in to Plex web app
2. Open any media item
3. Click the three dots (...) and select "Get Info"
4. Click the "View XML" button
5. Your token is in the URL (X-Plex-Token=YOUR_TOKEN)

## Automation

You can automate this script using cron or any other scheduler. Example cron entry to run daily at 3 AM:

```bash
0 3 * * * cd /path/to/script && /usr/bin/python3 update_plex_collections.py
```

## Error Handling

The script includes comprehensive error handling and logging. Check the console output for any issues. Common issues might include:
- Network connectivity problems
- Incorrect Plex configuration
- Content not found in your Plex library
- Invalid library section names

## Contributing

Feel free to submit issues and pull requests. # plextop10
