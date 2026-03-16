"""Template Service - Message template management"""


class TemplateService:
    """Manages message templates for different scenarios"""
    
    TEMPLATES = {
        'initial_contact': 'Hello {name}, this is regarding your account. Please contact us.',
        'payment_reminder': 'Payment reminder: ${amount} is due on {due_date}.',
        'urgency': 'Your account requires immediate attention. Please pay ${amount} today.',
        'final_notice': 'This is a final notice. Please contact us immediately.',
    }
    
    @classmethod
    def get_template(cls, name: str) -> str:
        """Get template by name"""
        return cls.TEMPLATES.get(name, '')
    
    @classmethod
    def render_template(cls, name: str, **kwargs) -> str:
        """Render template with variables"""
        template = cls.get_template(name)
        return template.format(**kwargs) if template else ''
