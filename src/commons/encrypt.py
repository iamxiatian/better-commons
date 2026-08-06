"""
=========================================================
文件加解密工具 — AES-CBC 与 EncryptFile
=========================================================

基于 AES-CBC 模式（PKCS7 填充）的文件加密与解密工具。
提供底层加解密函数，以及行为类似 ``pathlib.Path`` 的
``EncryptFile`` 类：开发时读写明文，发布时仅保留密文。

快速上手
--------

Path 风格透明读写::

    from commons.encrypt import EncryptFile, generate_key

    key = generate_key()  # 16 字节随机密钥，可 .hex() 持久化
    f = EncryptFile("plain.txt", "1234.dat", key)
    text = f.read_text()          # 有明文读明文，否则解密密文
    f.write_text('{"a": 1}')      # 写入明文并同步生成密文

底层 API::

    key = generate_key(32)
    encrypt_file("明文.txt", "密文.bin", key)
    data = decrypt_file_to_bytes("密文.bin", key)

基础概念
--------

加密后的文件格式为::

    [16 字节 IV] + [AES-CBC 密文]

``EncryptFile`` 在「使用」时（读/写/打开）会按需同步密文：
明文存在但无密文，或明文内容相对密文已变化时，自动重新加密。
判定时先用 mtime 快路径，必要时再比对明文与解密结果。

密钥由调用方传入，每个文件可使用不同密钥。AES 密钥长度须为
16 / 24 / 32 字节。

修改历史
--------
2026-08-05: 新增 EncryptFile（Path 风格透明加解密文件）
2026-08-05: 密钥改为调用方传入，新增 generate_key
"""

from __future__ import annotations

import os
from io import BytesIO, StringIO
from pathlib import Path
from typing import IO, Any, BinaryIO, Literal, TextIO, cast, overload

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


_AES_KEY_SIZES = frozenset({16, 24, 32})


# ── 密钥 ────────────────────────────────────────────


def generate_key(nbytes: int = 16) -> bytes:
    """生成随机 AES 密钥。

    Args:
        nbytes: 密钥字节数，须为 16、24 或 32（对应 AES-128/192/256）。
            默认 16。

    Returns:
        密码学安全的随机字节串，可用 ``key.hex()`` 转为十六进制字符串保存。

    Raises:
        ValueError: ``nbytes`` 不是合法的 AES 密钥长度。
    """
    _validate_key_size(nbytes)
    return os.urandom(nbytes)


def _validate_key_size(nbytes: int) -> None:
    if nbytes not in _AES_KEY_SIZES:
        raise ValueError(f"AES 密钥长度须为 16/24/32 字节，收到 {nbytes}")


def _validate_key(key: bytes) -> bytes:
    if not isinstance(key, (bytes, bytearray)):
        raise TypeError(f"key 须为 bytes，收到 {type(key).__name__}")
    key_bytes = bytes(key)
    _validate_key_size(len(key_bytes))
    return key_bytes


# ── 内部工具 ──────────────────────────────────────────


def _encrypt(plain_data: bytes, key: bytes) -> tuple[bytes, bytes]:
    """AES-CBC 加密，返回 (iv, cipher_text)。"""
    key = _validate_key(key)
    iv = os.urandom(16)
    cipher = Cipher(
        algorithms.AES(key), modes.CBC(iv), backend=default_backend()
    )
    encryptor = cipher.encryptor()

    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(plain_data) + padder.finalize()

    cipher_text = encryptor.update(padded_data) + encryptor.finalize()
    return iv, cipher_text


def _decrypt_to_bytes(data: bytes, key: bytes) -> bytes:
    """从 ``[16 字节 IV] + [密文]`` 格式中解密出原始字节。"""
    key = _validate_key(key)
    iv = data[:16]
    cipher_text = data[16:]

    cipher = Cipher(
        algorithms.AES(key), modes.CBC(iv), backend=default_backend()
    )
    decryptor = cipher.decryptor()

    decrypted_padded = decryptor.update(cipher_text) + decryptor.finalize()

    unpadder = padding.PKCS7(128).unpadder()
    return unpadder.update(decrypted_padded) + unpadder.finalize()


# ── 公开底层 API ──────────────────────────────────────


def encrypt_file(file_in: str | Path, file_out: str | Path, key: bytes) -> None:
    """读取 ``file_in``，用 ``key`` 加密后写入 ``file_out``。"""
    plain_path = Path(file_in)
    out_path = Path(file_out)
    plain_text = plain_path.read_bytes()

    iv, cipher_text = _encrypt(plain_text, key)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(iv + cipher_text)


def decrypt_file(file_in: str | Path, file_out: str | Path, key: bytes) -> None:
    """读取加密文件 ``file_in``，用 ``key`` 解密后写入 ``file_out``。"""
    plain_data = decrypt_file_to_bytes(file_in, key)
    Path(file_out).write_bytes(plain_data)


