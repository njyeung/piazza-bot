# Piazza API Library - User Guide

This guide covers the essential operations for working with the piazza-api library, focusing on reading and interacting with posts.

## Table of Contents
- [Installation & Authentication](#installation--authentication)
- [Getting Your Classes](#getting-your-classes)
- [Working with Posts](#working-with-posts)
- [Understanding Post Structure](#understanding-post-structure)
- [Comments & Discussions](#comments--discussions)
- [Responding to Posts](#responding-to-posts)

---

## Installation & Authentication

### Install the Library
```bash
pip install piazza-api
```

### Login
```python
from piazza_api import Piazza

# Create Piazza instance
p = Piazza()

# Login (will prompt for email/password if not provided)
p.user_login()

# Or provide credentials directly
p.user_login(email="your.email@example.com", password="your_password")
```

---

## Getting Your Classes

### List All Your Classes
```python
# Get all classes you're enrolled in
classes = p.get_user_classes()

for cls in classes:
    print(f"Class: {cls['name']}")
    print(f"  Course Number: {cls['num']}")
    print(f"  Term: {cls['term']}")
    print(f"  Network ID: {cls['nid']}")
    print(f"  Are you a TA?: {cls['is_ta']}")
    print()
```

### Connect to a Specific Class
```python
# Use the network ID (nid) from the class info above
# Or find it in the URL: https://piazza.com/class/{network_id}
network = p.network("your_network_id_here")
```

---

## Working with Posts

### Get a List of Posts (By Most Recent)

The feed returns posts sorted by most recent updates by default.

```python
# Get the most recent posts (default limit=100, offset=0)
feed = network.get_feed(limit=50, offset=0)

# The feed contains metadata and a list of post summaries
for post_summary in feed['feed']:
    print(f"Post #{post_summary['nr']}: {post_summary.get('subject', 'No subject')}")
    print(f"  ID: {post_summary['id']}")
    print(f"  Type: {post_summary['type']}")  # 'question', 'note', or 'poll'
    print(f"  Created: {post_summary['created']}")
    print()

# Pagination example: get next 50 posts
next_page = network.get_feed(limit=50, offset=50)
```

### Iterate Through All Posts

```python
# Get all posts one by one (be careful with large classes!)
for post in network.iter_all_posts(limit=10):  # limit=10 for demo
    print(f"Post #{post['nr']}: {post['history'][0]['subject']}")

# Add sleep parameter to avoid rate limiting (in seconds)
for post in network.iter_all_posts(limit=100, sleep=1):
    # Process post
    pass
```

### Filter Posts

```python
# Get only unread posts
unread_filter = network.feed_filters.unread()
unread_feed = network.get_filtered_feed(unread_filter)

# Get posts you're following
following_filter = network.feed_filters.following()
following_feed = network.get_filtered_feed(following_filter)

# Get posts from a specific folder
folder_filter = network.feed_filters.folder("homework")
homework_feed = network.get_filtered_feed(folder_filter)
```

### Search for Posts

```python
# Search posts by keywords
results = network.search_feed("binary search tree")

for post in results['feed']:
    print(f"Found: {post.get('subject', 'No subject')}")
```

---

## Understanding Post Structure

### Fetch a Complete Post

```python
# Get a post by its number (the @123 you see on Piazza)
post = network.get_post(123)

# Or by the post ID (the hash string)
post = network.get_post("some_post_id_hash")
```

### Accessing Post Content

```python
post = network.get_post(100)

# Basic metadata
post_number = post['nr']                    # The @123 number
post_id = post['id']                        # Unique hash ID
post_type = post['type']                    # 'question', 'note', or 'poll'
created_time = post['created']              # ISO8601 timestamp
folders = post['folders']                   # List of folder names
tags = post['tags']                         # ['unanswered', 'instructor-note', etc.]
num_views = post['unique_views']            # View count

# The actual post content is in the history (most recent is index 0)
latest_version = post['history'][0]
subject = latest_version['subject']         # Post title/subject (HTML string)
content = latest_version['content']         # Post body (HTML string)
author_id = latest_version.get('uid')       # Author's user ID (if not anonymous)

# Check if post needs an answer
is_resolved = 'unanswered' not in post['tags']
has_instructor_answer = 'i_answer' in post
has_student_answer = 's_answer' in post

# Instructor's answer (if exists)
if 'i_answer' in post:
    instructor_answer = post['i_answer']['history'][0]['content']

# Student's answer (if exists)
if 's_answer' in post:
    student_answer = post['s_answer']['history'][0]['content']
```

### Extracting Text from HTML Content

The content is stored as HTML (innerHTML). You'll likely want to parse it:

```python
from html.parser import HTMLParser
import re

def strip_html(html_string):
    """Remove HTML tags from a string"""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', html_string)

post = network.get_post(100)
content_html = post['history'][0]['content']
content_text = strip_html(content_html)
print(content_text)
```

Or use a library like BeautifulSoup for better parsing:

```python
from bs4 import BeautifulSoup

content_html = post['history'][0]['content']
soup = BeautifulSoup(content_html, 'html.parser')
content_text = soup.get_text()
print(content_text)
```

---

## Comments & Discussions

### Understanding the Discussion Structure

Piazza posts have a hierarchical structure:
- **Main Post** - The original question/note
- **Instructor Answer** - Collaborative answer from instructors (optional)
- **Student Answer** - Collaborative answer from students (optional)
- **Followups** - Comments/discussions on the main post
  - **Feedback** - Replies to followup comments (nested)

### Accessing Followups (Comments)

```python
post = network.get_post(100)

# All followups are in the 'children' list
followups = post.get('children', [])

for followup in followups:
    # Followup metadata
    followup_id = followup['id']
    followup_subject = followup['subject']  # The comment text (HTML)
    followup_created = followup['created']
    followup_author = followup.get('uid')
    num_upvotes = followup.get('no_upvotes', 0)

    # Check if it's instructor-only
    is_instructor_only = followup.get('config', {}).get('ionly', False)

    print(f"Followup by {followup_author}: {strip_html(followup_subject)}")

    # Replies to this followup (feedback)
    feedback_replies = followup.get('children', [])
    for reply in feedback_replies:
        reply_subject = reply['subject']
        reply_author = reply.get('uid')
        print(f"  -> Reply by {reply_author}: {strip_html(reply_subject)}")
```

### Complete Example: Display Full Discussion

```python
def display_post_discussion(network, post_number):
    post = network.get_post(post_number)

    # Main post
    print(f"\n{'='*80}")
    print(f"POST @{post['nr']}: {strip_html(post['history'][0]['subject'])}")
    print(f"{'='*80}")
    print(strip_html(post['history'][0]['content']))

    # Instructor answer
    if 'i_answer' in post:
        print(f"\n{'─'*80}")
        print("INSTRUCTOR ANSWER:")
        print(strip_html(post['i_answer']['history'][0]['content']))

    # Student answer
    if 's_answer' in post:
        print(f"\n{'─'*80}")
        print("STUDENT ANSWER:")
        print(strip_html(post['s_answer']['history'][0]['content']))

    # Followups
    print(f"\n{'─'*80}")
    print("FOLLOWUP DISCUSSION:")
    for i, followup in enumerate(post.get('children', []), 1):
        print(f"\n[Followup {i}]")
        print(strip_html(followup['subject']))

        # Replies to followup
        for j, reply in enumerate(followup.get('children', []), 1):
            print(f"  [Reply {j}] {strip_html(reply['subject'])}")

# Usage
display_post_discussion(network, 100)
```

---

## Responding to Posts

### Create a Followup (Comment on a Post)

```python
# Comment on a post
post = network.get_post(100)

response = network.create_followup(
    post=post,  # or just the post number: 100
    content="This is my comment on the post",
    anonymous=False  # Set to True to post anonymously
)

# For instructor-only followup
response = network.create_followup(
    post=100,
    content="This is visible only to instructors",
    instructor=True  # instructor parameter makes it instructor-only
)
```

### Reply to a Followup Comment

To reply to a followup, you need to use `create_reply()` with the followup's ID:

```python
post = network.get_post(100)

# Get the first followup
followup = post['children'][0]

# Reply to it
response = network.create_reply(
    post=followup['id'],  # Use the followup's ID, not the main post
    content="This is my reply to the followup",
    anonymous=False
)
```

### Provide an Instructor Answer

```python
post = network.get_post(100)

# Check current revision (if editing existing answer)
revision = 0 if 'i_answer' not in post else len(post['i_answer']['history'])

response = network.create_instructor_answer(
    post=100,
    content="<p>Here is the instructor's answer to this question.</p>",
    revision=revision,
    anonymous=False
)
```

### Content Formatting

Content can be:
- **Plain text** - Will be displayed as-is
- **HTML** - If it contains `<p>` tags, it will be rendered as HTML

```python
# Plain text
network.create_followup(post=100, content="Simple text response")

# HTML formatted
html_content = """
<p>This is a <strong>formatted</strong> response.</p>
<ul>
  <li>Point 1</li>
  <li>Point 2</li>
</ul>
"""
network.create_followup(post=100, content=html_content)
```

---

## Advanced Features

### Create a New Post

```python
response = network.create_post(
    post_type="question",  # or "note"
    post_folders=["homework"],
    post_subject="Question about binary trees",
    post_content="<p>How do I implement a binary search tree?</p>",
    is_announcement=0,  # 1 for announcement
    bypass_email=0,     # 1 to bypass email notifications (instructor only)
    anonymous=False,    # True to post anonymously
    is_private=False    # True to make it instructor-only
)
```

### Update a Post

```python
# Update the content of a post
network.update_post(
    post=100,
    content="<p>Updated content here</p>"
)
```

### Mark Post as Resolved

```python
network.resolve_post(post=100)
```

### Get User Information

```python
# Get all users in the class
all_users = network.get_all_users()

for user in all_users:
    print(f"{user['name']} - {user['email']}")

# Get specific users
user_ids = ["user_id_1", "user_id_2"]
users = network.get_users(user_ids)
```

### Get Class Statistics

```python
stats = network.get_statistics()
print(stats)
```

---

## Complete Working Example

```python
from piazza_api import Piazza
from bs4 import BeautifulSoup

# Login
p = Piazza()
p.user_login()

# Get classes
classes = p.get_user_classes()
print("Your classes:")
for i, cls in enumerate(classes):
    print(f"{i}: {cls['name']} ({cls['nid']})")

# Select a class
class_index = 0  # Change this
network = p.network(classes[class_index]['nid'])

# Get recent posts
print("\nRecent posts:")
feed = network.get_feed(limit=10)
for post_summary in feed['feed']:
    print(f"@{post_summary['nr']}: {post_summary.get('subject', 'No subject')}")

# Get details of a specific post
post = network.get_post(feed['feed'][0]['nr'])

# Extract text
soup = BeautifulSoup(post['history'][0]['content'], 'html.parser')
print(f"\nPost content:\n{soup.get_text()}")

# Show followups
print(f"\nFollowups ({len(post.get('children', []))}):")
for followup in post.get('children', []):
    soup = BeautifulSoup(followup['subject'], 'html.parser')
    print(f"- {soup.get_text()[:100]}")

# Add a comment
network.create_followup(
    post=post['nr'],
    content="Thanks for sharing!",
    anonymous=False
)
```

---

## Tips & Best Practices

1. **Rate Limiting**: When iterating through many posts, use the `sleep` parameter to avoid being rate-limited
2. **HTML Parsing**: Always parse HTML content with BeautifulSoup or similar to extract clean text
3. **Anonymous Posts**: Check the `anon` field in posts/followups to see if they're anonymous
4. **Instructor Detection**: Check `is_ta` in your class info to see if you have instructor privileges
5. **Post IDs**: You can use either the post number (e.g., 100) or the hash ID interchangeably in most methods
6. **Error Handling**: Wrap API calls in try-except blocks to handle authentication and request errors:

```python
from piazza_api.exceptions import AuthenticationError, RequestError

try:
    post = network.get_post(100)
except RequestError as e:
    print(f"Error fetching post: {e}")
```

---

## Quick Reference

| Task | Method |
|------|--------|
| Login | `p.user_login(email, password)` |
| Get classes | `p.get_user_classes()` |
| Connect to class | `p.network(network_id)` |
| Get recent posts | `network.get_feed(limit, offset)` |
| Get specific post | `network.get_post(post_number)` |
| Get all posts | `network.iter_all_posts(limit, sleep)` |
| Search posts | `network.search_feed(query)` |
| Add comment | `network.create_followup(post, content)` |
| Reply to comment | `network.create_reply(followup_id, content)` |
| Create post | `network.create_post(...)` |
| Mark resolved | `network.resolve_post(post)` |

---

## Questions & Answers

**Q: How do I get the text from a post without HTML tags?**
```python
from bs4 import BeautifulSoup
soup = BeautifulSoup(post['history'][0]['content'], 'html.parser')
text = soup.get_text()
```

**Q: How do I know if a post has been answered?**
```python
is_answered = 'unanswered' not in post['tags']
# Or check for specific answer types:
has_instructor_answer = 'i_answer' in post
```

**Q: How do I reply to a specific comment?**
Use the followup's `id` (not the main post number) with `create_reply()`.

**Q: What's the difference between followup and feedback?**
- **Followup**: Top-level comment on the main post
- **Feedback**: Reply to a followup (nested comment)

**Q: How do I get posts sorted by most recent?**
The default `get_feed()` already sorts by most recent (`sort="updated"`).
