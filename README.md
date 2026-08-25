# Youshengshu（有声书工作台）

一个面向长篇小说的本地 AI 有声书制作工具。

它把 **文本分章 → 本地 LLM 翻译 → 中文稿管理 → TTS 配音 → 音频合并** 放在同一个桌面工作台里，适合处理长篇小说、同人文和其他需要批量翻译与语音生成的长文本内容。

当前主要支持 Windows，本地模型通过 LM Studio 和 CosyVoice 运行。

---

## 产品功能

### 1. 小说自动分章节

导入长篇 TXT 后，程序可以自动识别章节并拆分成独立文件。

支持：

- 按章节标题自动切分
- 检查章节编号是否连续
- 过滤目录、短文本等无效章节
- 自动生成英文分章文件
- 自动创建翻译任务清单（Manifest）

适合把一个完整长篇文本整理成可逐章处理的结构。

---

### 2. 本地 AI 批量翻译

通过 LM Studio 调用本地 LLM，对拆分后的章节进行批量英译中。

支持：

- 自动识别 LM Studio 当前加载的模型
- 逐章翻译
- 连续翻译所有待处理章节
- 只翻译下一章
- 指定章节单独翻译
- 查看当前翻译进度
- 失败章节单独重试
- 翻译结果自动保存到中文章节目录

程序默认按段落批次发送给模型。如果当前批次超出模型上下文窗口，会自动缩小批次后继续尝试。

例如：

```text
8 个段落
  ↓ 上下文溢出
4 个段落
  ↓ 上下文溢出
2 个段落
  ↓ 成功
```

不会为了继续运行而静默截断原文。

---

### 3. 翻译断点续跑

长篇小说翻译通常需要运行很长时间，因此翻译任务支持断点恢复。

如果出现：

- LM Studio 超时
- 模型报错
- 程序关闭
- 电脑重启
- 翻译中途手动停止

重新运行后可以从已经完成的位置继续，而不需要整章重新翻译。

程序会保存：

- 已完成段落数量
- 已完成 batch 数量
- 当前 partial 译文
- Resume State
- 源文件 SHA-256

如果原文后来被修改，旧断点不会被错误继续使用。

---

### 4. 翻译进度管理

桌面端和 CLI 都可以查看每章状态。

状态包括：

```text
pending       待处理
in_progress   处理中
done          已完成
failed        失败
```

可以查看：

- 总章节数
- 已完成章节数
- 待处理章节数
- 失败章节数
- 当前处理章节
- 每章翻译进度
- 失败原因
- partial 文件位置

---

### 5. 中文文本 TTS 配音

翻译完成后，可以直接把中文章节送入 TTS 模块生成有声书音频。

当前使用 CosyVoice HTTP Provider。

支持：

- 单个 TXT 作为 TTS 输入
- 整个中文章节目录作为 TTS 输入
- 自动创建 TTS 项目
- 自动切分长文本
- 单章生成
- 生成下一章
- 连续生成所有待处理章节
- 查看每章 TTS 状态
- 自动输出 WAV 文件

---

### 6. 多种 CosyVoice 模式

当前支持：

- `sft`
- `zero_shot`
- `cross_lingual`
- `instruct`

可以根据模式配置：

- speaker ID
- prompt text
- prompt audio
- instruct text

用于不同的声音和生成方式。

---

### 7. TTS 文本自动切段

为了避免整章一次送入模型导致失败，程序会先把中文章节拆成适合语音生成的小段。

默认会根据：

- 目标字符长度
- 最大字符长度
- 中文标点

自动切分。

默认配置示例：

```json
{
  "target_chars_min": 80,
  "target_chars_max": 180,
  "hard_chars_max": 240,
  "punctuation": "。！？；……\n"
}
```

---

### 8. TTS 断点恢复

每个 TTS segment 都单独记录状态。

例如一章被拆成 100 个 segment：

```text
001 ✓
002 ✓
003 ✓
...
057 ✓
058 生成失败
```

重新运行后会从未完成的位置继续，而不是重新生成前 57 段。

程序恢复时会检查实际 WAV 文件，而不是只看 Manifest 状态。

---

### 9. WAV 校验与章节合并

TTS 输出后会检查音频文件是否有效。

包括：

- WAV 文件是否存在
- PCM 数据是否为空
- int16 数据是否对齐
- sample rate 是否符合配置
- 音频是否可正常读取

所有 segment 完成后，会自动合并为章节级 WAV。

---

### 10. 桌面图形界面

项目包含基于 **Tauri v2 + React + TypeScript** 的桌面应用。

桌面端可以直接完成主要操作，无需手动输入 CLI 命令。

当前界面包含：

#### 翻译模块

- 选择原始 TXT
- 设置英文分章目录
- 设置中文译文目录
- 设置 Manifest 路径
- 保存配置
- 系统诊断
- 分章节
- 刷新翻译状态
- 连续翻译待处理章节
- 翻译下一章
- 指定章节翻译
- 停止当前任务
- 查看章节表格
- 查看实时日志
- 打开输出目录

#### TTS 模块

- 检查 CosyVoice 服务状态
- 配置 TTS 输入路径
- 配置音频输出目录
- 配置 Provider 参数
- 选择 prompt audio
- 创建 TTS 项目
- 查看 TTS 进度
- 生成指定章节
- 生成下一章节
- 连续生成所有待处理章节
- 查看生成日志
- 打开音频输出位置

#### RVC 模块

RVC 目前只有工作台入口，实际 Voice Conversion pipeline 尚未完成。

---

### 11. 系统诊断

Translation 和 TTS 都提供 Doctor / Diagnostics 功能。

可以检查：

