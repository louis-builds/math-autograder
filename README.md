# New Zealand Primary School Math Exam Auto-Grader (Mac OS / Unix Guide)

This minimalist tool reads a local PDF exam paper via Python, parses it using a single lightweight request to the Google Gemini-2.5-flash LLM model, calculates the math strictly through built-in mathematical evaluations (for safety and zero cost), and finally exports a printable DOCX answer sheet!

## 0. Prerequisites

1. Open the **Terminal** on your Mac. You can find it by searching "Terminal" in Spotlight.
2. Ensure Python (version 3.9+) is installed. If not, download the installer directly from the [Python Official Website](https://www.python.org/downloads/macos/).

## 1. Install Dependencies

After copying the folder containing `batch_solver.py` to your Mac, navigate into that directory using the terminal:
```bash
cd /path/to/your/saved/folder
```

Execute the following command to install the required Python packages:
```bash
pip3 install pydantic google-genai PyPDF2 python-docx python-dotenv
```
*(If `pip3` is not found, try using `python3 -m pip install ...` instead)*

## 2. Configure API Key

The tool requires your Gemini API Key. The simplest way (without modifying code) is to create a plain text file named `.env` in the **same directory** as `batch_solver.py` (notice the leading dot in the filename).

If you are unfamiliar with creating hidden files, you can simply run this command in your terminal while inside the project directory:
```bash
echo "GEMINI_API_KEY=replace_with_your_actual_api_key_here" > .env
```
*(Replace the placeholder with your actual free API key obtained from Google AI Studio)*

## 3. Start Grading!

Prepare the PDF file you wish to process, for instance, placing it in your Downloads folder like `/Users/yourname/Downloads/test_paper.pdf`.

Then, from the terminal window running inside your project folder, execute:

```bash
python3 batch_solver.py /Users/yourname/Downloads/test_paper.pdf /Users/yourname/Desktop/answers.docx
```

After pressing Enter, the terminal will print out the 4-step progress:
* `[1/4] Reading local PDF... `
* `[2/4] Sending to LLM...`
* `[3/4] Calculating answers locally using pure Python...`
* `[4/4] Formatting densely and writing to Docx...`

Once it says `🎉 Processing complete`, you will find a generated document named `answers.docx` on your Mac's **Desktop**! This document will neatly list the answers to all extracted calculation and word problems, organized perfectly page by page.
