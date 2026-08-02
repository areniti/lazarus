"""Lazarus - AI-Powered CMS"""
import sys
from pathlib import Path


def main():
    from .core.config import Config
    from .web.app import create_app

    config = Config()

    # Always save config so credentials persist
    config.save()

    # Start web server
    app = create_app()
    print()
    print("╔═══════════════════════════════════════╗")
    print("║   🔧 L A Z A R U S   v5.0.4          ║")
    print("║   AI-Powered CMS                      ║")
    print("╚═══════════════════════════════════════╝")
    print()
    print(f"  🌐 Site:       http://localhost:5000")
    print(f"  ⚙️  Admin:      http://localhost:5000/admin")
    print(f"  👤 Username:   {config.data['username']}")
    print(f"  🔑 Password:   {config.data['password']}")
    print()
    print("  💡 Press Ctrl+C to stop")
    print()

    app.run(host="0.0.0.0", port=5000)


if __name__ == "__main__":
    main()
