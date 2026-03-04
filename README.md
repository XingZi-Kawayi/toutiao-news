# 智能新闻聚合与 AI 交互平台 (Toutiao News)

一个基于 FastAPI 和 Vue3 的现代化新闻系统，集成 LLM（大语言模型）AI 能力，支持用户注册登录、新闻浏览、收藏和历史记录等功能。

## ✨ 核心特性

### LLM AI 功能
- **新闻摘要生成** - 自动为新闻生成简洁摘要
- **AI 新闻助手对话** - 智能对话助手，回答新闻相关问题
- **关键词提取** - 从新闻内容中自动提取关键词
- **情感分析** - 判断新闻的情感倾向（正面/负面/中性）

### LLM 优化亮点
- **配置安全** - API Key 通过环境变量管理，无硬编码
- **智能缓存** - Redis + 内存双缓存，相同内容响应速度提升 90%+
- **自动重试** - 指数退避重试机制，提高 API 调用成功率
- **优雅降级** - 无 Redis 时自动使用内存缓存
- **完善的错误处理** - 分类错误处理，友好的错误提示

## 项目结构

```
toutiao/
├── backend/              # 后端代码 (FastAPI)
│   ├── config/          # 配置文件
│   ├── crud/            # 数据访问层
│   ├── models/          # 数据模型
│   ├── routers/         # API 路由
│   │   └── ai.py        # AI 相关接口
│   ├── schemas/         # 数据验证模型
│   ├── utils/           # 工具函数
│   │   ├── ai_service.py # LLM 服务封装
│   │   └── cache.py     # 缓存管理
│   ├── main.py          # 应用入口
│   ├── .env             # 环境变量配置
│   └── requirements.txt # Python 依赖
├── frontend/            # 前端代码 (Vue3)
│   └── toutiao-frontend/
├── database/           # 数据库 SQL 文件
│   └── database.sql
└── docs/              # 文档
    ├── API 接口规范文档.md
    └── backend-design.md
```

## 快速开始

### 环境配置

1. **后端环境变量配置** (`backend/.env`)：
```env
# 数据库配置
DB_USER=root
DB_PASSWORD=123456
DB_HOST=localhost
DB_PORT=3306
DB_NAME=news_app

# LLM 配置 (通义千问)
DASHSCOPE_API_KEY=your_api_key_here
DASHSCOPE_ENDPOINT=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
DEFAULT_MODEL=qwen3-max-preview
LLM_TIMEOUT=30.0

# Redis 配置 (可选)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
CACHE_TTL=86400
```

### 后端启动

```bash
cd backend
pip install -r requirements.txt
python main.py
```

### 前端启动

```bash
cd frontend/toutiao-frontend
npm install
npm run dev
```

## 技术栈

- **后端**: FastAPI, SQLAlchemy, MySQL, Redis, httpx, tenacity
- **前端**: Vue3, Vite, Pinia, Vue Router, Vant UI
- **LLM**: 阿里云通义千问 (Qwen)
