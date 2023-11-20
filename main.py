import os
import datetime
import time
import re
from html import escape
import imghdr
import smtplib
from email.message import EmailMessage

import requests

import flask
from flask import request
import flask_login
import werkzeug.security

import flask_sqlalchemy
import sqlalchemy
import sqlalchemy.orm
from sqlalchemy import exc

import wtforms

from jinja2.filters import FILTERS


NUMBER_OF_POSTS_PER_PAGE = 5


MY_EMAIL = os.environ.get("PYTHON_EMAIL")
MY_PASSWORD = os.environ.get("PYTHON_EMAIL_KEY")
TO_EMAIL = ""
with open(os.path.join("", "email.key"), "r") as f:
    TO_EMAIL = f.readline()


app = flask.Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///posts.db"
app.config["SQLALCHEMY_BINDS"] = {
    "users": "sqlite:///users.db",
}
with open(os.path.join("", "app.key"), "r") as f:
    conf = f.readline()
app.secret_key = conf


db = flask_sqlalchemy.SQLAlchemy()
db.init_app(app)


login_manager = flask_login.LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


def debug(text):
    print(type(text))


FILTERS["debug"] = debug


def main():
    with app.app_context():
        db.create_all()
        db.create_all(bind_key="users")
    app.run(debug=True)


############## DB RELATED ###############
class Post(db.Model):
    id = sqlalchemy.orm.mapped_column(sqlalchemy.Integer, primary_key=True, unique=True)
    title = sqlalchemy.orm.mapped_column(sqlalchemy.String(250), unique=True, nullable=False)
    subtitle = sqlalchemy.orm.mapped_column(sqlalchemy.String(250), nullable=False)
    body = sqlalchemy.orm.mapped_column(sqlalchemy.String(250), nullable=False)
    author = sqlalchemy.orm.mapped_column(sqlalchemy.String(250), nullable=False)
    date = sqlalchemy.orm.mapped_column(sqlalchemy.DateTime(True), nullable=False)
    img_url = sqlalchemy.orm.mapped_column(sqlalchemy.String(250), nullable=True)

    def separate_body(self):
        return self.body.split("\n")


class User(flask_login.UserMixin, db.Model):
    __bind_key__ = "users"
    id = sqlalchemy.orm.mapped_column(sqlalchemy.Integer, primary_key=True, unique=True)
    name = sqlalchemy.orm.mapped_column(sqlalchemy.String(250), unique=True, nullable=False)
    email = sqlalchemy.orm.mapped_column(sqlalchemy.String(250), unique=True, nullable=False)
    password = sqlalchemy.orm.mapped_column(sqlalchemy.String(250), nullable=False)


def fill_mock_data():
    with open(os.path.join("", "static", "assets", "mock-data.data")) as f:
        data = f.read().splitlines()
    for i in range(0, 10):
        print(i)
        print(data[i * 3])
        print(data[i * 3 + 1])
        print(data[i * 3 + 2])
        add_post(
            title=data[i * 3],
            subtitle=data[i * 3 + 1],
            body=data[i * 3 + 2],
            author="Axy",
            date=datetime.datetime.now(),
            img_url="",
        )
        time.sleep(1)


def fill_long_post():
    with open(os.path.join("", "static", "assets", "long_post.data")) as f:
        data = f.read().split("\n", 2)
    add_post(
        title=data[0],
        subtitle=data[1],
        body=data[2],
        author="Axy",
        date=datetime.datetime.now(),
        img_url="https://images.unsplash.com/photo-1639134501889-66bc86217baa?q=80&w=3738&auto=format&fit=crop&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
    )


def add_post(title: str, subtitle: str, body: str, author: str, date, img_url: str):
    with app.app_context():
        db.session.add(Post(title=title, subtitle=subtitle, body=body, author=author, date=date, img_url=img_url))
        db.session.commit()


def get_posts(num=0):
    number_of_posts_to_fetch = NUMBER_OF_POSTS_PER_PAGE
    with app.app_context():
        posts = db.session.execute(
            sqlalchemy.select(Post)
            .order_by(Post.date.desc())
            .limit(number_of_posts_to_fetch)
            .offset(num * number_of_posts_to_fetch),
            execution_options={"prebuffer_rows": True},
        ).scalars()
    return posts


def get_post(id):
    with app.app_context():
        post = db.get_or_404(Post, id)
    stripped_body = escape(post.body)
    exp1 = re.compile("{{img}}")
    exp2 = re.compile("{{/img}}")
    stripped_body = re.sub(exp1, "<img src='", stripped_body)
    stripped_body = re.sub(exp2, "'/>", stripped_body)
    post.body = stripped_body
    return post


