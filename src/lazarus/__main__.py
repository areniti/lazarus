"""Lazarus - AI-Powered CMS entry point."""
import argparse
import os

from . import __version__


def main():
    parser = argparse.ArgumentParser(prog="lazarus", description="AI-Powered CMS")
    parser.add_argument("--host", default="127.0.0.1",
                        help="bind address (default: 127.0.0.1, use 0.0.0.0 to expose)")
    parser.add_argument("--port", type=int, default=5000, help="port (default: 5000)")
    parser.add_argument("--version", action="version",
                        version=f"lazarus-cms {__version__}")
    args = parser.parse_args()

    from .core.config import Config
    from .web.app import create_app

    config = Config()
    is_first = config.data.get("is_first_run", False)
    generated_password = getattr(config, "generated_password", None)
    config.save()

    app = create_app()

    print()
    print("╔═══════════════════════════════════════╗")
    print(f"║   🔧 L A Z A R U S   v{__version__:<15}║")
    print("║   AI-Powered CMS                      ║")
    print("╚═══════════════════════════════════════╝")
    print()

    if is_first and generated_password:
        print("  ⚠️  FIRST RUN — Setup Required!")
        print()
        print("  Use these credentials once, then set your own:")
        print(f"  👤 Username:   {config.data['username']}")
        print(f"  🔑 Password:   {generated_password}")
        print()
        print("  ⚠️  This password is shown ONLY now and is NOT saved anywhere.")
        print()

    shown_host = "localhost" if args.host in ("127.0.0.1", "0.0.0.0") else args.host
    print(f"  🌐 Site:       http://{shown_host}:{args.port}")
    print(f"  ⚙️  Admin:      http://{shown_host}:{args.port}/admin")
    if not is_first:
        print(f"  👤 Username:   {config.data['username']}")
        print("  🔑 Password:   (hashed — use the one you set)")
    if args.host == "0.0.0.0":
        print()
        print("  ⚠️  Bound to 0.0.0.0 — reachable from the network.")
        print("      Anyone who can reach this port sees the login page.")
    print()
    print("  💡 Press Ctrl+C to stop")
    print()

    debug = os.environ.get("LAZARUS_DEBUG") == "1"
    app.run(host=args.host, port=args.port, debug=debug)


if __name__ == "__main__":
    main()
