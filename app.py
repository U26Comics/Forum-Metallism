import os
from datetime import datetime

from flask import Flask, redirect, render_template, request, session, url_for, flash
from urllib.parse import urlparse
from flask_sqlalchemy import SQLAlchemy


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "forum.db")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "dev-secret-key"

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    role = db.Column(db.String(20), nullable=False)  # reader or creator
    is_moderator = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    communities = db.relationship("Community", backref="creator", lazy=True)
    posts = db.relationship("Post", backref="author", lazy=True)

    def __repr__(self):
        return f"<User {self.username}>"


class Community(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    book_title = db.Column(db.String(200), nullable=True)
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    posts = db.relationship("Post", backref="community", lazy=True)

    def __repr__(self):
        return f"<Community {self.name}>"


class GeneralTopic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)

    posts = db.relationship("Post", backref="general_topic", lazy=True)

    def __repr__(self):
        return f"<GeneralTopic {self.name}>"


class Follow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    followee_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    follower = db.relationship("User", foreign_keys=[follower_id], backref="following")
    followee = db.relationship("User", foreign_keys=[followee_id], backref="followers")


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    community_id = db.Column(db.Integer, db.ForeignKey("community.id"), nullable=True)
    general_topic_id = db.Column(db.Integer, db.ForeignKey("general_topic.id"), nullable=True)
    profile_owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    profile_owner = db.relationship("User", foreign_keys=[profile_owner_id], backref="profile_posts")

    def __repr__(self):
        return f"<Post {self.title}>"


@app.before_first_request
def setup_defaults():
    db.create_all()
    seed_general_topics()


def seed_general_topics():
    default_topics = [
        ("Announcements", "General updates and platform news"),
        ("Hot Takes", "Opinionated discussions and debates"),
        ("Recommendations", "Suggest books, creators, or communities"),
    ]
    existing = {topic.name for topic in GeneralTopic.query.all()}
    for name, description in default_topics:
        if name not in existing:
            db.session.add(GeneralTopic(name=name, description=description))
    db.session.commit()


def current_user():
    user_id = session.get("user_id")
    if user_id:
        return User.query.get(user_id)
    return None


def login_required(route_function):
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("Please log in to continue.")
            return redirect(url_for("login"))
        return route_function(*args, **kwargs)

    wrapper.__name__ = route_function.__name__
    return wrapper


def moderator_required(route_function):
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or not user.is_moderator:
            flash("Moderator permissions required.")
            return redirect(url_for("index"))
        return route_function(*args, **kwargs)

    wrapper.__name__ = route_function.__name__
    return wrapper