def get_posts_by_user(user, num=0):
    number_of_posts_to_fetch = NUMBER_OF_POSTS_PER_PAGE
    with app.app_context():
        posts = db.session.execute(
            sqlalchemy.select(Post)
            .where(Post.author == user)
            .order_by(Post.date.desc())
            .limit(number_of_posts_to_fetch)
            .offset(number_of_posts_to_fetch * num),
            execution_options={"prebuffer_rows": True},
        ).scalars()
    return posts


def update_post(id: int, title: str, subtitle: str, body: str, img_url: str):
    with app.app_context():
        db.session.execute(
            sqlalchemy.update(Post),
            [
                {
                    "id": id,
                    "title": title,
                    "subtitle": subtitle,
                    "body": body,
                    "date": datetime.datetime.now(),
                    "img_url": img_url,
                }
            ],
        )
        db.session.commit()


def add_user(name: str, email: str, password: str):
    with app.app_context():
        new_user = User(
            name=name.strip(),
            email=email.strip(),
            password=werkzeug.security.generate_password_hash(password, method="scrypt:32768:32:2", salt_length=20),
        )
        db.session.add(new_user)
        db.session.commit()


def get_user(name: str):
    with app.app_context():
        user = db.session.execute(sqlalchemy.select(User).where(User.name == name.strip())).scalar()
    return user


############## DB RELATED ###############


############## FORM RELATED ###############
class ContactForm(wtforms.Form):
    name = wtforms.StringField(
        label="Name",
        validators=[
            wtforms.validators.DataRequired(),
            wtforms.validators.Length(min=1, message="The name should be at least 1 character long."),
        ],
    )
    email = wtforms.EmailField(
        label="Email",
        validators=[
            wtforms.validators.DataRequired(),
            wtforms.validators.Email("This is not a valid email address."),
        ],
    )
    message = wtforms.StringField(label="Message", validators=[wtforms.validators.DataRequired()])


def send_contact_mail(form: ContactForm):
    msg = EmailMessage()
    msg["Subject"] = "Our Blog message"
    msg["From"] = "me"
    msg["To"] = "Our Blog"
    msg.set_content(
        f"""
Dear Our Blog,

you have received a mail from {form.name.data} {form.email.data}!

{form.message.data}"""
    )

    # TODO the sending of the mail has been commented out
    # with smtplib.SMTP("smtp.gmail.com", port=587) as smtp:
    #     smtp.starttls()
    #     smtp.login(MY_EMAIL, MY_PASSWORD)
    #     smtp.sendmail(MY_EMAIL, TO_EMAIL, msg.as_string())


class ValidateImg:
    def __init__(self, message="This is not a valid url for an img.") -> None:
        self.message = message

    def __call__(self, form, field):
        url = field.data.strip() or None
        if url != "" and url is not None:
            try:
                img_type = imghdr.what("", requests.get(url, timeout=10).content)
            except Exception as err:
                raise wtforms.validators.ValidationError(err)
            if not img_type:
                raise wtforms.validators.ValidationError(self.message)


class NewPost(wtforms.Form):
    title = wtforms.StringField(
        label="Title",
        validators=[
            wtforms.validators.DataRequired(),
            wtforms.validators.Length(min=5, message="The title for the post should be at least 5 characters long."),
        ],
    )
    subtitle = wtforms.StringField(
        label="Subtitle",
        validators=[
            wtforms.validators.DataRequired(),
            wtforms.validators.Length(
                min=10, message="The subtitle for the post should be at least 10 characters long."
            ),
        ],
    )
    body = wtforms.StringField(
        label="Post body",
        validators=[
            wtforms.validators.DataRequired(),
            wtforms.validators.Length(min=10, message="The body for the post should be at least 10 characters long."),
        ],
    )
    img_url = wtforms.StringField(
        label="Post background image URL",
        validators=[ValidateImg()],
    )


class NewUser(wtforms.Form):
    name = wtforms.StringField(
        label="Name",
        validators=[
            wtforms.validators.DataRequired(),
            wtforms.validators.Length(min=3, message="Name must be at least 3 characters long."),
        ],
    )
    email = wtforms.EmailField(
        label="Email",
        validators=[
            wtforms.validators.DataRequired(),
            wtforms.validators.Email(message="This is not a valid email address"),
        ],
    )
    password = wtforms.PasswordField(
        label="Password",
        validators=[
            wtforms.validators.DataRequired(),
            wtforms.validators.Regexp(
                regex="^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?!.* ).{8,}$",
                message="Password must be at least 8 characters long.",
            ),
        ],
    )
    repeat_password = wtforms.PasswordField(
        label="Repeat password",
        validators=[
            wtforms.validators.DataRequired(),
            wtforms.validators.EqualTo(fieldname="password", message="Passwords must match."),
        ],
    )


