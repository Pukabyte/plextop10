#!/usr/bin/env python3
import os
import logging
from typing import Dict, List, Optional, Tuple, Union
import requests
from bs4 import BeautifulSoup
from plexapi.server import PlexServer
from plexapi.video import Movie, Show
from dotenv import load_dotenv
from colorama import init, Fore, Style
from arrapi import RadarrAPI, SonarrAPI
import re
from difflib import SequenceMatcher
from distutils.util import strtobool

# Initialize colorama
init()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'  # Simplified format as we'll handle the formatting
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def clean_title(title: str) -> str:
    """Clean a title for better matching by removing common suffixes, years, etc."""
    # Remove year patterns like (2024) or [2024]
    title = re.sub(r'[\(\[\{].*?[\)\]\}]', '', title)
    # Remove everything after colon (including the colon)
    title = re.sub(r'\s*:.*$', '', title)
    # Remove common suffixes after dash
    title = re.sub(r'\s*-.*$', '', title)
    # Remove special characters and extra spaces
    title = re.sub(r'[^\w\s]', '', title)
    return title.lower().strip()

def title_similarity(title1: str, title2: str) -> float:
    """Calculate similarity ratio between two titles."""
    return SequenceMatcher(None, clean_title(title1), clean_title(title2)).ratio()

def is_valid_match(search_title: str, plex_item: Union[Movie, Show], min_similarity: float = 0.8) -> bool:
    """
    Determine if a Plex item is a valid match for the search title.
    Uses title similarity and optionally checks year if available.
    """
    # Calculate title similarity
    similarity = title_similarity(search_title, plex_item.title)
    
    if similarity < min_similarity:
        return False
        
    # If we have an exact match, return True
    if similarity > 0.95:
        return True
        
    # Extract year from search title if present
    year_match = re.search(r'\((\d{4})\)', search_title)
    if year_match:
        search_year = int(year_match.group(1))
        # If years don't match and we're not extremely confident about the title match, return False
        if hasattr(plex_item, 'year') and plex_item.year and abs(search_year - plex_item.year) > 1:
            return False
    
    return True

class ArrManager:
    def __init__(self):
        self.radarr = None
        self.sonarr = None
        
        # Initialize Radarr if configured
        radarr_url = os.getenv('RADARR_URL')
        radarr_api_key = os.getenv('RADARR_API_KEY')
        if radarr_url and radarr_api_key:
            self.radarr = RadarrAPI(radarr_url, radarr_api_key)
        
        # Initialize Sonarr if configured
        sonarr_url = os.getenv('SONARR_URL')
        sonarr_api_key = os.getenv('SONARR_API_KEY')
        if sonarr_url and sonarr_api_key:
            self.sonarr = SonarrAPI(sonarr_url, sonarr_api_key)
    
    def search_movie(self, title: str) -> bool:
        """Search for a movie in Radarr and add it if found."""
        if not self.radarr:
            logger.warning(f"{Fore.YELLOW}⚠️  Radarr not configured - skipping movie search{Style.RESET_ALL}")
            return False
        
        try:
            search_results = self.radarr.search_movies(title)
            if search_results:
                # Get the first result
                movie = search_results[0]
                # Add the movie to Radarr using the correct method
                movie.add(
                    quality_profile=int(os.getenv('RADARR_QUALITY_PROFILE_ID', '1')),
                    root_folder=os.getenv('RADARR_ROOT_FOLDER', '/movies'),
                    monitor=True
                )
                logger.info(f"{Fore.GREEN}✅ Added movie to Radarr: {movie.title} ({movie.year}){Style.RESET_ALL}")
                return True
            else:
                logger.warning(f"{Fore.YELLOW}⚠️  No results found in Radarr for: {title}{Style.RESET_ALL}")
                return False
        except Exception as e:
            logger.error(f"{Fore.RED}❌ Error searching Radarr: {str(e)}{Style.RESET_ALL}")
            return False
    
    def search_show(self, title: str) -> bool:
        """Search for a TV show in Sonarr and add it if found."""
        if not self.sonarr:
            logger.warning(f"{Fore.YELLOW}⚠️  Sonarr not configured - skipping show search{Style.RESET_ALL}")
            return False
        
        try:
            search_results = self.sonarr.search_series(title)
            if search_results:
                # Get the first result
                show = search_results[0]
                # Add the show to Sonarr
                show.add(
                    quality_profile=int(os.getenv('SONARR_QUALITY_PROFILE_ID', '1')),
                    root_folder=os.getenv('SONARR_ROOT_FOLDER', '/tv'),
                    monitor='all',  # Options: all, future, missing, existing, pilot, firstSeason, latestSeason, none
                    season_folder=True
                )
                logger.info(f"{Fore.GREEN}✅ Added show to Sonarr: {show.title} ({show.year if hasattr(show, 'year') else 'N/A'}){Style.RESET_ALL}")
                return True
            else:
                logger.warning(f"{Fore.YELLOW}⚠️  No results found in Sonarr for: {title}{Style.RESET_ALL}")
                return False
        except Exception as e:
            logger.error(f"{Fore.RED}❌ Error searching Sonarr: {str(e)}{Style.RESET_ALL}")
            return False

