"""Scrapers module for downloading Warframe data."""

from .weapon_name_scraper import scrape_weapon_names
from .weapon_data_scraper import scrape_weapon_data
from .mod_name_scraper import scrape_mod_names
from .mod_data_scraper import scrape_mod_data

__all__ = ['scrape_weapon_names', 'scrape_weapon_data', 'scrape_mod_names', 'scrape_mod_data']

