from google.generativeai import configure, GenerativeModel
import google.generativeai as genai
import json
import re

from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Get API key from environment variable
API_KEY = os.getenv('GOOGLE_API_KEY')

# Validate API key is present
if not API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in environment variables. Please check your .env file.")


# Configure the library with your API key
configure(api_key=API_KEY)

def clean_response(text):
    """Clean the response by removing markdown formatting and extra text."""
    # Remove markdown code block markers
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    
    # Remove any text before the first {
    text = re.sub(r'^[^{]*({.*})[^}]*$', r'\1', text, flags=re.DOTALL)
    
    return text.strip()

def generate_poem():
    # Initialize the model (Gemini 2.0 Flash)
    model = GenerativeModel('gemini-2.0-flash')
    
    # Sample email in markdown format
    prompt = """Analyze this email and provide a summary in JSON format, please note do not include any other text, dont apply any markdown formatting, respond with ONLY JSON Object which can be parsed by JSON parser:

    # Weekly Tech Newsletter
    
    ## Latest Updates
    
    ### New Features Released
    We're excited to announce the launch of our new AI-powered analytics dashboard. This feature provides:
    - Real-time data visualization
    - Custom report generation
    - Automated insights
    
    ### Community Highlights
    - User engagement increased by 45% this month
    - New community guidelines published
    - Upcoming webinar on advanced features
    
    ## Upcoming Events
    - March 25: Live demo of new dashboard
    - March 30: Community Q&A session
    
    ---
    To unsubscribe, click here: [Unsubscribe](https://example.com/unsubscribe)
    
    Return your response as a JSON object with these fields:
    {
        "subject": "Main topic or theme",
        "key_points": ["List of main points"],
        "action_items": ["List of required actions"],
        "date": "Relevant date mentioned"
    }
    
   """

    try:
        print("Generated Prompt:")
        print(prompt)
    
        # Generate the response
        response = model.generate_content(prompt)

        print("Generated Response:")
        print(response.text)
        
        # Clean the response before parsing
        cleaned_response = clean_response(response.text)
        print("Cleaned Response:")
        print(cleaned_response)
        
        # Parse and print the JSON response
        print("Generated Summary:")
        summary = json.loads(cleaned_response)
        print(json.dumps(summary, indent=2))
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    generate_poem()