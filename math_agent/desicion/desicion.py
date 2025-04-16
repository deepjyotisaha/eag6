import logging
import json
from typing import Optional, Dict, List
from datetime import datetime
from userinteraction.console_ui import UserInteraction
from llm.llm import LLMManager
from memory.working_memory import ExecutionHistory

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
        execution_history: ExecutionHistory,
        previous_feedback: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Make a decision about the next step to execute using LLM and user confirmation.
        
        Args:
            llm_manager: LLM manager instance
            system_prompt: Current system prompt
            tools: Available tools list
            execution_history: Execution history object
            previous_feedback: Optional feedback from previous attempt
            
        Returns:
            Optional[Dict]: Processed decision with tool execution info, or None if should terminate
        """
        try:
            self.logger.info("Before determining next execution step...")
            # Print summary view
            #execution_history.print_status()

            # Print detailed view
            execution_history.print_status(detailed=True)

            # Print JSON view
            #execution_history.print_json()
            
            self.logger.info("Determining next execution step...")
            
            # Add previous feedback to prompt if exists
            if previous_feedback:
                system_prompt = f"{system_prompt}\n\nPrevious Feedback: {previous_feedback}\n\n. Refer to the context history and previous feedback to determine the next step."
                execution_history.add_step({
                    "step_type": "feedback",
                    "content": previous_feedback
                })
            
            # Get LLM's decision with timeout
            response = await llm_manager.generate_with_timeout(system_prompt)
            response_text = response.text.strip()
            self.logger.info(f"LLM Response: {response_text}")
            
            execution_history.add_step({
                "step_type": "llm_response",
                "content": response_text
            })

            self.logger.info(f"Added LLM response to execution history")
            
            return await self._process_llm_response(
                response_text, 
                system_prompt, 
                llm_manager, 
                tools,
                execution_history
            )
            
        except Exception as e:
            error_msg = str(e)
            UserInteraction.report_error(
                "Error in decision making",
                "Decision Error",
                error_msg
            )
            execution_history.add_step({
                "step_type": "error",
                "error_type": "decision_error",
                "error_message": error_msg
            })
            return None

    async def _process_llm_response(
        self,
        response_text: str,
        system_prompt: str,
        llm_manager: LLMManager,
        tools: List,
        execution_history: ExecutionHistory
    ) -> Optional[Dict]:
        """
        Process the LLM response and handle different response types.
        """
        try:
            # Clean and parse response
            cleaned_response = self._clean_response_text(response_text)
            response_json = json.loads(cleaned_response)
            response_type = response_json.get("llm_response_type")
            
            execution_history.add_step({
                "step_type": "processed_llm_response",
                "llm_response_type": response_type,
                "content": response_json
            })
            
            if response_type == "function_call":
                return await self._handle_function_call(
                    response_json, 
                    system_prompt, 
                    llm_manager, 
                    tools,
                    execution_history
                )
            elif response_type == "final_answer":
                return await self._handle_final_answer(
                    response_json, 
                    system_prompt, 
                    llm_manager, 
                    tools,
                    execution_history
                )
            else:
                error_msg = f"Unexpected response type: {response_type}"
                UserInteraction.report_error(
                    "Invalid response type",
                    "Decision Error",
                    error_msg
                )
                execution_history.add_step({
                    "step_type": "error",
                    "error_type": "invalid_response_type",
                    "error_message": error_msg
                })
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
        tools: List,
        execution_history: ExecutionHistory
    ) -> Optional[Dict]:
        """Handle function call type responses."""
        function_info = response_json.get("function", {})
        func_name = function_info.get("name")
        reasoning = function_info.get("reasoning", "No reasoning provided")
        
        execution_history.add_step({
            "step_type": "function_proposal",
            "function": func_name,
            "parameters": function_info.get("parameters", {}),
            "reasoning": reasoning
        })
        
        tool = next((t for t in tools if t.name == func_name), None)
        if not tool:
            error_msg = f"Unknown tool: {func_name}"
            UserInteraction.report_error(
                error_msg,
                "Tool Error",
                "The selected tool does not exist"
            )
            execution_history.add_step({
                "step_type": "error",
                "error_type": "unknown_tool",
                "error_message": error_msg
            })
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
            {"step_type": "function_call", "tool": tool, "function_info": function_info},
            execution_history
        )

    async def _handle_final_answer(
        self,
        response_json: Dict,
        system_prompt: str,
        llm_manager: LLMManager,
        tools: List,
        execution_history: ExecutionHistory
    ) -> Optional[Dict]:
        """Handle final answer type responses."""
        final_msg = (
            f"Execution Complete\n"
            f"Result: {response_json.get('result')}\n"
            f"Summary: {response_json.get('summary')}"
        )
        
        execution_history.add_step({
            "step_type": "final_answer_proposal",
            "result": response_json.get('result'),
            "summary": response_json.get('summary')
        })
        
        return await self._handle_user_confirmation(
            final_msg,
            "Is this final result acceptable?",
            system_prompt,
            llm_manager,
            tools,
            {"step_type": "final_answer", "response": response_json},
            execution_history
        )

    async def _handle_user_confirmation(
        self,
        message: str,
        prompt: str,
        system_prompt: str,
        llm_manager: LLMManager,
        tools: List,
        success_result: Dict,
        execution_history: ExecutionHistory
    ) -> Optional[Dict]:
        """Handle user confirmation and feedback."""
        choice, feedback = UserInteraction.get_confirmation(message, prompt)
        
        execution_history.add_step({
            "step_type": "user_confirmation",
            "choice": choice,
            "feedback": feedback,
            "message": message,
            "prompt": prompt
        })
        
        if choice == "confirm":
            self.logger.info("User confirmed decision")
            execution_history.add_step({
                "step_type": "decision_confirmed",
                "result": success_result
            })
            return success_result
        elif choice == "redo":
            self.logger.info(f"User requested revision with feedback: {feedback}")
            execution_history.add_step({
                "step_type": "decision_revision",
                "feedback": feedback
            })
            return await self.make_next_step_decision(
                llm_manager,
                system_prompt,
                tools,
                execution_history,
                feedback
            )
        else:  # abort
            self.logger.info("User aborted execution")
            execution_history.add_step({
                "step_type": "execution_aborted"
            })
            return None