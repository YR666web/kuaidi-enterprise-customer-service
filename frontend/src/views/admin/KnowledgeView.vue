<template>
  <div class="knowledge">
    <div class="flex items-center justify-between knowledge__head">
      <div>
        <div class="knowledge__title">知识库文档</div>
        <div class="text-secondary text-sm">上传文档后将解析、语义切分并向量化入库</div>
      </div>
      <el-button v-permission="'knowledge:write'" type="primary" @click="uploadVisible = true">
        <el-icon><Upload /></el-icon>
        上传文档
      </el-button>
    </div>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="docs" style="width: 100%">
        <el-table-column prop="name" label="文档名称" min-width="200">
          <template #default="{ row }">
            <div class="doc-name">
              <el-icon :size="16" class="doc-name__icon"><Document /></el-icon>
              <span>{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ typeLabel(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="110">
          <template #default="{ row }">{{ formatSize(row.size) }}</template>
        </el-table-column>
        <el-table-column prop="chunks" label="片段数" width="90" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="上传时间" width="160">
          <template #default="{ row }">{{ formatTime(row.uploadedAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openPreview(row)">预览</el-button>
            <el-button
              link
              type="danger"
              size="small"
              v-permission="'knowledge:write'"
              @click="removeDoc(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <EmptyState v-if="!loading && !docs.length" title="暂无文档" description="点击右上角「上传文档」开始构建知识库" />
    </el-card>

    <el-dialog v-model="uploadVisible" title="上传文档" width="460px">
      <el-upload drag multiple :auto-upload="true" :show-file-list="false" :http-request="doUpload">
        <el-icon :size="40" class="upload-icon"><UploadFilled /></el-icon>
        <div>将文件拖到此处，或<em>点击选择</em></div>
        <template #tip>
          <div class="text-sm text-secondary">支持 PDF / Markdown / 纯文本</div>
        </template>
      </el-upload>
    </el-dialog>

    <el-dialog v-model="previewVisible" :title="previewDoc?.name ?? '预览'" width="600px">
      <template v-if="previewDoc">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="类型">{{ typeLabel(previewDoc.type) }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusType(previewDoc.status)" size="small">
              {{ statusLabel(previewDoc.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="大小">{{ formatSize(previewDoc.size) }}</el-descriptions-item>
          <el-descriptions-item label="片段数">{{ previewDoc.chunks }}</el-descriptions-item>
        </el-descriptions>

        <div class="preview__label">内容片段（{{ previewChunks.length }}）</div>
        <div v-loading="previewLoading" class="preview__content">
          <div v-for="c in previewChunks" :key="c.index" class="preview__chunk">
            <span class="preview__chunk-idx">#{{ c.index }}</span>
            <span>{{ c.text }}</span>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Document, Upload, UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'

import {
  deleteDocument,
  listDocuments,
  previewDocument,
  uploadDocument,
  type KnowledgeChunk,
} from '@/api/knowledge'
import EmptyState from '@/components/common/EmptyState.vue'
import type { KnowledgeDoc } from '@/types'

const docs = ref<KnowledgeDoc[]>([])
const loading = ref(false)
const uploadVisible = ref(false)
const previewVisible = ref(false)
const previewLoading = ref(false)
const previewDoc = ref<KnowledgeDoc | null>(null)
const previewChunks = ref<KnowledgeChunk[]>([])

function typeLabel(t: KnowledgeDoc['type']) {
  return { pdf: 'PDF', markdown: 'Markdown', text: '纯文本' }[t]
}
function statusLabel(s: KnowledgeDoc['status']) {
  return { processing: '解析中', ready: '已就绪', failed: '失败' }[s]
}
function statusType(s: KnowledgeDoc['status']) {
  return { processing: 'warning', ready: 'success', failed: 'danger' }[s] as
    | 'warning'
    | 'success'
    | 'danger'
}
function formatSize(n: number) {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}
function formatTime(ts: number) {
  return new Date(ts).toLocaleString('zh-CN', { hour12: false })
}

async function loadDocuments() {
  loading.value = true
  try {
    docs.value = await listDocuments()
  } finally {
    loading.value = false
  }
}

// el-upload 自定义上传
async function doUpload(options: { file: File; onSuccess?: () => void; onError?: () => void }) {
  try {
    await uploadDocument(options.file)
    ElMessage.success('上传成功，已解析入库')
    options.onSuccess?.()
    uploadVisible.value = false
    await loadDocuments()
  } catch {
    ElMessage.error('上传失败')
    options.onError?.()
  }
}

async function openPreview(doc: KnowledgeDoc) {
  previewDoc.value = doc
  previewVisible.value = true
  previewLoading.value = true
  previewChunks.value = []
  try {
    previewChunks.value = await previewDocument(doc.id)
  } catch {
    previewChunks.value = []
  } finally {
    previewLoading.value = false
  }
}

async function removeDoc(doc: KnowledgeDoc) {
  try {
    await ElMessageBox.confirm(`确定删除「${doc.name}」吗？删除后不可恢复。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  await deleteDocument(doc.id)
  ElMessage.success('已删除')
  await loadDocuments()
}

onMounted(loadDocuments)
</script>

<style scoped lang="scss">
.knowledge {
  display: flex;
  flex-direction: column;
  gap: var(--sl-space-lg);
}
.knowledge__title {
  font-size: var(--sl-font-size-lg);
  font-weight: var(--sl-font-weight-semibold);
}
.doc-name {
  display: flex;
  align-items: center;
  gap: var(--sl-space-xs);
}
.doc-name__icon {
  color: var(--sl-text-secondary);
}
.upload-icon {
  color: var(--sl-primary);
}
.preview__label {
  margin: var(--sl-space-md) 0 var(--sl-space-sm);
  font-size: var(--sl-font-size-sm);
  color: var(--sl-text-secondary);
}
.preview__content {
  max-height: 360px;
  overflow-y: auto;
  padding: var(--sl-space-sm);
}
.preview__chunk {
  padding: var(--sl-space-sm) var(--sl-space-md);
  background: var(--sl-bg-subtle);
  border-radius: var(--sl-radius-md);
  margin-bottom: var(--sl-space-xs);
  line-height: var(--sl-line-height);
  color: var(--sl-text-regular);
  font-size: var(--sl-font-size-sm);
}
.preview__chunk-idx {
  color: var(--sl-primary);
  margin-right: var(--sl-space-xs);
  font-weight: var(--sl-font-weight-medium);
}
</style>
