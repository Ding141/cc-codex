# cc-codex

在 Claude Code 里输入一次 `/cc-codex:init`，为当前项目建立 Claude 规划和审查、Codex 实现和测试的协作方式。后续直接向 Claude 描述任务。每个任务有独立记录和 Codex 线程，可以在同一个项目里来回切换。

## 从 GitHub 安装

准备好 Claude Code、已登录的 Codex CLI 和 Python 3.9 或更高版本。插件只使用 Python 标准库。先在**系统终端**运行以下命令，确认两个 CLI 都能启动，并查看 Codex 登录状态。如果提示未登录，运行 `codex login`。

```shell
claude --version
codex --version
codex login status
python --version
```

若本机的 Python 命令是 `python3` 或 `py -3`，可用对应命令检查版本。Windows 支持原生 Codex 可执行文件和标准 npm 全局安装。

进入**你要开发的项目根目录**，运行 `claude`。以下三条是 **Claude Code 对话框里的命令**，逐条输入：

```text
/plugin marketplace add Ding141/cc-codex
/plugin install cc-codex@cc-codex
/reload-plugins
```

第一条从 GitHub 添加插件目录，第二条安装 `cc-codex`（希望在自己的多个项目使用时选择用户范围），第三条让当前会话加载插件。输入 `/plugin` 可在 Installed 页确认插件已启用。安装一次后，在每个需要接入的项目里分别初始化。[Claude Code 插件安装说明](https://code.claude.com/docs/en/discover-plugins)

## 插件命令

cc-codex 提供五个斜杠命令。用 `init` 接入项目，`status` 看进度，`project` 选项目，`task` 管理任务，`work` 开始或继续执行。

| 在 Claude Code 中输入 | 适用时机 | 执行结果 |
| --- | --- | --- |
| `/cc-codex:init` | 第一次接入项目，或重新检查环境 | 检查 Claude → Codex 链路，成功后写入项目分工约定，报告就绪 |
| `/cc-codex:init 任务描述` | 接入项目并立即开工 | 先完成同一项检查，再把附带任务交给工作流程 |
| `/cc-codex:status [项目]` | 看当前或指定项目的进度 | 报告最近探针、选中任务、检查点和其他未完成任务 |
| `/cc-codex:project list` | 查本机登记的项目 | 显示名称、完整路径和当前选择 |
| `/cc-codex:project use 项目` | 选择要处理的目录 | 切换本会话的目标，显示该项目的任务摘要 |
| `/cc-codex:task list [--all]` | 查看当前项目的任务 | 默认列出未完成任务，加 `--all` 包含已完成任务 |
| `/cc-codex:task use T2` | 选中已有任务 | 显示目标和检查点；也接受完整任务 ID |
| `/cc-codex:task new 标题` | 先记下新任务 | 建立并选中一条待办，标题作为初始简报 |
| `/cc-codex:work` | 继续当前选中的任务 | 根据状态开始实现、继续审查或核实阻碍 |
| `/cc-codex:work 任务描述` | 已初始化，希望明确派工、返工或恢复某个任务 | Claude 选定任务，按需要调用 Codex，审查结果后汇报 |

### `/cc-codex:init` 初始化或重新检查

只想配置当前仓库时，输入 `/cc-codex:init`。如果已经知道第一件要做的事，可以一次说完：

```text
/cc-codex:init 给设置页加一个深色模式开关，刷新页面后保留选择。
```

初始化会消耗一次真实 Codex 调用。插件让 Codex 在当前项目读出一个随机值、写回临时文件，并通过回复传回该值。两项核对通过后，Claude 报告测试所用的目录和模型配置。你可以在项目指导文件的 `<!-- cc-codex:begin -->` 和 `<!-- cc-codex:end -->` 之间看到新增约定。再次初始化会重新做探针并更新这部分内容，已有任务记录保留。

如果 Claude Code 提示执行 `scripts/bridge.py` 需要授权，核对当前项目和子命令后在对话框中确认。如果探针失败，按报错检查 Codex 登录、模型可用性或目录写权限，再运行 `/cc-codex:init`。附带的开发任务会等检查通过才开始。

### 查看进度，切换项目，选中任务

假设你在“网站后台”和“移动端”两个项目各运行过一次初始化。第二天打开 Claude，下面这组命令可以从查看进度一路走到恢复开发：

```text
/cc-codex:project list
/cc-codex:status 网站后台
/cc-codex:project use 网站后台
/cc-codex:task list
/cc-codex:task use T2
/cc-codex:work
```

`status 网站后台` 只读项目记录。你看到的是上次探针时间、Codex 的交付结果和 Claude 已保存的检查点；查看不会触发新的 Codex 调用。只有执行 `project use` 才会切换项目。项目名称取自目录名；如有重名，可直接输入 `/cc-codex:project use D:/work/网站后台`。目录需要已初始化，Claude 需要有权限读取它。

`T2` 是当前项目内稳定的短编号，请用 `task list` 实际返回的编号。新建、查看或选中任务时都不会启动实现。`work` 无参数时，选中的任务如果处于 `review`，Claude 从审查已有改动开始；如果已经完成，则报告完成情况；如果没有选择，则列出可选任务。

项目切换的作用域是当前 Claude 会话。切回某个项目会恢复**本会话**上次在该项目选中的任务。全新会话从启动目录开始，可用 `task use` 选回原任务。切换后，Claude 以所选项目的绝对路径读文件、看差异和运行测试，Codex 也在同一目录派工。

**从 v0.1 升级**：旧任务和线程 ID 可继续使用。从旧项目目录直接查询状态，或用 `project use <旧项目绝对路径>` 将它登记到本机索引。旧记录会获得短编号，重新初始化或写入任务时会保存编号。仅为了登记项目无需再消耗一次探针调用。

### `/cc-codex:work` 开始、切换和恢复任务

初始化后可以直接和 Claude 对话，也可以用 `/cc-codex:work` 明确进入这个流程。下面是一段可以逐条尝试的对话：

| 你想做什么 | 输入示例 | 预期行为 |
| --- | --- | --- |
| 开始任务 A | `/cc-codex:work 给设置页加深色模式，刷新后保留选择。` | Claude 建立任务 A，约定验收条件，交给 Codex 实现并检查结果 |
| 给 A 返工 | `深色模式打开后按钮文字太暗，请调高对比度。` | 沿用 A 的任务记录和 Codex 线程，传递新增要求 |
| 暂停 A，开始 B | `先放下深色模式，修一下登录超时后没有提示的问题。` | 为登录问题建立独立记录，两项任务的进度分别保存 |
| 查看进度 | `/cc-codex:status` | 查看上次保存的进度；要列出含已完成任务的清单，用 `/cc-codex:task list --all` |
| 第二天恢复 A | `/cc-codex:work 继续深色模式，先告诉我上次验收到哪里。` | 新会话从同一项目读取 A 的检查点，核对工作区后接着做 |
| 指定 Codex 配置 | `/cc-codex:work 修复登录超时，这个任务的 Codex 用 gpt-6.2-astra，思考强度 high。` | 将模型和强度用于该任务；模型 ID 和档位需在本机可用 |

日常无需记任务 ID。说“继续”时如果有多个候选，Claude 会请你从标题中选择。同一任务返工沿用已有模型配置；想换档位可以直接说明。不确定可选模型时，输入 `/cc-codex:work 列出本机 Codex 模型及其支持的思考强度。` 模型目录列出候选项，账号能否调用以实际派工结果为准。Claude 自身的模型和强度可以在启动宿主时指定，例如 `claude --model <Claude模型> --effort high`。

### 更新插件或试用本地源码

发布新版本后，可在**系统终端**更新，再打开新的 Claude Code 会话：

```shell
claude plugin marketplace update cc-codex
claude plugin update cc-codex@cc-codex
```

要试用本地修改，在目标项目目录的终端运行 `claude --plugin-dir "<本地源码仓库>/plugins/cc-codex"`，再输入 `/cc-codex:init`。将引号里的路径替换为实际插件目录。此方式只对这次启动生效。

## 派工脚本命令参考

下表供调试时使用。调用形式为 `python bridge.py [--session 会话ID] [--project 项目根目录] 子命令`。显式指定的根目录优先，其次使用该会话选中的根目录，最后使用当前目录。插件会自动传入 Claude 的会话 ID；手动试用时可以使用自己的标识，例如 `--session demo`。正文通过 UTF-8 标准输入传入。

| 子命令 | 输入 | 作用 |
| --- | --- | --- |
| `models` | 无 | 查询本机 Codex 模型目录，输出模型 ID、描述和支持的思考强度。可在初始化前运行 |
| `status [项目名或绝对路径]` | 无 | 读取项目状态，保留当前选择 |
| `project list` / `project use 项目` | 无 | 列出项目或选择目标；保存选择需要 `--session` |
| `task list [--all]` / `task use T2` / `task new "标题"` | 无 | 列出、选择或建档并选中；后两项需要 `--session` |
| `init [--model MODEL] [--effort LEVEL]` | 无 | 实测指定配置并写入项目指导文件。这里的模型和档位用于本次探针 |
| `new "标题"` | 标准输入传入目标、范围和验收条件 | 建立状态为 `planned` 的任务，返回任务 ID，供后续命令使用 |
| `list [--all]` | 无 | 默认列出未完成任务，加 `--all` 包含已完成任务 |
| `show ID` | 项目内短编号或完整任务 ID；`run`、`checkpoint` 同样支持两种格式 | 显示单项记录，包括简报、状态，以及已保存的线程 ID、结果或检查点 |
| `run ID [--model MODEL] [--effort LEVEL] [--fresh]` | 标准输入传入本轮工程要求 | 首次派工创建 Codex 线程，后续派工按 ID 续接。原线程丢失时，先核对进度，再用 `--fresh` 为同一个任务创建替代线程 |
| `checkpoint ID 状态` | 标准输入传入新的完整进度摘要 | 替换旧检查点并设置 `planned`、`review`、`blocked` 或 `done`。摘要应保留仍有效的决定、验证结果和剩余事项 |

下面以 PowerShell 为例，假设你在**插件源码仓库**打开终端，目标项目已成功初始化。将 `$project` 改为目标项目的实际路径。`/cc-codex:work` 会替你完成这些派工步骤；手动调用 `run` 时，需要自行安排审查。

```powershell
$bridge = (Resolve-Path ./plugins/cc-codex/scripts/bridge.py).Path
$project = (Resolve-Path 'D:/work/my-app').Path
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# 建档后直接使用返回的 ID
$task = '深色模式刷新后应保留。沿用现有设置存储。' | python $bridge --project $project new '深色模式' | ConvertFrom-Json
python $bridge --project $project show $task.id

# 正文通过管道传给 Codex。成功返回后，任务进入 review
'实现开关并验证刷新后的状态；报告修改文件和验证结果。' | python $bridge --project $project run $task.id
python $bridge --project $project list
```

例如，你已经检查了刷新行为、还需要看窄屏布局，可以保存检查点：

```powershell
'已验证刷新后保留设置；待检查窄屏布局。' | python $bridge --project $project checkpoint $task.id review
```

当进程意外退出且任务仍显示 `running`，先确认旧进程是否还在运行，并核对工作区已有改动。确认中断后，用 `checkpoint` 保存实际进度，再用 `run` 派发剩余工作。

## 架构

| 部件 | 职责 |
| --- | --- |
| `skills/init` | 确认目录和已有指令，执行真实环境探针，按需交接首个任务 |
| `skills/work` | 选择任务、决定派工参数、审查代码或实际页面、决定返工、向用户汇报 |
| `skills/status`、`skills/project`、`skills/task` | 查看进度、选择项目、创建或选择任务 |
| `scripts/navigation.py` | 在本机登记项目目录，按 Claude 会话保存当前项目及各项目的选中任务 |
| `scripts/bridge.py` | 初始化项目，维护项目指导文件的标记区块、任务状态、工作区写锁和探针 |
| `scripts/codex_cli.py` | 以 UTF-8 标准输入调用 `codex exec --json`，解析线程 ID、完成或失败事件和最终答复 |
| `templates/` | 写入项目指导文件的长期分工约定 |

正常调用链为 **用户 → Claude → bridge → Codex CLI → 工程改动 → Claude 独立审查 → 用户**。Claude 检查工作区真实差异、相关验证和界面效果。Codex 通过简短回执报告改动和阻碍。Claude Code 通过项目指令触发这个流程，用户可以显式改派。

## 任务和会话放在哪里

用户目录中的 `~/.cc-codex/navigation.sqlite3` 保存项目路径和会话选择，可用环境变量 `CC_CODEX_HOME` 指定其他存放目录。任务正文、检查点和 Codex 线程 ID 仍然保存在对应项目中。

```text
你的项目/
├─ CLAUDE.md                    Claude 的长期分工约定
├─ AGENTS.md                    Codex 的长期工程约定
└─ .cc-codex/                   由目录内的 .gitignore 排除
   ├─ project.json              最近一次探针结果
   ├─ writer.lock               运行期间由操作系统持有的锁
   └─ tasks/<任务ID>.json        标题、验收条件、进度、线程 ID 和审查记录
```

重新初始化只更新两处标记之间的内容。已有 `.claude/CLAUDE.md` 或根目录 `AGENTS.override.md` 时会使用相应的有效文件。任务 A 和 B 各有一个 JSON 文件；临时需求和进度都保存在各自的任务里。独立项目建议各自使用一个项目根目录。

Codex 启动后立即保存它返回的线程 ID。返工使用 `codex exec resume <thread_id>` 定向恢复。Claude 原生会话和 Codex 原生会话各自由对应 CLI 管理。任务文件仅保存接手需要的资料；同一台机器上的新 Claude 会话可以根据它继续工作。Git 克隆只迁移已提交的项目指导文件，本地线程和任务记录需要保留原工作环境才能直接续用。

任务通常经历 `planned → running → review → done`。模型调用失败会进入 `blocked`。进程意外退出可能留下 `running`，Claude 要先核对进程和实际工作区，再续接。Codex 本地线程已清理时，可以在原任务下开替代线程。每个项目同时允许一个派工进程写入；不同任务仍共享项目文件，切换任务不会撤销前一个任务留下的改动。

## 开发验证

```powershell
python -m unittest discover -s tests -v
claude plugin validate . --strict
claude plugin validate plugins/cc-codex --strict
```

回归测试使用临时目录和模拟 Codex 回执，可离线运行。要验证自己的实际环境，请在目标项目中运行 `/cc-codex:init`。初始化失败会报告原因；检查 Codex 的登录、选定模型和项目写权限，修复后可重试。
