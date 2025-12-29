<script setup>
import UploadsList from './docs/UploadsList.vue'
import Banner from './common/Banner.vue'
import UploadStatusRow from './docs/UploadStatusRow.vue'
import UploadActions from './docs/UploadActions.vue'

import { ref, onMounted } from 'vue'

const props = defineProps({
    workspaceId: { type: String, required: true },
})

const selectedFile = ref(null)
const isLoading = ref(false)
const errorText = ref('')
const successText = ref('')
const uploads = ref([])

onMounted(() => {
  loadDocuments()
})

async function loadDocuments() {
  try {
    const response = await fetch(
      `/api/rag/documents?workspace_id=${props.workspaceId}`
    )

    if (!response.ok) {
      throw new Error('Failed to load documents')
    }

    const data = await response.json()

    uploads.value = data.documents.map(doc => ({
      id: doc.id,
      name: doc.source,
      size: doc.size ?? '',
      chunks: doc.chunks_count ?? 0,
      status: 'Ready',
      workspaceId: props.workspaceId,
      createdAt: doc.created_at,
    }))
  } catch (err) {
    errorText.value = err.message
  }
}


function handleFileChange(event) {
    selectedFile.value = event.target.files?.[0] ?? null
}

const fileInputEl = ref(null)

async function upload() {
    if (!selectedFile.value) return

    isLoading.value = true
    errorText.value = ''
    successText.value = ''

    const formData = new FormData()
    formData.append('workspace_id', props.workspaceId)
    formData.append('file', selectedFile.value)

    try {
        const response = await fetch('/api/ingest/ingest-file', {
            method: 'POST',
            body: formData,
        })

        if (!response.ok) {
            const text = await response.text()
            throw new Error(text || 'Upload failed')
        }

        const data = await response.json()
        successText.value = `Uploaded ${selectedFile.value.name}. chunks: ${data.chunks_count ?? 'n/a'}`
        uploads.value.unshift({
            id: crypto.randomUUID(),
            name: selectedFile.value.name,
            size: `${(selectedFile.value.size / 1024 / 1024).toFixed(1)}MB`,
            chunks: data.chunks_count ?? 0,
            status: 'Ready',
            workspaceId: props.workspaceId,
            createdAt: new Date().toISOString(),
        })


        selectedFile.value = null
        if (fileInputEl.value) {
            fileInputEl.value.value = ''
        }


    } catch (error) {
        errorText.value = error.message
    } finally {
        isLoading.value = false
    }
}

async function uploadBook() {
    if (!selectedFile.value) return

    isLoading.value = true
    errorText.value = ''
    successText.value = ''

    const formData = new FormData()
    formData.append('workspace_id', props.workspaceId)
    formData.append('file', selectedFile.value)

    try {
        const response = await fetch('http://localhost:7777/ingest-file', {
            method: 'POST',
            body: formData,
        })

        if (!response.ok) {
            const text = await response.text()
            throw new Error(text || 'Local ingest failed')
        }

        const data = await response.json()

        successText.value = `Book processed locally: ${selectedFile.value.name}. chunks: ${data.chunks_count ?? 'n/a'}`

        uploads.value.unshift({
            id: crypto.randomUUID(),
            name: selectedFile.value.name,
            size: `${(selectedFile.value.size / 1024 / 1024).toFixed(1)}MB`,
            chunks: data.chunks_count ?? 0,
            status: 'Ready (local)',
            workspaceId: props.workspaceId,
            createdAt: new Date().toISOString(),
        })

        selectedFile.value = null
        if (fileInputEl.value) {
            fileInputEl.value.value = ''
        }

    } catch (error) {
        errorText.value =
            'Local ingest helper is not running. Please start it and try again.'
    } finally {
        isLoading.value = false
    }
}


</script>

<template>
    <section class="flex flex-col gap-4 h-full">
        <div class="rag-card-soft flex flex-col gap-4">
            <label class="text-sm font-semibold text-slate-300">Upload document</label>
            <input ref="fileInputEl" type="file"
                class="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-slate-500"
                @change="handleFileChange" />

            <UploadActions :selectedFile="selectedFile" :isLoading="isLoading" @upload="upload"
                @upload-book="uploadBook" />
            <UploadStatusRow :isLoading="isLoading" :errorText="errorText" :successText="successText" />
        </div>

        <Banner variant="error" :text="errorText" />
        <Banner variant="success" :text="successText && !isLoading ? successText : ''" />

        <UploadsList :uploads="uploads" />

    </section>
</template>