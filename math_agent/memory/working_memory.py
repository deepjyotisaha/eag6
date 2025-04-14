# eag6/math_agent/memory/working_memory.py
from typing import Optional, Dict


class ExecutionHistory:
    """
    Tracks the execution history of the math agent.
    Maintains the working memory of the agent's execution including
    plan, steps, results, and user queries.
    """
    def __init__(self):
        self.plan = None
        self.steps = []
        self.final_answer = None
        self.user_query = None

    def add_step(self, step_info: dict):
        """
        Add a new execution step to history
        
        Args:
            step_info: Dictionary containing step details
        """
        self.steps.append(step_info)

    def get_last_step(self) -> Optional[dict]:
        """
        Get the most recent execution step
        
        Returns:
            Optional[dict]: The last step info or None if no steps exist
        """
        return self.steps[-1] if self.steps else None

    def clear(self):
        """Reset the execution history"""
        self.plan = None
        self.steps = []
        self.final_answer = None
        self.user_query = None

    def get_step_count(self) -> int:
        """
        Get the total number of execution steps
        
        Returns:
            int: Number of steps executed
        """
        return len(self.steps)

    def has_plan(self) -> bool:
        """
        Check if a plan exists
        
        Returns:
            bool: True if plan exists, False otherwise
        """
        return self.plan is not None

    def get_execution_summary(self) -> dict:
        """
        Get a summary of the execution history
        
        Returns:
            dict: Summary of execution including plan, step count, and final answer status
        """
        return {
            "has_plan": self.has_plan(),
            "total_steps": self.get_step_count(),
            "has_final_answer": self.final_answer is not None,
            "user_query": self.user_query
        }