# Dify DingTalk AICard Bot

一个基于钉钉互动卡片的 AI 助手，将 Dify 的智能对话能力无缝集成到钉钉中。通过钉钉机器人 Stream 模式和互动卡片，为企业用户提供流畅的 AI 对话体验。

## 功能特点

- 集成 Dify AI 能力：接入 Dify 对话模型，提供智能对话服务
- 优雅的交互体验：使用钉钉互动卡片展示对话内容，支持实时更新
- 流式响应：基于 Stream 模式，AI 回复实时流式输出，体验更自然
- 易于部署：支持连接自己的 Dify 服务实例，灵活配置对话模型
- 完整的错误处理：包含日志记录和错误提示，便于问题排查

## 工作原理

1. 用户在钉钉中与机器人对话
2. 机器人接收消息并通过 Dify API 进行处理
3. Dify 返回的 AI 响应通过流式方式实时更新到钉钉卡片
4. 用户可以在对话卡片中继续进行提问

## 快速开始

### 环境要求
- Python 3.10+（3.10 测试通过）
- 钉钉开发者账号
- Dify 部署实例

### 安装

1. 克隆项目
```bash
git clone https://github.com/yourusername/dingtalk_card.git
cd dingtalk_card
```

2. 创建并激活虚拟环境
```bash
# 创建虚拟环境
python -m venv venv
```

激活虚拟环境（选择对应的操作系统）：

Linux/Mac:
```bash
source venv/bin/activate
```

Windows:
```bash
venv\Scripts\activate
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

4. 配置环境变量
复制 `.env.example` 到 `.env` 并填写配置:
```bash
cp .env.example .env
```

在 `.env` 文件中设置以下变量:
```
DINGTALK_APP_KEY=你的钉钉应用key
DINGTALK_APP_SECRET=你的钉钉应用secret
CARD_TEMPLATE_ID=你的卡片模板ID
API_KEY=你的Dify API密钥
DIFY_BASE_URL=你的Dify服务器地址
```

### 运行

开发环境运行：
```bash
python ai_card.py
```

生产环境运行：

1. 使用 nohup（简单方式）：
```bash
# 后台运行并将日志输出到 aicard.log
nohup python ai_card.py > aicard.log 2>&1 &

# 查看运行状态
ps aux | grep ai_card.py

# 查看日志
tail -f aicard.log
```

2. 使用 pm2（推荐方式）：
```bash
# 安装 pm2
npm install pm2 -g

# 启动服务
pm2 start ai_card.py --name "dify-dingtalk-bot"

# 查看运行状态
pm2 status

# 查看日志
pm2 logs dify-dingtalk-bot

# 停止服务
pm2 stop dify-dingtalk-bot

# 重启服务
pm2 restart dify-dingtalk-bot
```

## 配置说明

- `DINGTALK_APP_KEY`: 钉钉应用的AppKey
- `DINGTALK_APP_SECRET`: 钉钉应用的AppSecret
- `CARD_TEMPLATE_ID`: 钉钉互动卡片模板ID
- `API_KEY`: Dify应用的API密钥
- `DIFY_BASE_URL`: Dify服务器的基础URL，格式如 http://your-server/v1

## 项目结构

```
dingtalk_card/
├── ai_card.py          # 主程序文件
├── requirements.txt    # 项目依赖
├── .env.example       # 环境变量示例
└── .env              # 环境变量配置文件(需自行创建)
```

## 开发说明

项目使用了以下主要依赖：
- dingtalk-stream: 钉钉机器人Stream模式SDK
- python-dotenv: 环境变量管理
- loguru: 日志处理
- aiohttp: 异步HTTP客户端
- websockets: WebSocket客户端

钉钉AI卡片官方文档：https://open.dingtalk.com/document/orgapp/typewriter-effect-streaming-ai-card

## 贡献指南

欢迎提交Issue和Pull Request！

## 许可证

MIT License

## 联系方式

如有问题或建议，欢迎提Issue或联系作者。