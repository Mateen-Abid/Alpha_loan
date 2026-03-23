"""Gemini-based message generation service for collection communications."""

from __future__ import annotations

import logging
from typing import Optional

from apps.ai.clients.gemini_client import GeminiClient


logger = logging.getLogger(__name__)


class GeminiMessageGenerator:
    """
    Generates collection messages using Gemini AI.
    Converts case data to natural, human-friendly messages.
    """

    def __init__(self, gemini_api_key: str):
        """
        Initialize with Gemini API key.
        """
        self.client = GeminiClient(api_key=gemini_api_key)

    def generate_collection_message(
        self,
        borrower_name: str,
        failed_amount: float,
        nsf_fee: float = 50.00,
        current_balance: Optional[float] = None,
        reason: str = "Payment failed",
        wave: int = 1,
        channel: str = "sms",
    ) -> str:
        """
        Generate a collection message for a borrower.
        
        Args:
            borrower_name: Borrower's name
            failed_amount: Failed payment amount
            nsf_fee: NSF fee (default $50)
            current_balance: Account balance
            reason: Reason for failure
            wave: Escalation wave (1-4)
            channel: Target channel (sms, email, voice)
        
        Returns:
            Generated message text
        """
        tone = self._get_tone_for_wave(wave)
        
        message = self.client.generate_collection_message(
            borrower_name=borrower_name,
            failed_amount=failed_amount,
            nsf_fee=nsf_fee,
            current_balance=current_balance or failed_amount + nsf_fee,
            reason=reason,
            wave=wave,
            tone=tone,
        )
        
        # Adjust for channel (SMS has length limits)
        if channel == "sms" and len(message) > 160:
            message = self._shorten_for_sms(message)
        
        return message

    def analyze_borrower_reply(
        self,
        message: str,
        case_context: Optional[dict] = None,
    ) -> dict:
        """
        Analyze a borrower's reply message.
        
        Args:
            message: Borrower's message
            case_context: Optional case data for context
        
        Returns:
            Dict with intent, confidence, sentiment
        """
        return self.client.detect_intent(message, case_context)

    @staticmethod
    def _get_tone_for_wave(wave: int) -> str:
        """Map wave level to message tone."""
        tone_map = {
            1: "professional_friendly",
            2: "professional_firm",
            3: "serious",
            4: "urgent",
        }
        return tone_map.get(wave, "professional_friendly")

    @staticmethod
    def _shorten_for_sms(message: str, max_length: int = 160) -> str:
        """Shorten message for SMS (160 char limit)."""
        if len(message) <= max_length:
            return message
        
        # Find last sentence break before limit
        truncated = message[:max_length]
        last_period = truncated.rfind(".")
        
        if last_period > max_length - 50:  # At least 50 chars from limit
            return truncated[:last_period + 1]
        
        # Fall back to truncate at word boundary
        last_space = truncated.rfind(" ")
        if last_space > 50:
            return truncated[:last_space] + "..."
        
        return truncated[:max_length - 3] + "..."


class MessageGenerationPipeline:
    """
    End-to-end pipeline for generating messages from case data.
    """

    def __init__(self, gemini_api_key: str):
        """Initialize pipeline with Gemini client."""
        self.generator = GeminiMessageGenerator(gemini_api_key)

    def generate_for_case(
        self,
        case_id: str,
        borrower_name: str,
        failed_amount: float,
        current_balance: float,
        reason: str = "EFT Failed",
        wave: int = 1,
        channel: str = "sms",
    ) -> dict:
        """
        Generate message for a single case.
        
        Returns dict with all generation details for testing/logging.
        """
        nsf_fee = 50.00
        total_due = failed_amount + nsf_fee
        
        message = self.generator.generate_collection_message(
            borrower_name=borrower_name,
            failed_amount=failed_amount,
            nsf_fee=nsf_fee,
            current_balance=current_balance,
            reason=reason,
            wave=wave,
            channel=channel,
        )
        
        return {
            "case_id": case_id,
            "borrower_name": borrower_name,
            "channel": channel,
            "wave": wave,
            "reason": reason,
            "amounts": {
                "failed_payment": failed_amount,
                "nsf_fee": nsf_fee,
                "total_due": total_due,
                "account_balance": current_balance,
            },
            "generated_message": message,
            "message_length": len(message),
            "truncated_for_sms": len(message) > 160 if channel == "sms" else False,
        }
