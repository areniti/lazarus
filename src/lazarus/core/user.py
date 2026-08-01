"""User Management - simple role-based"""
ROLES = {"admin", "developer"}


class User:
    def __init__(self, username, role="developer"):
        self.username = username
        self.role = role if role in ROLES else "developer"

    def is_admin(self):
        return self.role == "admin"

    def is_developer(self):
        return self.role == "developer"
