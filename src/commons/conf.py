"""
=========================================================
OpenKB 配置加载与类型转换
=========================================================

从XML文件加载配置，并使用同名环境变量覆盖配置值。
环境变量名由配置键转为大写并将 ``.`` 替换为 ``_``，例如
``my.api.port`` 对应 ``MY_API_PORT``。

XML文件格式示例
--------
```xml
<configurations>
    <property>
        <name>my.api.host</name>
        <value>0.0.0.0</value>
        <description>API服务的主机地址</description>
    </property>

    <property>
        <name>my.api.port</name>
        <value>80</value>
        <description>提供API服务的端口</description>
    </property>
</configurations>
```

修改历史
--------
2026-07-27: 支持xml和环境变量的配置类
"""

from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import structlog

from commons.encrypt import EncryptFile


logger = structlog.get_logger(__name__)


class ConfigError(Exception):
    """配置错误异常。"""


class Config:
    """加载并读取配置。

    先读取`conf_files`中指定的变量，再继续读取对应的环境变量，如果指定则覆盖xml文件中的值。
    """

    def __init__(self, *conf_files: Path | str | EncryptFile) -> None:
        """初始化配置对象并立即加载配置。

        Args:
            *conf_files: 配置文件，可为 ``Path``/``str`` 路径，
                或 ``EncryptFile``（透明读取明文或密文）。
        """
        self._config: dict[str, str] = {}
        self.load(*conf_files)

    def _load_xml_config(self, xml_content: str) -> None:
        """从 xml_content 字符串中加载配置项。

        Args:
            xml_content: XML的配置字符串，通常从文件中读取
        """
        try:
            root: ET.Element[str] = ET.fromstring(xml_content)

            for property_elem in root.findall("property"):
                name_elem = property_elem.find("name")
                value_elem = property_elem.find("value")

                if name_elem is not None and value_elem is not None:
                    name = str(name_elem.text).strip()
                    value = str(value_elem.text).strip()
                    self._config[name] = value
        except ET.ParseError as e:
            print(f"警告: 解析XML文件失败: {e}")
            sys.exit()

    def _override_with_env(self) -> None:
        """使用环境变量覆盖已加载的配置。

        环境变量名由配置键转为大写，并将 ``.`` 替换为 ``_``。配置字典中的
        原始键名保持不变。
        """
        for name, _ in self._config.items():
            # 将点号转换为下划线，便于作为环境变量名
            env_name = name.upper().replace(".", "_")
            env_value = os.environ.get(env_name)
            if env_value is not None:
                logger.info(f"使用环境变量 {env_name} 覆盖配置 {name} 的值")
                self._config[name] = env_value

    def has_key(self, key: str) -> bool:
        """判断配置键是否存在。

        Args:
            key: 配置键。

        Returns:
            配置键存在时返回 ``True``。
        """
        return key in self._config

    def save(self, key: str, value: str) -> None:
        """设置配置值。

        Args:
            key: 区分大小写的配置键。
            value: 配置值。
        """
        self._config[key] = value

    def get_str(self, key: str) -> str:
        """读取字符串配置。

        Args:
            key: 配置键。

        Returns:
            配置字符串。

        Raises:
            ConfigError: 配置键不存在。
        """
        if key not in self._config:
            raise ConfigError(f"配置项 {key} 未定义")
        return self._config[key]

    def get_option_str(self, key: str) -> str | None:
        """读取可选字符串配置。

        Args:
            key: 配置键。

        Returns:
            配置字符串；配置键不存在时返回 ``None``。
        """
        if key not in self._config:
            return None
        return self._config[key]

    def get_int(self, key: str) -> int:
        """读取整数配置。

        Args:
            key: 配置键。

        Returns:
            转换后的整数。

        Raises:
            ConfigError: 配置不存在或无法转换为整数。
        """
        if key not in self._config:
            raise ConfigError(f"配置项 {key} 未定义")
        try:
            return int(self._config[key])
        except ValueError as err:
            raise ConfigError(
                f"配置项 {key} 的值 '{self._config.get(key)}' 无法转换为整数"
            ) from err

    def get_option_int(self, key: str) -> int | None:
        """读取可选整数配置。

        Args:
            key: 配置键。

        Returns:
            转换后的整数；配置键不存在时返回 ``None``。

        Raises:
            ConfigError: 配置值无法转换为整数。
        """
        if key not in self._config:
            return None
        try:
            return int(self._config[key])
        except ValueError as err:
            raise ConfigError(
                f"配置项 {key} 的值 '{self._config.get(key)}' 无法转换为整数"
            ) from err

    def get_float(self, key: str) -> float:
        """读取浮点数配置。

        Args:
            key: 配置键。

        Returns:
            转换后的浮点数。

        Raises:
            ConfigError: 配置不存在或无法转换为浮点数。
        """
        if key not in self._config:
            raise ConfigError(f"配置项 {key} 未定义")
        try:
            return float(self._config[key])
        except ValueError as err:
            raise ConfigError(
                f"配置项 {key} 的值 '{self._config.get(key)}' 无法转换为浮点数"
            ) from err

    def get_option_float(self, key: str) -> float | None:
        """读取可选浮点数配置。

        Args:
            key: 配置键。

        Returns:
            转换后的浮点数；配置键不存在时返回 ``None``。

        Raises:
            ConfigError: 配置值无法转换为浮点数。
        """
        if key not in self._config:
            return None
        try:
            return float(self._config[key])
        except ValueError as err:
            raise ConfigError(
                f"配置项 {key} 的值 '{self._config.get(key)}' 无法转换为浮点数"
            ) from err

    def get_bool(self, key: str) -> bool:
        """读取布尔配置。

        Args:
            key: 配置键。

        Returns:
            转换后的布尔值。

        Raises:
            ConfigError: 配置不存在或无法转换为布尔值。
        """
        value = self.get_option_bool(key)
        if value is None:
            raise ConfigError(f"配置项 {key} 未定义")
        return value

    def get_option_bool(self, key: str) -> bool | None:
        """读取可选布尔配置。

        接受 ``true/false``、``1/0``、``yes/no`` 和 ``on/off``，
        不区分大小写。

        Args:
            key: 配置键。

        Returns:
            转换后的布尔值；配置键不存在时返回 ``None``。

        Raises:
            ConfigError: 配置值无法转换为布尔值。
        """
        if key not in self._config:
            return None

        try:
            value = self._config[key].lower()

            if value in ("true", "1", "yes", "on"):
                return True
            elif value in ("false", "0", "no", "off"):
                return False
            else:
                raise ConfigError(
                    f"配置项 {key} 的值 '{self._config.get(key)}' 无法转换为布尔值"
                )
        except ValueError as err:
            raise ConfigError(
                f"配置项 {key} 的值 '{self._config.get(key)}' 无法转换为布尔值"
            ) from err

    def get_list(self, key: str) -> list[str]:
        """读取逗号分隔的字符串列表。

        Args:
            key: 配置键。

        Returns:
            去除首尾空白和空项后的字符串列表。

        Raises:
            ConfigError: 配置键不存在。
        """
        if key not in self._config:
            raise ConfigError(f"配置项 {key} 未定义")
        values = self._config[key].split(",")
        return [value.strip() for value in values if value.strip()]

    def load(self, *conf_files: Path | str | EncryptFile) -> None:
        """清空现有值并按优先级重新加载配置。

        Args:
            *conf_files: 配置文件，可为 ``Path``/``str`` 路径，
                或 ``EncryptFile``（透明读取明文或密文）。
        """
        self._config.clear()
        for f in conf_files:
            if isinstance(f, str):
                f = Path(f)
            if f.exists():
                content = self._read_conf(f)
                self._load_xml_config(content)
                logger.info(f"load conf: {f}")
            else:
                logger.error(f"conf file does not exist: {f}")
        self._override_with_env()
        logger.info("override configuration by env.")

    def _read_conf(self, conf_file: Path | str | EncryptFile) -> str:
        """读取配置文件内容。

        普通路径直接读取；``EncryptFile`` 通过其 ``read_text``
        透明读取（有明文读明文，否则解密密文）。

        Args:
            conf_file: 配置文件路径或 ``EncryptFile``。

        Returns:
            配置文件的内容字符串。
        """
        if isinstance(conf_file, EncryptFile):
            return conf_file.read_text(encoding="utf-8")

        return Path(conf_file).read_text(encoding="utf-8")

    def show_config(self, skip_keys: list[str] | None = None) -> dict[str, str]:
        """返回配置项。

        Args:
            skip_keys: 不需要展示的配置项，如敏感信息项

        Returns:
            配置字典。
        """
        return {
            key: value
            for key, value in self._config.items()
            if key not in (skip_keys or [])
        }
