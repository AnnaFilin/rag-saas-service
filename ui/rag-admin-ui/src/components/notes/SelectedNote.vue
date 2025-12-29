<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  note: {
    type: Object,
    default: null,
  },
})

const expandedSources = ref([])

const groupedSources = computed(() => {
  const map = new Map()
  const sources = props.note?.sources || []
  sources.forEach((source) => {
    const key = (source?.source || '').toString() || 'Unknown source'
    if (!map.has(key)) {
      map.set(key, new Set())
    }
    const entry = (source?.content || '').toString() || 'Empty content'
    map.get(key).add(entry)
  })
  return Array.from(map.entries()).map(([key, contents]) => ({
    key,
    count: contents.size,
    entries: Array.from(contents),
  }))
})

function toggleSourceGroup(key) {
  expandedSources.value = expandedSources.value.includes(key)
    ? expandedSources.value.filter((k) => k !== key)
    : [...expandedSources.value, key]
}

function isGroupExpanded(key) {
  return expandedSources.value.includes(key)
}

function prettySource(raw) {
  const value = (raw?.source || raw || '').toString()
  if (!value) return 'Unknown source'
  const clean = value.split('?')[0]
  return clean.split('/').pop() || clean
}

function formatNoteDate(note) {
  const value = note?.created_at || note?.createdAt || note?.date
  if (!value) return '—'
  const text = value.toString()
  if (text.includes('T')) {
    return text.slice(0, 16).replace('T', ' ')
  }
  return text.slice(0, 16)
}
</script>

<template>
  <template v-if="note">
    <header class="flex items-center justify-between">
      <h3 class="text-base font-semibold text-white">Selected note</h3>
      <span class="text-xs text-slate-500 uppercase tracking-[0.3em]">
  {{ formatNoteDate(note) }}
</span>
    </header>

    <div class="rag-card-soft flex-1 flex flex-col gap-3">
      <p class="text-sm font-semibold text-white">{{ note.question }}</p>
      <p class="text-sm text-slate-200">{{ note.answer }}</p>

      <div class="mt-4 text-xs uppercase tracking-[0.3em] text-slate-500">
        Sources
      </div>
      <template v-if="groupedSources.length">
        <div
          v-for="group in groupedSources"
          :key="group.key"
          class="rounded-lg border border-slate-800 bg-slate-900/70 p-3"
        >
          <button
            type="button"
            class="flex w-full items-center justify-between text-sm font-medium text-slate-100"
            @click="toggleSourceGroup(group.key)"
          >
            <span>{{ prettySource({ source: group.key }) }} ×{{ group.count }}</span>
            <span class="text-[0.6rem] text-slate-500">
              {{ isGroupExpanded(group.key) ? 'Collapse' : 'Expand' }}
            </span>
          </button>

          <div v-if="isGroupExpanded(group.key)" class="mt-2 space-y-1 text-[0.65rem] text-slate-400">
            <div v-for="entry in group.entries" :key="entry" class="break-words">
  {{ entry }}
</div>

          </div>
        </div>
      </template>

      <p v-else class="text-xs text-slate-500 italic">No sources for this note.</p>
    </div>
  </template>

  <template v-else>
    <div class="rag-card-soft flex-1 flex flex-col items-center justify-center text-slate-500 text-sm">
      No note selected.
    </div>
  </template>
</template>