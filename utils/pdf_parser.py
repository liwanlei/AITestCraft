# -*- coding: utf-8 -*-
import base64
from typing import Optional

from utils.logger import logger

try:
    import fitz
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

_ocr_client = None


def check_pdf_support() -> None:
    if not HAS_PYMUPDF:
        raise RuntimeError("PyMuPDF 未安装，请运行: pip install PyMuPDF")


def _get_ocr_client():
    global _ocr_client
    if _ocr_client is None:
        from openai import AsyncOpenAI
        _ocr_client = AsyncOpenAI()
    return _ocr_client


def _extract_page_text(page) -> str:
    return page.get_text().strip()


def _page_to_image_bytes(page, dpi: int = 150) -> bytes:
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    return pix.tobytes("png")


async def _ocr_page(image_bytes: bytes, model_id: str, client) -> str:
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    prompt = "请识别并提取这张图片中的所有文字内容，保持原始格式和结构，只输出提取的文本，不要添加任何解释。"

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"}
                }
            ]
        }
    ]

    try:
        response = await client.chat.completions.create(
            model=model_id,
            messages=messages,
            max_tokens=4096
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"PDF 页面 OCR 失败: {e}")
        return ""


async def parse_pdf(content: bytes, vision_model_id: Optional[str] = None) -> str:
    check_pdf_support()

    from config.config import Config

    if vision_model_id is None:
        vision_model_id = Config.PDF_VISION_MODEL_ID

    doc = fitz.open(stream=content, filetype="pdf")
    page_count = len(doc)

    if page_count > Config.PDF_MAX_PAGES:
        doc.close()
        raise ValueError(f"PDF 页数 ({page_count}) 超过限制 ({Config.PDF_MAX_PAGES})")

    logger.info(f"PDF 解析开始: {page_count} 页")

    ocr_client = _get_ocr_client()

    text_parts = []
    try:
        for i, page in enumerate(doc):
            page_text = _extract_page_text(page)

            if len(page_text) >= Config.PDF_TEXT_THRESHOLD:
                logger.debug(f"PDF 第 {i + 1} 页: 文本提取成功 ({len(page_text)} 字符)")
                text_parts.append(page_text)
            else:
                logger.debug(f"PDF 第 {i + 1} 页: 文本不足，使用多模态 OCR")
                try:
                    image_bytes = _page_to_image_bytes(page)
                    ocr_text = await _ocr_page(image_bytes, vision_model_id, ocr_client)
                    if ocr_text:
                        text_parts.append(ocr_text)
                        logger.debug(f"PDF 第 {i + 1} 页: OCR 成功 ({len(ocr_text)} 字符)")
                    else:
                        logger.warning(f"PDF 第 {i + 1} 页: OCR 返回空文本")
                except Exception as e:
                    logger.warning(f"PDF 第 {i + 1} 页: OCR 失败: {e}")
    finally:
        doc.close()

    full_text = "\n\n".join(text_parts)
    logger.info(f"PDF 解析完成: 总计 {len(full_text)} 字符")
    return full_text
