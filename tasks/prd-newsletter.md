好的 ✅ 我帮你把完整 PRD 输出为 Markdown，直接放在下面的代码框中：


# 📄 产品需求文档（PRD）

**项目名称**：AI Newsletter Generator  
**作者**：Liz  
**日期**：2025-09-18  
**版本**：v1.0  

---

## 1. 背景与目标
研究者、工程师和产品团队每天都会接触大量论文、博客、开源项目和产品新闻。人工筛选和总结这些信息耗时且低效。  
本项目旨在通过 **Python 工作流**，将输入的 URL 列表自动处理成一份结构化 newsletter，支持分类、标签、推荐理由生成和 Markdown 输出。

---

## 2. 用户场景
- **研究者**：快速获取顶会论文和核心研究趋势。  
- **工程师/产品经理**：跟踪开源项目和行业产品动态。  
- **社区运营者**：生成定期 newsletter，减少人工编辑成本。  

---

## 3. 功能需求

### 输入
- 用户上传一个 `.txt` 文件，包含若干 URL，每行一个。  
- 系统自动去重。  

### 分类（一级分类）
- **论文 Papers**（arxiv.org, openreview.net, 顶会论文库）  
- **博客 Blogs**（medium.com, substack.com, 微信公众号, 知乎等）  
- **工程 / 产品 / 商业 Engineering & Product & Business**（新闻站点，公司博客，产品发布页）  
- **开源项目 Open Source Roundup**（github.com, huggingface.co, gitlab）  
- 方法：规则匹配为主，模糊情况调用 LLM（OpenRouter 可配置模型）。  

### 元数据提取 + 推荐理由生成（合并步骤）
- **工具**：Jina Reader 提取网页完整内容。  
- **处理**：调用 OpenRouter LLM，从内容中抽取：  
  - 标题（Title）  
  - 作者（Author）  
  - 作者机构（Organization）  
  - 推荐理由（Recommendation，≤100词）：  
    - 核心贡献  
    - 是否提及顶会（NeurIPS/ICLR/ACL/CVPR等）  
    - 是否包含 GitHub/HuggingFace Repo 或 Dataset  
    - 是否提及附件（附录、Slides 等）  

### 论文子类标签（二级分类，仅限 Papers）
- 输入：论文标题 + 摘要/正文（来自 Jina Reader）  
- 调用 OpenRouter LLM 进行分类：  
  - 候选子类：  
    - **LLM, Agents, Multimodal, RL, System/Engineering, Retrieval/RAG, Evaluation, Data/Synthetic Data, Safety/Alignment**  
  - 若不匹配 → 允许新建标签。  
- 输出：为论文添加 `subtopics` 字段。  

### 输出结构
- 每个条目的输出 JSON 格式：  
```json
{
  "topic": "Paper | Blog | Open Source | Engineering & Product & Business ",
  "title": "string",
  "author": ["string"],
  "organization": ["string"],
  "recommendation": "string (<=100 words)",
  "subtopics": ["string", "..."] // only for Papers
}
````

### Newsletter 组装 & 输出

* 按 **topic** 一级分类。
* Papers 按 **subtopic** 二级分组。
* 统一生成 Markdown 文件：

示例：

```markdown
### 📄 Papers
#### RL
标题：Deep Reinforcement Learning with Human Feedback  
链接：https://arxiv.org/abs/1706.03741  
作者机构：OpenAI, UC Berkeley  
推荐理由：提出了RLHF方法，将人类偏好整合到强化学习训练中，后续被广泛应用于大模型对齐研究。本文为NeurIPS 2017论文，附带开源代码，具有里程碑意义。
```

---

## 4. 技术需求

### 核心组件

* **数据抓取**：Jina Reader（统一解析 URL 内容）。
* **分类 & 提取**：OpenRouter LLM（可替换模型）。
* **工作流实现**：Python 3.10+，`requests`, `json`, `pydantic`。
* **配置**：通过.env中的环境变量切换模型：

  ```bash
  OPENROUTER_BASE_URL=
  OPENROUTER_KEY=
  OPENROUTER_MODEL="anthropic/claude-3.5-sonnet"
  ```

### 异常处理

* URL 不可访问 → 跳过并记录日志。
* LLM 输出超长/不符合 JSON → 重试或 fallback。
* 允许手工编辑最终 Markdown。

---

## 5. 非功能需求

* **性能**：处理 100 个 URL ≤ 5 分钟。
* **扩展性**：支持新增分类和标签。
* **鲁棒性**：日志记录错误，保证输出完整。

---

## 6. MVP 范围

* ✅ txt 输入
* ✅ 一级分类
* ✅ Jina Reader + LLM 抽取（标题、作者、机构、推荐理由）
* ✅ 论文二级标签（子类分类）
* ✅ Markdown 输出

未来扩展：

* 视频转录（Whisper 等） → 统一处理
* Substack/WeChat API 自动发布
* 多模型 A/B 测试 & 成本优化


