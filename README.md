# youshengshu (有声书)

小说 TXT 分章节 + 调用 LM Studio 批量翻译的本地工具系统。

## 用途

本程序将一个 AO3 导出的英文长篇小说 TXT 文件：

1. **分章节**：按 AO3 章节标题自动切分为单个英文章节文件。
2. **批量翻译**：通过 LM Studio 本地 API 调用本地 LLM，逐章翻译为中文。
3. **断点续跑**：翻译进度保存在 manifest 中，中断后可从中断处继续。

## 为什么源文和译文不被提交到 GitHub

- 原文和译文可能涉及版权。
- 文本文件可能很大，不应污染仓库。
- GitHub 仓库只保存程序、配置、测试和 README。

## 安装

```bash
git clone https://github.com/z443208468/youshengshu.git
cd youshengshu

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
```

## LM Studio 设置

1. 打开 LM Studio
2. 加载任意本地模型
3. 进入 Developer / Local Server 页面
4. 点击 Start Server
5. 确认服务器地址为 `http://localhost:1234/v1`

LM Studio 当前加载什么模型，程序就调用什么模型。如果加载了多个模型，默认使用列表中的第一个。

## 输入文件

将你的 AO3 导出的英文小说 TXT 放入 `data/input/` 目录，例如：

```
data/input/ReZero_Watching_Him_Die.txt
```

如需修改输入文件路径，请编辑 `config/default_config.json` 中的 `paths.input_file`。

## 使用

### 分章节

```bash
python -m src.youshengshu.cli split --config config/default_config.json
```

输出到 `data/en_chapters/` 目录，例如 `chapter_001_en.txt`。

### 查看翻译进度

```bash
python -m src.youshengshu.cli status --config config/default_config.json
```

### 批量翻译

```bash
python -m src.youshengshu.cli translate --config config/default_config.json
```

输出到 `data/cn_chapters/` 目录，例如 `chapter_001_cn.txt`。

### 一次完成所有操作

```bash
python -m src.youshengshu.cli all --config config/default_config.json
```

### 续跑

翻译过程中如果中断，直接重新运行 translate 命令：

```bash
python -m src.youshengshu.cli translate --config config/default_config.json
```

程序会自动跳过已完成的章节，从中断处继续。

## 输出位置

| 内容 | 路径 |
|------|------|
| 英文分章 | `data/en_chapters/chapter_XXX_en.txt` |
| 中文译文 | `data/cn_chapters/chapter_XXX_cn.txt` |
| 翻译进度 | `data/manifests/translation_manifest.json` |

## 配置文件说明

配置文件 `config/default_config.json` 包含以下参数：

### 路径配置 (paths)
- `input_file`: 输入 TXT 文件路径
- `en_chapters_dir`: 英文分章输出目录
- `cn_chapters_dir`: 中文译文输出目录
- `manifest_file`: 翻译进度文件路径

### 章节切分 (chapter_split)
- `strict_chapter_sequence`: 是否检查章节序号连续
- `min_valid_chapter_chars`: 有效章节最小字符数（用于过滤目录条目）

### LM Studio 配置 (lmstudio)
- `base_url`: LM Studio API 地址
- `model_id`: 模型 ID (`auto` 表示自动检测当前加载的模型)
- `temperature`: 生成温度 (0.2)
- `max_output_tokens`: 最大输出 token 数 (4096)
- `request_timeout_seconds`: 请求超时时间 (600)
- `max_retries`: 失败重试次数 (3)

### Token 预算 (chunking)
- `context_tokens`: 模型上下文窗口 (8192, 8k 基准)
- `reserved_prompt_tokens`: 提示词预留 (1800)
- `reserved_output_tokens`: 输出预留 (4096)
- `safety_ratio`: 安全系数 (0.72)
- `english_chars_per_token`: 英文每 token 字符数 (4.0)
- `cjk_chars_per_token`: 中文每 token 字符数 (1.2)

## 常见问题

### LM Studio 当前没有模型

先在 LM Studio 里加载模型，并启动 Local Server。

### 翻译太慢

换更小的量化模型，或者降低 `max_output_tokens`，但不要随意增大 chunk。

### 输出中途停止

降低 `config/default_config.json` 中 `context_tokens` 或 `reserved_output_tokens`，或换更短的 chunk 预算。

### 翻译质量不好

换更强模型；不要用过小模型直接跑全书；先跑一章抽查。

### 使用 Qwen3 模型

如果你使用 Qwen3 系列模型，可以在提示词中加入 `/no_think` 来禁用思考输出。本程序默认不加。