@app.route("/")
def index():
    topics = GeneralTopic.query.all()
    communities = Community.query.order_by(Community.created_at.desc()).all()
    creators = User.query.filter_by(role="creator").order_by(User.username).all()
    return render_template(
        "index.html",
        user=current_user(),
        topics=topics,
        communities=communities,
        creators=creators,
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        role = request.form.get("role")
        is_moderator = bool(request.form.get("is_moderator"))

        if not username or role not in {"reader", "creator"}:
            flash("Please provide a username and choose a role.")
            return redirect(url_for("register"))

        if User.query.filter_by(username=username).first():
            flash("Username already exists.")
            return redirect(url_for("register"))

        user = User(username=username, role=role, is_moderator=is_moderator)
        db.session.add(user)
        db.session.commit()
        session["user_id"] = user.id
        flash("Registration successful.")
        return redirect(url_for("index"))

    return render_template("register.html", user=current_user())


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        user = User.query.filter_by(username=username).first()
        if user:
            session["user_id"] = user.id
            flash("Logged in successfully.")
            return redirect(url_for("index"))
        flash("User not found. Please register first.")
        return redirect(url_for("login"))

    return render_template("login.html", user=current_user())


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("You have been logged out.")
    return redirect(url_for("index"))


@app.route("/communities/create", methods=["GET", "POST"])
@login_required
def create_community():
    user = current_user()
    if user.role != "creator":
        flash("Only creators can start book communities.")
        return redirect(url_for("index"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        book_title = request.form.get("book_title", "").strip()

        if not name:
            flash("Community name is required.")
            return redirect(url_for("create_community"))

        community = Community(
            name=name, description=description, book_title=book_title, creator_id=user.id
        )
        db.session.add(community)
        db.session.commit()
        flash("Community created.")
        return redirect(url_for("community_detail", community_id=community.id))

    return render_template("create_community.html", user=user)


@app.route("/communities/<int:community_id>")
def community_detail(community_id):
    community = Community.query.get_or_404(community_id)
    posts = (
        Post.query.filter_by(community_id=community.id)
        .order_by(Post.created_at.desc())
        .all()
    )
    return render_template(
        "community_detail.html",
        community=community,
        posts=posts,
        user=current_user(),
    )


@app.route("/topics/<int:topic_id>")
def general_topic(topic_id):
    topic = GeneralTopic.query.get_or_404(topic_id)
    posts = (
        Post.query.filter_by(general_topic_id=topic.id)
        .order_by(Post.created_at.desc())
        .all()
    )
    return render_template(
        "general_topic.html", topic=topic, posts=posts, user=current_user()
    )


@app.route("/users/<int:user_id>")
def profile(user_id):
    owner = User.query.get_or_404(user_id)
    posts = (
        Post.query.filter_by(profile_owner_id=owner.id)
        .order_by(Post.created_at.desc())
        .all()
    )
    user = current_user()
    is_following = False
    if user:
        is_following = (
            Follow.query.filter_by(follower_id=user.id, followee_id=owner.id).first()
            is not None
        )
    return render_template(
        "profile.html",
        owner=owner,
        posts=posts,
        is_following=is_following,
        user=user,
    )


@app.route("/posts/create", methods=["GET", "POST"])
@login_required
def create_post():
    user = current_user()
    communities = Community.query.order_by(Community.name).all()
    topics = GeneralTopic.query.order_by(GeneralTopic.name).all()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        community_id = request.form.get("community_id")
        topic_id = request.form.get("topic_id")
        profile_post = request.form.get("profile_post")

        if not title or not content:
            flash("Title and content are required.")
            return redirect(url_for("create_post"))

        post = Post(title=title, content=content, author_id=user.id)

        if profile_post:
            if user.role != "creator":
                flash("Only creators can post on a profile page.")
                return redirect(url_for("create_post"))
            post.profile_owner_id = user.id
        elif community_id:
            post.community_id = int(community_id)
        elif topic_id:
            post.general_topic_id = int(topic_id)
        else:
            flash("Choose a destination for your post.")
            return redirect(url_for("create_post"))

        db.session.add(post)
        db.session.commit()

        flash("Post created.")
        if post.profile_owner_id:
            return redirect(url_for("profile", user_id=user.id))
        if post.community_id:
            return redirect(url_for("community_detail", community_id=post.community_id))
        return redirect(url_for("general_topic", topic_id=post.general_topic_id))

    return render_template(
        "create_post.html",
        user=user,
        communities=communities,
        topics=topics,
    )


@app.route("/follow/<int:user_id>")
@login_required
def follow(user_id):
    follower = current_user()
    if follower.id == user_id:
        flash("You cannot follow yourself.")
        return redirect(url_for("profile", user_id=user_id))

    existing = Follow.query.filter_by(follower_id=follower.id, followee_id=user_id).first()
    if existing:
        flash("You already follow this creator.")
        return redirect(url_for("profile", user_id=user_id))

    followee = User.query.get_or_404(user_id)
    db.session.add(Follow(follower_id=follower.id, followee_id=followee.id))
    db.session.commit()
    flash("Now following this user.")
    return redirect(url_for("profile", user_id=user_id))


@app.route("/unfollow/<int:user_id>")
@login_required
def unfollow(user_id):
    follower = current_user()
    relation = Follow.query.filter_by(follower_id=follower.id, followee_id=user_id).first()
    if relation:
        db.session.delete(relation)
        db.session.commit()
        flash("Unfollowed user.")
    return redirect(url_for("profile", user_id=user_id))


@app.route("/feed")
@login_required
def social_feed():
    user = current_user()
    follow_ids = [f.followee_id for f in user.following]
    posts = (
        Post.query.filter(Post.profile_owner_id.in_(follow_ids))
        .order_by(Post.created_at.desc())
        .all()
    )
    return render_template("social_feed.html", posts=posts, user=user)


@app.route("/posts/<int:post_id>/delete", methods=["POST"])
@moderator_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash("Post deleted.")
    referrer = request.referrer or ""
    referrer = referrer.replace("\\", "")
    parsed_referrer = urlparse(referrer)
    if not parsed_referrer.netloc and not parsed_referrer.scheme:
        destination = referrer
    else:
        destination = url_for("index")
    return redirect(destination)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_general_topics()
    app.run()
