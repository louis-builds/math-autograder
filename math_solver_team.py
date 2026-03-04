import asyncio
from typing import List
from google.genai import types
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

# 1. Define exact calculation tool (Core: Prevent AI calculation errors)
def strict_calculator(expression: str) -> str:
    """Used to execute addition, subtraction, multiplication, and division calculations for New Zealand exam papers, supporting fractions and percentages.
    Supported operators include: +, -, *, /, x, ×, ÷
    """
    # Clean up and replace common multiplication and division expressions
    exp = expression.replace('x', '*').replace('×', '*').replace('÷', '/')
    try:
        # In actual production environments, it is recommended to use safe math or ast.literal_eval combinations, or the sympy library instead of eval
        result = float(eval(exp))
        # Remove the trailing .0 of integer results
        if result.is_integer():
            return str(int(result))
        return str(result)
    except Exception as e:
        return f"Calculation Error: {e}"

# 2. Define an Agent specifically for parsing PDFs
pdf_parser = Agent(
    name="NZ_Paper_Scanner",
    model="gemini-2.5-flash",
    instruction="""You are responsible for reading the PDF/image content of New Zealand primary and secondary school math exam papers.
Responsibilities:
1. Accurately identify all addition, subtraction, multiplication, and division expressions, as well as fractions and percentages within them.
2. You must retain the original question numbers (e.g., Q1, Q2, etc.).
3. If you encounter columnar arithmetic problems on the page, you need to convert them into standard horizontal expressions.
4. Output the organized list of standard expressions completely and clearly to the Math_Expert in the team."""
)

# 3. Define the Solver Agent
math_solver = Agent(
    name="Math_Expert",
    model="gemini-2.5-flash",
    tools=[strict_calculator],
    instruction="""You are a Math Solver Expert. You receive organized math expressions from the scanner.
Responsibilities:
1. For every expression received, you are strictly forbidden to "mentally calculate" or guess the answer yourself.
2. You must call the `strict_calculator` tool, input the mathematical expression to calculate it, and obtain a 100% accurate forward calculation result.
3. Consolidate the original question number, original expression, and the forward result calculated by the tool, and hand it over to the Math_Checker for verification."""
)

# 4. Define the Checker Agent
math_checker = Agent(
    name="Math_Checker",
    model="gemini-2.5-flash",
    tools=[strict_calculator],
    instruction="""You are a rigorous Checker. Your core responsibility is to perform strict reverse verification on the math answers provided by the Solver to completely eliminate errors.
The verification logic is as follows (you must use reverse operations to verify):
- If the original expression is subtraction (e.g., 100 - 34 = 66), you must verify the corresponding addition (call the tool to calculate 66 + 34 and see if it equals 100).
- If the original expression is addition (e.g., 66 + 34 = 100), you must verify the corresponding subtraction (call the tool to calculate 100 - 34 and see if it equals 66).
- If the original expression is division (e.g., 100 / 4 = 25), you must verify the corresponding multiplication (call the tool to calculate 25 * 4 and see if it equals 100).
- If the original expression is multiplication (e.g., 25 * 4 = 100), you must verify the corresponding division (call the tool to calculate 100 / 4 and see if it equals 25).

Workflow:
1. Analyze the expression and initial result sent by the Solver.
2. Construct the corresponding "reverse expression".
3. Call `strict_calculator` to calculate the result of the reverse expression.
4. Compare and verify:
   - If the reverse calculation result matches the original value on the other side of the equation, it means the initial calculation was correct. Output: "Verification Passed ✅" and provide the accurate answer in the final report.
   - If it does not match, it indicates the initial calculation or parsing was wrong. Output: "Verification Failed ❌", and correct the answer."""
)

# 5. Simulate workflow team execution logic (Replacing the non-existent google.adk.workflows.Team)
class BasicTeamWorkflow:
    def __init__(self, agents: List[Agent], name: str, instruction: str):
        self.agents = agents
        self.name = name
        self.instruction = instruction
        self.session_service = InMemorySessionService()

    async def _call_agent_async(self, agent: Agent, query: str) -> str:
        runner = Runner(agent=agent, app_name=self.name, session_service=self.session_service)
        await self.session_service.create_session(
            app_name=self.name, user_id="test_user", session_id="test_session"
        )
        print(f"\n[🔄] {agent.name} is thinking/executing...")
        content = types.Content(role='user', parts=[types.Part(text=query)])
        final_response_text = "No final result generated"
        
        async for event in runner.run_async(user_id="test_user", session_id="test_session", new_message=content):
            if event.is_final_response():
                if getattr(event, 'content', None) and getattr(event.content, 'parts', None):
                    final_response_text = event.content.parts[0].text
                break
        return final_response_text

    async def run(self, initial_input: str):
        print(f"====== Starting pipeline team: {self.name} ======")
        print(self.instruction)
        
        current_input = initial_input
        # Sequentially pass the output of the previous Agent to the next system according to the pipeline order
        for agent in self.agents:
            response = await self._call_agent_async(agent, current_input)
            print(f"\n[Answer] {agent.name} output result:\n{response}")
            print("-" * 50)
            current_input = f"Please continue your task based on this report from the previous stage:\n{response}"
            
        print("====== Pipeline execution finished ======\n")

# Instantiate pipeline team
math_team = BasicTeamWorkflow(
    agents=[pdf_parser, math_solver, math_checker],
    name="NZ_Math_Assessment_Team",
    instruction="""Collaboration pipeline workflow: Scanner organizes questions -> Expert calculates forwards -> Checker verifies backwards."""
)

# ========== Test Entry ==========
async def main():
    # Simulate an input: Assume this is a page of PDF OCR extracted text or user-directly-input exam content
    mock_pdf_input = """
    New Zealand Year 4 Math Test:
    Q1: 125 - 45
    Q2: 12 x 8
    Q3: 144 ÷ 12
    Q4: 25 + 77
    """
    await math_team.run(mock_pdf_input)

if __name__ == "__main__":
    asyncio.run(main())
