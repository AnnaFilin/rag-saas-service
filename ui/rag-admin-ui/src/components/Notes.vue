<script setup>
import { computed, ref, toRefs, watch } from 'vue'

const props = defineProps({
    notes: {
        type: Array,
        default: () => [],
    },
    workspaceId: {
        type: String,
        required: true,
    },
})

const isLoading = ref(false)
const errorText = ref('')
const loadedNotes = ref([])

// make props reactive
const { notes } = toRefs(props)

// local selected note id (UI state)
const selectedId = ref(null)


watch(
    () => props.workspaceId,
    () => {
        selectedId.value = null
        loadNotes()
    },
    { immediate: true }
)


async function loadNotes() {
    if (!props.workspaceId) return

    isLoading.value = true
    errorText.value = ''

    try {
        const res = await fetch(`/api/rag/notes?workspace_id=${encodeURIComponent(props.workspaceId)}`)
        if (!res.ok) {
            const text = await res.text()
            throw new Error(text || `Request failed: ${res.status}`)
        }
        const data = await res.json()
        loadedNotes.value = Array.isArray(data.notes) ? data.notes : []
    } catch (error) {
        errorText.value = error?.message || 'Unable to fetch notes'
        loadedNotes.value = []
    } finally {
        isLoading.value = false
    }
}


const note = computed(() => {
    const list = loadedNotes.value || []
    if (!list.length) return null
    return list.find((n) => n.id === selectedId.value) || list[0]
})


function selectNote(id) {
    selectedId.value = id
}

function prettySource(s) {
    const raw = (s?.source || s || '').toString()
    if (!raw) return 'Unknown source'
    const clean = raw.split('?')[0] // убираем query params если есть
    const last = clean.split('/').pop() || clean
    return last
}

const expandedSources = ref([])

const groupedSources = computed(() => {
  if (!note.value?.sources?.length) return []
  const map = new Map()
  note.value.sources.forEach((source) => {
    const key = (source?.source || source || '').toString() || 'Unknown source'
    if (!map.has(key)) {
      map.set(key, [])
    }
    map.get(key).push(source)
  })
  return Array.from(map.entries()).map(([key, entries]) => {
  const rawLines = Array.from(
    new Set(entries.map((e) => (e?.source || e || '').toString() || 'Unknown source'))
  )
  return {
    key,
    count: entries.length,
    rawLines,
  }
})

})

function toggleSourceGroup(key) {
  expandedSources.value = expandedSources.value.includes(key)
    ? expandedSources.value.filter((k) => k !== key)
    : [...expandedSources.value, key]
}

function isGroupExpanded(key) {
  return expandedSources.value.includes(key)
}

watch(
  note,
  () => {
    expandedSources.value = []
  },
  { immediate: true }
)

</script>

<template>
    <section class="flex flex-col gap-4 h-full">
        <!-- Header: search + filter -->
        <div class="rag-card-soft flex flex-col gap-3">
            <div class="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <input type="text" placeholder="Search notes..."
                    class="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-slate-500" />
                <select
                    class="mt-2 rounded-lg border border-slate-700 bg-slate-950 px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-slate-500 md:mt-0 md:ml-3">
                    <option>All tags</option>
                    <option>Pipeline</option>
                    <option>Prompting</option>
                </select>
            </div>
            <p class="text-xs uppercase tracking-[0.3em] text-slate-500">
                Master / detail
            </p>
        </div>

        <!-- Master / Detail -->
        <div class="rag-card flex-1 min-h-0 flex flex-col gap-4">
            <div class="grid flex-1 gap-4 md:grid-cols-[minmax(0,0.55fr)_minmax(0,0.45fr)]">
                <!-- LEFT: list of notes -->
                <!-- LEFT: list of notes -->
                <div class="flex flex-col gap-4 min-h-0">
                    <div v-if="isLoading" class="text-xs text-slate-500 italic">
                        Loading notes...
                    </div>

                    <div v-else-if="errorText" class="text-xs text-red-300">
                        {{ errorText }}
                    </div>

                    <template v-else>
                        <div v-for="item in loadedNotes" :key="item.id"
                            class="rag-card-soft cursor-pointer border border-transparent transition-colors hover:border-emerald-400">
                            <button class="w-full text-left" type="button" @click="selectNote(item.id)">
                                <p class="text-sm font-semibold text-white">
                                    {{ item.question }}
                                </p>
                                <p class="mt-2 text-xs text-slate-400 line-clamp-4">
                                    {{ item.answer }}
                                </p>

                                <div
                                    class="mt-3 flex flex-wrap gap-2 text-[0.65rem] uppercase tracking-[0.2em] text-slate-500">
                                    <span>
                                        {{ item.date || item.createdAt || 'No date' }}
                                    </span>
                                    <span v-if="item.tags && item.tags.length">
                                        {{ item.tags.join(', ') }}
                                    </span>
                                    <span v-else class="italic text-slate-600">
                                        No tags
                                    </span>
                                </div>
                            </button>
                        </div>

                        <p v-if="!loadedNotes || !loadedNotes.length" class="text-xs text-slate-500 italic">
                            No notes yet.
                        </p>
                    </template>
                </div>


                <!-- RIGHT: selected note -->
                <div class="flex flex-col gap-4">
                    <template v-if="note">
                        <header class="flex items-center justify-between">
                            <h3 class="text-base font-semibold text-white">
                                Selected note
                            </h3>
                            <span class="text-xs text-slate-500 uppercase tracking-[0.3em]">
                                {{ note.date || note.createdAt || 'No date' }}
                            </span>
                        </header>

                        <div class="rag-card-soft flex-1 flex flex-col gap-3">
                            <p class="text-sm font-semibold text-white">
                                {{ note.question }}
                            </p>
                            <p class="text-sm text-slate-200">
                                {{ note.answer }}
                            </p>

                            <div class="mt-auto text-xs uppercase tracking-[0.3em] text-slate-500">
                                Sources
                            </div>

                            <div v-if="groupedSources.length" class="flex flex-col gap-2 text-xs text-slate-300 max-h-40 overflow-auto pr-1">
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
          {{ isGroupExpanded(group.key) ? '−' : '+' }}
        </span>
      </button>
      <div v-if="isGroupExpanded(group.key)" class="mt-2 space-y-1 text-[0.65rem] text-slate-400">
        <div v-for="entry in group.entries" :key="entry" class="break-words">
          {{ entry }}
        </div>
      </div>
    </div>
  </div>
                            <p v-else class="text-xs text-slate-500 italic">
                                No sources for this note.
                            </p>
                        </div>
                    </template>

                    <template v-else>
                        <div
                            class="rag-card-soft flex-1 flex flex-col items-center justify-center text-slate-500 text-sm">
                            No note selected.
                        </div>
                    </template>
                </div>
            </div>
        </div>
    </section>
</template>