<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  sources: {
    type: Array,
    required: true,
  },
  answer: {
    type: String,
    required: true,
  },
})

const SOURCES_PREVIEW_LEN = 220
const showAllSources = ref(false)
const expandedSourceKey = ref(null)

const visibleSources = computed(() => {
  const list = Array.isArray(props.sources) ? props.sources : []
  return showAllSources.value ? list : list.slice(0, 5)
})

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
</script>

<template>
  <div v-if="props.sources.length && props.answer.trim() && !props.answer.toLowerCase().startsWith('i do not know')">
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
      <div v-if="props.sources.length > 5" class="mt-2">
        <button
          type="button"
          class="text-xs text-slate-400 hover:text-slate-200 underline underline-offset-4"
          @click="showAllSources = !showAllSources"
        >
          {{ showAllSources ? 'Show less' : `Show all (${props.sources.length})` }}
        </button>
      </div>
    </div>
  </div>
</template>