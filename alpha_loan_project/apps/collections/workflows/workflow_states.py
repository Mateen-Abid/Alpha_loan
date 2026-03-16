"""Workflow States - Collection workflow step definitions"""

from enum import Enum


class WorkflowState(Enum):
    """Enumeration of workflow states"""
    STEP_1 = 'STEP_1'
    STEP_2 = 'STEP_2'
    STEP_3 = 'STEP_3'
    STEP_4 = 'STEP_4'
    FINAL_PRESSURE = 'FINAL_PRESSURE'


class WorkflowActions(Enum):
    """Actions that trigger workflow transitions"""
    BORROWER_REFUSED = 'borrower_refused'
    PAYMENT_RECEIVED = 'payment_received'
    COMMITMENT_BROKEN = 'commitment_broken'
    ESCALATE = 'escalate'
    RESET = 'reset'
