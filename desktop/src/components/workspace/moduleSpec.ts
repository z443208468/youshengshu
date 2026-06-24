import type { ModuleCardInfo } from "../../types/app";

export const MODULE_CARDS: ModuleCardInfo[] = [
  {
    id: "translation",
    title: "翻译工坊",
    subtitle: "英文 TXT → 中文章节",
    statusLabel: "已集成",
    description: "分章节、断点翻译、失败续跑。",
    primaryAction: "进入翻译工坊",
  },
  {
    id: "tts",
    title: "TTS 工坊",
    subtitle: "中文章节 → 人声音频",
    statusLabel: "第一版：CosyVoice HTTP",
    description: "把中文 TXT 或 cn_chapters 生成章节 WAV。",
    primaryAction: "进入 TTS 工坊",
  },
  {
    id: "rvc",
    title: "RVC 工坊",
    subtitle: "音频 → 声线转换",
    statusLabel: "预留入口",
    description: "后续接入本地 RVC 项目。",
    primaryAction: "查看 RVC 入口",
  },
];
