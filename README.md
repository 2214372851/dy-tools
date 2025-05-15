# dy-live

这是一个使用 PySide6 构建的直播工具。它利用了 Qt 框架的强大功能来处理多媒体和网络请求，适用于各种直播场景。

## 环境安装步骤

1. 安装 Python:
    - 下载并安装 [Python 3.x](https://www.python.org/downloads/)
    - 确保勾选 `Add Python to PATH`

2. 安装 Poetry:
   ```bash
   pip install poetry
   ```

3. 安装项目依赖和虚拟环境:
   ```bash
   poetry install
   ```

4. 验证安装:
   ```bash
   poetry run main.py --help
   ```

> 如果你使用的是现代 IDE 或编辑器，你可以选择 `.venv/Scripts` 目录下的 `python.exe` 作为解释器。
> 如果你使用的是终端，你可以通过 `.venv/Scripts` 目录下的 `activate.bat` 激活虚拟环境。

## 目录结构

```
.
├── live_data               # 存放直播数据文件
│   └── *.jsonl             # JSON Lines 格式的直播记录
├── static                  # 静态资源文件
│   ├── bg.js               # 背景脚本
│   ├── naive.ico           # 图标文件
│   ├── timbre.json         # 印章信息
│   ├── timbre.txt          # 文本印章
│   └── webmssdk.js         # WebMS SDK 脚本
├── utils                   # 工具类模块
│   ├── backup.py           # 备份逻辑
│   ├── dy_pb2.py           # Protocol Buffers 定义
│   ├── expired_queue.py    # 过期队列管理
│   ├── live_ws.py          # WebSocket 直播连接
│   └── retry.py            # 重试机制
├── README.md               # 项目说明文档
├── config.toml             # 配置文件
├── dy-tools.exe.spec       # PyInstaller spec 文件
├── main.py                 # 主程序入口
├── naive-0.0.3-py3-none-any.whl # Naive UI 包
├── poetry.lock             # Poetry 锁定依赖版本
└── pyproject.toml          # Python 项目配置
```

## 使用方法

1. 安装依赖:
   ```bash
   poetry install
   ```

2. 运行主程序:
   ```bash
   python main.py
   ```

3. 查看帮助:
   ```bash
   python main.py --help
   ```

## 功能特点

- 实时直播数据处理
- 支持多种直播平台
- 强大的消息解析与过滤能力
- 自定义配置选项丰富

## 注意事项

- 确保您的环境已安装 Python 和必要的构建工具。

## 免责声明

本软件仅供学习和研究使用，作者不对任何因使用本软件引发的直接或间接损失承担责任。请遵守相关法律法规，谨慎使用。

## 许可证

本项目采用 GPLv3 许可证。详情请查看 LICENSE 文件。