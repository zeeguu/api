# Security checks for configuration validation
import os
import secrets
from zeeguu.logging import warning


# Known insecure default values that should be changed in production
INSECURE_SECRET_KEYS = {
    "lalala", "lalalal", "lulu", "secret", "changeme", "default",
    "test", "development", "dev", "",
}

INSECURE_PASSWORDS = {
    "rootpass", "zeeguu_test", "zeeguutest", "password", "admin",
    "test", "changeme", "fmdtest", "fmdadmin", "akindofrice",
}

PLACEHOLDER_API_KEYS = {
    "blabla", "blublu", "blieblie", "changeme", "your-api-key-here",
    "CHANGE_ME", "", "test",
}


def check_security_config(app):
    """
    Check for insecure configuration values and log warnings.
    Call this during app startup in production.
    """
    warnings_found = []

    # Check SECRET_KEY
    secret_key = app.config.get("SECRET_KEY", "")
    if secret_key.lower() in INSECURE_SECRET_KEYS or len(secret_key) < 32:
        warnings_found.append(
            "SECRET_KEY is insecure! Use a strong random key: "
            f"python -c \"import secrets; print(secrets.token_hex(32))\""
        )

    # Check DEBUG mode
    if app.config.get("DEBUG", False) and not app.testing:
        warnings_found.append(
            "DEBUG=True in production exposes sensitive error information!"
        )

    # Check database URI for hardcoded credentials
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    for insecure_pass in INSECURE_PASSWORDS:
        if insecure_pass in db_uri:
            warnings_found.append(
                f"Database URI contains insecure password '{insecure_pass}'! "
                "Use environment variables for credentials."
            )
            break

    # Check environment variables for API keys
    env_checks = [
        ("MICROSOFT_TRANSLATE_API_KEY", "Microsoft Translate"),
        ("GOOGLE_TRANSLATE_API_KEY", "Google Translate"),
        ("WORDNIK_API_KEY", "Wordnik"),
        ("YOUTUBE_API_KEY", "YouTube"),
        ("DEEPSEEK_API_KEY", "DeepSeek"),
        ("ANTHROPIC_API_KEY", "Anthropic"),
        ("AZURE_SPEECH_KEY", "Azure Speech"),
    ]

    for env_var, service_name in env_checks:
        value = os.environ.get(env_var, "")
        if value.lower() in PLACEHOLDER_API_KEYS:
            warnings_found.append(
                f"{env_var} is a placeholder value! "
                f"Set a real {service_name} API key or remove the service."
            )

    # Check SMTP credentials
    smtp_pass = os.environ.get("SMTP_PASSWORD", "") or app.config.get("SMTP_PASS", "")
    if smtp_pass.lower() in INSECURE_PASSWORDS:
        warnings_found.append(
            "SMTP_PASSWORD is insecure! Use a strong password or app-specific password."
        )

    # Log all warnings
    if warnings_found:
        warning("=" * 60)
        warning("SECURITY CONFIGURATION WARNINGS:")
        warning("=" * 60)
        for w in warnings_found:
            warning(f"  - {w}")
        warning("=" * 60)

    return warnings_found


def generate_secure_secret_key():
    """Generate a cryptographically secure secret key."""
    return secrets.token_hex(32)


def is_production_ready(app):
    """
    Check if the app configuration is ready for production.
    Returns (is_ready, list_of_issues).
    """
    issues = check_security_config(app)
    return len(issues) == 0, issues
