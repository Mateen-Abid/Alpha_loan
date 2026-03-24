"""Gemini AI API client wrapper for message generation and intent analysis."""

from __future__ import annotations

import logging
from typing import Optional

import google.genai as genai
from apps.ai.constants import (
    build_gemini_collection_message_prompt,
    build_gemini_intent_prompt,
)


logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Wrapper for Google Gemini API.
    Handles message generation, intent analysis, and content moderation.
    """

    def __init__(self, api_key: str):
        """
        Initialize Gemini client with API key.
        
        Args:
            api_key: Google Gemini API key
        """
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.5-flash"

    def generate_collection_message(
        self,
        borrower_name: str,
        failed_amount: float,
        nsf_fee: float = 50.00,
        current_balance: float = 0.0,
        reason: str = "Payment failed",
        wave: int = 1,
        tone: str = "professional_friendly",
    ) -> str:
        """
        Generate a collection message using Gemini.
        
        Args:
            borrower_name: Borrower's full name
            failed_amount: Amount of failed payment
            nsf_fee: NSF fee amount (default $50)
            current_balance: Current account balance
            reason: Reason for collection (EFT failed, NSF, etc.)
            wave: Escalation wave (1-4)
            tone: Message tone (professional_friendly, firm, urgent)
        
        Returns:
            Generated message text
        """
        first_name = borrower_name.split()[0]
        
        prompt = self._build_message_prompt(
            first_name=first_name,
            failed_amount=failed_amount,
            nsf_fee=nsf_fee,
            current_balance=current_balance,
            reason=reason,
            wave=wave,
            tone=tone,
        )
        
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            if response.text:
                sanitized = self._sanitize_message(response.text.strip())
                return self._humanize_text(sanitized)
            return self._fallback_message(first_name, failed_amount, nsf_fee, wave)
        except Exception as exc:
            logger.error(f"Gemini API error: {exc}")
            return self._fallback_message(first_name, failed_amount, nsf_fee, wave)

    def detect_intent(
        self,
        borrower_message: str,
        case_context: Optional[dict] = None,
    ) -> dict:
        """
        Detect intent from borrower message using Gemini.
        
        Args:
            borrower_message: Borrower's message/reply
            case_context: Optional case context for better detection
        
        Returns:
            Dict with intent, confidence, sentiment
        """
        prompt = self._build_intent_prompt(borrower_message, case_context)
        
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            if response.text:
                return self._parse_intent_response(response.text)
            return {
                "intent": "UNKNOWN",
                "confidence": 0.0,
                "sentiment": "neutral",
                "explanation": "Could not determine intent",
            }
        except Exception as exc:
            logger.error(f"Intent detection error: {exc}")
            return {
                "intent": "ERROR",
                "confidence": 0.0,
                "sentiment": "neutral",
                "explanation": str(exc),
            }

    @staticmethod
    def _build_message_prompt(
        first_name: str,
        failed_amount: float,
        nsf_fee: float,
        current_balance: float,
        reason: str,
        wave: int,
        tone: str,
    ) -> str:
        """
        Build the prompt for Gemini to generate collection message.
        """
        return build_gemini_collection_message_prompt(
            first_name=first_name,
            failed_amount=failed_amount,
            nsf_fee=nsf_fee,
            current_balance=current_balance,
            reason=reason,
            wave=wave,
            tone=tone,
        )

    @staticmethod
    def _build_intent_prompt(
        borrower_message: str,
        case_context: Optional[dict] = None,
    ) -> str:
        """
        Build the prompt for Gemini to analyze borrower intent.
        """
        return build_gemini_intent_prompt(
            borrower_message=borrower_message,
            case_context=case_context,
        )

    @staticmethod
    def _parse_intent_response(response_text: str) -> dict:
        """
        Parse Gemini's intent response.
        """
        lines = response_text.strip().split("\n")
        result = {
            "intent": "UNKNOWN",
            "confidence": 0.0,
            "sentiment": "neutral",
            "explanation": "Parse error",
        }
        
        for line in lines:
            if line.startswith("INTENT:"):
                result["intent"] = line.replace("INTENT:", "").strip()
            elif line.startswith("CONFIDENCE:"):
                try:
                    conf = line.replace("CONFIDENCE:", "").strip().rstrip("%")
                    result["confidence"] = float(conf) / 100.0
                except (ValueError, AttributeError):
                    result["confidence"] = 0.0
            elif line.startswith("SENTIMENT:"):
                result["sentiment"] = line.replace("SENTIMENT:", "").strip().lower()
            elif line.startswith("EXPLANATION:"):
                result["explanation"] = line.replace("EXPLANATION:", "").strip()
        
        return result

    @staticmethod
    def _fallback_message(
        first_name: str,
        failed_amount: float,
        nsf_fee: float,
        wave: int = 1,
    ) -> str:
        """
        Fallback message if Gemini API fails. Wave-specific escalation, no gendered language.
        """
        total_due = failed_amount + nsf_fee
        company = "ilowns"
        
        if wave == 1:
            # Friendly and helpful
            return f"hey {first_name}, this is mike from {company}. your payment bounced. we gotta figure this out. total is ${total_due:.2f}. when can you take care of it?"
        elif wave == 2:
            # More firm
            return f"hey {first_name}, this is mike from {company}. look, your payment bounced. I need ${total_due:.2f} from you. when can you send it?"
        elif wave == 3:
            # Urgent and serious
            return f"hey {first_name}, this is mike from {company}. your payment bounced. we need ${total_due:.2f} ASAP. this is serious. when can you handle this?"
        else:  # wave 4
            # Final pressure - URGENT
            return f"hey {first_name}, this is mike from {company}. URGENT - your payment bounced. we need ${total_due:.2f} RIGHT NOW. this is final. respond immediately."

    @staticmethod
    def _sanitize_message(message: str) -> str:
        """Remove phone/call directives and enforce update-payment CTA language."""
        cleaned = message
        blocked_phrases = [
            "please give us a call",
            "please call us",
            "call us",
            "give us a call",
            "contact us by phone",
        ]

        for phrase in blocked_phrases:
            cleaned = cleaned.replace(phrase, "resolve or update payment information")
            cleaned = cleaned.replace(phrase.title(), "Resolve or update payment information")

        return cleaned

    def _humanize_text(self, text: str) -> str:
        """Aggressively post-process to convert formal language to actual human texting."""
        replacements = {
            # Remove gendered casual language (handle all variations)
            ", man": "",
            " man.": ".",
            " man,": ",",
            ", buddy": "",
            " buddy.": ".",
            " buddy,": ",",
            ", dude": "",
            " dude.": ".",
            " dude,": ",",
            ", bro": "",
            " bro.": ".",
            " bro,": ",",
            
            # Casual action phrases
            "get that sent over": "take care of this",
            "get that to me": "get that sorted",
            "send that in": "get it handled",
            "send it today": "take care of it",
            "get this in": "take care of this",
            "get that in": "get that sorted",
            
            # Greetings
            "Hi ": "hey ",
            "Hello ": "hey ",
            
            # Formal payment language
            "your last payment was unsuccessful": "your payment bounced",
            "your last payment has been unsuccessful": "your payment bounced",
            "your payment was unsuccessful": "your payment bounced",
            "your payment was stopped": "your payment bounced",
            "payment was stopped": "payment bounced",
            "was stopped/failed": "bounced",
            "has been declined": "didn't go through",
            "has failed": "bounced",
            "failed to process": "bounced",
            
            # Formal business language
            "We see that": "look,",
            "we see that": "look,",
            "We need": "I need",
            "we need": "I need",
            "We have": "I got",
            "we have": "I got",
            "current balance is": "total's",
            "Your current balance is": "total's",
            "the total owed is": "total's",
            # Replace "and" only when it's a standalone word (surrounded by spaces or punctuation)
            " and ": " & ",
            " and.": " &.",
            " and,": " &,",
            " and?": " &?",
            " and!": " &!",
            
            # Formal action language
            "to resolve": "to sort",
            "to update payment information": "to get this sorted",
            "resolve or update payment information": "get this handled",
            "update payment": "send payment",
            "please": "",
            "kindly": "",
            
            # Fee language
            "NSF fee": "NSF charge",
            "+ ": "& ",
        }
        
        result = text
        for old, new in replacements.items():
            result = result.replace(old, new)
        
        # Clean up double spaces
        while "  " in result:
            result = result.replace("  ", " ")
        
        return result.strip()
