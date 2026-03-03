# AI 新闻功能使用说明

## 已实现的功能

### 1. AI 新闻摘要

**功能说明**: 为新闻内容自动生成简洁摘要，帮助用户快速了解新闻要点。

**API 接口**: `POST /api/ai/summary`

**请求示例**:
```json
{
  "content": "新闻正文内容...",
  "max_length": 200
}
```

**响应示例**:
```json
{
  "code": 200,
  "message": "生成摘要成功",
  "data": {
    "summary": "摘要内容...",
    "original_length": 500,
    "summary_length": 150
  }
}
```

**前端使用**:
- 打开新闻详情页后，系统会自动调用 AI 生成摘要
- 摘要显示在新闻顶部，蓝色渐变背景区域
- 点击摘要头部可以展开/收起

---

### 2. AI 新闻助手（增强版）

**功能说明**: 智能对话助手，可以回答新闻相关问题、解读事件、分析趋势。

**API 接口**: `POST /api/ai/chat`

**请求示例**:
```json
{
  "messages": [
    {"role": "user", "content": "今天有什么重要新闻？"}
  ]
}
```

**响应示例**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "response": "AI 回答内容..."
  }
}
```

**前端使用**:
- 点击底部导航栏的"AI 问答"进入
- 页面提供 6 个快捷问题，点击即可发送
- 支持多轮对话，AI 会记住上下文

---

### 3. 关键词提取

**API 接口**: `POST /api/ai/keywords`

**请求示例**:
```json
{
  "content": "新闻内容...",
  "top_k": 5
}
```

**响应示例**:
```json
{
  "code": 200,
  "message": "提取关键词成功",
  "data": {
    "keywords": ["关键词 1", "关键词 2", "关键词 3"]
  }
}
```

---

## 技术实现

### 后端技术
- **框架**: FastAPI
- **AI 服务**: 阿里云通义千问 (Qwen3-max-preview)
- **HTTP 客户端**: httpx (异步)

### 文件结构
```
backend/
├── routers/
│   └── ai.py              # AI 相关路由
├── utils/
│   └── ai_service.py      # AI 服务封装
└── main.py                # 注册了 ai 路由
```

### 配置说明

AI 配置在 `backend/utils/ai_service.py`:
```python
DASHSCOPE_API_KEY = "sk-9c4d89982a6a4bd3b7494d94751fe81c"
DASHSCOPE_ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
DEFAULT_MODEL = "qwen3-max-preview"
```

---

## 运行说明

### 1. 启动后端
```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### 2. 启动前端
```bash
cd frontend/toutiao-frontend
npm run dev
```

### 3. 访问应用
- **前端**: http://localhost:5173
- **API 文档**: http://localhost:8000/docs
- **根路径**: http://localhost:8000

---

## 注意事项

1. **API Key**: 当前使用的是阿里云 DashScope API，需要有效的 API Key
2. **网络连接**: 需要能够访问阿里云 API 服务
3. **请求限制**: 注意 API 调用频率和配额限制
4. **错误处理**: 前端已添加错误提示，AI 服务失败时会显示友好提示

---

## 后续优化建议

1. **缓存**: 对相同新闻的摘要进行缓存，减少 API 调用
2. **流式响应**: AI 对话已支持 SSE 流式输出，可优化用户体验
3. **个性化**: 根据用户兴趣定制摘要风格和长度
4. **多模型**: 支持切换不同的 LLM 模型
5. **本地部署**: 可选配本地部署的开源模型
