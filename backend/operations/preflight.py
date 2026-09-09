"""Validate production configuration without printing secrets."""

from __future__ import annotations

from backend.api.settings import Settings


def main() -> None:
    settings = Settings()
    print(f"PASS: NovaQ {settings.environment} configuration preflight")


if __name__ == "__main__":
    main()