class FlixPatrolScraper:
    BASE_URL = "https://flixpatrol.com"
    
    # Service name mapping
    SERVICE_NAMES = {
        'Netflix': 'Netflix',
        'HBO': 'Max',
        'Disney+': 'Disney+',
        'Prime': 'Prime Video',
        'Apple': 'Apple TV+',
        'Paramount+': 'Paramount+'
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def get_top_content(self) -> Dict[str, Dict[str, List[Tuple[int, str]]]]:
        try:
            response = self.session.get(self.BASE_URL)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            content = {
                'movies': {},
                'shows': {}
            }

            # Find all service sections
            service_sections = soup.select("div.content.mt-8.mb-20 > div:nth-child(4) > div:nth-child(2) > div > div")
            
            for section in service_sections:
                try:
                    # Get content type (movies/shows)
                    content_type_elem = section.select_one("div.px-4.py-3.bg-gray-900.text-center > div")
                    if not content_type_elem:
                        continue
                    content_type = content_type_elem.text.strip().lower()
                    
                    # Get service name
                    service_elem = section.select_one("div.px-4.py-3.bg-gray-900.text-center > h2 > a")
                    if not service_elem:
                        continue
                    service_original = service_elem.text.strip()
                    service = self.SERVICE_NAMES.get(service_original, service_original)
                    
                    # Get all titles from the ordered list
                    titles = []
                    
                    # Get first result (uses first pattern)
                    title_elem = section.select_one("div.card-body.p-0.group > ol > li > a")
                    if title_elem:
                        titles.append((1, title_elem.text.strip()))
                    
                    # Get results 2-10 (use second pattern)
                    for i in range(1, 10):  # This gets positions 2-10
                        title_elem = section.select_one(f"div.card-body.py-0.flex-grow > ol > li:nth-child({i}) > a")
                        if title_elem:
                            titles.append((i + 1, title_elem.text.strip()))
                    
                    # Map content type to our dictionary structure
                    if 'movie' in content_type:
                        content['movies'][service] = titles
                        logger.info(f"{Fore.CYAN}🎬 Found {len(titles)} movies for {Fore.YELLOW}{service}{Fore.CYAN}:")
                        for pos, title in titles:
                            logger.info(f"{Fore.WHITE}    {pos}. {title}")
                    elif 'show' in content_type or 'tv' in content_type:
                        content['shows'][service] = titles
                        logger.info(f"{Fore.MAGENTA}📺 Found {len(titles)} shows for {Fore.YELLOW}{service}{Fore.MAGENTA}:")
                        for pos, title in titles:
                            logger.info(f"{Fore.WHITE}    {pos}. {title}")
                    
                except Exception as e:
                    logger.error(f"{Fore.RED}❌ Error processing section: {str(e)}{Style.RESET_ALL}")
                    continue
            
            return content
            
        except Exception as e:
            logger.error(f"{Fore.RED}❌ Error scraping FlixPatrol: {str(e)}{Style.RESET_ALL}")
            return {'movies': {}, 'shows': {}}

class PlexCollectionManager:
    def __init__(self):
        self.plex = PlexServer(
            os.getenv('PLEX_URL'),
            os.getenv('PLEX_TOKEN')
        )
        # Get movie and show library sections
        self.movies_sections = [
            section.strip() 
            for section in os.getenv('LIBRARY_SECTION_MOVIES', '').split(',')
        ]
        self.shows_sections = [
            section.strip() 
            for section in os.getenv('LIBRARY_SECTION_SHOWS', '').split(',')
        ]
        self.arr_manager = ArrManager()
        self.search_missing = bool(strtobool(os.getenv('SEARCH_MISSING', 'false')))

    def _find_best_match(self, section, title: str) -> Optional[Union[Movie, Show]]:
        """Find the best matching item in the Plex library."""
        search_results = section.search(title)
        
        if not search_results:
            return None
            
        # Filter and sort results by similarity
        valid_matches = []
        for item in search_results:
            if isinstance(item, (Movie, Show)) and is_valid_match(title, item):
                similarity = title_similarity(title, item.title)
                valid_matches.append((similarity, item))
        
        # Sort by similarity score
        valid_matches.sort(reverse=True, key=lambda x: x[0])
        
        return valid_matches[0][1] if valid_matches else None

    def _update_collection(self, section, collection_name: str, titles: List[Tuple[int, str]]):
        try:
            logger.info(f"\n{Fore.BLUE}📌 Updating collection: {Fore.YELLOW}{collection_name}{Fore.BLUE} in section: {Fore.YELLOW}{section.title}{Style.RESET_ALL}")
            
            # Find matching items in the library
            items = []
            positions = []
            matched_titles = []
            unmatched_titles = []
            
            for pos, title in titles:
                match = self._find_best_match(section, title)
                if match:
                    items.append(match)
                    positions.append(pos)
                    matched_titles.append((pos, title))
                    logger.info(f"{Fore.CYAN}🔍 Matched '{title}' to '{match.title}'{' (' + str(match.year) + ')' if hasattr(match, 'year') and match.year else ''}{Style.RESET_ALL}")
                else:
                    unmatched_titles.append((pos, title))

            # Log matches and non-matches
            if matched_titles:
                logger.info(f"{Fore.GREEN}✅ Found matches:{Style.RESET_ALL}")
                for pos, title in matched_titles:
                    logger.info(f"{Fore.GREEN}    #{pos}: {title}{Style.RESET_ALL}")
            
            if unmatched_titles:
                logger.info(f"{Fore.RED}❌ Missing matches:{Style.RESET_ALL}")
                for pos, title in unmatched_titles:
                    logger.info(f"{Fore.RED}    #{pos}: {title}{Style.RESET_ALL}")
                
                # Search for missing titles in Radarr/Sonarr if enabled
                if self.search_missing:
                    logger.info(f"\n{Fore.BLUE}🔍 Searching for missing titles in Radarr/Sonarr...{Style.RESET_ALL}")
                    for pos, title in unmatched_titles:
                        if section.type == 'movie':
                            self.arr_manager.search_movie(title)
                        else:
                            self.arr_manager.search_show(title)
                else:
                    logger.info(f"\n{Fore.YELLOW}ℹ️ Skipping search for missing titles (SEARCH_MISSING is disabled){Style.RESET_ALL}")

            if items:
                # Get or create collection
                try:
                    # Try to get existing collection
                    collection = section.collection(collection_name)
                    # Clear existing items
                    current_items = collection.items()
                    if current_items:
                        collection.removeItems(current_items)
                except:
                    # Create new collection with items
                    collection = section.createCollection(title=collection_name, items=items)
                    return  # Items are already added in order
                
                # Add items in original order
                collection.addItems(items)
                
                logger.info(f"{Fore.GREEN}✨ Successfully updated collection with {len(items)} items{Style.RESET_ALL}")
            else:
                logger.warning(f"{Fore.YELLOW}⚠️  No matching items found for collection{Style.RESET_ALL}")

        except Exception as e:
            logger.error(f"{Fore.RED}❌ Error updating collection: {str(e)}{Style.RESET_ALL}")

    def update_collections(self, content: Dict[str, Dict[str, List[Tuple[int, str]]]]):
        # Update movie collections across all movie sections
        for section_name in self.movies_sections:
            try:
                section = self.plex.library.section(section_name)
                for service, titles in content['movies'].items():
                    collection_name = f"{service} Top 10"
                    self._update_collection(section, collection_name, titles)
            except Exception as e:
                logger.error(f"{Fore.RED}❌ Error processing movie section {section_name}: {str(e)}{Style.RESET_ALL}")

        # Update TV show collections across all show sections
        for section_name in self.shows_sections:
            try:
                section = self.plex.library.section(section_name)
                for service, titles in content['shows'].items():
                    collection_name = f"{service} Top 10"
                    self._update_collection(section, collection_name, titles)
            except Exception as e:
                logger.error(f"{Fore.RED}❌ Error processing show section {section_name}: {str(e)}{Style.RESET_ALL}")

def main():
    try:
        # Initialize scraper and Plex manager
        scraper = FlixPatrolScraper()
        plex_manager = PlexCollectionManager()

        # Get content from FlixPatrol
        logger.info(f"\n{Fore.CYAN}🌐 Scraping FlixPatrol for top content...{Style.RESET_ALL}")
        content = scraper.get_top_content()

        # Update Plex collections
        logger.info(f"\n{Fore.CYAN}🔄 Updating Plex collections...{Style.RESET_ALL}")
        plex_manager.update_collections(content)

        logger.info(f"\n{Fore.GREEN}✅ Successfully completed updating Plex collections{Style.RESET_ALL}")

    except Exception as e:
        logger.error(f"\n{Fore.RED}❌ Error in main execution: {str(e)}{Style.RESET_ALL}")

if __name__ == "__main__":
    main() 