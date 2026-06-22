# agent.md — 本机环境知识库

---

## Windows Kits 路径问题（Tauri / Rust 编译）

### 背景

本机上 Windows SDK 安装在 `D:\Windows Kits` 而非默认的 `C:\Program Files (x86)\Windows Kits`。

`vcvars64.bat`（Visual Studio 2022 BuildTools 的环境初始化脚本）只设置 `C:\Program Files (x86)\Windows Kits` 的库路径，不检测 `D:` 盘。因此 Rust 编译依赖 `vswhom-sys` 时，链接器 `link.exe` 找不到 `kernel32.lib` 等 Windows SDK 库文件，报错：

```
LINK : fatal error LNK1181: 无法打开输入文件"kernel32.lib"
```

### 影响范围

- `cargo check`、`cargo build`、`tauri dev`、`tauri build` 均受影响
- 仅影响 Rust 编译链路，不影响 Python 测试和前端构建
- 之前编译通过是因为 `target/` 中有缓存产物；一旦 `target/debug/build/vswhom-sys-*` 被清除或 Cargo 检测到新的编译配置（如修改 `lib.rs`），就会触发重新编译并暴露此问题

### 临时修复

在 PowerShell 中手动设置 `LIB` 环境变量，指向 SDK 的正确路径，然后再执行 cargo 命令：

```powershell
$env:LIB = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\14.44.35207\lib\x64;D:\Windows Kits\10\Lib\10.0.26100.0\um\x64;D:\Windows Kits\10\Lib\10.0.26100.0\ucrt\x64"
$env:INCLUDE = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\14.44.35207\include;D:\Windows Kits\10\Include\10.0.26100.0\ucrt;D:\Windows Kits\10\Include\10.0.26100.0\um;D:\Windows Kits\10\Include\10.0.26100.0\shared"

Set-Location d:\project\youshengshu\desktop\src-tauri
cargo check
```

### 长期修复（推荐）

在系统环境变量 `LIB` 和 `INCLUDE` 中永久添加 `D:\Windows Kits` 路径：

1. 按 `Win + R` → `sysdm.cpl` → 「高级」→「环境变量」
2. 在「系统变量」中找到 `LIB`，编辑，追加：
   ```
   D:\Windows Kits\10\Lib\10.0.26100.0\um\x64
   D:\Windows Kits\10\Lib\10.0.26100.0\ucrt\x64
   ```
3. 在「系统变量」中找到 `INCLUDE`，编辑，追加：
   ```
   D:\Windows Kits\10\Include\10.0.26100.0\ucrt
   D:\Windows Kits\10\Include\10.0.26100.0\um
   D:\Windows Kits\10\Include\10.0.26100.0\shared
   ```
4. 重启终端使环境变量生效

### SDK 版本信息

| 项 | 值 |
|------|------|
| Windows SDK 版本 | 10.0.26100.0 |
| SDK 安装路径 | `D:\Windows Kits\10\` |
| MSVC 版本 | 14.44.35207 |
| Visual Studio | 2022 BuildTools (v17.14.25) |

### 验证修复

```powershell
Set-Location d:\project\youshengshu\desktop\src-tauri
cargo check
```

预期输出末尾：`Finished \`dev\` profile [unoptimized + debuginfo] target(s) in X.XXs`
