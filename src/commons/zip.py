#!/usr/bin/env python3
"""
zip_dir.py - 压缩目录为 ZIP 文件（支持忽略指定文件，Windows 无乱码）

用法:
    python zip_dir.py <要压缩的目录> <输出的 ZIP 文件名>
示例:
    python zip_dir.py ./my_project my_project.zip
"""

import os
import sys
import zipfile


# 需要排除的文件名（无论路径）
DEFAULT_EXCLUDE = {".DS_Store", "__MACOSX", "Thumbs.db", "desktop.ini"}


def should_exclude(filename: str, exclude_set: set[str] = DEFAULT_EXCLUDE):
    """判断文件或目录是否应该被排除"""
    # 检查文件名本身是否在排除集合中
    base = os.path.basename(filename)
    if base in exclude_set:
        return True
    # 排除以 ._ 开头的 macOS 资源分支文件
    if base.startswith("._"):
        return True
    return False


def zip_directory(
    source_dir: str, output_zip: str, exclude: set[str] | None = None
):
    """
    递归压缩 source_dir 下的所有文件和子目录，忽略排除的文件。
    source_dir: 要压缩的目录路径
    output_zip: 输出的 ZIP 文件路径
    exclude:    可选的额外排除文件名集合（会合并到默认排除集）
    """
    if exclude is None:
        exclude = set()
    exclude_set = DEFAULT_EXCLUDE.union(exclude)

    source_dir = os.path.abspath(source_dir)
    # 确保源目录存在
    if not os.path.isdir(source_dir):
        raise NotADirectoryError(f"目录不存在: {source_dir}")

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_dir):
            # 修改 dirs 列表，原地排除不想要遍历的子目录
            dirs[:] = [
                d
                for d in dirs
                if not should_exclude(os.path.join(root, d), exclude_set)
            ]

            for file in files:
                full_path = os.path.join(root, file)
                if should_exclude(full_path, exclude_set):
                    print(f"跳过: {full_path}")
                    continue

                # ZIP 内部路径（相对于 source_dir）
                arcname = os.path.relpath(full_path, start=source_dir)
                # 使用 UTF-8 写入文件名，自动设置通用标志位 (bit 11)
                # 现代 Windows 解压软件（Win10 1803+，7-Zip，Bandizip 等）均可正常显示中文
                zf.write(full_path, arcname)
                print(f"已添加: {arcname}")

    print(f"压缩完成: {output_zip}")


def zip_files(
    source_dir: str,
    *,
    source_files: list[str],
    output_zip: str,
    exclude: set[str] | None = None,
):
    """
    递归压缩 source_dir 下的所有文件和子目录，忽略排除的文件。
    source_dir: 要压缩的目录路径
    output_zip: 输出的 ZIP 文件路径
    exclude:    可选的额外排除文件名集合（会合并到默认排除集）
    """
    if exclude is None:
        exclude = set()

    source_dir = os.path.abspath(source_dir)
    # 确保源目录存在
    if not os.path.isdir(source_dir):
        raise NotADirectoryError(f"目录不存在: {source_dir}")

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for source_file in source_files:
            if not os.path.exists(source_file):
                continue
            full_path = os.path.abspath(source_file)

            # ZIP 内部路径（相对于 source_dir）
            arcname = os.path.relpath(full_path, start=source_dir)
            # 使用 UTF-8 写入文件名，自动设置通用标志位 (bit 11)
            # 现代 Windows 解压软件（Win10 1803+，7-Zip，Bandizip 等）均可正常显示中文
            zf.write(full_path, arcname)
            print(f"已添加: {arcname}")

    print(f"压缩完成: {output_zip}")


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    source_dir = sys.argv[1]
    output_zip = sys.argv[2]

    try:
        zip_directory(source_dir, output_zip)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
