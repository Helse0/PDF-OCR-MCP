import os
import sys
import base64
import io
import time
import logging
import requests
from typing import List, Optional
from fastmcp import FastMCP
from PIL import Image, ImageDraw, ImageFont
import fitz  # PyMuPDF

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# --- Конфигурация --- #################################################
LM_STUDIO_URL = "http://localhost:3301/v1"
DEFAULT_DPI = 150
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

OCR_PROMPT = """
You are an expert OCR assistant. Transcribe the text from the image with maximum fidelity.
Rules:
1. Preserve original language. Do not translate.
2. Use Markdown for structure.
3. Use LaTeX for formulas ($...$ or $$...$$).
4. Output ONLY the transcribed content. No thinking process.
5. If no text, output "[NO TEXT]".
"""

########################################################################

mcp = FastMCP("PDF OCR Server")

def create_test_image() -> str:
    img = Image.new('RGB', (200, 100), color='white')
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except IOError:
        font = ImageFont.load_default()
    d.text((10, 10), "OCR TEST 123", fill='black', font=font)
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def get_first_model_id() -> Optional[str]:
    try:
        response = requests.get(f"{LM_STUDIO_URL}/models")
        if response.status_code == 200:
            data = response.json()
            models = data.get('data', [])
            if models:
                model_id = models[0]['id']
                logger.info(f"Selected first available model: {model_id}")
                return model_id
            else:
                logger.error("No models found in LM Studio.")
                return None
        else:
            logger.error(f"Error fetching models: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Connection error to LM Studio: {e}")
        return None

def check_vision_capability(model_id: str) -> bool:
    test_img_b64 = create_test_image()
    payload = {
        "model": model_id,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What text is in this image? Answer with only the text you see."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{test_img_b64}"}}
                ]
            }
        ],
		"max_tokens": 4000,
        "temperature": 0.1,
        "reasoning": False,
        "extra_body": {"reasoning_effort": "none"}
    }
    
    try:
        response = requests.post(f"{LM_STUDIO_URL}/chat/completions", json=payload, timeout=40)
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            if "TEST" in content.upper() or "123" in content:
                logger.info(f"Vision check passed for {model_id}")
                return True
            else:
                logger.warning(f"Vision check failed for {model_id}: {content}")
                return False
        else:
            logger.warning(f"Vision check API error for {model_id}: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error checking vision capability for {model_id}: {e}")
        return False

def pdf_to_images(pdf_path: str, page_numbers: List[int], dpi: int = DEFAULT_DPI) -> List[tuple]:
    """
    Конвертирует указанные страницы PDF в изображения.
    Возвращает список кортежей (номер_страницы, изображение_PIL).
    """
    images = []
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
        # Фильтруем несуществующие номера страниц
        valid_page_numbers = [p for p in page_numbers if 1 <= p <= total_pages]
        if not valid_page_numbers:
            logger.warning(f"No valid pages found in range 1-{total_pages}. Requested: {page_numbers}")
            return []
            
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        
        for page_num in valid_page_numbers:
            # fitz использует индексацию с 0, поэтому вычитаем 1
            page_index = page_num - 1
            page = doc.load_page(page_index)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            images.append((page_num, img))
            
        doc.close()
        return images
    except Exception as e:
        raise Exception(f"PyMuPDF failed: {e}")

def save_result_to_file(text: str, source_filename: str):
    safe_name = os.path.splitext(os.path.basename(source_filename))[0]
    timestamp = int(time.time())
    filename = f"ocr_{safe_name}_{timestamp}.txt"
    filepath = os.path.join(OUTPUT_DIR, filename)

    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(text)
    
    logger.info(f"Result appended to: {filepath}")
    return filepath

@mcp.tool()
def ocr_pdf_pages(
    file_path: str, 
    page_numbers: List[int],
    dpi: int = DEFAULT_DPI,
    max_chars: Optional[int] = None
) -> str:
    """
    Performs OCR on specific pages of a PDF file using LM Studio Vision model.
    Use this tool to process large documents in chunks to avoid timeouts.
    
    Args:
        file_path: Path to the PDF file.
        page_numbers: List of page numbers to process (e.g., [1, 2, 3]).
        dpi: Resolution for conversion (default 150).
        max_chars: Optional limit on total characters for this chunk.
        
    Returns:
        Markdown text with LaTeX formulas for the specified pages.
    """
    logger.info(f"Starting OCR for file: {file_path}, pages: {page_numbers}")
    
    if not os.path.exists(file_path):
        return f"Error: File not found at {file_path}"
    
    model_id = get_first_model_id()
    if not model_id:
        return "Error: Could not connect to LM Studio or no models found."
    
    # Проверяем vision capability при каждом вызове, на случай если пул загруженных изменится. 
    if not check_vision_capability(model_id):
        return f"Error: The first model '{model_id}' does not appear to support vision."
    
    try:
        # Получаем изображения указанных страниц
        page_images = pdf_to_images(file_path, page_numbers, dpi)
    except Exception as e:
        logger.error(f"Error processing PDF: {e}")
        return f"Error processing PDF: {str(e)}"
    
    if not page_images:
        return "Error: No valid pages were processed."
    
    full_text = ""
    total_chunks = len(page_images)
    logger.info(f"Processing {total_chunks} pages/chunks...")
    
    for i, (page_num, img) in enumerate(page_images):
        if max_chars and len(full_text) >= max_chars:
            logger.info(f"Character limit ({max_chars}) reached. Stopping.")
            break
            
        logger.info(f"Processing page {page_num} ({i+1}/{total_chunks})...")
        
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=85)
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        payload = {
            "model": model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": OCR_PROMPT},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
                    ]
                }
            ],
		"max_tokens": 4000,
        "temperature": 0.1,
        "reasoning": False,
            "extra_body": {"reasoning_effort": "none"}
        }
        
        try:
            response = requests.post(f"{LM_STUDIO_URL}/chat/completions", json=payload, timeout=40)
            if response.status_code == 200:
                result = response.json()
                page_text = result['choices'][0]['message']['content']
                
                if page_text.strip() != "[NO TEXT]":
                    full_text += f"\n\n--- Page {page_num} ---\n\n{page_text}\n"
                else:
                    full_text += f"\n\n--- Page {page_num} ---\n[NO TEXT]\n"
            else:
                error_msg = f"API Error on page {page_num}: {response.text}"
                logger.error(error_msg)
                full_text += f"\n\n--- Page {page_num} ---\n[ERROR: {error_msg}]\n"
        except Exception as e:
            error_msg = f"Request failed on page {page_num}: {str(e)}"
            logger.error(error_msg)
            full_text += f"\n\n--- Page {page_num} ---\n[ERROR: {error_msg}]\n"
            
    save_result_to_file(full_text, file_path)
    return full_text

if __name__ == "__main__":
    try:
        logger.info("Starting MCP PDF OCR Server...")
        mcp.run()
    except Exception as e:
        logger.critical(f"Fatal error in MCP server: {e}", exc_info=True)
        sys.exit(1)
