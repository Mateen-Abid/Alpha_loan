"""Workflow Constants - Workflow-related constants"""


class WorkflowConstants:
    """Workflow step constants and configurations"""
    
    STEPS = {
        'STEP_1': {
            'name': 'Immediate Payment',
            'description': 'Initial contact - request immediate payment',
            'days_in_step': 3,
            'escalation_action': 'Remind of obligation'
        },
        'STEP_2': {
            'name': 'Double Payment',
            'description': 'Request 2x payment to catch up',
            'days_in_step': 5,
            'escalation_action': 'Mention NSF possibility'
        },
        'STEP_3': {
            'name': 'Add NSF to Next Payment',
            'description': 'Inform of NSF fee that will be added',
            'days_in_step': 7,
            'escalation_action': 'Coordinate split payment'
        },
        'STEP_4': {
            'name': 'Split NSF',
            'description': 'Offer split payment arrangement',
            'days_in_step': 7,
            'escalation_action': 'Final notice'
        },
        'FINAL_PRESSURE': {
            'name': 'Final Pressure',
            'description': 'Final escalation before legal action',
            'days_in_step': None,
            'escalation_action': 'Legal action'
        }
    }
    
    @classmethod
    def get_step_info(cls, step: str) -> dict:
        """Get information about a workflow step"""
        return cls.STEPS.get(step, {})


class CommunicationConstants:
    """Communication-related constants"""
    
    CHANNELS = ['SMS', 'EMAIL', 'VOICE']
    
    INTERACTION_TYPES = {
        'OUTBOUND': 'Message sent to borrower',
        'INBOUND': 'Message received from borrower'
    }
    
    STATUS_CODES = {
        'PENDING': 'Waiting to be sent',
        'SENT': 'Sent successfully',
        'DELIVERED': 'Confirmed delivered',
        'READ': 'Message read by borrower',
        'REPLIED': 'Borrower replied',
        'FAILED': 'Failed to send',
        'BOUNCED': 'Bounced back'
    }
