import logging
import json
from typing import Optional, Dict, List
from userinteraction.console_ui import UserInteraction
from llm.llm import LLMManager

class DecisionMaker:
    """
    Handles decision making logic for the math agent system.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def make_next_step_decision(
        self,
        llm_manager: LLMManager, 
        system_prompt: str, 
        tools: List,
        previous_feedback: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Make a decision about the next step to execute using LLM and user confirmation.
        
        Args:
            llm_manager: LLM manager instance
            system_prompt: Current system prompt
            tools: Available tools list
            previous_feedback: Optional feedback from previous attempt
            
        Returns:
            Optional[Dict]: Processed decision with tool execution info, or None if should terminate
        """
        try:
            self.logger.info("Determining next execution step...")
            
            # Add previous feedback to prompt if exists
            if previous_feedback:
                system_prompt = f"{system_prompt}\n\nPrevious Feedback: {previous_feedback}"
            
            # Get LLM's decision with timeout
            response = await llm_manager.generate_with_timeout(system_prompt)
            response_text = response.text.strip()
            self.logger.info(f"LLM Response: {response_text}")
            
            return await self._process_llm_response(response_text, system_prompt, llm_manager, tools)
            
        except Exception as e:
            UserInteraction.report_error(
                "Error in decision making",
                "Decision Error",
                str(e)
            )
            return None

    async def _process_llm_response(
        self,
        response_text: str,
        system_prompt: str,
        llm_manager: LLMManager,
        tools: List
    ) -> Optional[Dict]:
        """
        Process the LLM response and handle different response types.
        """
        try:
            # Clean and parse response
            cleaned_response = self._clean_response_text(response_text)
            response_json = json.loads(cleaned_response)
            response_type = response_json.get("response_type")
            
            if response_type == "function_call":
                return await self._handle_function_call(
                    response_json, system_prompt, llm_manager, tools
                )
            elif response_type == "final_answer":
                return await self._handle_final_answer(
                    response_json, system_prompt, llm_manager, tools
                )
            else:
                UserInteraction.report_error(
                    "Invalid response type",
                    "Decision Error",
                    f"Unexpected response type: {response_type}"
                )
                return None
                
        except json.JSONDecodeError as e:
            UserInteraction.report_error(
                "Failed to parse LLM response",
                "Parse Error",
                str(e)
            )
            return None

    def _clean_response_text(self, response_text: str) -> str:
        """Clean the response text by removing markdown and extra whitespace."""
        cleaned = response_text
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()

    async def _handle_function_call(
        self,
        response_json: Dict,
        system_prompt: str,
        llm_manager: LLMManager,
        tools: List
    ) -> Optional[Dict]:
        """Handle function call type responses."""
        function_info = response_json.get("function", {})
        func_name = function_info.get("name")
        reasoning = function_info.get("reasoning", "No reasoning provided")
        
        # Verify tool exists
        tool = next((t for t in tools if t.name == func_name), None)
        if not tool:
            UserInteraction.report_error(
                f"Unknown tool: {func_name}",
                "Tool Error",
                "The selected tool does not exist"
            )
            return None
        
        # Show decision to user and get confirmation
        decision_msg = (
            f"Proposed Next Step:\n"
            f"Tool: {func_name}\n"
            f"Parameters: {function_info.get('parameters', {})}\n"
            f"Reasoning: {reasoning}"
        )
        
        return await self._handle_user_confirmation(
            decision_msg,
            "Do you want to proceed with this step?",
            system_prompt,
            llm_manager,
            tools,
            {"type": "function_call", "tool": tool, "function_info": function_info}
        )

    async def _handle_final_answer(
        self,
        response_json: Dict,
        system_prompt: str,
        llm_manager: LLMManager,
        tools: List
    ) -> Optional[Dict]:
        """Handle final answer type responses."""
        final_msg = (
            f"Execution Complete\n"
            f"Result: {response_json.get('result')}\n"
            f"Summary: {response_json.get('summary')}"
        )
        
        return await self._handle_user_confirmation(
            final_msg,
            "Is this final result acceptable?",
            system_prompt,
            llm_manager,
            tools,
            {"type": "final_answer", "response": response_json}
        )

    async def _handle_user_confirmation(
        self,
        message: str,
        prompt: str,
        system_prompt: str,
        llm_manager: LLMManager,
        tools: List,
        success_result: Dict
    ) -> Optional[Dict]:
        """Handle user confirmation and feedback."""
        choice, feedback = UserInteraction.get_confirmation(message, prompt)
        
        if choice == "confirm":
            self.logger.info("User confirmed decision")
            return success_result
        elif choice == "redo":
            self.logger.info(f"User requested revision with feedback: {feedback}")
            return await self.make_next_step_decision(
                llm_manager,
                system_prompt,
                tools,
                feedback
            )
        else:  # abort
            self.logger.info("User aborted execution")
            return None