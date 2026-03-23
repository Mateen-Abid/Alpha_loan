"""Gemini AI API client wrapper for message generation and intent analysis."""

from __future__ import annotations

import logging
from typing import Optional

import google.genai as genai


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
        prompt = self._build_message_prompt(
            borrower_name=borrower_name,
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
                return self._sanitize_message(response.text.strip())
            return self._fallback_message(borrower_name, failed_amount, nsf_fee)
        except Exception as exc:
            logger.error(f"Gemini API error: {exc}")
            return self._fallback_message(borrower_name, failed_amount, nsf_fee)

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
        borrower_name: str,
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
        wave_descriptions = {
            1: "initial contact, friendly reminder",
            2: "second notice, more firm",
            3: "legal escalation, serious tone",
            4: "final pressure, urgent action required",
        }
        
        wave_desc = wave_descriptions.get(wave, "follow-up")
        total_due = failed_amount + nsf_fee
        
        prompt = f"""
You are a professional collections agent writing a short, human, SMS-style message.

Details:
- Name: {borrower_name}
- Failed Payment: ${failed_amount:.2f}
- NSF Fee: ${nsf_fee:.2f}
- Total Due: ${total_due:.2f}
- Balance: ${current_balance:.2f}
- Reason: {reason}
- Escalation: Wave {wave} ({wave_desc})
- Tone: {tone}

Instructions:
- Sound natural, like a real human texting (NOT robotic or templated)
- Be clear, polite, and slightly empathetic
- Keep it under 3 sentences
- Mention payment failure + total due clearly
- Encourage action (pay/update details), but NO phone call instructions
- Adjust tone:
  • Wave 1-2 → friendly, understanding  
  • Wave 3-4 → firmer, more urgent but still respectful

Avoid:
- Repeating numbers unnecessarily
- Robotic phrasing like “we see that”
- Overly formal or legal tone

Write ONE clean message only.
"""
        
        return prompt.strip()

    @staticmethod
    def _build_intent_prompt(
        borrower_message: str,
        case_context: Optional[dict] = None,
    ) -> str:
        """
        Build the prompt for Gemini to analyze borrower intent.
        """
        context_str = ""
        if case_context:
            context_str = f"\nCase Context: Amount due ${case_context.get('amount_due', 0)}, Wave {case_context.get('wave', 1)}"
        
        prompt = f"""
        Analyze the borrower's message and classify their intent.{context_str}
        
        Borrower Message: "{borrower_message}"
        
        Possible intents:
        - PROMISE_TO_PAY (borrower commits to payment)
        - PARTIAL_PAYMENT (will pay some but not full amount)
        - REQUEST_TIME_EXTENSION (needs more time)
        - REQUEST_NEW_ARRANGEMENT (wants payment plan)
        - REFUSAL (refuses to pay)
        - DISPUTE (disputes the charge)
        - NEEDS_INFO (requests account information)
        - IRRELEVANT (no collection relevance)
        - UNCLEAR (cannot determine)
        
        Respond ONLY in this format:
        INTENT: [intent]
        CONFIDENCE: [0-100]
        SENTIMENT: [positive/neutral/negative]
        EXPLANATION: [brief reason]
        """
        
        return prompt.strip()

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
        borrower_name: str,
        failed_amount: float,
        nsf_fee: float,
    ) -> str:
        """
        Fallback message if Gemini API fails.
        """
        total_due = failed_amount + nsf_fee
        return (
            f"Hi {borrower_name}, we see that your last payment for ${failed_amount:.2f} was stopped/failed. "
            f"We need ${failed_amount:.2f} + ${nsf_fee:.2f} NSF fee now. "
            f"Your current balance is ${total_due:.2f}. To resolve or update payment information, complete payment today."
        )

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
