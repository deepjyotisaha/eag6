# eag6/math_agent/memory/working_memory.py
from typing import Optional, Dict, List
from datetime import datetime
import json
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree
from rich.text import Text

console = Console()

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
        self.current_step_number = 0

    def add_step(self, step_info: dict):
        """
        Add a new execution step to history
        
        Args:
            step_info: Dictionary containing step details
        """
        self.current_step_number += 1
        step_info["step_number"] = self.current_step_number
        step_info["timestamp"] = datetime.now()
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
        self.current_step_number = 0

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
            "user_query": self.user_query,
            "last_step": self.get_last_step()
        }

    def get_step_history(self) -> List[Dict]:
        """
        Get complete step history
        
        Returns:
            List[Dict]: List of all execution steps
        """
        return self.steps

    def _format_timestamp(self, timestamp: datetime) -> str:
        """Format timestamp for display"""
        return timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    def _create_step_tree(self, tree: Tree, step: Dict) -> None:
        """Recursively create a tree representation of a step"""
        for key, value in step.items():
            if key == "timestamp":
                tree.add(f"{key}: {self._format_timestamp(value)}")
            elif isinstance(value, dict):
                subtree = tree.add(f"{key}:")
                self._create_step_tree(subtree, value)
            elif isinstance(value, list):
                subtree = tree.add(f"{key}:")
                for item in value:
                    if isinstance(item, dict):
                        self._create_step_tree(subtree, item)
                    else:
                        subtree.add(str(item))
            else:
                tree.add(f"{key}: {value}")

    def print_status(self, detailed: bool = False) -> None:
        """
        Print the current execution history status in a pretty format
        
        Args:
            detailed: If True, prints full step details. If False, prints summary
        """
        # Create main tree
        main_tree = Tree("📋 Execution History")

        # Add Query Information
        query_tree = main_tree.add("🔍 Query")
        query_tree.add(str(self.user_query) if self.user_query else "No query set")

        # Add Plan Information
        plan_tree = main_tree.add("📝 Plan")
        if self.plan:
            if isinstance(self.plan, dict):
                self._create_step_tree(plan_tree, self.plan)
            else:
                plan_tree.add(str(self.plan))
        else:
            plan_tree.add("No plan set")

        # Add Steps Information
        steps_tree = main_tree.add(f"👣 Steps ({self.get_step_count()} total)")
        if detailed:
            # Show all steps in detail
            for step in self.steps:
                step_tree = steps_tree.add(f"Step {step.get('step_number', '?')}")
                self._create_step_tree(step_tree, step)
        else:
            # Show summary of steps
            for step in self.steps:
                step_type = step.get('type', 'unknown')
                step_num = step.get('step_number', '?')
                timestamp = step.get('timestamp', datetime.now())
                steps_tree.add(
                    f"Step {step_num}: {step_type} "
                    f"({self._format_timestamp(timestamp)})"
                )

        # Add Final Answer Information
        answer_tree = main_tree.add("✅ Final Answer")
        if self.final_answer:
            if isinstance(self.final_answer, dict):
                self._create_step_tree(answer_tree, self.final_answer)
            else:
                answer_tree.add(str(self.final_answer))
        else:
            answer_tree.add("No final answer yet")

        # Print the tree in a panel
        console.print(Panel(
            main_tree,
            title="Execution Status",
            subtitle=f"Generated at {self._format_timestamp(datetime.now())}",
            border_style="blue"
        ))

    def print_json(self) -> None:
        """Print the execution history as formatted JSON"""
        status = {
            "query": self.user_query,
            "plan": self.plan,
            "steps": self.steps,
            "final_answer": self.final_answer,
            "summary": self.get_execution_summary()
        }
        
        console.print(Panel(
            json.dumps(status, indent=2, default=str),
            title="Execution Status (JSON)",
            subtitle=f"Generated at {self._format_timestamp(datetime.now())}",
            border_style="blue"
        ))