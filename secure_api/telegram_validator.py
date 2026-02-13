"""
Telegram WebApp initData validator.

Validates the cryptographic signature of Telegram WebApp initData
to ensure it hasn't been tampered with.

Supports both validation methods:
1. Using Telegram Bot Token (HMAC-SHA256) - legacy method
2. Using Telegram Public Key (Ed25519) - new third-party validation

Reference: https://docs.telegram-mini-apps.com/platform/init-data#validating
"""

import hmac
import hashlib
from urllib.parse import parse_qsl
from typing import Dict, Optional
import logging
import base64

logger = logging.getLogger(__name__)

# Telegram Ed25519 public keys
TELEGRAM_PUBLIC_KEY_PRODUCTION = "e7bf03a2fa4602af4580703d88dda5bb59f32ed8b02a56c187fe7d34caed242d"
TELEGRAM_PUBLIC_KEY_TEST = "40055058a4ee38156a06562e52eece92a771bcd8346a8c4615cb7376eddf72ec"


class TelegramInitDataValidator:
    """Validates Telegram WebApp initData cryptographic signature."""

    def __init__(self, bot_token: str, use_ed25519: bool = True):
        """
        Initialize validator with bot token.

        Args:
            bot_token: Telegram bot token (from BotFather)
            use_ed25519: Use Ed25519 signature validation (recommended)
        """
        self.bot_token = bot_token
        self.use_ed25519 = use_ed25519
        self.bot_id = bot_token.split(':')[0] if bot_token else None

    def _validate_ed25519(self, data_dict: Dict[str, str], signature: str) -> bool:
        """
        Validate initData using Ed25519 signature (third-party validation).

        Reference: https://docs.telegram-mini-apps.com/platform/init-data#using-telegram-public-key
        """
        try:
            from cryptography.hazmat.primitives.asymmetric import ed25519
            from cryptography.hazmat.primitives import serialization
        except ImportError:
            logger.error("cryptography library not installed. Install with: pip install cryptography")
            return False

        # Step 1: Build data-check string
        # Format: {bot_id}:WebAppData\n{sorted_params}
        sorted_params = "\n".join(
            f"{key}={value}"
            for key, value in sorted(data_dict.items())
            if key not in ("hash", "signature")
        )
        data_check_string = f"{self.bot_id}:WebAppData\n{sorted_params}"

        # Step 2: Decode signature from base64
        # Add padding if needed (Telegram sends invalid base64 without padding)
        signature_padded = signature + "=" * (4 - len(signature) % 4)
        try:
            signature_bytes = base64.urlsafe_b64decode(signature_padded)
        except Exception as e:
            logger.warning(f"Failed to decode signature: {e}")
            return False

        # Step 3: Get Telegram public key (production)
        public_key_hex = TELEGRAM_PUBLIC_KEY_PRODUCTION
        public_key_bytes = bytes.fromhex(public_key_hex)

        # Step 4: Verify Ed25519 signature
        try:
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
            public_key.verify(signature_bytes, data_check_string.encode())
            logger.info("✅ Ed25519 signature validation successful")
            return True
        except Exception as e:
            logger.warning(f"❌ Ed25519 signature validation failed: {e}")
            return False

    def validate(self, init_data: str) -> Dict[str, str]:
        """
        Validate initData signature and return parsed data.

        Args:
            init_data: Raw initData string from Telegram WebApp

        Returns:
            Dict with parsed initData fields (user, chat_instance, etc.)

        Raises:
            ValueError: If signature is invalid or data is malformed
        """
        if not init_data:
            raise ValueError("initData is empty")

        # Parse query string
        try:
            data_dict = dict(parse_qsl(init_data))
        except Exception as e:
            raise ValueError(f"Failed to parse initData: {e}")

        # Try Ed25519 validation first (new method)
        signature = data_dict.get("signature")
        if self.use_ed25519 and signature:
            logger.info("Attempting Ed25519 signature validation")
            if self._validate_ed25519(data_dict, signature):
                # Remove signature from returned data
                data_dict.pop("signature", None)
                data_dict.pop("hash", None)
                logger.info("initData validated successfully via Ed25519")
                return data_dict
            else:
                logger.warning("Ed25519 validation failed, trying HMAC-SHA256")

        # Fallback to HMAC-SHA256 validation (legacy method)
        received_hash = data_dict.pop("hash", None)
        if not received_hash:
            raise ValueError("initData missing 'hash' or 'signature' parameter")

        # Note: 'signature' field (if present) is excluded in _compute_hash()
        data_dict.pop("signature", None)

        # Compute expected hash
        expected_hash = self._compute_hash(data_dict)

        # Compare hashes (constant-time comparison to prevent timing attacks)
        if not hmac.compare_digest(received_hash, expected_hash):
            logger.warning("Invalid initData signature")
            raise ValueError("Invalid initData signature")

        logger.info("initData signature validated successfully")
        return data_dict

    def _compute_hash(self, data_dict: Dict[str, str]) -> str:
        """
        Compute HMAC-SHA256 hash according to Telegram spec.

        Steps:
        1. Sort data alphabetically by key
        2. Join as key=value pairs with newlines (excluding 'signature' field)
        3. Compute HMAC-SHA256 using secret key derived from bot token

        Note: The 'signature' field should be excluded from validation.
        It's used for other purposes (like startParam verification) but is not
        part of the standard WebApp initData validation.
        """
        # Sort data alphabetically and format as key=value\n
        # Exclude 'signature' field (it's not part of standard validation)
        data_check_string = "\n".join(
            f"{key}={value}"
            for key, value in sorted(data_dict.items())
            if key != "signature"
        )

        # Derive secret key from bot token
        # secret_key = HMAC_SHA256(bot_token, "WebAppData")
        secret_key = hmac.new(
            key=b"WebAppData",
            msg=self.bot_token.encode(),
            digestmod=hashlib.sha256
        ).digest()

        # Compute hash
        hash_value = hmac.new(
            key=secret_key,
            msg=data_check_string.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()

        return hash_value

    def extract_user_id(self, init_data: str) -> int:
        """
        Validate initData and extract user ID.

        Args:
            init_data: Raw initData string from Telegram WebApp

        Returns:
            Telegram user ID (integer)

        Raises:
            ValueError: If signature is invalid or user data is missing
        """
        data = self.validate(init_data)

        # Parse user JSON
        user_json = data.get("user")
        if not user_json:
            raise ValueError("initData missing 'user' field")

        import json
        try:
            user = json.loads(user_json)
            user_id = user.get("id")
            if not user_id:
                raise ValueError("User object missing 'id' field")
            return int(user_id)
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"Failed to parse user data: {e}")


def validate_init_data(init_data: str, bot_token: str) -> int:
    """
    Convenience function to validate initData and extract user ID.

    Args:
        init_data: Raw initData string from Telegram WebApp
        bot_token: Telegram bot token

    Returns:
        Telegram user ID

    Raises:
        ValueError: If validation fails
    """
    validator = TelegramInitDataValidator(bot_token)
    return validator.extract_user_id(init_data)
