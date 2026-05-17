# -*- coding: utf-8 -*-
from pathlib import Path

from fastapi import UploadFile, HTTPException, status

from config.config import Config
from utils.logger import logger


async def resolve_file_content(file: UploadFile) -> str:
    filename = file.filename or ""
    file_ext = Path(filename).suffix.lower().lstrip(".") if filename else ""

    if file_ext not in Config.ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型，支持: {', '.join(Config.ALLOWED_FILE_TYPES)}"
        )

    try:
        chunks = []
        total = 0
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > Config.MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"文件大小超过限制（最大 {Config.MAX_FILE_SIZE // (1024 * 1024)}MB）"
                )
            chunks.append(chunk)
        content = b"".join(chunks)

        if file_ext == "pdf":
            return await _parse_pdf(content, filename)
        elif file_ext in ("md", "markdown"):
            return _parse_markdown(content, filename)
        else:
            return _parse_text(content, filename)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败: {e}")


async def _parse_pdf(content: bytes, filename: str) -> str:
    try:
        from utils.pdf_parser import parse_pdf, check_pdf_support
        check_pdf_support()
        task_content = await parse_pdf(content)
        logger.info(f"PDF 解析完成: {filename}, 内容长度: {len(task_content)}")
        return task_content
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF 解析失败: {e}")


def _parse_markdown(content: bytes, filename: str) -> str:
    try:
        task_content = content.decode("utf-8")
        from utils.md_parser import parse_markdown
        task_content = parse_markdown(task_content)
        logger.info(f"Markdown 解析完成: {filename}, 内容长度: {len(task_content)}")
        return task_content
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件编码错误，无法解析为UTF-8文本")


def _parse_text(content: bytes, filename: str) -> str:
    try:
        task_content = content.decode("utf-8").strip()
        logger.info(f"文件解析完成: {filename}, 内容长度: {len(task_content)}")
        return task_content
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件编码错误，无法解析为UTF-8文本")


async def resolve_doc_content(doc_url: str) -> str:
    from utils.parsers import parse_doc_url, check_doc_support

    try:
        check_doc_support(doc_url)
        task_content = await parse_doc_url(doc_url)
        logger.info(f"文档链接解析完成，内容长度: {len(task_content)}")
        return task_content
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文档解析失败: {e}")
