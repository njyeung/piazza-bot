"""Simple script to test Piazza API"""
from piazza_api import Piazza
from bs4 import BeautifulSoup

# Login
p = Piazza()
email = "njyeung@wisc.edu"  # Your Piazza email
password = "Sakura123$"  # Your Piazza password

p.user_login(email, password)

# Get user's classes
user = p.get_user_profile()
cs544 = p.network("merk8zm4in1ib")

# Fetch the feed
print("Fetching feed for CS544...\n")
feed = cs544.get_feed(limit=20, offset=0)  # Fetch more to account for pinned posts

# Filter out pinned posts
unpinned_posts = [post for post in feed['feed'] if 'pin' not in post.get('tags', [])]

# Get the 3 most recent unpinned posts
recent_posts = unpinned_posts[:26]

# Iterate through the most recent 3 unpinned posts
for i, post_summary in enumerate(recent_posts, 1):
    print(f"POST #{i} - @{post_summary['nr']}")

    # Fetch the full post to get complete content
    full_post = cs544.get_post(post_summary['nr'])

    # Extract subject and content
    subject_html = full_post['history'][0]['subject']
    content_html = full_post['history'][0]['content']

    # Parse HTML to get clean text
    subject_text = BeautifulSoup(subject_html, 'html.parser').get_text()
    content_text = BeautifulSoup(content_html, 'html.parser').get_text()

    print(f"Subject: {subject_text}")
    print(f"\nContent:\n{content_text}")

    # Get followup comments
    followups = full_post.get('children', [])

    if followups:
        print(f"COMMENTS ({len(followups)}):")

        for j, followup in enumerate(followups, 1):
            followup_content = ""
            followup_subject = ""

            try:
                followup_content = followup['history'][0].get('content', '')
            except:
                pass
            
            try:
                followup_subject = followup.get('subject', '')
            except:
                pass

            comment_html = ""
            if followup_content:
                comment_html = followup_content
            else:
                comment_html = followup_subject

            if comment_html == "":
                continue

            comment = BeautifulSoup(comment_html, 'html.parser').get_text()
            print(comment)
            

    else:
        print("\nNo comments yet.")

    print(f"\n")
