# AI 掘金头条新闻系统 (Toutiao News)

一个基于 FastAPI 和 Vue3 的现代化新闻系统，支持用户注册登录、新闻浏览、收藏和历史记录等功能。

## 项目结构

```
toutiao/
├── backend/              # 后端代码 (FastAPI)
│   ├── config/          # 配置文件
│   ├── crud/            # 数据访问层
│   ├── models/          # 数据模型
│   ├── routers/         # API 路由
│   ├── schemas/         # 数据验证模型
│   ├── utils/           # 工具函数
│   ├── main.py          # 应用入口
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

### 后端

```bash
cd backend
pip install -r requirements.txt
python main.py
```

### 前端

```bash
cd frontend/toutiao-frontend
npm install
npm run dev
```

## 技术栈

- **后端**: FastAPI, SQLAlchemy, MySQL, Redis
- **前端**: Vue3, Vite, Pinia, Vue Router, Vant UI
