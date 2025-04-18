import os
import json
from dotenv import load_dotenv
import google.generativeai as genai
import logging
import asyncio
from concurrent.futures import TimeoutError
from config.config import Config
from typing import Tuple, Optional, Dict

class LLMManager:
    def __init__(self):
        """Initialize the LLM manager with configuration and API setup"""
        self.logger = logging.getLogger(__name__)
        self.model = None
        
    def initialize(self):
        """Initialize the LLM with API key and model configuration"""
        self.logger.info("Initializing LLM...")
        try:
            # Load environment variables
            load_dotenv()
            
            # Get API key
            api_key = os.getenv('GOOGLE_API_KEY')
            if not api_key:
                raise ValueError("GOOGLE_API_KEY not found in environment variables")
            
            # Configure Gemini
            self.logger.info("Configuring Gemini API...")
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(Config.MODEL_NAME)
            self.logger.info("Gemini API configured successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing LLM: {str(e)}")
            raise

    async def generate_with_timeout(self, prompt: str, timeout: int = Config.TIMEOUT_SECONDS):
        """
        Generate content with a timeout
        
        Args:
            prompt: The prompt to send to the LLM
            timeout: Maximum time to wait for response in seconds
            
        Returns:
            The LLM response
            
        Raises:
            TimeoutError: If generation takes too long
            Exception: For other errors during generation
        """
        self.logger.info("Starting LLM generation...")
        try:
            # Convert the synchronous generate_content call to run in a thread
            loop = asyncio.get_event_loop()
            #self.logger.info(f"Prompt: {prompt}")
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None, 
                    lambda: self.model.generate_content(
                        contents=prompt
                    )
                ),
                timeout=timeout
            )
            self.logger.info("LLM generation completed")
            return response
            
        except TimeoutError:
            self.logger.error("LLM generation timed out!")
            raise
        except Exception as e:
            self.logger.error(f"Error in LLM generation: {e}")
            raise

    def parse_llm_response(self, response_text: str, expected_type: str = None) -> Tuple[bool, str, Optional[Dict]]:
        """
        Parse and validate LLM response
        
        Args:
            response_text: Raw response text from LLM
            expected_type: Expected response type (e.g., 'plan', 'function_call')
            
        Returns:
            Tuple[bool, str, Optional[Dict]]: (success, error_message, parsed_response)
        """
        try:
            # Remove markdown code block markers
            cleaned_text = response_text.replace('```json', '').replace('```', '').strip()
            
            # Handle newlines in the message content
            # First, try to parse as is
            try:
                parsed_response = json.loads(cleaned_text)
            except json.JSONDecodeError:
                # If parsing fails, try to properly escape newlines in message content
                if '"message":' in cleaned_text:
                    # Split the text at the message field
                    parts = cleaned_text.split('"message":', 1)
                    if len(parts) == 2:
                        # Get the message content and the rest
                        before_message = parts[0] + '"message": "'
                        # Find where the message content ends (at the next unescaped quote)
                        message_content = parts[1].strip()
                        in_quote = False
                        quote_end = 0
                        for i, char in enumerate(message_content):
                            if char == '"' and (i == 0 or message_content[i-1] != '\\'):
                                if in_quote:
                                    quote_end = i
                                    break
                                in_quote = True
                        
                        if quote_end > 0:
                            message = message_content[:quote_end]
                            after_message = message_content[quote_end:]
                            
                            # Escape newlines and control characters
                            escaped_message = (
                                message
                                .replace('\n', '\\n')  # Escape newlines
                                .replace('\r', '\\r')  # Escape carriage returns
                                .replace('\t', '\\t')  # Escape tabs
                                .replace('"', '\\"')   # Escape quotes
                            )
                            
                            # Reconstruct the JSON
                            cleaned_text = before_message + escaped_message + '"' + after_message
            
            # Validate response type if specified
            if expected_type and parsed_response.get("llm_response_type") != expected_type:
                return False, f"Unexpected response type. Expected {expected_type}, got {parsed_response.get('llm_response_type')}", None
            
            return True, "", parsed_response
            
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in response: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(f"Problematic text: {response_text}")
            return False, error_msg, None
            
        except Exception as e:
            error_msg = f"Error parsing response: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg, None

    def validate_response(self, response_text: str, expected_type: str = None) -> bool:
        """
        Validate that the LLM response is properly formatted
        
        Args:
            response_text: The text response from the LLM
            expected_type: Expected response type (e.g., 'plan', 'function_call')
            
        Returns:
            bool: Whether the response is valid
        """
        try:
            # Remove markdown code block markers if present
            cleaned_text = response_text.replace('```json', '').replace('```', '').strip()
            
            # Try to parse as JSON
            response_data = json.loads(cleaned_text)
            
            # Check response type if specified
            if expected_type and response_data.get("llm_response_type") != expected_type:
                self.logger.warning(f"Unexpected response type. Expected {expected_type}, got {response_data.get('response_type')}")
                return False
                
            return True
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in response: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error validating response: {e}")
            return False

    def clean_response(self, response_text: str) -> str:
        """
        Clean the LLM response text by removing markdown and extra whitespace
        
        Args:
            response_text: The raw response text from the LLM
            
        Returns:
            str: Cleaned response text
        """
        return response_text.replace('```json', '').replace('```', '').strip()
