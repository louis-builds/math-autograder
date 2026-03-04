import sys
import os
try:
    import PyPDF2
    from docx import Document
    from docx.shared import Pt
    from google import genai
    from pydantic import BaseModel, Field
    from typing import List
except ImportError:
    print("Please install dependencies first: pip install pydantic google-genai PyPDF2 python-docx python-dotenv")
    sys.exit(1)

# Define the structure for each extracted math problem
class EquationEntry(BaseModel):
    page_number: int = Field(description="The page number of the exam paper, starting from 1")
    expression: str = Field(description="The mathematical expression extracted and converted to standard format, e.g., 125 - 45 or 144 / 12")
    is_word_problem: bool = Field(description="Determine if this is a word problem that requires understanding text to formulate the equation (not just a standalone mathematical expression)")

class PaperStructure(BaseModel):
    equations: List[EquationEntry]

def extract_text_from_pdf(pdf_path: str) -> str:
    print(f"[1/4] Reading local PDF: {pdf_path}")
    text = ""
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        # Annotate each page with its page number to help the LLM extract the correct page
        for idx, page in enumerate(reader.pages):
            t = page.extract_text()
            if t:
                text += f"\n--- The following content is from page {idx+1} ---\n"
                text += t + "\n"
    return text

def parse_with_gemini(text: str) -> List[EquationEntry]:
    print("[2/4] Sending to LLM for equation extraction... (This only takes one request, please wait)")
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.environ.get("GEMINI_API_KEY")
        except ImportError:
            pass
            
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY environment variable! Provide it in the terminal or create a .env file with `GEMINI_API_KEY=xxx`.")
        
    client = genai.Client(api_key=api_key) 
    prompt = f"""
Please analyze the following primary school math exam paper text, which includes page number markers.
Your primary goal is to be EXHAUSTIVE. You must extract EVERY SINGLE mathematical calculation problem, word problem, and equation you can find in the text. DO NOT SKIP ANY QUESTIONS.
Convert columnar addition/subtraction, or text multiplication/division signs into standard operators (+ - * /).
For every extracted problem, correctly identify which page it belongs to (page_number).
Also, based on the question content, determine whether it's a word problem that requires reading context to formulate the equation (set is_word_problem to true).

CRITICAL EXTRACTION RULES FOR VALID COMPUTATION:
1. VARIABLES: If a question asks to calculate `x + y` or `a * b` based on a table/context, DO NOT output `x + y` literally. You MUST substitute the actual numerical values from the context into the expression (e.g. `15 + 7`). Furthermore, SET `is_word_problem` to `false` for these variable substitution questions, because they only need a simple number answer, not a word problem sentence.
2. FRACTIONS & DECIMALS: You MUST NOT skip any questions involving fractions (e.g. 1/2) or decimals (e.g. 0.5). Extract them all. All fractions must be converted to valid Python float division. Mixed fractions like `1 1/2` MUST be formatted as `(1 + 1/2)`. `3 3/4` MUST be formatted as `(3 + 3/4)`.
3. MULTIPLE ANSWERS: If a question asks for two or more numbers (e.g., "What are the two numbers?"), the `expression` field MUST be formatted as a Python tuple of mathematical expressions separated by a comma (e.g. `(25+7)/2, (25-7)/2`). Set `is_word_problem` to `false` so it only shows the final numbers.
4. EQUALS SIGN: The `expression` field MUST ONLY contain the left-hand side of the equation. NEVER include the `=` sign or the final computed answer in the `expression`.
5. GARBAGE CHARACTERS: If you encounter garbled characters like '\ufffd' that clearly represent operators (like division), fix them to standard operators (like /).

Remember: Be exhaustive. Missing a question is a failure. Return standard valid Python math equations.

Exam Text:
-------------------
{text}
"""
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config={
            'response_mime_type': 'application/json',
            'response_schema': PaperStructure
        }
    )
    result = PaperStructure.model_validate_json(response.text)
    return result.equations

def calculate_local(equations: List[EquationEntry]) -> dict:
    print("[3/4] Calculating answers locally using pure Python for precision and zero API cost...")
    # Group answers by page number
    pages_answers = {}
    
    for eq in equations:
        # Fallback safeguard: if the LLM still outputs an equation with '=', strip everything after it
        raw_exp = eq.expression.split('=')[0].strip()
        
        # Replace common variations of multiplication and division, as well as PyPDF2 garbled chars
        exp = raw_exp.replace('x', '*').replace('×', '*').replace('÷', '/').replace('\ufffd', '/')
        try:
            val = eval(exp)
            if isinstance(val, tuple):
                ans = ", ".join([str(int(float(v))) if float(v).is_integer() else str(float(v)) for v in val])
            else:
                val = float(val)
                ans = str(int(val)) if val.is_integer() else str(val)
        except Exception as e:
            ans = f"?[{e}]"
            
        # Simplistic presentation: If it's a word problem, show the equation. Otherwise, just the answer.
        # Completely drop the question numbers/labels.
        if eq.is_word_problem:
            # Prettify the expression operators back for rendering
            pretty_exp = raw_exp.replace('*', '×').replace('/', '÷')
            styled_answer = f"{pretty_exp}={ans}"
        else:
            styled_answer = f"{ans}"
            
        if eq.page_number not in pages_answers:
            pages_answers[eq.page_number] = [styled_answer]
        else:
            pages_answers[eq.page_number].append(styled_answer)
            
    return pages_answers

def export_docx(pages_answers: dict, output_path: str):
    print(f"[4/4] Formatting densely and writing to Docx: {output_path}")
    doc = Document()
    doc.add_heading('Math Assessment Answers', 0)
    
    # Output ordered by page number
    for page_num in sorted(pages_answers.keys()):
        # Provide a clear section header for the page
        p_heading = doc.add_paragraph()
        run = p_heading.add_run(f"### Page {page_num} ###")
        run.bold = True
        
        # Join all answers for this page tightly with a separator to form a dense paragraph
        answers_list_str = "  |  ".join(pages_answers[page_num])
        
        p = doc.add_paragraph(answers_list_str)
        p.paragraph_format.space_after = Pt(12)
        
    doc.save(output_path)
    print(f"Processing complete! Dense answers saved at: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python batch_solver.py <PDF_FILE_PATH> [OUTPUT_DOCX_PATH]")
        sys.exit(1)
        
    pdf_input = sys.argv[1]
    docx_output = sys.argv[2] if len(sys.argv) >= 3 else "answers_aligned.docx"
    
    try:
        raw_text = extract_text_from_pdf(pdf_input)
        structured_data = parse_with_gemini(raw_text)
        line_aligned_answers = calculate_local(structured_data)
        export_docx(line_aligned_answers, docx_output)
    except Exception as e:
        print("An error occurred: ", e)
