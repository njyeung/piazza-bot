DO NOT PUT SECRETS IN THE .ENV IT IS FOR DOCKER STUFF AND GETS PUSHED

# piazza-bot

Architecure:

There is a cluster of scrapers, they take kaltura gallery URLs from a Redis queue and get the transcripts. Since course pages have different layouts, the user can define python files that visit these pages and print out the kaltura gallery urls via stdout (see cs544.py).  Since the Cassandra database has a user-facing port, there is a convenient command: `python manage.py apply` to sync your code with the cassandra database (users write their code in the parsers directory). From within the cluster, there is a watcher program that polls the database. It retreives your code in real time and executes them in a control loop.

After the scraper pulls a transcript from kaltura gallery, it will upload it to the cassandra database and send a message through kafka for the next step of the processing pipeline.

The processor nodes are responsible for taking the raw transcripts and optimizing them for RAG, we want to clean the transcripts, create overlapping intervals, and embed them using a local model. There will be a separate table for this in the database, cassandra supports vectorDB with lookup.
