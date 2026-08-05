from pathlib import Path


def restore_linebreak_symbols(filename: str, encoding: str = "utf-8"):
    """将文本文本中的”\\n"转换为真正的换行符"""
    text = Path(filename).read_text(encoding=encoding)
    text = text.replace("\\n", "\n")
    Path(filename).write_text(text, encoding=encoding)
