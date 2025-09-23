# 📄 产品需求文档补充（PRD Supplement）- 简化版

**项目名称**：AI Newsletter Generator - Simple Web Interface  
**作者**：Liz  
**日期**：2025-01-27  
**版本**：v2.0-simple  
**基于**：原始PRD v1.0

---

## 1. 补充背景与目标

基于现有的CLI版本newsletter生成器，我们需要将其改造为一个**简单的Web应用**，支持前端用户通过Web界面进行交互。主要目标是：

- 将现有Python工作流封装为RESTful API服务
- 提供简单的HTML前端界面，支持用户上传URL列表或粘贴URL文本
- 保持原有的Markdown输出格式和质量
- 支持异步处理和实时状态更新
- 使用Render进行部署，无需Docker

---

## 2. 新增用户场景

### 2.1 Web用户场景
- **研究人员**：通过Web界面快速上传论文URL列表，获取分类整理的研究动态
- **产品经理**：批量处理行业新闻和产品发布链接，生成定期报告
- **社区运营**：在线创建newsletter，支持实时预览和下载

---

## 3. 新增功能需求

### 3.1 API服务架构

#### 3.1.1 核心API端点
```
POST /api/v1/newsletter/generate
- 输入：URL列表（JSON格式）
- 输出：任务ID和状态

GET /api/v1/newsletter/status/{task_id}
- 输出：处理进度和状态

GET /api/v1/newsletter/result/{task_id}
- 输出：生成的Markdown内容

POST /api/v1/newsletter/upload
- 输入：TXT文件上传
- 输出：解析后的URL列表

GET /
- 输出：静态HTML页面
```

#### 3.1.2 请求/响应格式
```json
// 生成请求
{
  "urls": [
    "https://arxiv.org/abs/2301.12345",
    "https://openai.com/blog/...",
    "https://github.com/..."
  ],
  "options": {
    "include_subtopics": true,
    "max_recommendation_length": 100
  }
}

// 状态响应
{
  "task_id": "uuid-string",
  "status": "processing|completed|failed",
  "progress": {
    "total_urls": 10,
    "processed": 7,
    "failed": 1
  },
  "estimated_completion": "2025-01-27T15:30:00Z"
}

// 结果响应
{
  "task_id": "uuid-string",
  "status": "completed",
  "markdown_content": "# Newsletter\n\n### 📄 Papers...",
  "metadata": {
    "generated_at": "2025-01-27T15:25:00Z",
    "total_processed": 10,
    "topics": ["Papers", "Blogs", "Open Source"]
  }
}
```

### 3.2 简单HTML前端界面

#### 3.2.1 单页面设计
- **左侧面板**：URL输入区域
- **右侧面板**：Markdown预览和下载区域
- **底部状态栏**：处理进度显示

#### 3.2.2 输入方式
1. **文本输入**：
   - 大文本框，支持多行URL粘贴
   - 自动检测和验证URL格式
   - 实时去重和计数

2. **文件上传**：
   - 支持TXT文件选择上传
   - 文件内容预览和编辑
   - 支持最大5MB文件

#### 3.2.3 输出展示
- **实时预览**：处理过程中显示已完成的条目
- **Markdown渲染**：使用marked.js渲染Markdown
- **下载功能**：支持Markdown文件下载

### 3.3 异步处理架构

#### 3.3.1 任务队列
- 使用Celery + Redis实现异步任务处理
- 支持任务优先级和重试机制
- 任务状态持久化存储

#### 3.3.2 实时通信
- Server-Sent Events (SSE) 推送处理进度
- 支持长时间运行的任务

---

## 4. 技术实现方案

### 4.1 后端技术栈
- **Web框架**：FastAPI（基于现有API结构扩展）
- **任务队列**：Celery + Redis
- **数据库**：SQLite（简单存储任务状态）
- **静态文件**：FastAPI静态文件服务
- **部署**：Render（无需Docker）

### 4.2 前端技术栈
- **HTML/CSS/JavaScript**：原生前端技术
- **Markdown渲染**：marked.js
- **HTTP客户端**：fetch API
- **实时通信**：EventSource (SSE)


---

## 5. 开发任务分解

### 5.1 Phase 1: API服务改造 
- [x] 5.1.1 扩展FastAPI应用，添加新的API端点
- [x] 5.1.2 集成Celery任务队列，实现异步处理
- [x] 5.1.3 添加任务状态管理和SQLite存储
- [x] 5.1.4 实现SSE实时通信
- [x] 5.1.5 添加静态文件服务

### 5.2 Phase 2: 简单前端开发 
- [x] 5.2.1 创建HTML页面布局（左右分栏）
- [x] 5.2.2 实现URL输入界面（文本+文件上传）
- [x] 5.2.3 开发Markdown预览和下载功能
- [x] 5.2.4 添加SSE进度显示
- [x] 5.2.5 优化样式和用户体验

### 5.3 Phase 3: Render部署 
- [x] 5.3.1 配置render.yaml部署文件
- [x] 5.3.2 设置环境变量和Redis服务
- [x] 5.3.3 测试生产环境部署
- [x] 5.3.4 性能优化和错误处理

## Relevant Files
- `pyproject.toml`：声明 FastAPI、Celery、SSE 等运行依赖
- `render.yaml`：Render 平台部署配置（Web、Worker、Redis、持久化磁盘）
- `README.md`：更新本地运行、部署和环境变量说明
- `src/newsletter/api/app.py`：FastAPI 应用、健康检查、SSE 端点与上传限制
- `src/newsletter/api/models.py`：API 请求/响应与任务数据模型
- `src/newsletter/api/task_store.py`：内存与 SQLite 任务存储实现
- `src/newsletter/api/pipeline_executor.py`：管道执行封装，复用现有工作流
- `src/newsletter/api/dependencies.py`：依赖提供者（任务存储、执行器、调度器）
- `src/newsletter/api/task_dispatcher.py`：Celery 调度适配器
- `src/newsletter/api/celery_app.py`：Celery 应用初始化与任务注册
- `src/newsletter/api/celery_tasks.py`：Celery 任务入口
- `src/newsletter/api/service.py`：任务执行与结果持久化逻辑
- `src/newsletter/api/progress.py`：进度计算工具
- `src/newsletter/api/static/index.html`：单页前端界面
- `src/newsletter/api/static/styles.css`：界面布局与样式
- `src/newsletter/api/static/app.js`：客户端逻辑、SSE、交互处理
- `tests/api/test_app.py`：端到端 API 与 SSE 流测试
- `tests/api/test_pipeline_api.py`：API 验证/错误分支测试
