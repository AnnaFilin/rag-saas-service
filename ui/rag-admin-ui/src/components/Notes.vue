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
                <div class="flex flex-col gap-4">
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

                    <p v-if="!notes || !notes.length" class="text-xs text-slate-500 italic">
                        No notes yet.
                    </p>
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

                            <template v-if="note.sources && note.sources.length">
                                <ul class="flex flex-col gap-1 text-xs text-slate-300">
                                    <li v-for="(s, idx) in note.sources" :key="idx">
                                        {{ s.source || 'Unknown source' }}
                                    </li>

                                </ul>
                            </template>
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