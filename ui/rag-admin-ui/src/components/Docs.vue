<script setup>
import { ref } from 'vue'

const props = defineProps({
    workspaceId: { type: String, required: true },
})

const selectedFile = ref(null)
const isLoading = ref(false)
const errorText = ref('')
const successText = ref('')
const uploads = ref([])

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
            <div class="flex flex-wrap gap-3">
                <button
                    class="rounded-full border border-slate-600 px-3 py-1 text-xs font-semibold text-slate-200 hover:border-white"
                    type="button" :disabled="!selectedFile || isLoading" @click="upload">
                    Upload
                </button>
                <button
                    class="rounded-full border border-indigo-600 px-3 py-1 text-xs font-semibold text-indigo-300 hover:border-indigo-400"
                    type="button" :disabled="!selectedFile || isLoading" @click="uploadBook">
                    Upload book (local)
                </button>

            </div>
            <div class="flex items-center justify-between text-sm text-slate-400">
                <div>
                    <div v-if="isLoading" class="flex items-center gap-2">
                        <div class="h-4 w-4 animate-spin rounded-full border-2 border-slate-400 border-t-transparent">
                        </div>
                        <span class="text-sm text-slate-300">Uploading...</span>
                    </div>

                    <span v-else-if="errorText">{{ errorText }}</span>
                    <span v-else-if="successText">{{ successText }}</span>
                    <span v-else>Ready to upload your document</span>
                </div>

                <span class="text-[0.65rem] uppercase tracking-[0.3em] text-slate-500">Idle</span>
                <div class="h-2 w-24 rounded-full bg-slate-800">
                    <div class="h-2"
                        :class="isLoading ? 'w-12 rounded-full bg-emerald-500 animate-pulse' : 'w-6 rounded-full bg-emerald-500'">
                    </div>
                </div>
            </div>
        </div>

        <div v-if="errorText" class="rounded-md border border-red-600 bg-red-700/40 px-4 py-2 text-sm text-red-200">
            {{ errorText }}
        </div>

        <div v-if="successText && !isLoading"
            class="rounded-md border border-emerald-500 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-200">
            {{ successText }}
        </div>

        <div class="rag-card flex-1 flex flex-col gap-4 overflow-hidden">
            <div class="flex items-center justify-between border-b border-slate-800 px-4 py-3">
                <h3 class="text-base font-semibold text-white">Uploaded documents</h3>
                <span class="text-xs uppercase tracking-[0.3em] text-slate-500">{{ uploads.length }} files</span>
            </div>
            <ul class="flex-1 px-4 pb-4 space-y-3 overflow-y-auto">
                <li v-for="upload in uploads" :key="upload.id"
                    class="rounded-lg border border-slate-800 bg-slate-950 p-3 text-sm text-slate-200 flex flex-col gap-1">
                    <div class="flex items-center justify-between">
                        <span class="font-semibold">{{ upload.name }}</span>
                        <span class="text-xs text-slate-400">{{ upload.size }}</span>
                    </div>
                    <div class="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                        <span>Chunks: {{ upload.chunks }}</span>
                        <span class="flex items-center gap-1">
                            Status:
                            <span
                                class="rounded-full bg-slate-800 px-2 py-0.5 text-[0.6rem] uppercase tracking-[0.2em]">
                                {{ upload.status }}
                            </span>
                        </span>
                    </div>
                    <div class="text-[0.65rem] text-slate-500">
                        {{ upload.workspaceId }} · {{ new Date(upload.createdAt).toLocaleTimeString() }}
                    </div>

                </li>
            </ul>
        </div>
    </section>
</template>