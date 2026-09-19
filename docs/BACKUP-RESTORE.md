# 备份与恢复

备份目标是让“语料、索引身份、知识库状态和配置”能够共同解释一次查询。`.env` 可能包含 API key，不复制到共享备份；恢复后由操作者单独配置。

## 停机备份清单

先停止 API 和采集/更新任务，再复制以下项目（按实际 profile 取用）：

| 路径 | 用途 | 是否必须 |
|---|---|---|
| `data/raw/` | 原始输入/采集页面 | 建议保留 |
| `data/processed/` | 清洗后的可索引正文 | 建议保留 |
| `data/qdrant/` | Qdrant Local 索引 | Local profile 必须 |
| `data/index_manifest.json` | active collection 与模型/分块身份 | 持久化索引必须 |
| `data/knowledge_manifest.sqlite3*` | 来源、版本、增量任务状态 | 使用采集增量时必须 |
| `configs/` | 来源和实验配置 | 建议保留 |
| 锁文件与 `pyproject.toml` | 重建运行环境 | 发布备份必须 |

`data/run/` 是诊断日志和 PID 状态，不是索引备份；是否保留取决于审计需要。Qdrant Server 不应直接复制服务正在写入的存储目录，应使用 Qdrant 自身 snapshot/运维备份流程，并同时保留 manifest。

## 恢复步骤

1. 在新目录恢复语料、Qdrant Local 目录、manifest 和 SQLite 文件，保持路径关系或更新 `.env` 中对应路径。
2. 使用对应锁文件建立 `.venv`，运行 `pip check`。
3. 复制 `.env.example` 为 `.env`，重新填写本机模型、Qdrant URL 和必要 key；不要覆盖备份中的用户 `.env`。
4. 运行环境检查：

   ```powershell
   .\.venv\Scripts\python.exe -m scripts.check_environment --json
   ```

5. 确认 `runtime.manifest_status=compatible`、active collection、indexed chunk 数和 `knowledge_state` 与备份记录一致，再启动 API。
6. 用已知问题检查来源和回答；恢复验证通过前不要删除旧备份或旧集合。

## 索引不兼容时

如果模型 backend、provider digest、维度、分块算法或 tokenizer 变化，程序应拒绝复用旧索引。按 [INDEX-MIGRATION.md](INDEX-MIGRATION.md) 使用新 collection 执行候选重建，并保留旧 collection 作为回滚点；不要通过手改 manifest 伪装兼容。