def decrypt_file_to_bytes(file_in: str | Path, key: bytes) -> bytes:
    """读取加密文件，用 ``key`` 解密后返回 ``bytes``。"""
    data = Path(file_in).read_bytes()
    return _decrypt_to_bytes(data, key)


def decrypt_file_to_memory(file_in: str | Path, key: bytes) -> BytesIO:
    """读取加密文件，用 ``key`` 解密后返回 ``BytesIO`` 对象。"""
    return BytesIO(decrypt_file_to_bytes(file_in, key))


def decrypt_file_to_str(
    file_in: str | Path, key: bytes, encoding: str = "utf-8"
) -> str:
    """读取加密的文本文件，用 ``key`` 解密后返回字符串。"""
    return decrypt_file_to_bytes(file_in, key).decode(encoding)


# ── EncryptFile ───────────────────────────────────────


class EncryptFile:
    """行为类似 ``pathlib.Path`` 的透明加解密文件。

    初始化时直接指定明文路径、密文路径与密钥。使用时：

    - 有明文则读写明文，并在明文缺失密文或内容变化时自动生成密文；
    - 无明文则从密文解密读取；
    - 两者皆无则抛出 ``FileNotFoundError``。

    明文「内容变化」判定：无密文则加密；明文 mtime 不新于密文则跳过；
    否则解密密文与明文逐字节比较，不同则重新加密。
    经本类 ``write_*`` / 写模式 ``open`` 写入时会强制同步密文。

    Args:
        plain_file: 明文文件路径。
        encrypted_file: 密文文件路径（由调用方直接指定）。
        key: AES 密钥（16 / 24 / 32 字节），可用 ``generate_key()`` 生成。
    """

    def __init__(
        self,
        plain_file: str | Path,
        encrypted_file: str | Path,
        key: bytes,
    ) -> None:
        self._plain = Path(plain_file)
        self._encrypted = Path(encrypted_file)
        self._key = _validate_key(key)

    # ── Path 身份 ─────────────────────────────────────

    @property
    def plain_path(self) -> Path:
        """明文文件路径。"""
        return self._plain

    @property
    def encrypted_path(self) -> Path:
        """加密文件路径。"""
        return self._encrypted

    @property
    def key(self) -> bytes:
        """当前使用的 AES 密钥。"""
        return self._key

    def __fspath__(self) -> str:
        """作为路径使用时返回明文路径（逻辑身份）。"""
        return os.fspath(self._plain)

    def __str__(self) -> str:
        if not self._plain.exists() and self._encrypted.exists():
            return str(self._encrypted)
        else:
            return str(self._plain)

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}({self._plain!r}, "
            f"{self._encrypted!r}, key=<{len(self._key)} bytes>)"
        )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, EncryptFile):
            return (
                self._plain == other._plain
                and self._encrypted == other._encrypted
                and self._key == other._key
            )
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self._plain, self._encrypted, self._key))

    def __getattr__(self, name: str) -> Any:
        """其余属性委托给明文 ``Path``（如 name/stem/suffix/parent）。"""
        return getattr(self._plain, name)

    # ── 存在性 ────────────────────────────────────────

    def exists(self) -> bool:
        """明文或密文任一存在即为 True。"""
        return self._plain.exists() or self._encrypted.exists()

    def is_file(self) -> bool:
        """明文或密文任一为文件即为 True。"""
        return self._plain.is_file() or self._encrypted.is_file()

    def is_dir(self) -> bool:
        """始终为 False（本对象表示文件，不是目录）。"""
        return False

    # ── 同步密文 ──────────────────────────────────────

    def sync(self, *, force: bool = False) -> Path | None:
        """按需将明文加密到指定的密文路径。

        Args:
            force: 为 True 时强制重新加密。

        Returns:
            生成或更新后的密文路径；无明文可同步时返回 None。
        """
        if not self._plain.is_file():
            return None
        plain_data = self._plain.read_bytes()
        if force or self._needs_encrypt(plain_data):
            self._encrypted.parent.mkdir(parents=True, exist_ok=True)
            iv, cipher_text = _encrypt(plain_data, self._key)
            self._encrypted.write_bytes(iv + cipher_text)
        return self._encrypted

    def _needs_encrypt(self, plain_data: bytes) -> bool:
        """判断是否需要（重新）生成密文。"""
        if not self._encrypted.is_file():
            return True
        if self._plain.stat().st_mtime_ns <= self._encrypted.stat().st_mtime_ns:
            return False
        try:
            return (
                decrypt_file_to_bytes(self._encrypted, self._key) != plain_data
            )
        except Exception:
            return True

    def _ensure_readable(self) -> None:
        """使用前确保可读：有明文则同步密文；皆无则报错。"""
        if self._plain.is_file():
            self.sync()
            return
        if self._encrypted.is_file():
            return
        raise FileNotFoundError(
            f"文件不存在: 明文 {self._plain} 与密文 {self._encrypted} 均不存在"
        )

    def _resolve_read_bytes(self) -> bytes:
        """读取逻辑内容：优先明文，否则解密密文。"""
        self._ensure_readable()
        if self._plain.is_file():
            return self._plain.read_bytes()
        return decrypt_file_to_bytes(self._encrypted, self._key)

    # ── Path 风格读写 ─────────────────────────────────

    def read_bytes(self) -> bytes:
        """读取文件字节内容（优先明文，否则解密密文）。"""
        return self._resolve_read_bytes()

    def read_text(
        self, encoding: str | None = None, errors: str | None = None
    ) -> str:
        """读取文件文本内容（优先明文，否则解密密文）。"""
        enc = encoding or "utf-8"
        err = errors or "strict"
        return self.read_bytes().decode(enc, errors=err)

    def write_bytes(self, data: bytes) -> int:
        """写入明文，并强制同步生成/更新密文。"""
        self._plain.parent.mkdir(parents=True, exist_ok=True)
        n = self._plain.write_bytes(data)
        self.sync(force=True)
        return n

    def write_text(
        self,
        data: str,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> int:
        """写入明文文本，并强制同步生成/更新密文。"""
        enc = encoding or "utf-8"
        err = errors or "strict"
        self._plain.parent.mkdir(parents=True, exist_ok=True)
        n = self._plain.write_text(
            data, encoding=enc, errors=err, newline=newline
        )
        self.sync(force=True)
        return n

    @overload
    def open(
        self,
        mode: Literal["r", "rt", "w", "wt", "a", "at", "x", "xt"] = "r",
        buffering: int = -1,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> TextIO: ...

    @overload
    def open(
        self,
        mode: Literal["rb", "wb", "ab", "xb"],
        buffering: int = -1,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> BinaryIO: ...

    @overload
    def open(
        self,
        mode: str = "r",
        buffering: int = -1,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> IO[Any]: ...

    def open(
        self,
        mode: str = "r",
        buffering: int = -1,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> IO[Any]:
        """打开文件，接口对齐 ``Path.open``。

        读模式：有明文打开明文；仅有密文时返回内存中的解密流。
        写模式：打开明文文件，关闭后自动同步密文。
        """
        writing = any(c in mode for c in "wax+")

        if writing:
            self._plain.parent.mkdir(parents=True, exist_ok=True)
            raw = self._plain.open(
                mode,
                buffering=buffering,
                encoding=encoding,
                errors=errors,
                newline=newline,
            )
            return cast(IO[Any], _SyncOnClose(raw, self))

        self._ensure_readable()
        if self._plain.is_file():
            return self._plain.open(
                mode,
                buffering=buffering,
                encoding=encoding,
                errors=errors,
                newline=newline,
            )

        data = decrypt_file_to_bytes(self._encrypted, self._key)
        if "b" in mode:
            return BytesIO(data)
        enc = encoding or "utf-8"
        text = StringIO(data.decode(enc, errors=errors or "strict"))
        text.encoding = enc  # type: ignore[attr-defined]
        return text


class _SyncOnClose:
    """包装可写文件对象，关闭时触发 EncryptFile 密文同步。"""

    def __init__(self, fileobj: IO[Any], owner: EncryptFile) -> None:
        self._fileobj = fileobj
        self._owner = owner

    def close(self) -> None:
        if not self._fileobj.closed:
            self._fileobj.close()
            self._owner.sync(force=True)

    def __enter__(self) -> IO[Any]:
        return self._fileobj

    def __exit__(self, *args: object) -> None:
        self.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._fileobj, name)

    def __iter__(self) -> Any:
        return iter(self._fileobj)


if __name__ == "__main__":
    import tempfile

    tmp_path = Path("./temp")
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"临时目录路径: {tmpdir}")
        tmp_path = Path(tmpdir)
        plain = tmp_path / "plain.txt"
        encrypted = tmp_path / "1234.dat"
        key = generate_key()
        print("key.hex():", key.hex())
        # key = bytes.fromhex("88bed135e2ae528f8f5e4dfd58fa8467")

        f = EncryptFile(plain, encrypted, key)
        f.write_text("hello encrypt\n")
        print("明文:", f.plain_path, "存在=", f.plain_path.exists())
        print("密文:", f.encrypted_path, "存在=", f.encrypted_path.exists())
        print("读取:", repr(f.read_text()))

        plain.unlink()
        print("删除明文后读取:", repr(f.read_text()))
        print("exists:", f.exists())
