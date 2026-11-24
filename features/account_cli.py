"""Create accounts from a trusted server shell without exposing web signup."""
import re
import sqlite3

import click
from werkzeug.security import generate_password_hash


def register_account_cli(app, connect_db):
    @app.cli.command("create-user")
    @click.option("--username", prompt="Username")
    @click.password_option(confirmation_prompt=True)
    def create_user(username, password):
        """Create an account; passwords are prompted and never printed."""
        username = username.strip().lower()
        if not re.fullmatch(r"[a-z0-9_]{3,32}", username):
            raise click.ClickException("Username must be 3-32 lowercase letters, digits or underscores.")
        if not 10 <= len(password) <= 128:
            raise click.ClickException("Password must be 10-128 characters.")
        try:
            with connect_db() as db:
                first_user = db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
                if first_user and db.execute("SELECT 1 FROM assignments WHERE owner_id IS NULL LIMIT 1").fetchone():
                    click.confirm("The first account will own existing unowned assignments. Continue?", abort=True)
                cursor = db.execute("INSERT INTO users(username,password_hash) VALUES (?,?)",
                                    (username, generate_password_hash(password)))
                if first_user:
                    db.execute("UPDATE assignments SET owner_id=? WHERE owner_id IS NULL", (cursor.lastrowid,))
        except sqlite3.IntegrityError as exc:
            raise click.ClickException("Username already exists.") from exc
        click.echo("Account created. Sign in through the website.")
