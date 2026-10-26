import http from './http'

import type { KnowledgeDoc } from '@/types'

export interface KnowledgeChunk {
  index: number
  page?: number
  text: string
}

export interface KnowledgeVersion {
  docId: string
  version: number
  name: string
  size: number
  chunks: number
  createdAt: number
}

export async function listDocuments(): Promise<KnowledgeDoc[]> {
  const res = await http.get<KnowledgeDoc[]>('/knowledge/documents')
  return res.data
}

export async function uploadDocument(file: File): Promise<KnowledgeDoc> {
  const form = new FormData()
  form.append('file', file)
  const res = await http.post<KnowledgeDoc>('/knowledge/documents', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export async function previewDocument(docId: string): Promise<KnowledgeChunk[]> {
  const res = await http.get<{ chunks: KnowledgeChunk[] }>(`/knowledge/documents/${docId}`)
  return res.data.chunks
}

export async function deleteDocument(docId: string): Promise<void> {
  await http.delete(`/knowledge/documents/${docId}`)
}

export async function replaceDocument(docId: string, file: File): Promise<KnowledgeDoc> {
  const form = new FormData()
  form.append('file', file)
  const res = await http.put<KnowledgeDoc>(`/knowledge/documents/${docId}`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export async function listDocumentVersions(docId: string): Promise<KnowledgeVersion[]> {
  const res = await http.get<KnowledgeVersion[]>(`/knowledge/documents/${docId}/versions`)
  return res.data
}
