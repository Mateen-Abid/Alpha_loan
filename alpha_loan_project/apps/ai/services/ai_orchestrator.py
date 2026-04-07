"""AI Orchestrator - Orchestrates AI operations"""

from apps.ai.intent_detection.intent_analyzer import IntentAnalyzer
from apps.ai.message_generation.message_generator import MessageGenerator
from typing import Dict


class AIOrchestrator:
    """Main orchestrator for AI operations"""
    
    def __init__(self):
        self.intent_analyzer = IntentAnalyzer()
        self.message_generator = MessageGenerator()
    
    def process_borrower_message(self, message: str, case: Dict, channel: str = "sms") -> Dict:
        """
        Process incoming borrower message.
        
        Args:
            message: Message from borrower
            case: Collection case info
        
        Returns:
            Dict with intent detection and suggested response
        """
        # Detect intent
        intent_result = self.intent_analyzer.analyze_message(message, case_context=case)
        
        # Generate response based on intent and workflow step
        context = {
            'amount_due': case.get('total_due'),
            'workflow_step': case.get('current_workflow_step'),
            'days_delinquent': case.get('days_delinquent'),
            'borrower_name': case.get('borrower_name'),
            'detected_intent': intent_result.get('intent'),
            'conversation_memory': case.get('conversation_memory'),
            'prior_loan_history': case.get('prior_loan_history'),
            'policy_flags': case.get('policy_flags'),
        }
        
        if channel == "email":
            email_response = self.message_generator.generate_email(context)
            response = {
                "message": email_response.get("body", ""),
                "subject": email_response.get("subject", "Account Update"),
                "status": email_response.get("status"),
                "error": email_response.get("error"),
            }
        else:
            response = self.message_generator.generate_sms(context)
        
        return {
            'intent': intent_result,
            'suggested_response': response,
            'requires_human_review': intent_result.get('confidence', 0) < 0.7
        }
    
    def generate_outbound_message(self, channel: str, case: Dict, template: str = None) -> Dict:
        """
        Generate outbound message for borrower.
        
        Args:
            channel: 'sms' or 'email'
            case: Collection case info
            template: Optional template name
        
        Returns:
            Dict with generated message
        """
        context = {
            'amount_due': case.get('total_due'),
            'workflow_step': case.get('current_workflow_step'),
            'days_delinquent': case.get('days_delinquent'),
            'borrower_name': case.get('borrower_name'),
            'conversation_memory': case.get('conversation_memory'),
            'prior_loan_history': case.get('prior_loan_history'),
            'policy_flags': case.get('policy_flags'),
        }
        
        if channel == 'sms':
            return self.message_generator.generate_sms(context)
        elif channel == 'email':
            email_response = self.message_generator.generate_email(context)
            email_response["message"] = email_response.get("body", "")
            return email_response
        else:
            return {'error': f'Unknown channel: {channel}'}
