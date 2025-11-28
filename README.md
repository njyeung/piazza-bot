# piazza-bot

Architecure:


Crawling:
- Redis queue
- Workers pull urls from the redis queue
- User defined fetcher files in parsers directory. Returns a list of urls. For example, cs544.py fetches the kaltura gallery urls from the cs544 course page and returns a list of urls.
- Run python manage.py upload to sync upload files into cassandra db
- watcher.py checks for these files periodically. Once found, it runs these once in a while to put links into the redis queue 
