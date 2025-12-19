Hi Meena! See "Piazza Bof.pdf"

## Quick Start

Clone the repository
```
git clone git@github.com:njyeung/piazza-bot.git
cd piazza-bot
```

Implement parsers
- Since each professor has their own unique website, if a user wishes to scrape a website that does not already have a parser written for it, they must write a parser to print kaltura gallery links (and other metadata) obtained from that website.
- This parser will be a python file placed in `/piazza-bot/parsers/`
- Refer to demo.py as an example
- To upload the new parsers to the cassandra database, the user must run ‘’python manage.py apply’’
Start the cluster using
```
  ./build.sh
  docker-compose up
```
After bringing down the cluster, run ./build.sh again before doing docker compose up
