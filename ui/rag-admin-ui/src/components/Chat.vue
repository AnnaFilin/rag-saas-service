<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  workspaceId: { type: String, required: true },
})

const question = ref('')
const role = ref('')
const isLoading = ref(false)
const errorText = ref('')
const saveStatus = ref('')
const ragMode = ref('reference')
const answer = ref('')
const sources = ref([])
const chatMode = ref('local') // 'cloud' | 'local'
let saveTimerId = null

const CHAT_ENDPOINTS = {
  cloud: '/api/rag/chat',
  local: 'http://localhost:8000/chat',
}


const emit = defineEmits(['save-note'])

const SOURCES_PREVIEW_LEN = 220

const showAllSources = ref(false)

const visibleSources = computed(() => {
  const list = Array.isArray(sources.value) ? sources.value : []
  return showAllSources.value ? list : list.slice(0, 5)
})

const expandedSourceKey = ref(null)

function sourceKey(source, idx) {
  return `${source?.document_id ?? 'doc'}:${source?.chunk_index ?? 'idx'}:${idx}`
}

function toggleSource(source, idx) {
  const key = sourceKey(source, idx)
  expandedSourceKey.value = expandedSourceKey.value === key ? null : key
}


function sourcePreviewText(source) {
  const text = String(source?.content || '').replace(/\s+/g, ' ').trim()
  if (!text) return ''
  return text.length > SOURCES_PREVIEW_LEN
    ? text.slice(0, SOURCES_PREVIEW_LEN) + '…'
    : text
}

function sourceTitle(source) {
  const raw = source?.source || ''
  const file = String(raw).split('/').pop() || raw
  const idx = source?.chunk_index
  return idx == null ? file : `${file} • chunk ${idx}`
}


async function submitQuestion() {
    showAllSources.value = false

  if (!question.value.trim()) {
    return
  }

  isLoading.value = true
  errorText.value = ''
  answer.value = ''
  sources.value = []
  const endpoint = CHAT_ENDPOINTS[chatMode.value]


  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workspace_id: props.workspaceId,
        question: question.value,
        mode: ragMode.value, // "reference" | "synthesis" | "custom"
        role: ragMode.value === 'custom' && role.value.trim() ? role.value : null,
      }),
    })

    if (!response.ok) {
      throw new Error(`Request failed: ${response.status}`)
    }

    const data = await response.json()

    console.log('endpoint:', endpoint)
console.log('source sample:', data.sources?.[0])

    answer.value = data.answer || ''
    sources.value = Array.isArray(data.sources) ? data.sources : []
  } catch (error) {
    errorText.value = error.message
  } finally {
    isLoading.value = false
  }
}

function saveCurrentNote() {
  if (!answer.value.trim()) return
  if (!props.workspaceId) return

  const normalizedSources = (sources.value || [])
    .map((item) => {
      if (!item) return null
      if (typeof item === 'string') {
        const trimmed = item.trim()
        return { source: trimmed || 'Unknown source' }
      }
      if (typeof item === 'object') {
        const sourceValue = (item.source || '').toString().trim() || 'Unknown source'
        return {
          source: sourceValue,
          chunk_index: item.chunk_index,
          chunk_id: item.chunk_id,
          content: item.content,
        }
      }
      return null
    })
    .filter(Boolean)

  saveStatus.value = 'saving'
  if (saveTimerId) {
    clearTimeout(saveTimerId)
    saveTimerId = null
  }

  emit('save-note', {
    question: question.value,
    answer: answer.value,
    sources: normalizedSources,
    workspaceId: props.workspaceId,
    createdAt: new Date().toISOString(),
  })

  saveStatus.value = 'saved'
  saveTimerId = setTimeout(() => {
    saveStatus.value = ''
    saveTimerId = null
  }, 2500)
}



</script>

<template>
  <section class="flex flex-col gap-4 h-full">
    <div class="rag-card-soft flex flex-col gap-3">
      <label class="text-sm font-semibold text-slate-300">Question</label>
      <textarea
        v-model="question"
        class="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-slate-500"
        rows="3"
        placeholder="Type your question..."
      ></textarea>
    <!-- Mode + Role (replace your current Mode/Role block with this whole block) -->
<div class="flex flex-col gap-2">
  <label class="text-sm font-semibold text-slate-300">Mode</label>

  <div class="flex flex-wrap gap-2">
    <button
      type="button"
      class="px-3 py-1 text-xs rounded border"
      :class="ragMode === 'reference'
        ? 'bg-slate-800 border-slate-500 text-white'
        : 'bg-transparent border-slate-700 text-slate-400'"
      @click="ragMode = 'reference'"
    >
      Reference
    </button>

    <button
      type="button"
      class="px-3 py-1 text-xs rounded border"
      :class="ragMode === 'synthesis'
        ? 'bg-slate-800 border-slate-500 text-white'
        : 'bg-transparent border-slate-700 text-slate-400'"
      @click="ragMode = 'synthesis'"
    >
      Synthesis
    </button>

    <button
      type="button"
      class="px-3 py-1 text-xs rounded border"
      :class="ragMode === 'custom'
        ? 'bg-slate-800 border-slate-500 text-white'
        : 'bg-transparent border-slate-700 text-slate-400'"
      @click="ragMode = 'custom'"
    >
      Custom
    </button>
  </div>

  <div v-if="ragMode === 'custom'" class="mt-2 flex flex-col gap-2">
    <label class="text-sm font-semibold text-slate-300">Role (custom)</label>
    <textarea
      v-model="role"
      class="w-full rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-slate-500"
      rows="3"
      placeholder="Custom instruction for the assistant..."
    ></textarea>
  </div>
