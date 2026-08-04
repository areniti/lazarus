"""Config Management - credentials are hashed, never stored in plaintext."""
import hashlib
import hmac
import json
import secrets
import string
from pathlib import Path

# PBKDF2 parameters
_HASH_NAME = "sha256"
_ITERATIONS = 200_000
_SALT_BYTES = 16


class Config:
    """Central configuration stored in ~/.lazarus/config.json"""

    def __init__(self):
        self.base_dir = Path.home() / ".lazarus"
        self.config_file = self.base_dir / "config.json"
        self.output_dir = self.base_dir / "output"
        self.data = self._load()
        self._migrate()

    # ===== load / save =====

    def _load(self):
        if self.config_file.exists():
            try:
                return json.loads(self.config_file.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                # Corrupt config: keep a backup instead of silently losing it
                backup = self.config_file.with_suffix(".json.broken")
                try:
                    backup.write_text(self.config_file.read_text("utf-8"), "utf-8")
                except OSError:
                    pass
        return self._first_run_data()

    def _first_run_data(self):
        username = self._gen_username()
        password = self._gen_password()
        data = {
            "username": username,
            "password_hash": self.hash_password(password),
            "secret_key": secrets.token_hex(32),
            "domain": "",
            "api": {"url": "", "key": "", "model": "mimo-v2.5-free"},
            "models": [],
            "is_first_run": True,
        }
        # Plaintext is kept ONLY in memory for this process so __main__ can
        # print it once. It is never written to disk.
        self.generated_password = password
        return data

    def _migrate(self):
        """Upgrade older configs (plaintext password, missing secret key)."""
        changed = False

        # Old versions stored the password in plaintext.
        if "password" in self.data:
            plain = self.data.pop("password")
            if plain and not self.data.get("password_hash"):
                self.data["password_hash"] = self.hash_password(plain)
            changed = True

        # Old versions stored a setup hash of username:password.
        if "setup_hash" in self.data:
            self.data.pop("setup_hash")
            changed = True

        if not self.data.get("secret_key"):
            self.data["secret_key"] = secrets.token_hex(32)
            changed = True

        self.data.setdefault("api", {"url": "", "key": "", "model": "mimo-v2.5-free"})
        self.data.setdefault("models", [])
        self.data.setdefault("domain", "")
        self.data.setdefault("is_first_run", False)

        # Older versions never cleared is_first_run after setup. If the username
        # is no longer a generated one, setup clearly already happened — leaving
        # the flag set would send the user to a setup page asking for generated
        # credentials that no longer exist, locking them out.
        if (self.data.get("is_first_run")
                and self.data.get("password_hash")
                and not str(self.data.get("username", "")).startswith("usr_")):
            self.data["is_first_run"] = False
            changed = True

        if changed:
            self.save()

    def save(self):
        self.base_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.config_file.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False), "utf-8"
        )
        tmp.replace(self.config_file)
        try:
            self.config_file.chmod(0o600)
        except OSError:
            pass

    # ===== auth =====

    def login(self, username, password):
        if not username or not password:
            return False
        if not hmac.compare_digest(str(username), str(self.data.get("username", ""))):
            return False
        return self.verify_password(password)

    def verify_password(self, password):
        stored = self.data.get("password_hash", "")
        try:
            algo, iterations, salt_hex, digest_hex = stored.split("$")
            iterations = int(iterations)
        except (ValueError, AttributeError):
            return False
        candidate = hashlib.pbkdf2_hmac(
            algo, password.encode(), bytes.fromhex(salt_hex), iterations
        ).hex()
        return hmac.compare_digest(candidate, digest_hex)

    def set_password(self, password):
        self.data["password_hash"] = self.hash_password(password)
        self.save()

    def complete_setup(self, new_username, new_password):
        """Called after first-time setup is verified."""
        self.data["username"] = new_username
        self.data["password_hash"] = self.hash_password(new_password)
        self.data["is_first_run"] = False
        self.save()

    @staticmethod
    def hash_password(password):
        salt = secrets.token_bytes(_SALT_BYTES)
        digest = hashlib.pbkdf2_hmac(
            _HASH_NAME, password.encode(), salt, _ITERATIONS
        ).hex()
        return f"{_HASH_NAME}${_ITERATIONS}${salt.hex()}${digest}"

    # ===== models =====

    def add_model(self, name, url, key):
        self.data.setdefault("models", []).append(
            {"name": name, "url": url, "key": key}
        )
        self.save()

    def remove_model(self, index):
        models = self.data.get("models", [])
        if 0 <= index < len(models):
            models.pop(index)
            self.save()

    # ===== template-safe view =====

    def public_data(self):
        """Config without secrets that must never reach a template/response."""
        safe = {k: v for k, v in self.data.items()
                if k not in ("password_hash", "secret_key")}
        return safe

    # ===== generators =====

    @staticmethod
    def _gen_username():
        chars = string.ascii_letters + string.digits
        return "usr_" + "".join(secrets.choice(chars) for _ in range(10))

    @staticmethod
    def _gen_password():
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        chars = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            secrets.choice("!@#$%^&*"),
        ]
        chars += [secrets.choice(alphabet) for _ in range(16)]
        rng = secrets.SystemRandom()
        rng.shuffle(chars)
        return "".join(chars)
