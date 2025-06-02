import os
import openai
import json
import logging
from typing import List, Dict, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TechniqueExtractor:
    def __init__(self):
        """Initialize the technique extractor with OpenAI client."""
        # Get API key from environment variable
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            logger.warning("OPENAI_API_KEY not found in environment variables")
        else:
            self.client = openai.OpenAI(api_key=self.api_key)

    def extract_techniques(self, caption: str) -> Dict:
        """
        Extract BJJ techniques and positions from a caption using GPT.
        
        Args:
            caption: The Instagram post caption
            
        Returns:
            Dictionary containing:
            - techniques: List of specific techniques mentioned
            - positions: List of positions mentioned
            - confidence: Confidence score for the extraction
        """
        if not self.api_key:
            logger.error("OpenAI API key not set")
            return {"techniques": [], "positions": [], "confidence": 0.0}

        try:
            # Craft a detailed prompt for GPT
            prompt = f"""Extract Brazilian Jiu-Jitsu techniques and positions from this Instagram caption.
            Separate them into two categories: specific techniques (like submissions, sweeps, passes) and positions (like guard types, mount, back control).
            Format the response as a JSON object with "techniques" and "positions" lists.
            Only include clearly mentioned BJJ-related items, don't infer or guess.
            
            Caption: {caption}
            
            Response format:
            {{
                "techniques": ["technique1", "technique2"],
                "positions": ["position1", "position2"]
            }}"""

            # Call GPT API
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a BJJ technique analyzer that extracts specific techniques and positions from text."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent results
                max_tokens=300
            )

            # Parse the response
            try:
                result = json.loads(response.choices[0].message.content)
                # Add confidence based on GPT's response
                result["confidence"] = 0.9 if response.choices[0].finish_reason == "stop" else 0.7
                return result
            except json.JSONDecodeError:
                logger.error("Failed to parse GPT response as JSON")
                return {"techniques": [], "positions": [], "confidence": 0.0}

        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return {"techniques": [], "positions": [], "confidence": 0.0}

    def format_technique_name(self, technique: str) -> str:
        """
        Format a technique name for consistency in the database.
        
        Args:
            technique: Raw technique name
            
        Returns:
            Formatted technique name
        """
        # Remove extra whitespace and convert to lowercase
        formatted = " ".join(technique.strip().split()).lower()
        
        # Remove common prefixes if they exist
        prefixes_to_remove = ["bjj", "the", "a"]
        for prefix in prefixes_to_remove:
            if formatted.startswith(prefix + " "):
                formatted = formatted[len(prefix) + 1:]
        
        return formatted.strip() 