# cc-codex

把 Claude 和 Codex 接成一条流水线的 Claude Code 插件。你只和 Claude 对话：**Claude 负责理解需求、设计架构和审美、最终验收；Codex（GPT）负责写代码、查证资料、跑测试。**

各用所长：Claude 擅长架构、审美和把话说清楚，GPT 擅长工程实现和严谨性。Claude 侧的用量也随之降低：它只写一份简报、读一份报告，读代码、改文件、跑测试这些占上下文的工作都留在 Codex 里。

## 安装

### 1. 前置条件

- Claude Code 2.1.292 或更新
- Python 3.9+（插件只用标准库）
- Codex CLI，并已登录
- 可选：Chrome、Edge 或 Chromium，用于页面截图

安装 Codex CLI：

| 系统 | 命令 |
| --- | --- |
| Windows | `powershell -ExecutionPolicy ByPass -c "irm https://chatgpt.com/codex/install.ps1 \| iex"`，或 `npm install -g @openai/codex` |
| macOS | `brew install --cask codex`，或 `npm install -g @openai/codex` |
| Linux | `curl -fsSL https://chatgpt.com/codex/install.sh \| sh`，或 `npm install -g @openai/codex` |

装好后运行一次 `codex`，选择 **Sign in with ChatGPT** 完成登录。Python 解释器按 `python`、`python3`、`py -3` 的顺序自动选用，不需要额外配置。

### 2. 安装插件

三个系统的命令相同，在终端（PowerShell、Terminal 均可）任意目录运行：

```shell
claude plugin install cc-codex --marketplace Ding141/cc-codex --scope user
```

`--scope user` 让本机所有项目都能用。已打开的会话输入 `/reload-plugins` 生效，新会话自动加载。

更新：

```shell
claude plugin marketplace update cc-codex
claude plugin update cc-codex@cc-codex
```

试用本地源码：`claude --plugin-dir "<仓库>/plugins/cc-codex"`。

### 3. 接入项目

在项目目录启动 `claude`，输入 `/cc-codex:init`。它会真实调用一次 Codex，让它读写一个临时文件并回传，三项都对上才算就绪，并在项目里写入分工约定。之后直接描述需求，或输入 `/cc-codex:work 给设置页加个深色模式开关`。

## 功能

| 命令 | 用途 |
| --- | --- |
| `/cc-codex:init` | 首次接入项目，或重新检查链路 |
| `/cc-codex:work` | 主流程：规划、派工给 Codex、审查、返工、交付；也用来列出和切换项目与任务 |
| `/cc-codex:status` | 只读查看项目是否就绪、任务进度和 Codex 的结果，不会调用 Codex |

- **Codex 当作自主的子代理。** Claude 和你确认验收标准后交出一份简报，Codex 自己拆步骤、写代码、跑测试，并对照每条标准自检。它返回一份结构化报告：结果、改动文件、跑过的检查、每条标准的证据、待决问题。Claude 读报告并抽查，不重复 Codex 已做的调研和测试。
- **任务可以暂停、切换、隔天继续。** 每个任务有编号（T1、T2…）和独立的 Codex 线程，返工和续做都会接着同一个上下文。状态为 `planned`、`running`、`review`、`done`，失败进入 `blocked`。进程中断后，Claude 先核对工作区实际改动，再派发剩余工作。
- **视觉验收。** 做网页类任务时，插件在 Codex 完成后用本机浏览器截取桌面和手机、浅色和深色共四张图，交给 Claude 看，不需要 Codex 自己开浏览器。
- **可指定 Codex 的模型和思考强度。** 直接对话里说「这个任务用某某模型，强度 high」即可；说「列出本机 Codex 模型」可查看候选。
- **多项目、多会话。** 每个 Claude 会话记住自己选中的项目和任务，互不干扰。同一项目同一时刻只允许一个派工进程写入。

## 架构

```
你 → Claude（规划 / 审美 / 验收）
        │  简报文件
        ▼
     bridge.py ──→ Codex CLI（沙箱内实现、查证、测试、自检）
        │                  │
        │  任务记录         ▼
        ▼             结构化报告
   截图（沙箱外）──────→ Claude 验收 → 你
```

| 部件 | 职责 |
| --- | --- |
| `skills/init`、`work`、`status` | 三个命令的流程说明，决定 Claude 何时规划、派工、审查 |
| `scripts/bridge.py` | 唯一入口：初始化、项目与任务记录、状态机、写锁、派工 |
| `scripts/codex_cli.py` | 调用 `codex exec --json`，解析线程 ID、完成事件和最终报告；支持 Windows 原生和 npm 安装 |
| `scripts/navigation.py` | 本机项目登记与各会话的选择（SQLite） |
| `scripts/render.py` | 在 Codex 沙箱外用本机 Chrome 或 Edge 无头截图 |
| `templates/` | 写入项目的分工约定，以及 Codex 报告的 JSON 格式 |

设计上的几点：

- **Codex 在 `workspace-write` 沙箱里运行**，只能改项目目录。沙箱里启动不了浏览器，所以工作约定禁止它这么做，截图由 bridge 在沙箱外完成。
- **正文走文件。** 简报和返工说明由 Claude 写成文件，再通过 `--input` 交给 bridge，让每次调用都是一条简单命令。
- **状态都在本机。** 项目里的 `.cc-codex/`（自带 `.gitignore`）存放任务记录、简报和截图。`CLAUDE.md` 与 `AGENTS.md` 只更新插件自己的标记区块，你手写的内容保留。全局索引在 `~/.cc-codex/`。

MIT License.
