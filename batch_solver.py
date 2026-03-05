import sys
import os
import io
import time # 必须引入 time 库
import fitz  # PyMuPDF
from typing import List
from pydantic import BaseModel, Field
from google import genai
from PIL import Image

from docx import Document
import dotenv

# 加载 .env 里的 API Key
dotenv.load_dotenv()

# --- 1. 定义数据结构 ---
class EquationEntry(BaseModel):
    page_number: int = Field(description="页码")
    expression: str = Field(description="算式，如 (1/2)+0.5 或 (1+3/4)*2")
    is_word_problem: bool = Field(description="是否为需要逻辑理解的应用题")

class PaperStructure(BaseModel):
    equations: List[EquationEntry]

# --- 2. 视觉转换逻辑 (无需 poppler) ---
def convert_pdf_to_images(pdf_path: str):
    print(f"🚀 [1/4] 正在解析 PDF: {pdf_path}")
    try:
        doc = fitz.open(pdf_path)
        images = []
        for page in doc:
            # 2.0 倍缩放确保 300DPI 左右的清晰度，方便识别微小的符号
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_data = pix.tobytes("png")
            images.append(Image.open(io.BytesIO(img_data)))
        return images
    except Exception as e:
        print(f"❌ 读取 PDF 失败: {e}")
        sys.exit(1)

# --- 3. Gemini 视觉识别核心 ---
def parse_with_gemini_vision(images: list) -> List[EquationEntry]:
    print(f"👁️ [2/4] 使用 Gemini 2.5 Flash 识别图片 (共 {len(images)} 页)...")
    
    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    all_extracted_data = []

    for i, img in enumerate(images):
        page_num = i + 1
        print(f"  正在识别第 {page_num} 页...")
        
        prompt = """你是一个数学专家。请从图片中提取所有算式：
        1. 竖式分数转为 (a/b)。
        2. 只提取等号左侧。
        3. 应用题 is_word_problem 设为 true。"""

        # --- 核心：使用你确认可用的模型名 ---
        # 加上重试和降速逻辑
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model='gemini-2.5-flash', # 回到你那个能跑通的模型
                    contents=[prompt, img],    # 视觉模式：列表包含文字和图片
                    config={
                        'response_mime_type': 'application/json', 
                        'response_schema': PaperStructure
                    }
                )
                page_data = PaperStructure.model_validate_json(response.text)
                for eq in page_data.equations:
                    eq.page_number = page_num
                    all_extracted_data.append(eq)
                
                # 每成功一页，歇 5 秒（为了躲避 429 限制）
                time.sleep(5) 
                break 

            except Exception as e:
                error_str = str(e)
                if "429" in error_str:
                    print(f"  ⏳ 频率太快，强制等待 15 秒后重试...")
                    time.sleep(15)
                elif "404" in error_str:
                    # 如果 2.5 也报 404，尝试去掉开头的 models/ 或者加上它
                    print(f"  ❌ 依然找不到模型，请检查 SDK 是否支持视觉输入。")
                    break
                else:
                    print(f"  ❌ 错误: {e}")
                    break
            
    return all_extracted_data

# --- 4. 本地计算与 Word 导出 ---
def calculate_and_save(equations, output_path):
    print("🧮 [3/4] 正在计算答案...")
    doc = Document()
    doc.add_heading('Assessment Answers (NZ Year 4)', 0)
    
    results_map = {}
    for eq in equations:
        try:
            # 清洗常见非数学字符并计算
            exp_to_eval = eq.expression.replace('×','*').replace('÷','/')
            val = eval(exp_to_eval)
            # 格式化结果：去掉多余的 .0
            ans = f"{val:.2f}".rstrip('0').rstrip('.')
            display_text = f"{eq.expression} = {ans}" if eq.is_word_problem else ans
        except:
            display_text = f"{eq.expression} (?)"
            
        results_map.setdefault(eq.page_number, []).append(display_text)

    print(f"📝 [4/4] 正在写入 Word: {output_path}")
    for p_num in sorted(results_map.keys()):
        p = doc.add_paragraph()
        run = p.add_run(f"--- Page {p_num} ---")
        run.bold = True
        
        # 紧凑排版：答案之间用分隔线隔开
        doc.add_paragraph("  |  ".join(results_map[p_num]))
        
    doc.save(output_path)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 batch_solver.py <试卷PDF路径>")
        sys.exit(1)
        
    input_pdf = sys.argv[1]
    output_docx = "math_answers_vision.docx"
    
    # 执行流水线
    img_list = convert_pdf_to_images(input_pdf)
    extracted_data = parse_with_gemini_vision(img_list)

    # ✨ 新增：结果预览验证区
    print("\n" + "="*50)
    print(f"{'页码':<5} | {'提取的算式 (Expression)':<30} | {'应用题?'}")
    print("-" * 50)
    for eq in extracted_data:
        word_tag = "✅" if eq.is_word_problem else "❌"
        print(f"{eq.page_number:<5} | {eq.expression:<30} | {word_tag}")
    print("="*50 + "\n")

    # 询问是否继续生成 Word
    confirm = input("数据如上，是否生成 Word 答案文件？(y/n): ")
    if confirm.lower() == 'y':
        calculate_and_save(extracted_data, output_docx)
    else:
        print("已取消导出。")
    
    print(f"\n✨ 大功告成！答案文件已生成：{output_docx}")
