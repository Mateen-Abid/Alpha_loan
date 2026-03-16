"""Workflow State Machine - Deterministic workflow engine"""

from .workflow_states import WorkflowState, WorkflowActions


class WorkflowStateMachine:
    """
    Deterministic state machine for collection workflow.
    Manages transitions between workflow steps.
    """
    
    # State transitions - only progress when borrower refuses
    TRANSITIONS = {
        WorkflowState.STEP_1: {
            WorkflowActions.BORROWER_REFUSED: WorkflowState.STEP_2,
        },
        WorkflowState.STEP_2: {
            WorkflowActions.BORROWER_REFUSED: WorkflowState.STEP_3,
        },
        WorkflowState.STEP_3: {
            WorkflowActions.BORROWER_REFUSED: WorkflowState.STEP_4,
        },
        WorkflowState.STEP_4: {
            WorkflowActions.BORROWER_REFUSED: WorkflowState.FINAL_PRESSURE,
        },
        WorkflowState.FINAL_PRESSURE: {
            # Final state - no further transitions
        },
    }
    
    def __init__(self, current_state: WorkflowState):
        """Initialize state machine with current state"""
        self.current_state = current_state
    
    def can_transition(self, action: WorkflowActions) -> bool:
        """Check if action is allowed from current state"""
        if self.current_state not in self.TRANSITIONS:
            return False
        return action in self.TRANSITIONS[self.current_state]
    
    def transition(self, action: WorkflowActions) -> bool:
        """
        Attempt to transition to next state.
        Returns True if transition successful, False otherwise.
        """
        if not self.can_transition(action):
            return False
        
        next_state = self.TRANSITIONS[self.current_state][action]
        self.current_state = next_state
        return True
    
    def get_next_state(self, action: WorkflowActions) -> WorkflowState:
        """Get next state without transitioning"""
        if not self.can_transition(action):
            return self.current_state
        return self.TRANSITIONS[self.current_state][action]
