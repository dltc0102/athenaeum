# Purpose:

A personal use program that allows me to scrape comics from websites without having to deal with their advertisements.
Won't be distributing.

""" TODO CATALOG.PY """
o smart downloads
o progress.json garbage collector
o update catalogue.json with updated configs and extra attributes
o for flamecomics, if comic_id and soup_name don't match with catalogue config name, then fix the comic_id
o needs more retries for getting comic page and getting comic details

""" TODO PAGE.PY """
o categories: Pinned, recently read, recently updated, comics
o connect page.py to new catalog.py
o improve page.py with targeted comic request ('refresh' button?), or when reading certain comic, an async function will detect comic being read, and download according to chapters read per minute/day/hour
o download for iphone with comic selection
o make images draggable=False

# v1.0.4 Changes:

o Restructed to importing domain classmethods for ease of maintenance
o Added logic to check catalogue.json for any updates after every comic scraped
o Created API Endpoints using FastAPI
o Created routes for SvelteJS frontend
o Created favorites.json and archive.json for keeping track of respective data

# v1.0.3

Changes:
o Added validation to skip re-downloading cover images if they already exist locally
o Added basic Discord notification support (progress, error)
o Added support for domains GenzToon and ManhwaReads
o Added validation to skip premium_chapters when getting comic details for Domains (Vortexscans)
o Refactored functions for getting chapters left and downloaded chapters to validate chapters that have special names and decimals to be downloaded
o Added memory usage logs for local directories
o Added retry attempts for the get_url_response()
o Made functions for getting comic details in class methods for ease of maintenance and readability. (Omegascans so far)
o Temporarily disabled mangafire domain and ravenscans domain

# v1.0.2

Changes:
o Integrated Ebook into main.py to create ebooks while running scrape

# v1.0.1

o Added check that if cover image is already in the directory, skip so that it doesn't redownload again
o Added Archivist, a discord bot that sends error and other messages to notify the user.
o Added commands !start, !stop, !catalogue (add/remove/edit)
o Created API endpoints to prepare for svelte frontend
o Temporarily removed Domain Utoon until they stop using cloudflare
o Memray showed 143k+ allocations of the Comparer LLM Model, which causes mem allocations of more than 5gb, therefore \_shared_model was added to reduce that, loading the model ONCE, reusing it when needed and not creating one everytime.
o Created airplane_mode.py to convert downloaded comics into epubs for offline reading.

# v1.0.0

- integrated comic_db into comic_scraper
- changed chapter_processing to take into account other attributes such as release_day, comic_uid for certain domains, and if the comic is completed or not to reduce redundant scraping
- refactored and improved config:
  o merging with other configs
  o restructuring to the current new format
  o regulating domains, comic_names
- added new domains for broader comic extracting possibilities: asuracomics, flamecomics, omegacomics, kingofshojo, mangafire, toonily, vortexscans, hivetoon,
- added domain checking for if domain has a cf token/challenge, those comics with those domains are ignored
- added Comparer for Synopsis as a helper
- created Template for ease of any future domain adding
- added search_x functions for domains such as asuracomics, mangakatana and more where unique_uids are part of the url and need to be searched.
- added chromium extension availability for persistence domains like mangafire, using PersistencePlaywright class

# things to add (higher priority):

- create tasks for async: if html requests a comic to be scraped, async processing
- asuracomics: fuzzy matching for similarity ratio in search_asura()
- post get_comic_details(): collect changed configs and update config file with changed configs at the end of the scraping process
- check: check if updating config during conversion added duplicates?
- add domains: kingofshojo, custom, chinese manhwa/manhua domains

# things to add (less priority):

- webpage: pinned section, recently_read section, recently_updated section
- smart downloads: when a new comic is added, have a minimum reading buffer of 10-20 chapters. if comic has 100 chapters per say, and comic progress is within minimum reading buffer, until it is near max of min reading buffer, do nothing. if minimum reading buffer is 20 and comic progress is 15, start downloading the next 50. smart downloads can also include chapters_read_per_day or chapters_read_per_hour
- live console
- live notifications of subscribed pings?

# v1.1.0 (old ver)

- made comic_db in an attempt to refactor everything
  - used classes for better structure and to add more comic domains for ease of adaptability to different scraping generations
  - used classes for ease of management of comics
  - used async for parallel downloads and batch downloads to expedite downloading process and resource gathering
  - use of async also allowed playwright (imitation library for scraping) to work faster and be more efficient

# v 1.0.0 (old ver)

- A main web page with a grid of 3 comics displayed per row. Each comic has a title, cover image and a read button.
- Each comic chapter consists of the title - chapter number, a dropdown for easy skipping of chapter, the comic with no line breaks and seamless reading, and a 'next chapter' button at the end for ease of going to the next chapter.
- Progress on each comic is saved so that if user were to read something else and come back to the first comic they were reading, it would continue where they left off of
- dropdown for comic pages have been fixed
- before updating start chapter from the original '1' or '0' to the counted chapters, count from chapter 1 to counted_chapters and see if theres any missing chapters. if there are, try to fetch their chapters again before starting from new_start_chapter:
  for example:
  Comic: Lightning Degree
  Skipped Chapters: 14, 15, 16
  start_chapter: 1
  end_chapter: 198
  counted_chapters: 58
  \*\* fetch 14, 15, 16 before updating start_chapter to 58, then start from 58 and scan all thats left for the comic till 198
- if there isnt a 'next chapter', there will now be a button that says 'back to home' to redirect you to main page
- if a chapter has been skipped, the 'finished processign chapter' message wont show in console
- created a search bar to search through comics on the main page.
- froze search bar so that it appears even when scrolling on main page
- added progress of each comic and sorted the comics in terms of progress
- if next link isnt found, it will use the 'next' button's href link
