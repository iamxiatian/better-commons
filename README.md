# better-commons

Python版本的基础库，方便开发复用

## 日常开发

运行以下脚本，可以自动格式化代码，并发现类型错误。

```shell
make fine
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
   uv run -m commons.main
   ```

4. 代码格式化

  ```shell
  uv run ruff check --fix src
  #或者
  make fmt
  ```

5. git设置

避免中文文件名称乱码：

```shell
git config --global core.quotepath false # 让 Git 不要将非 ASCII 字符的文件名用引号括起来
```
