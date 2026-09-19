# 索引身份迁移与回滚

## 目的

`data/index_manifest.json` 是持久化索引的身份清单。它描述向量库后端、嵌入模型及其 provider digest、向量维度、分块策略与算法版本、稀疏检索 tokenizer 和活动集合。清单中的身份字段发生变化时，旧索引必须重建，不能仅凭“模型名相同”继续复用。

当前清单 schema 为 `2`。schema 1 或缺少新身份字段的清单会被拒绝，并明确要求重新索引；程序不会自动删除旧集合。

## 哪些变化会触发重建

- `embedder_backend`、`embedding_model` 或 `embedding_digest` 变化；
- 向量维度、归一化方式或向量库后端变化；
- `chunk_strategy`、`chunk_algorithm_version`、`chunk_size` 或 `chunk_overlap` 变化；
- `tokenizer_version` 变化。

`embedding_digest` 优先使用 `RAG_EMBEDDER_DIGEST`。Ollama 运行时会尝试从 `/api/tags` 读取模型 digest，并支持把未带 tag 的模型名映射到 `:latest`。如果 provider 不提供 digest，应在发布配置中显式记录可验证的 revision；空值表示“未提供 provider revision”，不是伪造的固定版本。

## 安全迁移流程

1. 固定当前配置、语料目录和旧 `index_manifest.json`，先复制清单作为审计记录。
2. 使用新的候选集合名执行 `scripts/reindex.py`。候选名必须是尚不存在的集合；指定 active 集合或其他已有集合会在第一次写入前失败。
3. 等待候选索引完成数量检查和查询回读验证。失败时保留候选集合名称及错误，不切换活动清单。
4. 检查候选清单的 `active_collection`、模型 digest、分块算法版本和语料快照记录，再进行人工验收。
5. 只有候选验证成功后才原子替换 `data/index_manifest.json`。旧集合保留，用于回滚和比对。
6. 回滚时恢复经过核验的旧清单，使 `active_collection` 指向旧集合；不要直接覆盖集合内容。

## 记录要求

每次迁移至少记录：执行时间、旧/新 manifest、候选集合名、语料根目录及文件清单 hash、嵌入 backend/model/digest、分块参数、候选 chunk 数量、验证结果和操作者。清理旧集合属于单独的变更，必须在回滚窗口结束并完成备份后再执行。

