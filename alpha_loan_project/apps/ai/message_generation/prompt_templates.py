"""Prompt Templates - AI prompt templates"""


class PromptTemplates:
    """Collection of AI prompt templates"""
    
    @staticmethod
    def intent_detection_system():
        return """You are a specialized AI for loan collection communications analysis.
Your task is to classify borrower responses accurately."""
    
    @staticmethod
    def message_generation_system(workflow_step: str):
        return f"""You are a professional debt collection communication specialist.
Generate messages appropriate for {workflow_step} of the collection workflow.
Be firm but professional. Motivate borrower to pay."""