class LoginForm(wtforms.Form):
    name = wtforms.StringField(label="Name", validators=[wtforms.validators.DataRequired()])
    password = wtforms.PasswordField(label="Password", validators=[wtforms.validators.DataRequired()])


############## FORM RELATED ###############


############## VIEW RELATED ###############


# TODO convert UTC time to client local time?
@app.route("/")
def home():
    # fill_long_post()
    posts = get_posts().fetchall()
    return flask.render_template("index.html", posts=posts, page=0)


@app.route("/<int:page>")
def page(page):
    if page < 1:
        return flask.redirect(flask.url_for("home"))
    posts = get_posts(page - 1).fetchall()
    return flask.render_template("index.html", posts=posts, page=page)


@app.route("/<user>/<int:page>")
def users_posts(user, page):
    if not page or page < 2:
        posts = get_posts_by_user(user=user).fetchall()
        return flask.render_template("users_posts.html", posts=posts, page=1, user=user)
    else:
        posts = get_posts_by_user(user=user, num=page - 1).fetchall()
        return flask.render_template("users_posts.html", posts=posts, page=page, user=user)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if flask.request.method == "POST":
        form = ContactForm(request.form)
        if form.validate():
            send_contact_mail(form)
            flask.flash("The message has been successfully sent.")
            return flask.redirect(flask.url_for("home"))
        else:
            return flask.render_template("contact.html", form=form)
    else:
        form = ContactForm()
        return flask.render_template("contact.html", form=form)


@app.route("/about")
def about():
    return flask.render_template("about.html")


# TODO make comment section
@app.route("/post/<int:id>")
def view_post(id):
    post = get_post(id)
    return flask.render_template("post.html", post=post)


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        form = NewUser(request.form)
        if form.validate():
            try:
                add_user(name=form.name.data, email=form.email.data, password=form.password.data)
                return flask.redirect(flask.url_for("login"))
            except exc.IntegrityError:
                return flask.render_template("register.html", form=form, error="Name or email already taken.")
        else:
            return flask.render_template("register.html", form=form)

    form = NewUser()
    return flask.render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        form = LoginForm(request.form)
        with app.app_context():
            user = db.session.execute(sqlalchemy.select(User).where(User.name == form.name.data.strip())).scalar()
        if user:
            if werkzeug.security.check_password_hash(user.password, form.password.data):
                flask_login.login_user(user)
                flask.flash(f"Successfully logged in as {user.name}")
                return flask.redirect(flask.url_for("home"))
            else:
                error = "Invalid password."
                return flask.render_template("login.html", form=form, error=error)
        else:
            error = "Incorrect username"
            return flask.render_template("login.html", form=form, error=error)

    form = LoginForm()
    return flask.render_template("login.html", form=form)


@app.route("/create", methods=["GET", "POST"])
@flask_login.login_required
def create_post():
    if request.method == "POST":
        form = NewPost(request.form)
        if form.validate():
            try:
                add_post(
                    title=form.title.data,
                    subtitle=form.subtitle.data,
                    body=form.body.data,
                    author=flask_login.current_user.name,
                    date=datetime.datetime.now(),
                    img_url=form.img_url.data,
                )
            except exc.IntegrityError as err:
                return flask.render_template("create.html", form=form, error=err.orig)
        else:
            return flask.render_template("create.html", form=form)
    form = NewPost()
    return flask.render_template("create.html", form=form)


@app.route("/edit/<int:post_id>", methods=["GET", "POST"])
@flask_login.login_required
def edit_post(post_id):
    with app.app_context():
        post = db.get_or_404(Post, post_id)
    bg = post.img_url
    if request.method == "POST":
        form = NewPost(request.form)
        if form.validate():
            try:
                update_post(
                    id=post_id,
                    title=form.title.data,
                    subtitle=form.subtitle.data,
                    body=form.body.data,
                    img_url=form.img_url.data,
                )
            except Exception as err:
                return flask.render_template("edit.html", bg=bg, form=form, post_id=post_id, error=err)
            return flask.redirect(flask.url_for("view_post", id=post_id))
        else:
            return flask.render_template("edit.html", bg=bg, form=form, post_id=post_id)
    form = NewPost(title=post.title, subtitle=post.subtitle, body=post.body, img_url=post.img_url)
    return flask.render_template("edit.html", bg=bg, form=form, post_id=post_id)


@app.route("/logout")
@flask_login.login_required
def logout():
    flask_login.logout_user()
    flask.flash("You have logged out.")
    return flask.redirect(flask.url_for("home"))


############## VIEW RELATED ###############


if __name__ == "__main__":
    main()
