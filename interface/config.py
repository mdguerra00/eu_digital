"""
Configuration management for the Control Interface

This module provides configuration constants and utilities for the Flask dashboard.
"""

import os
from typing import Optional

# ──────────────────────────────────────────────────────────────────────────────
# Flask Configuration
# ──────────────────────────────────────────────────────────────────────────────
DEBUG = os.environ.get("DASHBOARD_DEBUG", "false").lower() in ("1", "true")
PORT = int(os.environ.get("PORT", os.environ.get("DASHBOARD_PORT", "5000")))
HOST = os.environ.get("DASHBOARD_HOST", "0.0.0.0")

# ──────────────────────────────────────────────────────────────────────────────
# Agent Configuration
# ──────────────────────────────────────────────────────────────────────────────
AGENT_NAME = os.environ.get("AGENT_NAME", "EU_DE_NEGOCIOS")
AGENT_MODE = os.environ.get("AGENT_MODE", "real")

# ──────────────────────────────────────────────────────────────────────────────
# Supabase Configuration
# ──────────────────────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

# Prioritize service role key, fall back to anon key
SUPABASE_KEY = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY

# ──────────────────────────────────────────────────────────────────────────────
# Database Table Names
# ──────────────────────────────────────────────────────────────────────────────
TABLES = {
    # Core agent tables
    "CYCLES": os.environ.get("AGENT_CYCLES_TABLE", "agent_cycles"),
    "STATE": os.environ.get("AGENT_STATE_TABLE", "agent_state"),
    "RECEIPTS": os.environ.get("EXECUTION_RECEIPTS_TABLE", "execution_receipts"),
    "MESSAGES": os.environ.get("CREATOR_MESSAGES_TABLE", "creator_messages"),

    # Financial tables
    "WALLET_BALANCE": "agent_wallet_balance",
    "WALLET_TX": "agent_wallet_transactions",

    # Monitoring tables
    "ALERTS": "system_alerts",
    "AUDIT_LOG": "audit_log",
    "METRICS": "performance_metrics",
    "HEALTH": "service_health",

    # Business tables
    "AFFILIATES": "affiliate_links",
}

# ──────────────────────────────────────────────────────────────────────────────
# Feature Flags
# ──────────────────────────────────────────────────────────────────────────────
FEATURES = {
    "ENABLE_REAL_TIME_UPDATES": True,
    "ENABLE_ALERTS": True,
    "ENABLE_AUDIT_LOG": True,
    "ENABLE_AFFILIATE_MANAGEMENT": True,
    "ENABLE_PERFORMANCE_METRICS": True,
    "ENABLE_HEALTH_MONITORING": True,
    "ENABLE_FINANCIAL_REPORTS": True,
}

# ──────────────────────────────────────────────────────────────────────────────
# Alert Configuration
# ──────────────────────────────────────────────────────────────────────────────
ALERTS = {
    "STATUTE_VIOLATION_ENABLED": True,
    "LOW_BALANCE_THRESHOLD": 100.0,  # R$
    "HIGH_FALLBACK_RATE_THRESHOLD": 50,  # Percentage
    "SERVICE_ERROR_RETRY_LIMIT": 3,
    "PERFORMANCE_WARNING_LATENCY_MS": 5000,
}

# ──────────────────────────────────────────────────────────────────────────────
# Monitoring Configuration
# ──────────────────────────────────────────────────────────────────────────────
MONITORING = {
    "HEALTH_CHECK_INTERVAL": 60,  # Seconds
    "METRICS_AGGREGATION_INTERVAL": 300,  # Seconds
    "AUDIT_LOG_RETENTION_DAYS": 90,
    "METRICS_RETENTION_DAYS": 365,
}

# ──────────────────────────────────────────────────────────────────────────────
# API Configuration
# ──────────────────────────────────────────────────────────────────────────────
API = {
    "DEFAULT_LIMIT": 20,
    "MAX_LIMIT": 500,
    "CACHE_TIMEOUT": 60,  # Seconds
    "SSE_HEARTBEAT_INTERVAL": 25,  # Seconds
    "SSE_CLIENT_TIMEOUT": 45,  # Seconds
    "SSE_QUEUE_SIZE": 50,
}

# ──────────────────────────────────────────────────────────────────────────────
# Notification Configuration
# ──────────────────────────────────────────────────────────────────────────────
NOTIFICATIONS = {
    "SLACK_WEBHOOK_URL": os.environ.get("SLACK_WEBHOOK_URL", ""),
    "DISCORD_WEBHOOK_URL": os.environ.get("DISCORD_WEBHOOK_URL", ""),
    "EMAIL_ENABLED": os.environ.get("EMAIL_ENABLED", "false").lower() in ("1", "true"),
    "EMAIL_FROM": os.environ.get("EMAIL_FROM", ""),
}

# ──────────────────────────────────────────────────────────────────────────────
# Affiliate Configuration
# ──────────────────────────────────────────────────────────────────────────────
AFFILIATES = {
    "MIN_COMMISSION_PCT": 5.0,
    "MAX_COMMISSION_PCT": 100.0,
    "MIN_RATING": 0.0,
    "MAX_RATING": 5.0,
    "ALLOW_BULK_IMPORT": True,
}

# ──────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ──────────────────────────────────────────────────────────────────────────────


def is_configured() -> bool:
    """Check if Supabase is properly configured"""
    return bool(SUPABASE_URL and SUPABASE_KEY)


def get_table_name(table_key: str) -> str:
    """Get full table name by key"""
    return TABLES.get(table_key, "")


def is_feature_enabled(feature_key: str) -> bool:
    """Check if a feature is enabled"""
    return FEATURES.get(feature_key, False)


def get_alert_setting(setting_key: str) -> Optional[float]:
    """Get alert configuration setting"""
    return ALERTS.get(setting_key)


def get_monitoring_setting(setting_key: str) -> Optional[int]:
    """Get monitoring configuration setting"""
    return MONITORING.get(setting_key)


# ──────────────────────────────────────────────────────────────────────────────
# Service URLs (for health monitoring)
# ──────────────────────────────────────────────────────────────────────────────
SERVICE_ENDPOINTS = {
    "openai": {
        "name": "OpenAI API",
        "health_url": "https://api.openai.com/v1/models",
        "timeout": 10,
    },
    "supabase": {
        "name": "Supabase",
        "health_url": SUPABASE_URL or "https://supabase.com",
        "timeout": 5,
    },
    "perplexity": {
        "name": "Perplexity AI",
        "health_url": "https://api.perplexity.ai/chat/completions",
        "timeout": 10,
    },
    "steel_browser": {
        "name": "Steel Browser",
        "health_url": os.environ.get("STEEL_BROWSER_ENDPOINT", "http://localhost:3000/health"),
        "timeout": 15,
    },
}
