# Python项目模板

这是一个Python项目模板，帮助你快速创建规范化的项目结构。

当你使用此模板时，请将项目中所有的**pytemplate**替换为你的实际项目名称。

## 日常开发

```shell
uv run ruff check --fix --watch src/
```

每写完一个Python文件，都要运行如下命令通过检查：

```shell
./lint.sh
```

## 开发环境设置

1. 安装uv

   ```shell
   curl -fsSL https://get.uv.dev | bash
   # 或者通过pip安装
   pip install uv
   ```

2. 可编辑安装本项目

   ```shell
   #创建虚拟环境
   uv venv
   uv pip install -e .
   ```

3. 通过uv运行脚本main.py示例

   ```shell
   uv run -m pytemplate.main
   ```

4. 代码格式化

   ```shell
   uv run ruff check --fix src
   ```

5. git设置

避免中文文件名称乱码：

```shell
git config --global core.quotepath false # 让 Git 不要将非 ASCII 字符的文件名用引号括起来
```
