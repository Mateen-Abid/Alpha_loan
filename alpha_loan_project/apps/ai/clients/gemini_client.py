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
        wave_descriptions = {
            1: "initial contact, friendly reminder",
            2: "second notice, more firm",
            3: "legal escalation, serious tone",
            4: "final pressure, urgent action required",
        }
        
        wave_desc = wave_descriptions.get(wave, "follow-up")
        total_due = failed_amount + nsf_fee
        
        prompt = f"""
You are mike or sarah, a REAL collections agent texting {first_name} casually on their phone.

REQUIRED FORMAT - START YOUR MESSAGE WITH THIS:
"hey {first_name}, this is [mike or sarah] from [company name]..."

Then continue naturally. You're having a brief conversation, not sending a corporate email.

Details:
- Borrower: {first_name}
- Failed Payment: ${failed_amount:.2f}
- NSF Fee: ${nsf_fee:.2f}
- Total Due: ${total_due:.2f}
- Wave {wave}

YOUR TONE (CRITICAL):
✓ ALWAYS start: "hey {first_name}, this is [agent] from [company]..."
✓ Pick any company name (iloans, fashloan, quickcash, loanpro, etc.) - make it realistic
✓ Conversational and direct after the intro
✓ Use dropped caps, contractions, casual words (gotta, wanna, gonna, etc.)
✓ Slightly imperfect grammar = HUMAN
✓ NO gendered casual language - NEVER say "man", "buddy", "dude", "bro"
✓ Say things like: "we gotta figure this out", "can you send that in?", "the latest I can go is Friday"
✓ 2-3 short casual sentences MAX (after intro)
✗ NO formal bank language: avoid "Hi", "we see that", "to resolve", "kindly", "update payment information"
✗ NO robotic phrases: "unsuccessful", "has declined", "current balance is"
✗ NO excessive politeness or structure
✗ Do not sound like a bank email AT ALL

Must mention:
- Payment bounced/failed
- Total due amount
- When you need it (ask for deadline)

Wave guidance:
- Wave 1: Friendly, straightforward, helpful vibe - offer to help solve problem
- Wave 2: More direct and firm - they know they owe money, need quick payment
- Wave 3: Urgent and serious - legal escalation territory, ASAP tone
- Wave 4: Final pressure - URGENT, RIGHT NOW, CONSEQUENCES, no more negotiating

EXAMPLES TO MATCH TONE (ALL START WITH AGENT INTRO):
Wave 1 (Friendly): "hey {first_name}, this is mike from iloans. your payment bounced. we gotta figure this out. when can you take care of it?"
Wave 2 (Firm): "hey {first_name}, this is sarah from fashloan. look, your payment bounced. I need ${total_due:.2f} from you. when can you send it?"
Wave 3 (Urgent): "yo {first_name}, this is mike from quickcash. your payment bounced. we need ${total_due:.2f} ASAP. this is serious. when can you handle this?"
Wave 4 (Final): "hey {first_name}, this is sarah from loanpro. your payment bounced. this is URGENT and FINAL - we need ${total_due:.2f} RIGHT NOW. respond immediately."

WAVE {wave} SPECIFIC RULES:
- Wave 1: Be friendly and helpful. Show you want to collaborate to fix the problem.
- Wave 2: Still respectful but firmer. They had their chance, now need concrete timeline.
- Wave 3: Urgent and serious. Use ASAP, serious, important. This is legal territory.
- Wave 4: FINAL AND URGENT. Use RIGHT NOW, URGENT, FINAL, IMMEDIATE, DO NOT IGNORE.

CRITICAL: 
- EVERY message MUST start with "hey {first_name}, this is [agent] from [company]..."
- If your response sounds like a bank wrote it, REWRITE IT. It should sound like a real person, not AI.

Generate ONLY the message text. No explanations. No brackets. Just raw text like a real text message.
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
            context_str = f"\nCase Context: Amount due ${case_context.get('amount_due', 0)}, Wave {case_context.get('wave', 3)}"
        
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
        first_name: str,
        failed_amount: float,
        nsf_fee: float,
        wave: int = 1,
    ) -> str:
        """
        Fallback message if Gemini API fails. Wave-specific escalation, no gendered language.
        """
        total_due = failed_amount + nsf_fee
        companies = ["iLoans", "QuickCash", "LoanPro", "FastFunds", "CashFlow"]
        company = companies[wave % len(companies)]
        
        if wave == 1:
            # Friendly and helpful
            return f"hey {first_name}, this is mike from {company}. your payment bounced. we gotta figure this out. total is ${total_due:.2f}. when can you take care of it?"
        elif wave == 2:
            # More firm
            return f"hey {first_name}, this is sarah from {company}. look, your payment bounced. I need ${total_due:.2f} from you. when can you send it?"
        elif wave == 3:
            # Urgent and serious
            return f"hey {first_name}, this is mike from {company}. your payment bounced. we need ${total_due:.2f} ASAP. this is serious. when can you handle this?"
        else:  # wave 4
            # Final pressure - URGENT
            return f"hey {first_name}, this is sarah from {company}. URGENT - your payment bounced. we need ${total_due:.2f} RIGHT NOW. this is final. respond immediately."

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
