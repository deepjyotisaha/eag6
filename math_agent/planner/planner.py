import json
import logging
from typing import Optional, Dict
from userinteraction.console_ui import UserInteraction
from llm.llm import LLMManager

class Planner:
    def __init__(self, llm_manager: LLMManager):
        """
        Initialize the planner
        
        Args:
            llm_manager: LLMManager instance
        """
        self.llm_manager = llm_manager
        self.logger = logging.getLogger(__name__)

    async def get_plan(self, system_prompt: str, execution_history) -> Optional[Dict]:
        """
        Get the initial plan from LLM and seek user confirmation
        
        Args:
            system_prompt: The system prompt to use
            execution_history: Current execution history
            
        Returns:
            Optional[Dict]: The confirmed plan or None if aborted
        """
        self.logger.info("Generating initial plan...")
        
        try:
            # Generate plan from LLM
            plan_prompt = f"{system_prompt}\n\nPlease generate a plan for the following query: {execution_history.user_query}"
            response = await self.llm_manager.generate_with_timeout(plan_prompt)
            response_text = response.text

            # Clean and validate the response
            if not self.llm_manager.validate_response(response_text, expected_type="plan"):
                raise ValueError("Invalid plan response format")
                
            response_text = self.llm_manager.clean_response(response_text)
            self.logger.info(f"Plan response: {response_text}")
            
            # Clean the response text by removing markdown code block markers
            #response_text = response_text.replace('```json', '').replace('```', '').strip()
            #self.logger.info(f"Plan response: {response_text}")
            
            try:
                # Parse the response to get the plan
                plan_data = json.loads(response_text)
                if plan_data.get("llm_response_type") != "plan":
                    raise ValueError("Expected plan response type")
                
                plan_steps = plan_data.get("steps", [])
                
                # Format plan for user display
                plan_display = "Proposed Plan:\n"
                for step in plan_steps:
                    plan_display += f"\nStep {step['step_number']}:"
                    plan_display += f"\n- Action: {step['description']}"
                    plan_display += f"\n- Reasoning: {step['reasoning']}"
                    plan_display += f"\n- Tool: {step.get('expected_tool', 'No tool specified')}"
                
                # Show plan to user and get confirmation
                choice, feedback = UserInteraction.get_confirmation(
                    plan_display,
                    "Please review the proposed plan. You can confirm to proceed, provide feedback to revise, or abort."
                )
                
                if choice == "confirm":
                    self.logger.info("Plan confirmed by user")
                    execution_history.plan = plan_data
                    return plan_data
                elif choice == "redo":
                    self.logger.info(f"User requested plan revision with feedback: {feedback}")
                    # Add feedback to prompt and try again
                    revised_prompt = f"{plan_prompt}\n\nRevision Request Feedback: {feedback}\n\nYou need to consider the revision request feedback while generating the plan."
                    return await self.get_plan(revised_prompt, execution_history)
                else:  # abort
                    self.logger.info("Plan aborted by user")
                    UserInteraction.show_information("Operation aborted by user", "Abort")
                    return None
                    
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse LLM response as JSON: {e}")
                UserInteraction.report_error(
                    "Failed to generate a valid plan",
                    "Plan Generation Error",
                    f"The model response was not in the expected format: {str(e)}"
                )
                return None
                
        except Exception as e:
            self.logger.error(f"Error generating plan: {str(e)}")
            UserInteraction.report_error(
                "Failed to generate plan",
                "Plan Generation Error",
                str(e)
            )
            return None