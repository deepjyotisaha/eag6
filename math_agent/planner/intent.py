from typing import Dict, List, Optional, Any
from datetime import datetime
from memory.user_memory import UserMemory
from userinteraction.console_ui import UserInteraction
from llm.llm import LLMManager

class IntentAnalyzer:
    def __init__(self, llm_manager: LLMManager, user_memory: UserMemory):
        self.llm_manager = llm_manager
        self.user_memory = user_memory

    async def analyze_intent(
        self,
        query: str,
        system_prompt: str
    ) -> Dict:
        """
        Analyze the user's query to extract intent, constraints, and requirements.
        
        Args:
            query: The user's query
            system_prompt: System context/prompt
            
        Returns:
            Dict containing analyzed intent information
        """
        # Get relevant context from user memory
        memory_context = await self._gather_relevant_context(query)
        
        # Create comprehensive analysis prompt
        analysis_prompt = f"""
        Analyze the following user query to extract detailed intent information.
        
        User Query: {query}
        System Context: {system_prompt}
        
        User History and Context:
        {memory_context}
        
        Provide a comprehensive analysis in JSON format that includes:
        1. Primary intent (what the user wants to achieve)
        2. Sub-intents (component tasks or goals)
        3. Constraints and requirements
        4. Required knowledge or context
        5. Expected output format
        6. Potential challenges
        7. User preferences based on history
        
        Response Format:
        {{
            "primary_intent": {{
                "action": "main action or goal",
                "subject": "what the action applies to",
                "objective": "desired outcome"
            }},
            "sub_intents": [
                {{
                    "action": "component action",
                    "purpose": "why this is needed",
                    "dependencies": ["any dependencies"]
                }}
            ],
            "constraints": [
                {{
                    "type": "time/resource/format/etc",
                    "description": "constraint details",
                    "severity": "high/medium/low"
                }}
            ],
            "required_knowledge": [
                {{
                    "domain": "knowledge area",
                    "specifics": "what needs to be known",
                    "availability": "available/needs_gathering"
                }}
            ],
            "output_requirements": {{
                "format": "expected format",
                "level_of_detail": "basic/detailed/comprehensive",
                "special_requirements": ["any special requirements"]
            }},
            "potential_challenges": [
                {{
                    "challenge": "description",
                    "impact": "high/medium/low",
                    "mitigation_strategy": "how to address"
                }}
            ],
            "user_preferences": [
                {{
                    "preference": "description",
                    "source": "historical interaction/explicit statement",
                    "confidence": "high/medium/low"
                }}
            ]
        }}
        """

        try:
            # Get intent analysis from LLM
            response = await self.llm_manager.generate_with_timeout(analysis_prompt)
            intent_data = self.llm_manager.clean_response(response.text)
            
            # Parse and validate the response
            intent_analysis = self._validate_intent_analysis(intent_data)
            
            # Enhance analysis with additional context
            enhanced_analysis = await self._enhance_with_context(intent_analysis, query)
            
            # Store the intent analysis in user memory
            await self._store_intent_analysis(enhanced_analysis, query)
            
            return enhanced_analysis
            
        except Exception as e:
            UserInteraction.report_error(
                "Error analyzing query intent",
                "Intent Analysis Error",
                str(e)
            )
            return self._get_fallback_intent_analysis(query)

    async def _gather_relevant_context(self, query: str) -> str:
        """
        Gather relevant context from user memory for intent analysis.
        """
        try:
            # Get relevant facts from user memory
            relevant_facts = await self.user_memory.recall_query_specific_facts(query)
            
            # Format context information
            context_parts = []
            
            if relevant_facts:
                context_parts.append("Previous Relevant Information:")
                for fact in relevant_facts:
                    context_parts.append(f"- {fact.get('type', 'fact')}: {fact.get('response', '')}")
            
            # Add user preferences if available
            preferences = [f for f in self.user_memory.facts if f.get('type') == 'preference']
            if preferences:
                context_parts.append("\nUser Preferences:")
                for pref in preferences:
                    context_parts.append(f"- {pref.get('category', 'general')}: {pref.get('value', '')}")
            
            return "\n".join(context_parts) if context_parts else "No relevant context found."
            
        except Exception:
            return "Error retrieving context."

    def _validate_intent_analysis(self, intent_data: str) -> Dict:
        """
        Validate and structure the intent analysis response.
        """
        try:
            import json
            analysis = json.loads(intent_data)
            
            # Ensure all required fields are present
            required_fields = [
                "primary_intent",
                "sub_intents",
                "constraints",
                "required_knowledge",
                "output_requirements"
            ]
            
            for field in required_fields:
                if field not in analysis:
                    analysis[field] = self._get_default_field_value(field)
            
            return analysis
            
        except json.JSONDecodeError:
            return self._get_fallback_intent_analysis("Invalid response format")

    async def _enhance_with_context(self, intent_analysis: Dict, query: str) -> Dict:
        """
        Enhance intent analysis with additional context and insights.
        """
        # Add metadata
        intent_analysis["metadata"] = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "confidence_score": self._calculate_confidence_score(intent_analysis)
        }
        
        # Add execution hints
        intent_analysis["execution_hints"] = {
            "suggested_approach": self._determine_approach(intent_analysis),
            "priority_order": self._determine_priority_order(intent_analysis),
            "critical_checkpoints": self._identify_critical_checkpoints(intent_analysis)
        }
        
        return intent_analysis

    async def _store_intent_analysis(self, analysis: Dict, query: str) -> None:
        """
        Store the intent analysis in user memory for future reference.
        """
        self.user_memory.add_fact({
            "type": "intent_analysis",
            "query": query,
            "analysis": analysis,
            "timestamp": datetime.now().isoformat()
        })

    def _get_fallback_intent_analysis(self, query: str) -> Dict:
        """
        Provide a basic fallback intent analysis when detailed analysis fails.
        """
        return {
            "primary_intent": {
                "action": "process",
                "subject": query,
                "objective": "complete task"
            },
            "sub_intents": [],
            "constraints": [],
            "required_knowledge": [],
            "output_requirements": {
                "format": "standard",
                "level_of_detail": "basic"
            }
        }

    def _calculate_confidence_score(self, analysis: Dict) -> float:
        """
        Calculate a confidence score for the intent analysis.
        """
        score = 1.0
        
        # Reduce score based on missing or incomplete information
        if not analysis.get("sub_intents"):
            score *= 0.8
        if not analysis.get("constraints"):
            score *= 0.9
        if not analysis.get("required_knowledge"):
            score *= 0.85
            
        return round(score, 2)

    def _determine_approach(self, analysis: Dict) -> str:
        """
        Determine the suggested approach based on intent analysis.
        """
        if not analysis.get("sub_intents"):
            return "direct_execution"
        return "decomposed_execution"

    def _determine_priority_order(self, analysis: Dict) -> List[str]:
        """
        Determine the priority order of sub-intents.
        """
        sub_intents = analysis.get("sub_intents", [])
        return [si["action"] for si in sub_intents]

    def _identify_critical_checkpoints(self, analysis: Dict) -> List[str]:
        """
        Identify critical checkpoints in the execution process.
        """
        checkpoints = []
        
        # Add constraint-based checkpoints
        for constraint in analysis.get("constraints", []):
            if constraint.get("severity") == "high":
                checkpoints.append(f"Verify {constraint['type']}: {constraint['description']}")
        
        # Add knowledge-based checkpoints
        for knowledge in analysis.get("required_knowledge", []):
            if knowledge.get("availability") == "needs_gathering":
                checkpoints.append(f"Gather {knowledge['domain']} knowledge")
        
        return checkpoints

    def _get_default_field_value(self, field: str) -> Any:
        """
        Get default values for missing fields in intent analysis.
        """
        defaults = {
            "primary_intent": {"action": "process", "subject": "query", "objective": "complete"},
            "sub_intents": [],
            "constraints": [],
            "required_knowledge": [],
            "output_requirements": {"format": "standard", "level_of_detail": "basic"}
        }
        return defaults.get(field, {})
