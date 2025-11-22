import os
from datetime import datetime

import secrets

import pyotp
from flask import Flask, redirect, render_template, request, session, url_for, flash
from werkzeug.security import check_password_hash, generate_password_hash
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
    email = db.Column(db.String(255), unique=True, nullable=True)
    role = db.Column(db.String(20), nullable=False)  # reader, creator, journalist
    password_hash = db.Column(db.String(255), nullable=False)
    otp_secret = db.Column(db.String(32), nullable=False)
    is_moderator = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    communities = db.relationship("Community", backref="creator", lazy=True)
    posts = db.relationship("Post", backref="author", lazy=True)

    def __repr__(self):
        return f"<User {self.username}>"


class CreatorInvite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    domain_email = db.Column(db.String(255), unique=True, nullable=False)
    invite_code = db.Column(db.String(64), nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<CreatorInvite {self.domain_email}>"


class JournalistInvite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contact_email = db.Column(db.String(255), nullable=True)
    token = db.Column(db.String(64), unique=True, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<JournalistInvite {self.token}>"


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
    media_url = db.Column(db.String(500), nullable=True)
    media_type = db.Column(db.String(20), default="text")
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


@app.route("/journalist_invites/create", methods=["GET", "POST"])
@moderator_required
def create_journalist_invite():
    token = None
    if request.method == "POST":
        email = request.form.get("contact_email", "").strip() or None
        token = secrets.token_urlsafe(24)
        invite = JournalistInvite(contact_email=email, token=token)
        db.session.add(invite)
        db.session.commit()
        flash("Journalist invite created. Share the generated link.")

    return render_template(
        "create_journalist_invite.html",
        user=current_user(),
        token=token,
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    journalist_token = request.args.get("journalist_token") or request.form.get(
        "journalist_token", ""
    )
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        role = request.form.get("role")
        password = request.form.get("password", "")
        otp_secret = pyotp.random_base32()
        is_moderator = bool(request.form.get("is_moderator"))
        creator_key = request.form.get("creator_key", "").strip()
        invite_token = journalist_token.strip()

        if not username or role not in {"reader", "creator", "journalist"}:
            flash("Please provide a username and choose a role.")
            return redirect(url_for("register"))

        if User.query.filter_by(username=username).first():
            flash("Username already exists.")
            return redirect(url_for("register"))

        if not password:
            flash("Password is required.")
            return redirect(url_for("register"))

        if email and User.query.filter_by(email=email).first():
            flash("Email already associated with another account.")
            return redirect(url_for("register"))

        if role == "creator":
            if not email or not creator_key:
                flash("Creator email and invite code are required.")
                return redirect(url_for("register"))

            domain = email.split("@")[-1]
            if username != domain:
                flash("Creator username must match the email domain.")
                return redirect(url_for("register"))

            invite = CreatorInvite.query.filter_by(
                domain_email=email, invite_code=creator_key, is_used=False
            ).first()

            if not invite:
                flash("Invalid or already used creator invite code.")
                return redirect(url_for("register"))

        if role == "journalist":
            invite = JournalistInvite.query.filter_by(
                token=invite_token, is_used=False
            ).first()
            if not invite:
                flash("A valid journalist invite link is required.")
                return redirect(url_for("register"))

        user = User(
            username=username,
            email=email or None,
            role=role,
            password_hash=generate_password_hash(password),
            otp_secret=otp_secret,
            is_moderator=is_moderator,
        )
        db.session.add(user)

        if role == "creator":
            invite.is_used = True
        if role == "journalist":
            invite.is_used = True

        db.session.commit()
        session["user_id"] = user.id
        flash(
            "Registration successful. Add this secret to your authenticator app: "
            f"{otp_secret}"
        )
        return redirect(url_for("index"))

    valid_journalist = None
    if journalist_token:
        valid_journalist = JournalistInvite.query.filter_by(
            token=journalist_token, is_used=False
        ).first()

    return render_template(
        "register.html",
        user=current_user(),
        journalist_token=journalist_token,
        journalist_invite=valid_journalist,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        otp_code = request.form.get("otp_code", "")
        user = User.query.filter_by(username=username).first()
        if not user:
            flash("User not found. Please register first.")
            return redirect(url_for("login"))

        if not check_password_hash(user.password_hash, password):
            flash("Invalid credentials.")
            return redirect(url_for("login"))

        if not otp_code or not pyotp.TOTP(user.otp_secret).verify(otp_code, valid_window=1):
            flash("Invalid or missing authentication code.")
            return redirect(url_for("login"))

        session["user_id"] = user.id
        flash("Logged in successfully.")
        return redirect(url_for("index"))

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
        media_type = request.form.get("media_type", "text")
        media_url = request.form.get("media_url", "").strip()

        if not title or not content:
            flash("Title and content are required.")
            return redirect(url_for("create_post"))

        if media_type not in {"text", "image", "video"}:
            flash("Invalid media type.")
            return redirect(url_for("create_post"))

        if user.role == "reader" and media_type != "text":
            flash("Readers may only post text content.")
            return redirect(url_for("create_post"))

        if user.role == "creator" and media_type not in {"text", "image", "video"}:
            flash("Creators can post text, images, or videos.")
            return redirect(url_for("create_post"))

        if user.role == "journalist" and media_type not in {"text", "image", "video"}:
            flash("Journalists can post text, images, or videos.")
            return redirect(url_for("create_post"))

        if media_type in {"image", "video"} and not media_url:
            flash("A media URL is required for image or video posts.")
            return redirect(url_for("create_post"))

        post = Post(
            title=title,
            content=content,
            author_id=user.id,
            media_type=media_type,
            media_url=media_url or None,
        )

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
    posts = []
    if follow_ids:
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
    destination = request.referrer or url_for("index")
    return redirect(destination)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_general_topics()
    app.run(debug=True)
