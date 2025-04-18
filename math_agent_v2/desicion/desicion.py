import logging
import json
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime
from userinteraction.console_ui import UserInteraction
from llm.llm import LLMManager
from memory.working_memory import ExecutionHistory
from memory.user_memory import UserMemory
from userinteraction.userinteraction_tools import create_user_interaction_tools

class DecisionMaker:
    """
    Handles decision making logic for the math agent system.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.user_interaction_tools = create_user_interaction_tools()

    async def make_next_step_decision(
        self,
        llm_manager: LLMManager, 
        tools: List,
        general_instructions: str, 
        intent_analysis: Dict,
        user_memory: UserMemory,
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

            prompt = f"""

            The following information is available to you:

            USER QUERY: {execution_history.user_query}

            USER MEMORY: {user_memory.facts}

            INTENT ANALYSIS: {intent_analysis}
              
            GENERAL INSTRUCTIONS: {general_instructions}

            PREVIOUS FEEDBACK: {previous_feedback}

            USER INTERACTION TOOLS: {self.user_interaction_tools}

            PLAN & ACTUAL STEPS EXECUTED and RESULTS:
            {{
                "execution_plan": {execution_history.plan},
                "executed_steps": {execution_history.steps},
                "final_answer": {execution_history.final_answer}
            }}
            
            What is the next step for the user query:{execution_history.user_query}

            Example Function Call:
            {{
                "llm_response_type": "function_call",
                "function": {{
                    "name": "strings_to_chars_to_int",
                    "parameters": {{
                        "string": "INDIA"
                    }},
                    "reasoning_tag": "ARITHMETIC",
                    "reasoning": "Converting characters to ASCII values for calculation"
                }}
            }}

            Example User Interaction Handling Call:
            {{
                "llm_response_type": "user_interaction",
                "function": {{
                    "name": "escalate",
                    "parameters": {{
                        "interaction_type": "escalation",
                        "question": "Is the dimension provided in centimeters or inches?",
                        "context": "The problem statement doesn't specify units for measurement"
                    }},
                    "reasoning_tag": "UNCERTAINTY",
                    "reasoning": "Units of measurement are ambiguous which affects calculation approach",
                    "confidence": "low"
                }}
            }}

            Example Final Answer:
            {{
                "llm_response_type": "final_answer",
                "result": "42",
                "summary": "Completed all calculations and displayed result"
            }}

            Important:
            - Each function call must be in a separate JSON response. 
            - Your response should have ONLY JSON object.
            - Respond with the final answer ONLY when you have completed all the steps in the plan needed to solve the end user query.
            - When a function returns multiple values, you need to process all of them
            - Do not repeat function calls with the same parameters at any cost
            - Dont add () to the function names, just use the function name as it is.
            - For User Interaction, use the as "llm_response_type": "user_interaction" and NOT as a "function_call".

            IMPORTANT: You will always have access to multiple tools, but you must always invoke the tools needed to solve the problem, and you must always follow the sequence of solving the problem.

            DO NOT include any explanations or additional text.
            """
            
            # Add previous feedback to prompt if exists
            if previous_feedback:
                execution_history.add_step({
                    "step_type": "feedback",
                    "content": previous_feedback
                })
            
            # Get LLM's decision with timeout
            response = await llm_manager.generate_with_timeout(prompt)
            response_text = response.text.strip()
            self.logger.info(f"LLM Response: {response_text}")
            
            execution_history.add_step({
                "step_type": "llm_response",
                "content": response_text
            })

            self.logger.info(f"Added LLM response to execution history")
            
            return await self._process_llm_response(
                response_text, 
                prompt, 
                llm_manager, 
                tools,
                execution_history,
                intent_analysis,
                user_memory,
                general_instructions
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
        prompt: str,
        llm_manager: LLMManager,
        tools: List,
        execution_history: ExecutionHistory,
        intent_analysis: Dict,
        user_memory: UserMemory,
        general_instructions: str
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
                    prompt, 
                    llm_manager, 
                    tools,
                    execution_history,
                    intent_analysis,
                    user_memory,
                    general_instructions
                )
            elif response_type == "user_interaction":
                return await self._handle_user_interaction(
                    response_json, 
                    execution_history=execution_history
                )
            elif response_type == "final_answer":
                return await self._handle_final_answer(
                    response_json, 
                    prompt, 
                    llm_manager, 
                    tools,
                    execution_history,
                    intent_analysis,
                    user_memory,
                    general_instructions
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
        prompt: str,
        llm_manager: LLMManager,
        tools: List,
        execution_history: ExecutionHistory,
        intent_analysis: Dict,
        user_memory: UserMemory,
        general_instructions: str
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
            llm_manager,
            tools,
            {"step_type": "function_call", "tool": tool, "function_info": function_info},
            execution_history,
            intent_analysis,
            user_memory,
            general_instructions
        )

    async def _handle_final_answer(
        self,
        response_json: Dict,
        prompt: str,
        llm_manager: LLMManager,
        tools: List,
        execution_history: ExecutionHistory,
        intent_analysis: Dict,
        user_memory: UserMemory,
        general_instructions: str
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
            llm_manager,
            tools,
            {"step_type": "final_answer", "response": response_json},
            execution_history,
            intent_analysis,
            user_memory,
            general_instructions
        )

    #This function is used to handle the user confirmation and feedback, which is hard coded as a flow
    async def _handle_user_confirmation(
        self,
        message: str,
        prompt: str,
        llm_manager: LLMManager,
        tools: List,
        success_result: Dict,
        execution_history: ExecutionHistory, 
        intent_analysis: Dict,
        user_memory: UserMemory,
        general_instructions: str
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
                tools,
                general_instructions,
                intent_analysis,
                user_memory,
                execution_history,
                feedback
            )
        else:  # abort
            self.logger.info("User aborted execution")
            execution_history.add_step({
                "step_type": "execution_aborted"
            })
            return None
        
    #This function is used to handle the user interaction type responses, which is determined by the LLM
    async def _handle_user_interaction(
        self,
        response_json: Dict,
        execution_history: ExecutionHistory
    ) -> Optional[Dict]:
        """
        Handle user interaction type responses.
        Uses UserInteraction module for all user interactions.
        """
        function_details = response_json.get('function', {})
        function_name = function_details.get('name')
        parameters = function_details.get('parameters', {})
        
        if not function_name or not parameters:
            raise ValueError("Invalid user interaction format: missing function name or parameters")

        # Execute the interaction
        result = await self._execute_user_interaction(function_name, parameters)
        
        # Record the interaction in history
        interaction_record = {
            'type': 'user_interaction',
            'function': function_name,
            'parameters': parameters,
            'reasoning': function_details.get('reasoning', ''),
            'reasoning_tag': function_details.get('reasoning_tag', ''),
            'confidence': function_details.get('confidence', ''),
            'result': result
        }
        
        execution_history.add_step({
            "step_type": "user_interaction_complete",
            "interaction_type": function_name,
            "result": result
        })
        
        return {
            "step_type": "user_interaction",
            "status": "success",
            "interaction_type": function_name,
            "result": result
        }

    async def _execute_user_interaction(
        self,
        function_name: str,
        parameters: Dict
    ) -> Any:
        """Execute the appropriate user interaction based on type."""
        logging.info(f"Executing user interaction: {function_name}")
        logging.info(f"User interaction parameters: {parameters}")
        
        if function_name == "show_information":
            logging.info(f"Showing information: {parameters.get('message', '')}")
            UserInteraction.show_information(
                message=parameters.get("message", ""),
                title=parameters.get("title", "Information")
            )
            return {"status": "shown"}
            
        elif function_name == "get_confirmation":
            logging.info(f"Getting confirmation: {parameters.get('message', '')}")
            return UserInteraction.get_confirmation(
                message=parameters.get("message", ""),
                instructions=parameters.get("instructions")
            )
            
        elif function_name == "report_error":
            logging.info(f"Reporting error: {parameters.get('message', '')}")
            UserInteraction.report_error(
                error_message=parameters.get("message", ""),
                error_type=parameters.get("error_type", "Error"),
                details=parameters.get("details")
            )
            return {"status": "error_reported"}
            
        elif function_name == "escalate":
            logging.info(f"Escalating: {parameters.get('question', '')}")
            return UserInteraction.escalate(
                question=parameters.get("question", ""),
                context=parameters.get("context")
            )
            
        else:
            # Default to showing information
            logging.info(f"Unknown interaction type: {function_name}")
            UserInteraction.show_information(
                message=str(function_name),
                title="System Message"
            )
            return {"status": "unknown_type_handled"}


