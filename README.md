# Metallism Forum

A lightweight Flask + SQLite web forum that supports reader, creator, and journalist roles, creator-managed book communities, a general forum section, creator profile posting, follows with a chronological social feed, two-factor authentication, and basic moderator deletion controls.

## Features
- **Roles & auth**: Register as a reader, creator, or (with an admin one-time link) journalist. All accounts require passwords plus an authenticator-app code at login. Creator usernames must match their email domain.
- **Invites**: Creator registration enforces a pre-approved invite tied to their domain email and invite code. Journalists must register through a single-use invite link created by an admin/moderator.
- **Posting rules**: Readers can post text only. Creators can post text, images, or video to their communities, general topics, or their profile page. Journalists can post text, images, or video to communities or topics. Moderator controls allow deleting any post.
- **General forum**: Post into predefined hot topics (Announcements, Hot Takes, Recommendations).
- **Creator communities**: Creators can start book-specific communities and post inside them.
- **Profile posting**: Creators can post on their own profile pages; followers see those posts in their chronological social feed.
- **Following**: Follow/unfollow users; the social feed aggregates profile posts from followed creators.

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

### Preparing creator invites
Creator accounts cannot be created without a pre-approved invite. Admins can create these invite records directly in the database using the Flask shell:

```bash
flask shell
```

```python
from app import db, CreatorInvite
invite = CreatorInvite(domain_email="author@their-domain.com", invite_code="RANDOM-CODE-1234")
db.session.add(invite)
db.session.commit()
```

The invite enforces the exact domain email and one-time code during creator registration and is automatically marked as used once redeemed. Creator usernames must match the email domain (e.g., `author@mybooks.com` -> username `mybooks.com`).

### Preparing journalist invites
Moderators can create one-time registration links for journalists via the **Journalist Invites** nav link (visible only to moderators). The generated link pre-fills the journalist invite token; registering with it consumes the invite so it cannot be reused.

## Usage tips
- Use the **Register** page to create accounts. Check the moderator box to test moderation controls. Journalists must start from an invite link.
- After registering, add the provided secret to an authenticator app (e.g., Google Authenticator) and enter the 6-digit codes when logging in.
- Creators can start a community from the home page and post to their own profile. Readers are limited to text posts, while creators and journalists can attach image or video URLs.
- The **Social Feed** page shows profile posts from users you follow.
