# Youshengshu 产品功能说明

本文件用于集中记录当前已经实现的产品功能，README 以此为产品能力摘要。

## 文本处理

- 长篇 TXT 自动分章节
- 章节顺序校验
- 无效短章节过滤
- 英文章节文件输出
- Translation Manifest 初始化

## 本地 LLM 翻译

- LM Studio 本地模型调用
- 自动发现当前加载模型
- 连续翻译所有待处理章节
- 下一章翻译
- 指定章节翻译
- 段落批次处理
- Context overflow 自动缩小 batch
- 翻译结果输出到中文章节目录

## 翻译任务管理

- pending / in_progress / done / failed 状态
- 每章翻译进度
- 失败原因记录
- partial 文件
- Resume State
- 源文件 SHA-256 校验
- 断点续跑

## TTS

- 单 TXT 输入
- 中文章节目录输入
- 创建 TTS 项目
- 中文文本自动切段
- CosyVoice HTTP Provider
- sft / zero_shot / cross_lingual / instruct 模式
- 指定章节生成
- 下一章生成
- 全部待处理章节连续生成
- Segment 级状态管理
- Segment 级断点恢复
- WAV 校验
- 章节音频合并

## 桌面端

- Tauri + React + TypeScript
- 路径选择和配置保存
- Translation 操作面板
- TTS 操作面板
- 系统诊断
- 实时日志
- 状态卡片
- 章节表格
- 指定章节执行
- 停止当前任务
- 打开输出目录
- Runtime / frontend Git HEAD 一致性检查

## 尚未完成

- RVC Voice Conversion pipeline
- 自动 CI
- 更多 TTS Provider
- 完整跨平台支持