</div>

      <div class="flex items-center justify-between space-x-3">
        <span class="text-sm text-slate-400">
          <div v-if="isLoading" class="flex items-center gap-2">
            <div class="h-4 w-4 animate-spin rounded-full border-2 border-slate-400 border-t-transparent"></div>
            <span class="text-sm text-slate-300">Loading...</span>
            </div>

        <span v-else-if="errorText" class="text-sm text-red-300">
            {{ errorText }}
        </span>

          <span v-else>Ready to submit your question</span>
        </span>
        <span class="text-xs uppercase tracking-[0.2em] text-slate-500">Status</span>
        <div class="h-2 w-24 rounded-full bg-slate-800">
          <div class="h-2 rounded-full bg-emerald-500" :class="isLoading ? 'w-12 animate-pulse' : 'w-6'"></div>
        </div>
      </div>
      <div class="flex items-center gap-3 text-xs text-slate-300">
  <span class="uppercase tracking-wider text-slate-400">Chat mode</span>

  <label class="flex items-center gap-1 cursor-pointer">
    <input
      type="radio"
      value="cloud"
      v-model="chatMode"
    />
    <span>Cloud</span>
  </label>

  <label class="flex items-center gap-1 cursor-pointer">
    <input
      type="radio"
      value="local"
      v-model="chatMode"
    />
    <span>Local</span>
  </label>
</div>

      <div class="flex justify-end">
        <button
          class="rounded-full border border-emerald-400 px-4 py-1 text-xs font-semibold uppercase tracking-[0.3em] text-emerald-300 hover:border-emerald-200"
          type="button"
          @click="submitQuestion"
          :disabled="isLoading || !question.trim()"
        >
          Ask
        </button>
      </div>
    </div>

    <div class="rag-card flex-1 flex flex-col gap-3">
      <div class="flex items-center justify-between">
        <h3 class="text-lg font-semibold text-white">LLM Answer</h3>
        <button
         type="button"
  class="rounded-full border border-slate-500 px-4 py-1 text-xs font-semibold uppercase tracking-[0.3em] text-slate-200 hover:border-slate-300 disabled:opacity-40 disabled:cursor-not-allowed"
  @click="saveCurrentNote"
  :disabled="!answer.trim() || isLoading"
>
  Save as note
</button>

<span v-if="saveStatus === 'saved'" class="ml-3 text-sm text-emerald-400">
  Saved
</span>

      </div>

      <div class="flex-1 rounded-lg border border-slate-800 bg-slate-950 p-4 text-sm text-slate-100">
        {{ answer }}
        <div v-if="sources.length && answer.trim() && !answer.toLowerCase().startsWith('i do not know')">
        <div class="mt-3 border-t border-slate-800 pt-3 text-xs uppercase tracking-[0.2em] text-slate-500">
          Sources
        </div>
        <div class="mt-2 rounded-lg border border-slate-800 bg-slate-950/60 p-3">
  <ul class="space-y-2 text-slate-300">

    <li
  v-for="(source, idx) in visibleSources"
  :key="sourceKey(source, idx)"
  class="rounded-md border border-slate-800 bg-slate-950 px-3 py-2 cursor-pointer"
  @click="toggleSource(source, idx)"
>
  <div class="text-[11px] uppercase tracking-[0.18em] text-slate-500 truncate">
    {{ sourceTitle(source) }}
  </div>

  <div class="mt-1 text-sm text-slate-200 whitespace-pre-wrap">
    <span v-if="expandedSourceKey === sourceKey(source, idx)">
      {{ source?.content || '' }}
    </span>
    <span v-else>
      {{ sourcePreviewText(source) }}
    </span>
  </div>

  <div class="mt-2 text-[11px] text-slate-500">
    {{ expandedSourceKey === sourceKey(source, idx) ? 'Click to collapse' : 'Click to expand' }}
  </div>
</li>



</ul>
<div v-if="sources.length > 5" class="mt-2">
  <button
    type="button"
    class="text-xs text-slate-400 hover:text-slate-200 underline underline-offset-4"
    @click="showAllSources = !showAllSources"
  >
    {{ showAllSources ? 'Show less' : `Show all (${sources.length})` }}
  </button>
</div>
</div>
</div>
      </div>

      <div v-if="errorText" class="rounded-md border border-red-600 bg-red-700/40 px-4 py-2 text-sm text-red-200">
        {{ errorText }}
      </div>
    </div>
  </section>
</template>