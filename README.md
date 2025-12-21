## Quick Start

Clone the repository
```
git clone git@github.com:njyeung/piazza-bot.git
cd piazza-bot
```

#### Implement parsers
- Since each professor has their own unique website, if a user wishes to scrape a website that does not already have a parser written for it, they must write a parser to print kaltura gallery links (and other metadata) obtained from that website.
  - This parser will be a python file placed in `/piazza-bot/parsers/`
  - Refer to `/parsers/demo.example` as an example
- To upload the new parsers to the cassandra database, the user must run `python manage.py apply`
Start the cluster using
```
  ./build.sh
  docker-compose up
```
After bringing down the cluster, run `./build.sh` again before doing docker compose up (this is important!).

Logs can be accessed with the commands `bash docker-compose logs -f fetcher` and `bash docker-compose logs -f watcher`.



#### Environment Variables
Optionally modify these enviorment variables in `docker-compose.yml`:

- `CASSANDRA_HOSTS` - Cassandra cluster nodes
- `CASSANDRA_KEYSPACE` - Database keyspace name
- `REDIS_HOST`, `REDIS_PORT` - Redis connection
- `REDIS_QUEUE` - Job queue name
- `REDIS_SEEN_SET` - Set for tracking processed URLs





## Architecture

The full details of the archetcture can be found on `Piazza Bot.pdf`.


## Parsers

A parser should use Selenium to scrape a course website for lecture links. The program should take no arguments and should output JSON objects.

Once written, it should be placed in the `/parsers` directory.




