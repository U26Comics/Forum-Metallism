# Metallism Forum

A lightweight Flask + SQLite web forum that supports reader and creator roles, creator-managed book communities, a general forum section, creator profile posting, follows with a chronological social feed, and basic moderator deletion controls.

## Features
- **Roles**: Register as a reader or creator (with an optional moderator flag for testing).
- **General forum**: Post into predefined hot topics (Announcements, Hot Takes, Recommendations).
- **Creator communities**: Creators can start book-specific communities and post inside them.
- **Profile posting**: Creators can post on their own profile pages; followers see those posts in their chronological social feed.
- **Following**: Follow/unfollow users; the social feed aggregates profile posts from followed creators.
- **Moderation**: Moderators can delete any post from general topics, communities, or profile feeds.

## Running locally
1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the app:
   ```bash
   flask --app app run --debug
   ```
   The first start will create `forum.db` and seed the default forum topics.

## Usage tips
- Use the **Register** page to create accounts. Check the moderator box to test moderation controls.
- Creators can start a community from the home page and post to their own profile.
- The **Social Feed** page shows profile posts from users you follow.
