<!-- ui/rag-admin-ui/src/components/Notes.vue -->
<script setup>
import { computed, ref, watch } from 'vue'
import NotesList from './notes/NotesList.vue'
import SelectedNote from './notes/SelectedNote.vue'

const props = defineProps({
  workspaceId: {
    type: String,
    required: true,
  },
})

const isLoading = ref(false)
const errorText = ref('')
const loadedNotes = ref([])
const limit = ref(5)
const selectedId = ref(null)
const toast = ref('')
let toastTimer = null

watch(
  () => props.workspaceId,
  () => {
    selectedId.value = null
    limit.value = 4
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

async function deleteNote(noteId) {
  if (!noteId) return

  const ok = window.confirm('Delete this note?')
  if (!ok) return

  try {
    const res = await fetch(`/api/rag/notes/${encodeURIComponent(noteId)}`, {
      method: 'DELETE',
    })

    if (!res.ok) {
      const text = await res.text()
      throw new Error(text || `Delete failed: ${res.status}`)
    }

   
    loadedNotes.value = (loadedNotes.value || []).filter((n) => n.id !== noteId)

    
    if (selectedId.value === noteId) {
      const next = loadedNotes.value?.[0]
      selectedId.value = next ? next.id : null
    }

    showToast('Note deleted')

  } catch (err) {
    console.error('Delete note failed', err)
    window.alert(err?.message || 'Delete note failed')
  }
}

function showToast(message, ms = 2500) {
  toast.value = message
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toast.value = ''
    toastTimer = null
  }, ms)
}


const note = computed(() => {
  const list = loadedNotes.value || []
  if (!list.length) return null
  return list.find((n) => n.id === selectedId.value) || list[0]
})

const visibleNotes = computed(() => {
  return loadedNotes.value.slice(0, limit.value)
})

const canShowMore = computed(() => {
  return loadedNotes.value.length > visibleNotes.value.length && !isLoading.value && !errorText.value
})

function selectNote(id) {
  selectedId.value = id
}

function showMore() {
  limit.value += 5
}
</script>

<template>
  <section class="flex flex-col gap-4 h-full">
    <div class="rag-card-soft flex flex-col gap-3">
      <div class="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <input
          type="text"
          placeholder="Search notes..."
          class="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-slate-500"
        />
        <select
          class="mt-2 rounded-lg border border-slate-700 bg-slate-950 px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-slate-500 md:mt-0 md:ml-3"
        >
          <option>All tags</option>
          <option>Pipeline</option>
          <option>Prompting</option>
        </select>
      </div>
      <p class="text-xs uppercase tracking-[0.3em] text-slate-500">Master / detail</p>
    </div>

    <div class="rag-card flex-1 min-h-0 flex flex-col gap-4">
      <div
  v-if="toast"
  class="mb-2 rounded-lg border border-emerald-700 bg-emerald-900/30 px-3 py-2 text-xs text-emerald-200"
>
  {{ toast }}
</div>
      <div class="grid flex-1 gap-4 md:grid-cols-[minmax(0,0.4fr)_minmax(0,0.6fr)]">
        <div class="flex flex-col gap-4 min-h-0">
          <NotesList
  :notes="visibleNotes"
  :isLoading="isLoading"
  :errorText="errorText"
  :selectedId="selectedId"
  @select="selectNote"
  @delete="deleteNote"
/>


          <button
            v-if="canShowMore"
            type="button"
            class="self-start rounded-full border border-slate-600 px-4 py-1 text-xs font-semibold uppercase tracking-[0.3em] text-slate-200 hover:border-slate-300"
            @click="showMore"
          >
            Show more
          </button>
        </div>

        <div class="flex flex-col gap-4 min-h-0">
  <SelectedNote :note="note" />
</div>

      </div>
    </div>
  </section>
</template>