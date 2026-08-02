"""Config Management"""
import json
import secrets
from pathlib import Path


class Config:
    """Central configuration"""

    def __init__(self):
        self.base_dir = Path.home() / ".lazarus"
        self.config_file = self.base_dir / "config.json"
        self.output_dir = self.base_dir / "output"
        self.data = self._load()

    def _load(self):
        if self.config_file.exists():
            return json.loads(self.config_file.read_text("utf-8"))
        return {
            "username": "admin",
            "password": self._gen_password(),
            "domain": "",
            "api": {"url": "", "key": "", "model": "mimo-v2.5-free"},
            "models": [],
            "is_first_run": True,
        }

    def save(self):
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False), "utf-8"
        )

    def login(self, username, password):
        return username == self.data["username"] and password == self.data["password"]

    def add_model(self, name, url, key):
        """Add a saved model"""
        if "models" not in self.data:
            self.data["models"] = []
        self.data["models"].append({"name": name, "url": url, "key": key})
        self.save()

    def remove_model(self, index):
        """Remove a saved model"""
        if "models" in self.data and 0 <= index < len(self.data["models"]):
            self.data["models"].pop(index)
            self.save()

    @staticmethod
    def _gen_password():
        return secrets.token_urlsafe(12)