- Python 环境
- 配置文件
- 输入文件
- 输出目录
- Manifest
- LM Studio 服务
- CosyVoice Runtime
- 本地运行环境

桌面端启动后也会显示当前系统是否满足执行条件。

---

### 12. 实时日志与错误信息

桌面端会显示 Python / TTS 执行过程中的实时日志。

包括：

- 当前执行命令
- 模型名称
- 当前章节
- 当前 batch / segment
- 请求失败信息
- 上下文溢出
- Resume 状态
- 输出路径
- 错误原因

方便定位长任务运行过程中出现的问题。

---

## 典型使用流程

### 英文小说 → 中文译文 → 有声书

```text
1. 导入长篇英文 TXT
        ↓
2. 自动分章节
        ↓
3. LM Studio 本地模型逐章翻译
        ↓
4. 检查 / 续跑失败章节
        ↓
5. 得到中文章节目录
        ↓
6. 创建 TTS 项目
        ↓
7. 自动切分中文文本
        ↓
8. CosyVoice 批量生成音频
        ↓
9. 自动恢复失败 segment
        ↓
10. 合并为章节 WAV
```

---

## 技术栈

### AI / Runtime

- LM Studio
- OpenAI-compatible API
- CosyVoice
- CUDA / PyTorch

### Backend

- Python
- OpenAI Python SDK
- Requests
- pytest

### Desktop

- Tauri v2
- Rust
- React 18
- TypeScript
- Vite
- Tailwind CSS

---

## 项目结构

```text
youshengshu/
├─ config/
│  ├─ default_config.json
│  └─ tts_config.json
├─ src/
│  ├─ youshengshu/          # 分章 / 翻译 / Resume / Manifest
│  └─ youshengshu_tts/      # TTS / Segment / Resume / Provider
├─ desktop/
│  ├─ src/                  # React UI
│  └─ src-tauri/            # Tauri / Rust backend
├─ tests/
├─ scripts/
├─ requirements.txt
├─ dev_check.bat
└─ run_youshengshu.bat
```

---

## 快速启动

### 环境要求

- Windows
- Python 3
- Node.js / npm
- Rust / Cargo
- Visual Studio Build Tools / Windows SDK
- LM Studio（翻译）
- CosyVoice Runtime（TTS）

### 启动桌面端

```bat
run_youshengshu.bat
```

或者：

```bash
cd desktop
npm install
npm run tauri dev
```

---

## Translation CLI

### 安装依赖

```bash
git clone https://github.com/z443208468/youshengshu.git
cd youshengshu

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 系统诊断

```bash
python -m src.youshengshu.cli --config config/default_config.json doctor
```

### 分章节

```bash
python -m src.youshengshu.cli --config config/default_config.json split
```

### 查看状态

```bash
python -m src.youshengshu.cli --config config/default_config.json status
```

### 连续翻译所有待处理章节

```bash
python -m src.youshengshu.cli --config config/default_config.json translate
```

### 只翻译下一章

```bash
python -m src.youshengshu.cli --config config/default_config.json translate --max-chapters 1
```

### 指定章节

```bash
python -m src.youshengshu.cli --config config/default_config.json translate --chapter-index 4
```

---

## TTS CLI

### 系统诊断

```bash
python -m src.youshengshu_tts.cli --config config/tts_config.json doctor
```

### 创建项目

```bash
python -m src.youshengshu_tts.cli --config config/tts_config.json create-project
```

### 查看状态

```bash
python -m src.youshengshu_tts.cli --config config/tts_config.json status
```

### 生成指定章节

```bash
python -m src.youshengshu_tts.cli --config config/tts_config.json synthesize --chapter-index 1
```

### 生成下一章

```bash
python -m src.youshengshu_tts.cli --config config/tts_config.json synthesize-next
```

### 连续生成全部章节

```bash
python -m src.youshengshu_tts.cli --config config/tts_config.json synthesize-all
```

---

## 为什么长任务可以恢复

项目为 Translation 和 TTS 分别维护持久化状态。

Translation 保存 paragraph batch 级 Resume State；TTS 保存 segment 级 Manifest，并在恢复时重新检查实际产物。

关键文件使用临时文件后 replace 的方式写入，降低程序中断后留下损坏正式文件的概率。

这部分主要用于解决本地 AI 长任务中常见的：

- 模型超时
- 上下文溢出
- GPU / TTS 服务崩溃
- 客户端断开
- 程序被关闭
- 部分文件已经生成但任务没有完整结束

---

## 测试

Python：

```bash
pytest
```

前端：

```bash
cd desktop
npm run build
```

Rust：

```bash
cd desktop/src-tauri
cargo check
cargo test
```

Windows 开发环境也可以运行：

```bat
dev_check.bat
```

---

## 当前状态

### 已实现

- [x] 长篇 TXT 分章节
- [x] LM Studio 本地模型翻译
- [x] 翻译进度管理
- [x] 翻译断点续跑
- [x] Context overflow 自动退避
- [x] 指定章节 / 下一章 / 连续翻译
- [x] TTS 文本切段
- [x] CosyVoice TTS
- [x] 多种 CosyVoice 模式
- [x] TTS segment 级恢复
- [x] WAV 校验
- [x] 章节音频合并
- [x] Tauri 桌面端
- [x] 实时日志
- [x] 系统诊断
- [x] CLI JSON 输出

### 未完成 / 计划中

- [ ] RVC Voice Conversion pipeline
- [ ] 更多 TTS Provider
- [ ] 自动 CI
- [ ] 更完整的跨平台支持

---

## 数据与版权

仓库不提交：

- 原始小说全文
- 完整翻译文本
- 生成音频
- CosyVoice 模型文件
- 其他大型运行时文件

仓库主要保存程序代码、配置、测试和开发工具。